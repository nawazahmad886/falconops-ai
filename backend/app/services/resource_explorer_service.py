"""
FalconOps AI - Enterprise Resource Explorer

Extends db.topology_nodes (owned by topology_service.py) as the canonical
Resource model rather than creating a new collection — topology_service.py
itself gets zero signature changes; it stays a stable contract for its other
consumers (impact_analysis_engine, ai_correlation, smart_correlation_engine,
rca_engine, vulnerability_service). This module is a new orchestration layer,
same shape as problems_service.py: it reads/writes db.topology_nodes plus the
existing db.servers/db.oneagent_agents/db.db_instances registries directly,
without modifying those collections' owning route files beyond small
additive hooks (added separately).

Phase 1 bridges exactly two existing registries: Linux hosts (db.servers +
db.oneagent_agents, merged) and databases (db.db_instances). Real K8s/cloud/
VMware/Windows/middleware/network/storage/security discovery is out of scope
— zero code exists for any of them today. The Connector SDK's InventoryCapable
mixin (backend/app/connectors/base.py) is wired via upsert_from_connector_inventory()
for future connectors, though none implements it yet.
"""
import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.database import db
from .topology_service import topology_service

logger = logging.getLogger(__name__)

RESOURCE_BRIDGE_TICK_SECONDS = 60
HEARTBEAT_STALE_AFTER_SECONDS = 180  # matches ai_tools_service.py's OneAgent staleness constant
SERVER_STALE_AFTER_SECONDS = 300     # matches servers.py's 5-minute offline threshold
DB_INSTANCE_STALE_AFTER_SECONDS = 300


