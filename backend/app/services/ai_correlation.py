"""
FalconOps AI - AI Correlation Engine
Real multi-signal alert correlation for incident creation: topology dependency,
cross-host metric patterns, severity cascades, host grouping, and service grouping —
all computed from live db.alerts / db.topology_nodes / db.topology_edges data.
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

from ..core.database import db
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)


# ======================== CORRELATION STRATEGIES ========================
# Describes the real signal-grouping dimensions the engine below computes from live
# alert/topology data. These are informational (surfaced to the UI / stats endpoint) —
# unlike the old design, they do not gate matching via fixed if/then conditions.

STRUCTURAL_TYPES = {"topology_dependency", "metric_pattern", "severity_cascade"}

CORRELATION_STRATEGIES = [
    {
        "id": "topology_dependency",
        "name": "Topology Dependency",
        "description": "Alerts on services that share a topology dependency edge (e.g. a common upstream database or gateway).",
        "severity": "critical",
    },
    {
        "id": "metric_pattern",
        "name": "Metric Pattern Fleet-Wide",
        "description": "The same metric (e.g. cpu, latency) alerting across multiple hosts at once — usually a systemic issue.",
        "severity": "critical",
    },
    {
        "id": "severity_cascade",
        "name": "Severity Cascade",
        "description": "A burst of alerts across three or more services within the same time window — signals a cascading failure.",
        "severity": "critical",
    },
    {
        "id": "same_host",
        "name": "Same Host",
        "description": "Multiple alerts firing on the same host/server.",
        "severity": "warning",
    },
    {
        "id": "same_service",
        "name": "Same Service",
        "description": "Multiple alerts firing on the same service.",
        "severity": "warning",
    },
]


# ======================== DEDUPLICATION ENGINE ========================

async def deduplicate_alert(alert: Dict[str, Any]) -> Optional[str]:
    """
    Check if a similar alert already exists and return its ID for deduplication.

    Deduplication criteria:
    1. Same monitor_id or service
    2. Same severity
    3. Similar title (fuzzy match)
    4. Within time window (default 10 minutes)
    """
    time_window = datetime.now(timezone.utc) - timedelta(minutes=10)

    query = {
        "status": {"$in": ["open", "acknowledged"]},
        "created_at": {"$gte": time_window.isoformat()},
    }

    if alert.get("service"):
        query["service"] = alert["service"]

    if alert.get("severity"):
        query["severity"] = alert["severity"]

    existing_alerts = await db.alerts.find(query, {"_id": 0}).to_list(100)

    for existing in existing_alerts:
        if is_similar_title(alert.get("title", ""), existing.get("title", "")):
            logger.info(f"Deduplicated alert: {alert.get('title')} matches existing {existing.get('id')}")

            await db.alerts.update_one(
                {"id": existing["id"]},
                {
                    "$inc": {"occurrence_count": 1},
                    "$set": {"last_occurrence": datetime.now(timezone.utc).isoformat()}
                }
            )
            return existing["id"]

    return None


def is_similar_title(title1: str, title2: str, threshold: float = 0.7) -> bool:
    """Check if two alert titles are similar using simple word overlap."""
    if not title1 or not title2:
        return False

    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())

    stopwords = {"the", "a", "an", "is", "on", "for", "alert", "warning", "error", "critical"}
    words1 = words1 - stopwords
    words2 = words2 - stopwords

    if not words1 or not words2:
        return title1.lower() == title2.lower()

    intersection = words1 & words2
    union = words1 | words2

    similarity = len(intersection) / len(union)
    return similarity >= threshold


# ======================== TOPOLOGY LOADING ========================

async def _load_topology(tenant_id: Optional[str] = None):
    """Load the real service-dependency graph (shared with smart_correlation_engine)."""
    query = {} if not tenant_id else {"tenant_id": tenant_id}
    nodes = await db.topology_nodes.find(query, {"_id": 0}).to_list(500)
    edges = await db.topology_edges.find(query, {"_id": 0}).to_list(1000)

    service_map = {n["name"]: n for n in nodes if n.get("name")}
    service_id_map = {n["id"]: n for n in nodes if n.get("id")}

    upstream = defaultdict(set)    # child_id -> set(parent_ids)
    downstream = defaultdict(set)  # parent_id -> set(child_ids)
    for e in edges:
        src, tgt = e.get("source_id"), e.get("target_id")
        if src and tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    return service_map, service_id_map, upstream, downstream


# ======================== REAL MULTI-DIMENSIONAL GROUPING ========================

def _multi_dimension_group(
    alerts: List[Dict[str, Any]],
    service_map: Dict[str, Any],
    service_id_map: Dict[str, Any],
    upstream: Dict[str, set],
    downstream: Dict[str, set],
) -> List[Dict[str, Any]]:
    """
    Group alerts by topology dependency, cross-host metric pattern, severity cascade,
    same host, and same service. Each alert may appear in more than one candidate group;
    the caller resolves overlaps by processing groups highest-confidence-first and
    skipping alerts already claimed by a higher-confidence group.
    """
    groups: List[Dict[str, Any]] = []
    seen_id_sets = set()

    service_alerts = defaultdict(list)
    for a in alerts:
        svc = a.get("service")
        if svc:
            service_alerts[svc].append(a)

    # -- topology dependency: alerts on services sharing an upstream dependency --
    for svc, svc_alerts in service_alerts.items():
        node = service_map.get(svc)
        if not node:
            continue
        for dep_id in upstream.get(node["id"], set()):
            dep_node = service_id_map.get(dep_id)
            if not dep_node:
                continue
            for sib_id in downstream.get(dep_id, set()):
                if sib_id == node["id"]:
                    continue
                sib_node = service_id_map.get(sib_id)
                if sib_node and sib_node["name"] in service_alerts:
                    combined = svc_alerts + service_alerts[sib_node["name"]]
                    ids = frozenset(a["id"] for a in combined)
                    if ids not in seen_id_sets and len(combined) >= 2:
                        seen_id_sets.add(ids)
                        groups.append({
                            "type": "topology_dependency",
                            "reason": f"Shared dependency: {dep_node['name']} affects {svc} and {sib_node['name']}",
                            "alerts": combined,
                            "confidence": min(0.95, 0.75 + 0.05 * len(combined)),
                        })

    # -- metric pattern: same metric alerting across >=2 hosts --
    metric_groups = defaultdict(list)
    for a in alerts:
        mn = a.get("metric_name")
        if mn:
            metric_groups[mn].append(a)
    for metric, m_alerts in metric_groups.items():
        hosts_affected = {a.get("host") for a in m_alerts if a.get("host")}
        if len(hosts_affected) >= 2:
            ids = frozenset(a["id"] for a in m_alerts)
            if ids not in seen_id_sets:
                seen_id_sets.add(ids)
                groups.append({
                    "type": "metric_pattern",
                    "reason": f"{metric} anomaly across {len(hosts_affected)} hosts",
                    "alerts": m_alerts,
                    "confidence": min(0.9, 0.7 + 0.05 * len(hosts_affected)),
                })

    # -- severity cascade: many distinct services alerting within the same window --
    services_in_batch = {a.get("service") for a in alerts if a.get("service")}
    if len(services_in_batch) >= 3:
        ids = frozenset(a["id"] for a in alerts)
        if ids not in seen_id_sets:
            seen_id_sets.add(ids)
            groups.append({
                "type": "severity_cascade",
                "reason": f"{len(services_in_batch)} services alerting in the same window — possible cascading failure",
                "alerts": list(alerts),
                "confidence": min(0.9, 0.6 + 0.05 * len(services_in_batch)),
            })

    # -- same host --
    host_groups = defaultdict(list)
    for a in alerts:
        host = a.get("host")
        if host:
            host_groups[host].append(a)
    for host, h_alerts in host_groups.items():
        if len(h_alerts) >= 2:
            ids = frozenset(a["id"] for a in h_alerts)
            if ids not in seen_id_sets:
                seen_id_sets.add(ids)
                groups.append({
                    "type": "same_host",
                    "reason": f"Multiple alerts on host {host}",
                    "alerts": h_alerts,
                    "confidence": 0.7,
                })

    # -- same service (fallback) --
    for svc, svc_alerts in service_alerts.items():
        if len(svc_alerts) >= 2:
            ids = frozenset(a["id"] for a in svc_alerts)
            if ids not in seen_id_sets:
                seen_id_sets.add(ids)
                groups.append({
                    "type": "same_service",
                    "reason": f"Multiple alerts on service {svc}",
                    "alerts": svc_alerts,
                    "confidence": 0.6,
                })

    groups.sort(key=lambda g: g["confidence"], reverse=True)
    return groups


def _root_cause_and_actions(group_type: str, reason: str, alerts: List[Dict[str, Any]]):
    """Keyword-driven action suggestions from the real alerts in the group (enrichment, not a gate)."""
    text = " ".join(
        f"{a.get('metric_name', '') or ''} {a.get('title', '') or ''}" for a in alerts
    ).lower()

    actions: List[str] = []
    if "cpu" in text:
        actions.append("Scale up CPU resources or identify CPU-intensive processes")
    if "memory" in text:
        actions.append("Investigate memory leaks / increase allocation")
    if "disk" in text:
        actions.append("Clear old logs, expand disk volume, set up log rotation")
    if "connection" in text or "pool" in text or "timeout" in text:
        actions.append("Check connection pool sizing and for connection leaks")
    if "network" in text or "unreachable" in text or "refused" in text:
        actions.append("Check network infrastructure, DNS, and firewall rules")
    if "ssl" in text or "certificate" in text or "expir" in text:
        actions.append("Renew SSL certificate and enable auto-renewal")

    if group_type == "topology_dependency":
        actions.insert(0, "Investigate the shared upstream dependency first — likely root cause")
    elif group_type == "severity_cascade":
        actions.insert(0, "Address the earliest-alerting service first — likely cascade origin")

    if not actions:
        actions = ["Review alert details and recent changes", "Check service logs", "Investigate correlated services"]

    return reason, actions[:5]


async def _create_incident_from_group(
    group_type: str,
    reason: str,
    confidence: float,
    alerts: List[Dict[str, Any]],
    context: Dict[str, Any],
    tenant_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not alerts:
        return None

    incident_id = str(uuid.uuid4())
    alert_ids = [a["id"] for a in alerts]
    services = list({a.get("service", "unknown") for a in alerts})
    primary_service = services[0] if services else "unknown"

    severity_order = {"critical": 3, "warning": 2, "info": 1}
    top_alert = max(alerts, key=lambda a: severity_order.get(a.get("severity", "info"), 0))
    severity = top_alert.get("severity", "warning")

    root_cause, suggested_actions = _root_cause_and_actions(group_type, reason, alerts)
    now_iso = datetime.now(timezone.utc).isoformat()

    incident = {
        "id": incident_id,
        "title": f"{reason} ({len(alerts)} alerts)"[:160],
        "description": reason,
        "severity": severity,
        "status": "open",
        "service": primary_service,
        "affected_services": services,
        "alert_count": len(alerts),
        "alert_ids": alert_ids,
        "correlation_rule_id": group_type if group_type in STRUCTURAL_TYPES else None,
        "correlation_type": group_type,
        "root_cause": root_cause,
        "suggested_actions": suggested_actions,
        "ai_analysis": {
            "correlation_type": group_type,
            "confidence": round(confidence, 2),
            "context": context,
        },
        "tenant_id": tenant_id,
        "created_at": now_iso,
        "updated_at": now_iso,
        "resolved_at": None,
        "mttr_seconds": None,
    }

    await db.incidents.insert_one(incident)
    await db.alerts.update_many({"id": {"$in": alert_ids}}, {"$set": {"incident_id": incident_id}})

    await ws_manager.broadcast({
        "type": "new_incident",
        "data": {k: v for k, v in incident.items() if k != "_id"}
    })

    # Autonomous investigation — fire-and-forget, must never affect incident creation.
    # Note: this incident lives in db.incidents (the legacy system), not
    # db.incidents_engine, so only the recommendation half of the orchestrator applies
    # here (its validate/escalate/learn steps are wired to the incident_engine.py
    # resolve path specifically — see autonomous_ops_orchestrator.py's module docstring).
    try:
        from . import autonomous_ops_orchestrator as orchestrator
        asyncio.create_task(orchestrator.investigate_and_recommend(incident_id, top_alert, tenant_id=tenant_id))
    except Exception:
        pass

    logger.info(
        f"Created incident {incident_id} via '{group_type}' correlation with "
        f"{len(alerts)} alerts (confidence={confidence:.2f})"
    )
    return {k: v for k, v in incident.items() if k != "_id"}


# ======================== CORRELATION ENGINE ========================

async def correlate_alerts(time_window_minutes: int = 15, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Correlate alerts into incidents using real multi-signal grouping
    (topology dependency, metric pattern, severity cascade, host, service).
    Returns list of newly created incidents. Supports multi-tenancy via tenant_id.
    """
    logger.info("Running alert correlation engine...")

    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)

    query = {
        "incident_id": None,
        "status": {"$in": ["open", "acknowledged"]},
        "created_at": {"$gte": time_threshold.isoformat()}
    }
    if tenant_id:
        query["tenant_id"] = tenant_id

    uncorrelated_alerts = await db.alerts.find(query, {"_id": 0}).to_list(500)

    if not uncorrelated_alerts:
        logger.info("No uncorrelated alerts to process")
        return []

    logger.info(f"Processing {len(uncorrelated_alerts)} uncorrelated alerts")

    service_map, service_id_map, upstream, downstream = await _load_topology(tenant_id)

    # Real current-state signals, attached to created incidents as RCA context
    # (informational enrichment only — they no longer gate whether a group forms).
    server_metrics = await get_current_server_metrics()
    apm_metrics = await get_current_apm_metrics()
    service_status = await get_service_status_counts()
    context = {"server_metrics": server_metrics, "apm_metrics": apm_metrics, "service_status": service_status}

    groups = _multi_dimension_group(uncorrelated_alerts, service_map, service_id_map, upstream, downstream)

    created_incidents = []
    claimed_ids = set()
    for group in groups:
        group_alerts = [a for a in group["alerts"] if a["id"] not in claimed_ids]
        if len(group_alerts) < 2:
            continue
        incident = await _create_incident_from_group(
            group["type"], group["reason"], group["confidence"], group_alerts, context, tenant_id
        )
        if incident:
            created_incidents.append(incident)
            claimed_ids.update(a["id"] for a in group_alerts)

    logger.info(
        f"Created {len(created_incidents)} new incidents from correlation "
        f"({len(claimed_ids)}/{len(uncorrelated_alerts)} alerts correlated)"
    )
    return created_incidents


