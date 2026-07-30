"""
FalconOps AI — Enterprise Knowledge Graph (Phase 1)

A thin, named API surface over what already exists rather than a new data
model: every entity's composed view (health, blast radius, related problems)
is already built by resource_explorer_service.get_resource() — this module
never re-derives that. It adds exactly the two pieces that were missing at
the entity level (runbooks, similar-past-incidents) plus one genuinely new
aggregation (the business-service rollup).

Two match-precision regimes end up side by side in the composed view:
problems_service (used inside resource_explorer_service's enrichment) matches
services via unanchored, case-insensitive substring regex — a node named "db"
matches almost anything containing that substring. rag_service.find_similar_incidents
matches via exact ChromaDB metadata equality, silently falling back to an
unfiltered (any-service) query if nothing matches. "Related problems" and
"similar past incidents" are therefore not equally strictly scoped, even
though both are shown in one place here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..core.database import db
from . import rag_service
from . import resource_explorer_service

logger = logging.getLogger(__name__)


async def get_entity_graph(node_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """One composed view of an entity: everything resource_explorer_service.get_resource()
    already returns (node fields incl. owner/business_criticality/
    incident_response_target_minutes/business_service, health, risk/blast-radius,
    related_problems), plus runbooks and similar-past-incidents, which nothing
    surfaces at the entity level today."""
    resource = await resource_explorer_service.get_resource(node_id, tenant_id=tenant_id)
    if not resource:
        return None

    name = resource.get("name")

    try:
        runbooks = await db.runbooks.find({"service": name}, {"_id": 0}).to_list(50)
    except Exception as e:
        logger.warning("knowledge_graph: runbook lookup failed for %s: %s", name, e)
        runbooks = []

    try:
        similar_past_incidents = await rag_service.find_similar_incidents(name, top_k=5, service=name)
    except Exception as e:
        logger.warning("knowledge_graph: similar-incident lookup failed for %s: %s", name, e)
        similar_past_incidents = []

    # db.service_topology is a separate, still-live store (PUT /api/context/topology,
    # admin-gated) with its own tier/owner fields — read-only here, never merged into
    # topology_nodes, since a one-time copy would silently go stale the next time
    # anyone calls that endpoint.
    legacy_service_topology = await db.service_topology.find_one({"service": name}, {"_id": 0})

    resource["runbooks"] = runbooks
    resource["similar_past_incidents"] = similar_past_incidents
    resource["legacy_service_topology"] = legacy_service_topology
    return resource


async def get_business_services(tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Roll up topology_nodes by business_service: node count, worst status, avg
    health. Nodes with no business_service set are excluded (nothing to roll up)."""
    match: Dict[str, Any] = {"business_service": {"$nin": [None, ""]}}
    if tenant_id:
        match["tenant_id"] = tenant_id

    _STATUS_RANK = {"critical": 0, "degraded": 1, "unknown": 2, "healthy": 3}

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": "$business_service",
            "node_count": {"$sum": 1},
            "avg_health_score": {"$avg": "$health_score"},
            "statuses": {"$addToSet": "$status"},
        }},
        {"$sort": {"_id": 1}},
    ]
    rows = await db.topology_nodes.aggregate(pipeline).to_list(200)

    out = []
    for r in rows:
        statuses = [s for s in (r.get("statuses") or []) if s]
        worst_status = min(statuses, key=lambda s: _STATUS_RANK.get(s, 2)) if statuses else "unknown"
        out.append({
            "business_service": r["_id"],
            "node_count": r["node_count"],
            "avg_health_score": round(r["avg_health_score"], 1) if r.get("avg_health_score") is not None else None,
            "worst_status": worst_status,
        })
    return out
