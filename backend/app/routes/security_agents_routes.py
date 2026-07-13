"""
FalconOps AI - Specialized Security Agents Routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services.security_agents_service import get_agent_catalog, run_security_agent, SECURITY_AGENTS

router = APIRouter(prefix="/api/security-agents", tags=["Specialized Security Agents"])


class RunAgentRequest(BaseModel):
    query: str


@router.get("")
async def list_agents(current_user: dict = Depends(require_auth)):
    """List the specialized security agents (Threat Hunting, Compliance, Cloud Security, Network, Identity)."""
    return {"agents": get_agent_catalog()}


@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, request: RunAgentRequest, current_user: dict = Depends(require_auth)):
    """Run a specialized security agent against a natural-language query."""
    if agent_id not in SECURITY_AGENTS:
        raise HTTPException(status_code=404, detail=f"Unknown security agent '{agent_id}'")
    result = await run_security_agent(agent_id, request.query, tenant_id=current_user.get("tenant_id"))
    if not result:
        raise HTTPException(status_code=502, detail="Security agent run failed")
    return result
