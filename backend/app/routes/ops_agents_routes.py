"""
FalconOps AI - Specialized Operations Agents Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services.ops_agents_service import get_agent_catalog, run_ops_agent, OPS_AGENTS

router = APIRouter(prefix="/api/ops-agents", tags=["Specialized Operations Agents"])


class RunAgentRequest(BaseModel):
    query: str


@router.get("")
async def list_agents(current_user: dict = Depends(require_auth)):
    """List the specialized operations agents (API Performance, Capacity, SLA Risk, Executive Ops)."""
    return {"agents": get_agent_catalog()}


@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, request: RunAgentRequest, current_user: dict = Depends(require_auth)):
    """Run a specialized operations agent against a natural-language query."""
    if agent_id not in OPS_AGENTS:
        raise HTTPException(status_code=404, detail=f"Unknown ops agent '{agent_id}'")
    result = await run_ops_agent(agent_id, request.query, tenant_id=current_user.get("tenant_id"))
    if not result:
        raise HTTPException(status_code=502, detail="Ops agent run failed")
    return result
