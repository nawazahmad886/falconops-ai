"""
FalconOps AI — Enterprise Knowledge Graph Routes (Phase 1)
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..services import knowledge_graph_service
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/knowledge-graph", tags=["Knowledge Graph"])


@router.get("/entity/{node_id}")
async def get_entity(node_id: str, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Composed entity view: node + owner/business_criticality/incident_response_target_minutes/
    business_service + health + blast radius + related problems (all reused from
    resource_explorer_service.get_resource()) plus runbooks + similar-past-incidents."""
    result = await knowledge_graph_service.get_entity_graph(node_id, tenant_id=current_user.get("tenant_id"))
    if not result:
        raise HTTPException(404, "Entity not found")
    return result


@router.get("/business-services")
async def business_services(current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Rollup of topology_nodes grouped by business_service: node count, worst
    status, avg health score. Only nodes with a business_service set (via
    PUT /api/resources/{id}/governance) are included."""
    rows = await knowledge_graph_service.get_business_services(tenant_id=current_user.get("tenant_id"))
    return {"business_services": rows, "count": len(rows)}