class ResourceCategory(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    APPLICATION = "application"
    KUBERNETES = "kubernetes"
    CLOUD = "cloud"
    MIDDLEWARE = "middleware"
    NETWORK = "network"
    STORAGE = "storage"
    SECURITY = "security"
    PROCESS = "process"
    CONTAINER = "container"
    OTHER = "other"


class LifecycleStatus(str, Enum):
    DISCOVERED = "discovered"
    MONITORED = "monitored"
    UNREACHABLE = "unreachable"
    RETIRED = "retired"


# Legacy topology_nodes (created via create_service_node/auto_discover_from_traces,
# using topology_service.SERVICE_TYPES-style `type` values) never get a
# resource_category written — this fallback is applied at READ time only,
# never by migrating old docs.
_TYPE_TO_CATEGORY_FALLBACK = {"database": "database", "storage": "storage"}


def _seconds_since(iso_ts: Optional[str]) -> Optional[float]:
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


# ─────────────────────────────────────────────────────
#  Indexes (lazy, idempotent — same idiom as network_flow_service.py / problems_service.py)
# ─────────────────────────────────────────────────────

_indexes_ready = False


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await db.topology_nodes.create_index(
            [("source_ref.collection", 1), ("source_ref.id", 1)],
            unique=True,
            partialFilterExpression={"source_ref": {"$exists": True}},
        )
        await db.topology_nodes.create_index(
            [("tenant_id", 1), ("resource_category", 1), ("environment", 1), ("lifecycle_status", 1)]
        )
        await db.topology_nodes.create_index("technology")
        await db.topology_nodes.create_index("owner")
        await db.topology_nodes.create_index("tags")
        await db.topology_nodes.create_index([("name", 1), ("environment", 1), ("tenant_id", 1)])
    except Exception as e:
        logger.warning(f"Resource Explorer index creation skipped/partial: {e}")
    _indexes_ready = True


# ─────────────────────────────────────────────────────
#  Bridge / sync
# ─────────────────────────────────────────────────────

async def _sync_hosts() -> Dict[str, int]:
    """Merges db.servers + db.oneagent_agents (both represent hosts) into single
    infrastructure resources, keyed by lowercased hostname. Prefers oneagent's
    liveness fields (actively-heartbeating) and servers' metrics fields (the
    only source with real cpu/memory/disk numbers)."""
    servers = await db.servers.find({}, {"_id": 0}).to_list(2000)
    agents = await db.oneagent_agents.find({}, {"_id": 0}).to_list(2000)

    servers_by_host = {s["hostname"].strip().lower(): s for s in servers if s.get("hostname")}
    agents_by_host = {a["host"].strip().lower(): a for a in agents if a.get("host")}
    host_keys = set(servers_by_host) | set(agents_by_host)

    created = 0
    updated = 0

    for host_key in host_keys:
        srv = servers_by_host.get(host_key)
        ag = agents_by_host.get(host_key)

        existing = await db.topology_nodes.find_one(
            {"source_ref.collection": "host", "source_ref.id": host_key}, {"_id": 0}
        )
        if existing and (
            existing.get("lifecycle_status") == LifecycleStatus.RETIRED.value
            or (existing.get("metadata") or {}).get("monitoring_disabled")
        ):
            continue  # manual override in effect — bridge never overwrites it

        name = (srv or {}).get("hostname") or (ag or {}).get("host") or host_key
        environment = (ag or {}).get("environment") or ((srv or {}).get("tags") or {}).get("env") or "production"
        technology = (srv or {}).get("os_type")

        agent_age = _seconds_since((ag or {}).get("last_seen"))
        server_age = _seconds_since((srv or {}).get("last_seen"))

        if ag and agent_age is not None and agent_age <= HEARTBEAT_STALE_AFTER_SECONDS:
            lifecycle_status = LifecycleStatus.MONITORED.value
        elif srv and server_age is not None and server_age <= SERVER_STALE_AFTER_SECONDS:
            lifecycle_status = LifecycleStatus.MONITORED.value
        elif (srv or ag):
            lifecycle_status = LifecycleStatus.UNREACHABLE.value
        else:
            lifecycle_status = LifecycleStatus.DISCOVERED.value
        # Never received any metrics/heartbeat at all -> discovered, not unreachable
        if srv and srv.get("cpu_usage") is None and not ag:
            lifecycle_status = LifecycleStatus.DISCOVERED.value

        if srv and srv.get("status"):
            health_status = {"online": "healthy", "warning": "degraded", "critical": "critical", "offline": "critical"}.get(srv["status"], "healthy")
            health_score = {"online": 100, "warning": 60, "critical": 20, "offline": 0}.get(srv["status"])
        elif ag:
            health_status = "healthy" if lifecycle_status == LifecycleStatus.MONITORED.value else "critical"
            health_score = None  # honest gap — oneagent heartbeat carries no numeric health score
        else:
            health_status = "healthy"
            health_score = None

        tags_dict = (srv or {}).get("tags") or {}
        tags_list = [f"{k}:{v}" for k, v in tags_dict.items()] if isinstance(tags_dict, dict) else list(tags_dict or [])

        source_refs = []
        if srv:
            source_refs.append({"collection": "servers", "id": srv["id"]})
        if ag:
            source_refs.append({"collection": "oneagent_agents", "id": ag["id"]})
        discovered_by = "bridge:servers+oneagent_agents" if (srv and ag) else ("bridge:servers" if srv else "bridge:oneagent_agents")

        new_metadata = {
            "ip_address": (srv or {}).get("ip_address"),
            "os_type": (srv or {}).get("os_type"),
            "os_version": (srv or {}).get("os_version"),
            "agent_version": (ag or {}).get("agent_version") or (srv or {}).get("agent_version"),
            "services": (ag or {}).get("services") or [],
            "cpu_usage": (srv or {}).get("cpu_usage"),
            "memory_usage": (srv or {}).get("memory_usage"),
            "disk_usage": (srv or {}).get("disk_usage"),
            "uptime_seconds": (srv or {}).get("uptime_seconds"),
        }
        merged_metadata = {**(existing.get("metadata") or {}), **new_metadata} if existing else new_metadata

        doc_updates = {
            "name": name,
            "type": existing.get("type") if existing else "external",
            "resource_category": ResourceCategory.INFRASTRUCTURE.value,
            "technology": technology,
            "environment": environment,
            "lifecycle_status": lifecycle_status,
            "status": health_status,
            "health_score": health_score if health_score is not None else (existing.get("health_score") if existing else 100),
            "discovered_by": discovered_by,
            "source_refs": source_refs,
            "tags": tags_list,
            "metadata": merged_metadata,
            "last_seen": (ag or {}).get("last_seen") or (srv or {}).get("last_seen"),
            "tenant_id": (srv or {}).get("tenant_id"),
        }

        if existing:
            await db.topology_nodes.update_one(
                {"id": existing["id"]}, {"$set": {**doc_updates, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            updated += 1
        else:
            now = datetime.now(timezone.utc).isoformat()
            await db.topology_nodes.insert_one({
                "id": str(uuid.uuid4()), "owner": None, "description": None, "created_at": now,
                "source_ref": {"collection": "host", "id": host_key},
                **doc_updates,
            })
            created += 1

    return {"created": created, "updated": updated}


async def _sync_databases() -> Dict[str, int]:
    """Walks db.db_instances into database-category resources, real 1:1 source_ref."""
    instances = await db.db_instances.find({}, {"_id": 0}).to_list(2000)
    created = 0
    updated = 0

    for inst in instances:
        existing = await db.topology_nodes.find_one(
            {"source_ref.collection": "db_instances", "source_ref.id": inst["id"]}, {"_id": 0}
        )
        if existing and (
            existing.get("lifecycle_status") == LifecycleStatus.RETIRED.value
            or (existing.get("metadata") or {}).get("monitoring_disabled")
        ):
            continue

        age = _seconds_since(inst.get("last_seen"))
        if inst.get("status") == "registered" and inst.get("last_seen") is None:
            lifecycle_status = LifecycleStatus.DISCOVERED.value
        elif age is not None and age <= DB_INSTANCE_STALE_AFTER_SECONDS:
            lifecycle_status = LifecycleStatus.MONITORED.value
        else:
            lifecycle_status = LifecycleStatus.UNREACHABLE.value

        tags_dict = inst.get("tags") or {}
        tags_list = [f"{k}:{v}" for k, v in tags_dict.items()] if isinstance(tags_dict, dict) else list(tags_dict or [])

        new_metadata = {
            "host": inst.get("host"), "port": inst.get("port"), "database": inst.get("database"),
            "db_type": inst.get("db_type"), "agent_version": inst.get("agent_version"),
        }
        merged_metadata = {**(existing.get("metadata") or {}), **new_metadata} if existing else new_metadata

        doc_updates = {
            "name": inst["name"],
            "type": existing.get("type") if existing else "database",
            "resource_category": ResourceCategory.DATABASE.value,
            "technology": inst.get("db_type"),
            "environment": inst.get("environment") or "production",
            "lifecycle_status": lifecycle_status,
            "status": "healthy" if lifecycle_status == LifecycleStatus.MONITORED.value else "critical" if lifecycle_status == LifecycleStatus.UNREACHABLE.value else "healthy",
            "health_score": existing.get("health_score") if existing else 100,
            "discovered_by": "bridge:db_instances",
            "source_refs": [{"collection": "db_instances", "id": inst["id"]}],
            "tags": tags_list,
            "metadata": merged_metadata,
            "last_seen": inst.get("last_seen"),
            "tenant_id": None,
        }

        if existing:
            await db.topology_nodes.update_one(
                {"id": existing["id"]}, {"$set": {**doc_updates, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            updated += 1
        else:
            now = datetime.now(timezone.utc).isoformat()
            await db.topology_nodes.insert_one({
                "id": str(uuid.uuid4()), "owner": None, "description": None, "created_at": now,
                "source_ref": {"collection": "db_instances", "id": inst["id"]},
                **doc_updates,
            })
            created += 1

    return {"created": created, "updated": updated}


async def _upsert_runs_on_edge(source_node_id: str, target_node_id: str) -> None:
    """Idempotent — create_connection() (topology_service.py) always inserts a
    new doc with no dedup, which would duplicate an edge every 60s tick; this
    bridge needs upsert semantics instead, same idiom as the node upserts
    above, applied directly to db.topology_edges."""
    now = datetime.now(timezone.utc).isoformat()
    await db.topology_edges.update_one(
        {"source_id": source_node_id, "target_id": target_node_id, "type": "runs_on"},
        {"$set": {"status": "healthy", "updated_at": now},
         "$setOnInsert": {"id": str(uuid.uuid4()), "protocol": None, "metrics": {}, "tenant_id": None, "created_at": now}},
        upsert=True,
    )


async def _sync_processes_and_containers() -> Dict[str, int]:
    """Walks db.oneagent_agents.services[] (now carrying pid/container_id/ports
    per service, see oneagent_routes.py::ingest_heartbeat) into Process and
    Container FalconGraph nodes, each with a real 'runs_on' edge back to its
    parent host — closing the gap where OneAgent already discovered processes
    but nothing turned that into a graph node. Processes/containers have no
    heartbeat of their own; lifecycle is inherited from the parent host's
    last_seen, same staleness window _sync_hosts() already uses."""
    agents = await db.oneagent_agents.find({}, {"_id": 0}).to_list(2000)
    created = 0
    updated = 0

    for ag in agents:
        host_key = (ag.get("host") or "").strip().lower()
        if not host_key:
            continue
        host_node = await db.topology_nodes.find_one(
            {"source_ref.collection": "host", "source_ref.id": host_key}, {"_id": 0, "id": 1}
        )
        if not host_node:
            continue  # host node hasn't been bridged yet this tick — will catch up next tick

        age = _seconds_since(ag.get("last_seen"))
        lifecycle_status = (
            LifecycleStatus.MONITORED.value if age is not None and age <= HEARTBEAT_STALE_AFTER_SECONDS
            else LifecycleStatus.UNREACHABLE.value
        )
        environment = ag.get("environment") or "production"

        container_nodes: Dict[str, str] = {}  # container_id -> topology node id, this host only
        for svc in ag.get("services") or []:
            name = svc.get("name")
            pid = svc.get("pid")
            if not name or pid is None:
                continue  # pre-V2 heartbeat shape ({name, runtime} only) — nothing to bridge yet for this entry
            container_id = svc.get("container_id")

            container_node_id = None
            if container_id:
                if container_id in container_nodes:
                    container_node_id = container_nodes[container_id]
                else:
                    container_node_id, container_created = await _upsert_container_node(
                        host_key, container_id, environment, lifecycle_status, host_node["id"],
                    )
                    container_nodes[container_id] = container_node_id
                    created += 1 if container_created else 0

            process_source_id = f"{host_key}:{pid}"
            existing = await db.topology_nodes.find_one(
                {"source_ref.collection": "oneagent_process", "source_ref.id": process_source_id}, {"_id": 0}
            )
            doc_updates = {
                "name": name,
                "type": existing.get("type") if existing else "external",
                "resource_category": ResourceCategory.PROCESS.value,
                "technology": svc.get("runtime"),
                "environment": environment,
                "lifecycle_status": lifecycle_status,
                "status": "healthy" if lifecycle_status == LifecycleStatus.MONITORED.value else "critical",
                "health_score": existing.get("health_score") if existing else 100,
                "discovered_by": "bridge:oneagent_agents.services",
                "source_refs": [{"collection": "oneagent_agents", "id": ag.get("id")}],
                "tags": [],
                "metadata": {"pid": pid, "runtime": svc.get("runtime"), "container_id": container_id,
                              "ports": svc.get("ports") or [], "host": host_key},
                "last_seen": ag.get("last_seen"),
                "tenant_id": None,
            }
            if existing:
                await db.topology_nodes.update_one(
                    {"id": existing["id"]}, {"$set": {**doc_updates, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                process_node_id = existing["id"]
                updated += 1
            else:
                process_node_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                await db.topology_nodes.insert_one({
                    "id": process_node_id, "owner": None, "description": None, "created_at": now,
                    "source_ref": {"collection": "oneagent_process", "id": process_source_id},
                    **doc_updates,
                })
                created += 1

            await _upsert_runs_on_edge(process_node_id, container_node_id or host_node["id"])

    return {"created": created, "updated": updated}


async def _upsert_container_node(
    host_key: str, container_id: str, environment: str, lifecycle_status: str, host_node_id: str,
) -> "tuple[str, bool]":
    source_id = f"{host_key}:{container_id}"
    existing = await db.topology_nodes.find_one(
        {"source_ref.collection": "oneagent_container", "source_ref.id": source_id}, {"_id": 0}
    )
    doc_updates = {
        "name": container_id,
        "type": existing.get("type") if existing else "external",
        "resource_category": ResourceCategory.CONTAINER.value,
        "technology": "container",
        "environment": environment,
        "lifecycle_status": lifecycle_status,
        "status": "healthy" if lifecycle_status == LifecycleStatus.MONITORED.value else "critical",
        "health_score": existing.get("health_score") if existing else 100,
        "discovered_by": "bridge:oneagent_agents.services",
        "source_refs": [],
        "tags": [],
        "metadata": {"container_id": container_id, "host": host_key},
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "tenant_id": None,
    }
    created = False
    if existing:
        await db.topology_nodes.update_one(
            {"id": existing["id"]}, {"$set": {**doc_updates, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        node_id = existing["id"]
    else:
        node_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.topology_nodes.insert_one({
            "id": node_id, "owner": None, "description": None, "created_at": now,
            "source_ref": {"collection": "oneagent_container", "id": source_id},
            **doc_updates,
        })
        created = True
    await _upsert_runs_on_edge(node_id, host_node_id)
    return node_id, created


async def upsert_from_connector_inventory(item: Dict[str, Any], connector_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Forward-looking hook for the Connector SDK's InventoryCapable mixin — no
    connector implements it yet. Expected item shape: {"resource_id"|"id", "name",
    "resource_category"?, "technology"?, "environment"?, "tags"?, "metadata"?, "status"?}."""
    resource_id = item.get("resource_id") or item.get("id")
    if not resource_id or not item.get("name"):
        return {"skipped": True, "reason": "connector inventory item missing resource_id/name"}

    source_collection = f"connector:{connector_id}"
    existing = await db.topology_nodes.find_one(
        {"source_ref.collection": source_collection, "source_ref.id": resource_id}, {"_id": 0}
    )
    if existing and (
        existing.get("lifecycle_status") == LifecycleStatus.RETIRED.value
        or (existing.get("metadata") or {}).get("monitoring_disabled")
    ):
        return {"skipped": True, "reason": "manual override in effect"}

    tags_dict = item.get("tags") or {}
    tags_list = [f"{k}:{v}" for k, v in tags_dict.items()] if isinstance(tags_dict, dict) else list(tags_dict or [])
    new_metadata = item.get("metadata") or {}
    merged_metadata = {**(existing.get("metadata") or {}), **new_metadata} if existing else new_metadata

    doc_updates = {
        "name": item["name"],
        "type": existing.get("type") if existing else "external",
        "resource_category": item.get("resource_category", ResourceCategory.OTHER.value),
        "technology": item.get("technology"),
        "environment": item.get("environment", "production"),
        "lifecycle_status": LifecycleStatus.MONITORED.value,
        "status": item.get("status", "healthy"),
        "health_score": existing.get("health_score") if existing else 100,
        "discovered_by": source_collection,
        "source_refs": [{"collection": source_collection, "id": resource_id}],
        "tags": tags_list,
        "metadata": merged_metadata,
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_id,
    }

    if existing:
        await db.topology_nodes.update_one(
            {"id": existing["id"]}, {"$set": {**doc_updates, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"created": False}
    now = datetime.now(timezone.utc).isoformat()
    await db.topology_nodes.insert_one({
        "id": str(uuid.uuid4()), "owner": None, "description": None, "created_at": now,
        "source_ref": {"collection": source_collection, "id": resource_id},
        **doc_updates,
    })
    return {"created": True}


async def sync_all_resources() -> Dict[str, Any]:
    await _ensure_indexes()
    hosts_result = await _sync_hosts()
    db_result = await _sync_databases()
    # Runs after hosts so each host's topology node already exists to link
    # process/container 'runs_on' edges against — see the "host node hasn't
    # been bridged yet this tick" skip inside _sync_processes_and_containers.
    proc_result = await _sync_processes_and_containers()
    if sum(hosts_result.values()) + sum(db_result.values()) + sum(proc_result.values()) > 0:
        try:
            from .resource_explorer_broadcaster import broadcast_resource_event
            await broadcast_resource_event(
                event_type="resource.synced", resource_id="*", resource_category=None, lifecycle_status=None, name=None,
            )
        except Exception:
            pass
    return {"hosts": hosts_result, "databases": db_result, "processes_and_containers": proc_result}


async def resource_bridge_scheduler():
    """Background loop started once at app startup (see main.py)."""
    while True:
        try:
            await sync_all_resources()
        except Exception as e:
            logger.error(f"resource bridge sync failed: {e}")
        await asyncio.sleep(RESOURCE_BRIDGE_TICK_SECONDS)


# ─────────────────────────────────────────────────────
#  List / facets
# ─────────────────────────────────────────────────────

async def list_resources(
    *,
    category: Optional[str] = None,
    technology: Optional[str] = None,
    environment: Optional[str] = None,
    owner: Optional[str] = None,
    business_service: Optional[str] = None,
    tags: Optional[List[str]] = None,
    lifecycle_status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "last_seen",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    tenant_id: Optional[str] = None,
    include_retired: bool = False,
) -> Dict[str, Any]:
    await _ensure_indexes()
    limit = min(max(limit, 1), 500)

    query: Dict[str, Any] = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    if category:
        query["resource_category"] = category
    if technology:
        query["technology"] = technology
    if environment:
        query["environment"] = environment
    if owner:
        query["owner"] = {"$regex": re.escape(owner), "$options": "i"}
    if business_service:
        query["business_service"] = business_service
    if tags:
        query["tags"] = {"$all": tags}
    if lifecycle_status:
        query["lifecycle_status"] = lifecycle_status
    elif not include_retired:
        query["lifecycle_status"] = {"$ne": LifecycleStatus.RETIRED.value}
    if search:
        query["name"] = {"$regex": re.escape(search), "$options": "i"}

    total = await db.topology_nodes.count_documents(query)
    sort_field = sort_by if sort_by in ("last_seen", "name", "health_score", "created_at") else "last_seen"
    sort_dir = 1 if sort_order == "asc" else -1
    rows = await db.topology_nodes.find(query, {"_id": 0}).sort(sort_field, sort_dir).skip(offset).limit(limit).to_list(limit)

    for r in rows:
        if not r.get("resource_category"):
            r["resource_category"] = _TYPE_TO_CATEGORY_FALLBACK.get(r.get("type"), ResourceCategory.APPLICATION.value)

    return {"resources": rows, "total": total, "offset": offset, "limit": limit}


async def get_facets(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    query: Dict[str, Any] = {"tenant_id": tenant_id} if tenant_id else {}
    categories = await db.topology_nodes.distinct("resource_category", query)
    technologies = await db.topology_nodes.distinct("technology", query)
    environments = await db.topology_nodes.distinct("environment", query)
    owners = await db.topology_nodes.distinct("owner", query)
    tags = await db.topology_nodes.distinct("tags", query)
    return {
        "categories": [c for c in categories if c],
        "technologies": [t for t in technologies if t],
        "environments": [e for e in environments if e],
        "owners": [o for o in owners if o],
        "tags": [t for t in tags if t],
    }


# ─────────────────────────────────────────────────────
#  Detail + enrichment
# ─────────────────────────────────────────────────────

async def get_resource(resource_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    resource = await topology_service.get_service_node(resource_id)
    if not resource:
        return None
    if tenant_id and resource.get("tenant_id") not in (None, tenant_id):
        return None
    if not resource.get("resource_category"):
        resource["resource_category"] = _TYPE_TO_CATEGORY_FALLBACK.get(resource.get("type"), ResourceCategory.APPLICATION.value)
    resource["enrichment"] = await _enrich_resource(resource, requesting_tenant_id=tenant_id)
    return resource


async def _enrich_resource(resource: Dict[str, Any], requesting_tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Same honesty discipline as problems_service._enrich_problem(): try/except,
    None + <field>_not_available_reason, never fabricated."""
    enrichment: Dict[str, Any] = {}
    name = resource.get("name")
    category = resource.get("resource_category")

    # Health — echo of stored fields, downgraded (not fabricated) when stale
    age = _seconds_since(resource.get("last_seen"))
    stale_threshold = HEARTBEAT_STALE_AFTER_SECONDS if category == ResourceCategory.INFRASTRUCTURE.value else DB_INSTANCE_STALE_AFTER_SECONDS
    if age is not None and age <= stale_threshold:
        enrichment["health"] = {"score": resource.get("health_score"), "status": resource.get("status"), "as_of": resource.get("last_seen")}
    else:
        enrichment["health"] = None
        reason = f"last_seen is {round(age)}s old (stale)" if age is not None else "no last_seen recorded yet"
        enrichment["health_not_available_reason"] = f"{reason} — resource may be unreachable, not reporting a live health status"

    # Risk / business impact — reuse impact_analysis_engine.get_blast_radius() directly.
    # Uses the RESOURCE's own tenant_id (often None for bridged resources) to find
    # itself in topology_nodes — using the requesting user's tenant_id here would
    # incorrectly report "not found" for any globally-scoped bridged resource.
    try:
        from .impact_analysis_engine import impact_analysis_engine
        result = await impact_analysis_engine.get_blast_radius(name, resource.get("tenant_id"))
        if result.get("error"):
            enrichment["risk"] = None
            enrichment["risk_not_available_reason"] = result["error"]
        else:
            enrichment["risk"] = result
    except Exception as e:
        enrichment["risk"] = None
        enrichment["risk_not_available_reason"] = str(e)[:200]

    # Predicted failure — category-gated, honest about the db.server_metrics /
    # db.metrics_timeseries mismatch found this session.
    if category == ResourceCategory.DATABASE.value:
        enrichment["predicted_failure"] = None
        enrichment["predicted_failure_not_available_reason"] = (
            "Phase 1 has no db-specific time series in db.metrics_timeseries keyed by instance name; "
            "db.db_metrics stores provider metrics per instance_id in an incompatible shape — deferred"
        )
    elif category == ResourceCategory.INFRASTRUCTURE.value:
        source_collections = {sr.get("collection") for sr in (resource.get("source_refs") or [])}
        if "oneagent_agents" in source_collections:
            try:
                from .capacity_prediction_engine import capacity_prediction_engine
                enrichment["predicted_failure"] = await capacity_prediction_engine.predict_capacity(metric_name="cpu_usage", host=name)
            except Exception as e:
                enrichment["predicted_failure"] = None
                enrichment["predicted_failure_not_available_reason"] = str(e)[:200]
        else:
            enrichment["predicted_failure"] = None
            enrichment["predicted_failure_not_available_reason"] = (
                "host metrics are stored in db.server_metrics (legacy /api/servers agent), not "
                "db.metrics_timeseries — capacity prediction isn't wired to that collection in Phase 1"
            )
    else:
        enrichment["predicted_failure"] = None
        enrichment["predicted_failure_not_available_reason"] = f"predicted failure is not yet implemented for resource_category={category}"

    # Related alerts/problems — exact reuse of the Problems console's existing
    # name-match filter. Scoped to the REQUESTING user's tenant (access control),
    # not the resource's own tenant_id.
    try:
        from . import problems_service
        result = await problems_service.list_problems(service=name, limit=10, tenant_id=requesting_tenant_id)
        enrichment["related_problems"] = result["problems"]
    except Exception as e:
        enrichment["related_problems"] = None
        enrichment["related_problems_not_available_reason"] = str(e)[:200]

    return enrichment


# ─────────────────────────────────────────────────────
#  Actions
# ─────────────────────────────────────────────────────

async def set_monitoring(resource_id: str, enabled: bool, user_email: str) -> Optional[Dict[str, Any]]:
    resource = await topology_service.get_service_node(resource_id)
    if not resource:
        return None
    metadata = dict(resource.get("metadata") or {})
    metadata["monitoring_disabled"] = not enabled
    updated = await topology_service.update_service_node(resource_id, {"metadata": metadata})

    linked_monitor = await db.monitors.find_one({"target": resource.get("name")}, {"_id": 0})
    if linked_monitor:
        await db.monitors.update_one({"id": linked_monitor["id"]}, {"$set": {"enabled": enabled}})

    if updated:
        await _broadcast(updated, "resource.monitoring_toggled")
    return updated


async def retire_resource(resource_id: str, reason: Optional[str], user_email: str) -> Optional[Dict[str, Any]]:
    resource = await topology_service.get_service_node(resource_id)
    if not resource:
        return None
    metadata = dict(resource.get("metadata") or {})
    metadata["retired_at"] = datetime.now(timezone.utc).isoformat()
    metadata["retired_by"] = user_email
    metadata["retired_reason"] = reason
    updated = await topology_service.update_service_node(
        resource_id, {"lifecycle_status": LifecycleStatus.RETIRED.value, "metadata": metadata}
    )
    if updated:
        await _broadcast(updated, "resource.lifecycle_changed")
    return updated


GOVERNANCE_CRITICALITY_LEVELS = ("mission_critical", "high", "medium", "low")


async def set_governance_fields(
    resource_id: str,
    *,
    owner: Optional[str] = None,
    business_criticality: Optional[str] = None,
    incident_response_target_minutes: Optional[int] = None,
    business_service: Optional[str] = None,
    user_email: str,
) -> Optional[Dict[str, Any]]:
    """Set the Knowledge Graph governance fields on a resource: who owns it, how
    business-critical it is, its incident-response target, and which business
    service it rolls up to. This is the first user-facing mutation of these
    fields anywhere in the app — `owner` previously existed on the schema but
    was only ever set by the resource bridge (always None) or connector
    auto-discovery; the other three fields are new.

    `business_criticality` is deliberately a different name/concept from
    vulnerability_service's dynamic `asset_criticality_bonus` (computed from
    topology fan-out for CVE scoring). `incident_response_target_minutes` is
    deliberately distinct from sla_service's uptime-percentage `sla_target`
    and incidents_engine's severity-derived `sla_breach_at` — three different
    "SLA" concepts that happen to share a name; this one is an admin-set,
    entity-level MTTR/MTTA target.

    NOTE: for db-instance-derived resources, resource_explorer_service._sync_databases()
    hardcodes tenant_id=None (a pre-existing read-only ambiguity — those resources are
    visible to every tenant). This mutation makes that a write ambiguity too: any
    tenant's admin can set governance fields on a shared, globally-visible db resource.
    Not fixed here — pre-existing gap in the bridge, out of scope for this feature."""
    if business_criticality is not None and business_criticality not in GOVERNANCE_CRITICALITY_LEVELS:
        raise ValueError(f"Invalid business_criticality '{business_criticality}'. Valid: {GOVERNANCE_CRITICALITY_LEVELS}")

    resource = await topology_service.get_service_node(resource_id)
    if not resource:
        return None

    updates: Dict[str, Any] = {}
    if owner is not None:
        updates["owner"] = owner
    if business_criticality is not None:
        updates["business_criticality"] = business_criticality
    if incident_response_target_minutes is not None:
        updates["incident_response_target_minutes"] = incident_response_target_minutes
    if business_service is not None:
        updates["business_service"] = business_service
    if not updates:
        resource.pop("_id", None)
        return resource

    updates["governance_updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["governance_updated_by"] = user_email
    updated = await topology_service.update_service_node(resource_id, updates)
    if updated:
        await _broadcast(updated, "resource.governance_updated")
    return updated


async def restore_resource(resource_id: str, user_email: str) -> Optional[Dict[str, Any]]:
    resource = await topology_service.get_service_node(resource_id)
    if not resource:
        return None
    age = _seconds_since(resource.get("last_seen"))
    new_status = LifecycleStatus.MONITORED.value if (age is not None and age <= HEARTBEAT_STALE_AFTER_SECONDS) else LifecycleStatus.DISCOVERED.value
    updated = await topology_service.update_service_node(resource_id, {"lifecycle_status": new_status})
    if updated:
        await _broadcast(updated, "resource.lifecycle_changed")
    return updated


async def _broadcast(resource: Dict[str, Any], event_type: str) -> None:
    try:
        from .resource_explorer_broadcaster import broadcast_resource_event
        await broadcast_resource_event(
            event_type=event_type, resource_id=resource["id"],
            resource_category=resource.get("resource_category"),
            lifecycle_status=resource.get("lifecycle_status"), name=resource.get("name"),
        )
    except Exception:
        pass


RESTART_INSTRUCTIONS = {
    "oneagent_agents": "sudo systemctl restart falconops-oneagent",  # verified exact unit name, oneagent/deploy/install.sh:13
}


async def get_restart_instruction(resource_id: str) -> Dict[str, Any]:
    """Recommendation/instruction-only — confirmed OneAgent has no inbound
    command channel anywhere (transport.go's heartbeat only ever sends).
    Mirrors the Connector SDK's RemediationCapable = recommendations-only
    decision. Logs to db.resource_actions as reviewed, never executes."""
    resource = await topology_service.get_service_node(resource_id)
    if not resource:
        raise LookupError("Resource not found")

    source_collections = {sr.get("collection") for sr in (resource.get("source_refs") or [])}
    if "oneagent_agents" in source_collections:
        instruction = RESTART_INSTRUCTIONS["oneagent_agents"]
        note = "Real remote restart isn't implemented in Phase 1 — OneAgent has no inbound command channel. Run this on the host yourself."
    else:
        instruction = None
        note = "No managed agent service exists for this resource in Phase 1 — it's monitored via the legacy /api/servers push API (no installable agent to restart) or has no linked agent at all."

    await db.resource_actions.insert_one({
        "id": str(uuid.uuid4()),
        "resource_id": resource_id,
        "action": "restart_agent_recommendation",
        "instruction": instruction,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"instruction": instruction, "note": note, "executed": False}