# ======================== HELPER FUNCTIONS (real signals, used as enrichment context) ========================

async def get_current_server_metrics() -> Dict[str, Any]:
    """Get aggregated server metrics."""
    servers = await db.servers.find({"status": {"$ne": "offline"}}, {"_id": 0}).to_list(100)

    if not servers:
        return {}

    total_cpu = sum(s.get("cpu_usage", 0) or 0 for s in servers)
    total_memory = sum(s.get("memory_usage", 0) or 0 for s in servers)
    total_disk = sum(s.get("disk_usage", 0) or 0 for s in servers)
    count = len(servers)

    return {
        "avg_cpu": total_cpu / count if count > 0 else 0,
        "avg_memory": total_memory / count if count > 0 else 0,
        "avg_disk": total_disk / count if count > 0 else 0,
        "server_count": count
    }


async def get_current_apm_metrics() -> Dict[str, Any]:
    """Get aggregated APM metrics."""
    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)

    transactions = await db.apm_transactions.find({
        "start_time": {"$gte": time_threshold.isoformat()}
    }, {"_id": 0, "duration_ms": 1}).to_list(1000)

    if not transactions:
        return {"avg_latency": 0}

    durations = [t.get("duration_ms", 0) for t in transactions]
    return {
        "avg_latency": sum(durations) / len(durations) if durations else 0,
        "transaction_count": len(transactions)
    }


