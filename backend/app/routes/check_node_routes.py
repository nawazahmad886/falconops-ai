"""
FalconOps AI - Check Node Routes
Distributed check node registration, heartbeat, config pull, result push
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_admin
from ..services.check_node_service import (
    register_node, heartbeat, get_nodes, get_node, delete_node,
    get_node_monitors, submit_check_result, get_node_stats,
)

router = APIRouter(prefix="/api/check-nodes", tags=["Check Nodes"])


class RegisterNodeRequest(BaseModel):
    name: str
    region: str
    ip: str
    version: str = "1.0.0"
    capabilities: Optional[List[str]] = None


class HeartbeatRequest(BaseModel):
    metrics: Optional[dict] = None


class CheckResultRequest(BaseModel):
    monitor_id: str
    url: str
    region: str
    status_code: int = 0
    response_time_ms: float = 0
    success: bool = False
    error: Optional[str] = None


@router.post("/register")
async def register(req: RegisterNodeRequest):
    """Register a check node (no auth — nodes self-register)"""
    return await register_node(req.name, req.region, req.ip, req.version, req.capabilities)


@router.post("/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, req: HeartbeatRequest):
    """Node heartbeat (no auth)"""
    return await heartbeat(node_id, req.metrics)


@router.get("/{node_id}/monitors")
async def node_monitors(node_id: str):
    """Get monitors for this node's region (no auth — node pulls config)"""
    return await get_node_monitors(node_id)


@router.post("/{node_id}/results")
async def submit_result(node_id: str, req: CheckResultRequest):
    """Submit check result from node (no auth)"""
    return await submit_check_result(node_id, req.dict())


@router.get("")
async def list_nodes(
    region: Optional[str] = Query(None),
    current_user: dict = Depends(require_auth),
):
    """List all check nodes"""
    return await get_nodes(region)


@router.get("/stats")
async def node_stats(current_user: dict = Depends(require_auth)):
    """Get node statistics"""
    return await get_node_stats()


@router.delete("/{node_id}")
async def remove_node(node_id: str, current_user: dict = Depends(require_admin)):
    """Delete a check node"""
    ok = await delete_node(node_id)
    return {"deleted": ok}
