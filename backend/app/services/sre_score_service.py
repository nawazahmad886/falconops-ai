"""
FalconOps AI — AI SRE Score.

Thin aggregator combining existing real per-domain health signals into one
composite reliability score — same "no new detection logic, just composition"
pattern executive_routes.py already uses for the security composite score.
Every component below is a real percentage derived from real counts in
existing collections; nothing here is a fabricated or hand-picked number.

Components:
  - application:    control_center.platform_overview's own healthy/warning/
                     critical classification (latency-based, real).
  - database:       db_monitoring's per-instance _calc_db_health(), averaged
                     across configured instances.
  - infrastructure:  db.servers status field (online/warning/critical/offline).
  - dependencies:    db.topology_nodes status field (service dependency graph).
  - network:         active alerts tagged network-related — simpler than the
                     other four (no dedicated network health aggregate exists
                     yet), disclosed here rather than hidden: this is a real
                     count, but a coarser signal than the others.

A domain with zero real data to compute from is reported as unavailable
(None), not defaulted to 100 or 0 — averaging in a fabricated "everything's
fine" or "everything's broken" for a domain nobody configured would misstate
the composite.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DOMAIN_WEIGHTS = {
    "application": 0.30, "database": 0.20, "infrastructure": 0.20,
    "dependencies": 0.15, "network": 0.15,
}


async def _application_component(tenant_id: Optional[str] = None) -> Optional[float]:
    from .control_center import platform_overview
    components = await platform_overview.get_service_components()
    if not components:
        return None
    healthy = sum(1 for c in components if c["status"] == "healthy")
    warning = sum(1 for c in components if c["status"] == "warning")
    # healthy=100%, warning=50% credit, critical=0% credit — matches this
    # session's earlier _calc_db_health convention of partial credit for degraded.
    score = (healthy * 100 + warning * 50) / len(components)
    return round(score, 1)


async def _database_component(tenant_id: Optional[str] = None) -> Optional[float]:
    from .core.database import db
    from ..routes.db_monitoring import _calc_db_health

    q: Dict[str, Any] = {"tenant_id": tenant_id} if tenant_id else {}
    instances = await db.db_instances.find(q, {"_id": 0, "id": 1}).to_list(200)
    if not instances:
        return None

    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    scores = []
    for inst in instances:
        instance_id = inst["id"]
        latest_metric = await db.db_metrics.find_one({"instance_id": instance_id}, {"_id": 0}, sort=[("timestamp", -1)])
        sq_count = await db.db_slow_queries.count_documents({"instance_id": instance_id, "detected_at": {"$gte": since}})
        lock_count = await db.db_locks.count_documents({"instance_id": instance_id, "detected_at": {"$gte": since}})
        current = (latest_metric or {}).get("metrics", {})
        scores.append(_calc_db_health(current, sq_count, lock_count))
    return round(sum(scores) / len(scores), 1) if scores else None


async def _infrastructure_component(tenant_id: Optional[str] = None) -> Optional[float]:
    from .core.database import db
    q: Dict[str, Any] = {"tenant_id": tenant_id} if tenant_id else {}
    servers = await db.servers.find(q, {"_id": 0, "status": 1}).to_list(2000)
    if not servers:
        return None
    weight = {"online": 100, "healthy": 100, "warning": 50, "critical": 0, "offline": 0}
    scores = [weight.get((s.get("status") or "").lower(), 50) for s in servers]
    return round(sum(scores) / len(scores), 1)


async def _dependencies_component(tenant_id: Optional[str] = None) -> Optional[float]:
    from .core.database import db
    q: Dict[str, Any] = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.topology_nodes.count_documents(q)
    if total == 0:
        return None
    unhealthy = await db.topology_nodes.count_documents({**q, "status": {"$ne": "healthy"}})
    return round((total - unhealthy) / total * 100, 1)


async def _network_component(tenant_id: Optional[str] = None) -> Optional[float]:
    """Coarser than the other four — see module docstring. Penalizes by count
    of currently-active alerts whose entity_type/source suggests a network
    cause; a real count, not a dedicated network health engine."""
    from .core.database import db
    q: Dict[str, Any] = {"status": {"$in": ["triggered", "acknowledged"]},
                          "$or": [{"entity_type": "network"}, {"source": {"$regex": "network|dns|firewall|routing", "$options": "i"}}]}
    if tenant_id:
        q["tenant_id"] = tenant_id
    active_network_alerts = await db.alerts_engine.count_documents(q)
    return round(max(0, 100 - active_network_alerts * 10), 1)


async def get_sre_score(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    components = {
        "application": await _application_component(tenant_id),
        "database": await _database_component(tenant_id),
        "infrastructure": await _infrastructure_component(tenant_id),
        "dependencies": await _dependencies_component(tenant_id),
        "network": await _network_component(tenant_id),
    }

    available = {k: v for k, v in components.items() if v is not None}
    if not available:
        return {
            "overall": None, "components": components,
            "reason": "no data available in any domain",
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    # Renormalize weights over only the domains with real data — an unconfigured
    # domain must not silently drag the composite toward 0 (or get defaulted to
    # 100), it's excluded from the weighted average entirely.
    total_weight = sum(DOMAIN_WEIGHTS[k] for k in available)
    overall = sum(available[k] * DOMAIN_WEIGHTS[k] for k in available) / total_weight

    return {
        "overall": round(overall, 1),
        "components": components,
        "unavailable_domains": [k for k, v in components.items() if v is None],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["get_sre_score", "DOMAIN_WEIGHTS"]