async def get_service_status_counts() -> Dict[str, int]:
    """Get count of services by status."""
    monitors = await db.monitors.find({}, {"_id": 0, "status": 1}).to_list(500)

    counts = defaultdict(int)
    for m in monitors:
        status = m.get("status", "unknown")
        if status in ["up", "healthy"]:
            counts["up"] += 1
        elif status in ["down", "unhealthy"]:
            counts["down"] += 1
        elif status == "degraded":
            counts["degraded"] += 1
        else:
            counts["unknown"] += 1

    return dict(counts)


# ======================== API FUNCTIONS ========================

async def run_correlation_cycle(tenant_id: Optional[str] = None):
    """Run a single correlation cycle - called by scheduler or API."""
    try:
        incidents = await correlate_alerts(tenant_id=tenant_id)
        return {
            "success": True,
            "incidents_created": len(incidents),
            "incidents": incidents
        }
    except Exception as e:
        logger.error(f"Correlation cycle failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def get_correlation_rules() -> List[Dict[str, Any]]:
    """Get the real correlation strategies applied by the engine."""
    return CORRELATION_STRATEGIES


async def get_correlation_stats(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get correlation engine statistics (tenant-aware)."""
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id

    total_incidents = await db.incidents.count_documents(query)
    structural_incidents = await db.incidents.count_documents(
        {**query, "correlation_rule_id": {"$in": list(STRUCTURAL_TYPES)}}
    )
    simple_grouped_incidents = await db.incidents.count_documents(
        {**query, "correlation_type": {"$in": ["same_host", "same_service"]}}
    )

    return {
        "total_incidents": total_incidents,
        "rule_based_incidents": structural_incidents,
        "auto_grouped_incidents": simple_grouped_incidents,
        "correlation_rules_count": len(CORRELATION_STRATEGIES),
        "rules": CORRELATION_STRATEGIES,
    }
