"""
Agent Definition CRUD + versioning.

Header/version split mirrors RASED's own mutable/immutable separation
(rased_investigations vs rased_trace): agent_definitions is a mutable
pointer (current_published_version, latest_draft_version); agent_versions
are immutable snapshots. Publish freezes a version and moves the pointer.
Rollback moves the pointer only — no version data is ever mutated or
deleted, so a running agent_execution that captured its config at start
time stays reproducible.

The 8 RASED-wrapper agents (is_rased_wrapper=True) are seeded once at
startup and are not editable through this service's update_draft/publish
path — their "config" is just a label; the actual behavior is RASED's own
class, dispatched directly by the workflow DAG engine (see
services/workflow/dag_engine.py's RASED integration), never routed through
react_engine.py's autonomous loop.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ...models.agent_workflow_schemas import AgentDefinition, AgentVersion

logger = logging.getLogger(__name__)

RASED_WRAPPER_AGENTS = [
    {"rased_agent_class": "OrchestratorAgent", "name": "RASED Orchestrator", "category": "investigation",
     "description": "Coordinates the investigation graph (dedup/storm suppression, routing to telemetry retrieval)."},
    {"rased_agent_class": "TelemetryRetrievalAgent", "name": "RASED Telemetry Retrieval", "category": "investigation",
     "description": "Gathers evidence from 7 parallel adapters (ELK, AppDynamics, DB, SolarWinds, MQ, CMDB, Changes)."},
    {"rased_agent_class": "RCAAgent", "name": "RASED RCA Agent", "category": "investigation",
     "description": "Two-pass root-cause hypothesis generation with evidence citation and computed confidence."},
    {"rased_agent_class": "PolicyAgent", "name": "RASED Policy Agent", "category": "governance",
     "description": "Checks a proposed action against policy documents before it can be approved."},
    {"rased_agent_class": "ActionAgent", "name": "RASED Action Agent", "category": "remediation",
     "description": "Proposes and gates remediation actions; interrupts for DESTRUCTIVE-tier approval."},
    {"rased_agent_class": "VerificationAgent", "name": "RASED Verification Agent", "category": "validation",
     "description": "Before/after metric check confirming an action actually resolved the incident."},
    {"rased_agent_class": "ImpactAgent", "name": "RASED Impact Agent", "category": "investigation",
     "description": "Assesses business/blast-radius impact of the affected service."},
    {"rased_agent_class": "CaseManagementAgent", "name": "RASED Case Management Agent", "category": "governance",
     "description": "Finalizes case records and audit entries once an investigation concludes."},
]


async def _ensure_indexes() -> None:
    from ...core.database import db
    try:
        await db.agent_definitions.create_index("agent_id", unique=True)
        await db.agent_definitions.create_index("status")
        await db.agent_definitions.create_index("category")
        await db.agent_versions.create_index([("agent_id", 1), ("version", 1)], unique=True)
        await db.agent_versions.create_index([("agent_id", 1), ("state", 1)])
        await db.agent_executions.create_index("agent_execution_id", unique=True)
        await db.agent_executions.create_index("agent_id")
    except Exception as e:
        logger.warning(f"agent_definitions index setup failed: {e}")


async def seed_rased_wrapper_agents() -> None:
    """Idempotent upsert, same pattern as rbac_service.init_default_roles()."""
    await _ensure_indexes()
    from ...core.database import db

    for spec in RASED_WRAPPER_AGENTS:
        agent_id = f"rased-{spec['rased_agent_class'].lower()}"
        existing = await db.agent_definitions.find_one({"agent_id": agent_id})
        if existing:
            continue
        now = datetime.now(timezone.utc)
        definition = AgentDefinition(
            agent_id=agent_id, name=spec["name"], description=spec["description"],
            category=spec["category"], icon="ShieldCheck", owner_email="system",
            status="published", current_published_version=1, latest_draft_version=1,
            is_rased_wrapper=True, rased_agent_class=spec["rased_agent_class"],
            tags=["rased", "built-in"], created_at=now, updated_at=now,
        )
        version = AgentVersion(
            version_id=str(uuid.uuid4()), agent_id=agent_id, version=1, state="published",
            system_instructions={"template": f"Built-in RASED agent ({spec['rased_agent_class']}) — "
                                              "not editable; behavior is the real RASED class.", "variables": []},
            permissions_required=["agent.read"], created_by="system", published_at=now,
        )
        await db.agent_definitions.insert_one(definition.model_dump(mode="json"))
        await db.agent_versions.insert_one(version.model_dump(mode="json"))
        logger.info(f"seeded RASED-wrapper agent definition '{agent_id}'")


async def _get_version(agent_id: str, version: int) -> Optional[Dict]:
    from ...core.database import db
    return await db.agent_versions.find_one({"agent_id": agent_id, "version": version}, {"_id": 0})


async def get_agent(agent_id: str, version: Optional[int] = None) -> Optional[Dict]:
    from ...core.database import db
    header = await db.agent_definitions.find_one({"agent_id": agent_id}, {"_id": 0})
    if header is None:
        return None
    target_version = version or header.get("current_published_version") or header.get("latest_draft_version")
    version_doc = await _get_version(agent_id, target_version) if target_version else None
    return {"definition": header, "version": version_doc}


async def list_agents(status: Optional[str] = None, category: Optional[str] = None) -> List[Dict]:
    from ...core.database import db
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    return await db.agent_definitions.find(query, {"_id": 0}).sort("name", 1).to_list(500)


async def get_agent_catalog() -> List[Dict]:
    """Union of custom + RASED-wrapper agents, for the workflow builder's
    Agent-node picker and the Agent Catalog page — mirrors runbooks.py's
    existing GET /agent-catalog union pattern (security+ops+core agents)."""
    return await list_agents(status="published")


async def create_draft(payload: Dict[str, Any], created_by: str) -> Dict[str, Any]:
    await _ensure_indexes()
    from ...core.database import db

    agent_id = payload.get("agent_id") or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    try:
        definition = AgentDefinition(
            agent_id=agent_id, name=payload.get("name", "Untitled Agent"),
            description=payload.get("description", ""), category=payload.get("category", "custom"),
            icon=payload.get("icon", "Bot"), owner_email=created_by, status="draft",
            latest_draft_version=1, is_rased_wrapper=False, tags=payload.get("tags", []),
            created_at=now, updated_at=now,
        )
        version = AgentVersion(
            version_id=str(uuid.uuid4()), agent_id=agent_id, version=1, state="draft",
            created_by=created_by, **{k: v for k, v in payload.items() if k in AgentVersion.model_fields and k not in ("version_id", "agent_id", "version", "state")},
        )
    except ValidationError as e:
        return {"error": f"invalid agent definition: {e}"}

    await db.agent_definitions.insert_one(definition.model_dump(mode="json"))
    await db.agent_versions.insert_one(version.model_dump(mode="json"))
    return {"definition": definition.model_dump(mode="json"), "version": version.model_dump(mode="json")}


async def update_draft(agent_id: str, updates: Dict[str, Any], updated_by: str) -> Dict[str, Any]:
    from ...core.database import db
    header = await db.agent_definitions.find_one({"agent_id": agent_id})
    if header is None:
        return {"error": "agent not found"}
    if header.get("is_rased_wrapper"):
        return {"error": "RASED-wrapper agents are not editable"}

    draft_version = header.get("latest_draft_version")
    existing = await _get_version(agent_id, draft_version)
    if existing is None or existing.get("state") != "draft":
        # Current pointer is a published/archived version — open a new draft from it.
        draft_version = (header.get("latest_draft_version") or 0) + 1
        existing = existing or {}

    merged = {**existing, **updates, "agent_id": agent_id, "version": draft_version, "state": "draft"}
    try:
        version = AgentVersion(**merged)
    except ValidationError as e:
        return {"error": f"invalid agent definition: {e}"}

    doc = version.model_dump(mode="json")
    await db.agent_versions.update_one(
        {"agent_id": agent_id, "version": draft_version}, {"$set": doc}, upsert=True,
    )
    await db.agent_definitions.update_one(
        {"agent_id": agent_id},
        {"$set": {
            "latest_draft_version": draft_version, "updated_at": datetime.now(timezone.utc).isoformat(),
            **{k: updates[k] for k in ("name", "description", "category", "icon", "tags") if k in updates},
        }},
    )
    return doc


async def publish(agent_id: str, published_by: str) -> Dict[str, Any]:
    from ...core.database import db
    header = await db.agent_definitions.find_one({"agent_id": agent_id})
    if header is None:
        return {"error": "agent not found"}
    if header.get("is_rased_wrapper"):
        return {"error": "RASED-wrapper agents are always published"}

    draft_version = header.get("latest_draft_version")
    version_doc = await _get_version(agent_id, draft_version)
    if version_doc is None:
        return {"error": "no draft version to publish"}

    now = datetime.now(timezone.utc)
    await db.agent_versions.update_one(
        {"agent_id": agent_id, "version": draft_version},
        {"$set": {"state": "published", "published_at": now.isoformat()}},
    )
    await db.agent_definitions.update_one(
        {"agent_id": agent_id},
        {"$set": {"status": "published", "current_published_version": draft_version, "updated_at": now.isoformat()}},
    )
    return {"agent_id": agent_id, "published_version": draft_version}


async def rollback(agent_id: str, target_version: int, actor: str) -> Dict[str, Any]:
    from ...core.database import db
    version_doc = await _get_version(agent_id, target_version)
    if version_doc is None or version_doc.get("state") != "published":
        return {"error": f"version {target_version} is not a published version"}
    await db.agent_definitions.update_one(
        {"agent_id": agent_id},
        {"$set": {"current_published_version": target_version, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"agent_id": agent_id, "current_published_version": target_version}


async def clone(agent_id: str, source_version: int, actor: str) -> Dict[str, Any]:
    from ...core.database import db
    header = await db.agent_definitions.find_one({"agent_id": agent_id})
    source = await _get_version(agent_id, source_version)
    if header is None or source is None:
        return {"error": "agent or version not found"}

    new_version = (header.get("latest_draft_version") or 0) + 1
    doc = {**source, "version": new_version, "state": "draft", "version_id": str(uuid.uuid4()),
           "created_by": actor, "created_at": datetime.now(timezone.utc).isoformat(), "published_at": None,
           "changelog": f"cloned from v{source_version}"}
    await db.agent_versions.insert_one(doc)
    await db.agent_definitions.update_one(
        {"agent_id": agent_id}, {"$set": {"latest_draft_version": new_version, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return doc


async def compare(agent_id: str, v1: int, v2: int) -> Dict[str, Any]:
    a = await _get_version(agent_id, v1)
    b = await _get_version(agent_id, v2)
    if a is None or b is None:
        return {"error": "one or both versions not found"}
    diff: Dict[str, Any] = {}
    keys = set(a.keys()) | set(b.keys())
    for key in keys:
        if key in ("version_id", "created_at", "published_at"):
            continue
        if a.get(key) != b.get(key):
            diff[key] = {"v1": a.get(key), "v2": b.get(key)}
    return {"agent_id": agent_id, "v1": v1, "v2": v2, "diff": diff}


async def archive(agent_id: str, actor: str) -> Dict[str, Any]:
    from ...core.database import db
    result = await db.agent_definitions.update_one(
        {"agent_id": agent_id, "is_rased_wrapper": {"$ne": True}},
        {"$set": {"status": "archived", "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        return {"error": "agent not found or is a non-archivable RASED-wrapper agent"}
    return {"agent_id": agent_id, "status": "archived"}


__all__ = [
    "seed_rased_wrapper_agents", "get_agent", "list_agents", "get_agent_catalog",
    "create_draft", "update_draft", "publish", "rollback", "clone", "compare", "archive",
    "RASED_WRAPPER_AGENTS",
]
