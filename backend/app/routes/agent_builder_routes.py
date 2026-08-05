"""AI Operations — Agent Builder routes. Thin plumbing over
services/agent_builder/*; see agent_definition_service.py and
react_engine.py for the actual logic."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services.agent_builder import agent_definition_service, react_engine
from ..services.rbac_service import check_permission
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/v1/agent-builder", tags=["Agent Builder"])


async def _require(current_user: dict, permission: str) -> None:
    if not await check_permission(current_user, permission):
        raise HTTPException(status_code=403, detail=f"requires '{permission}' permission")


@router.get("/agent-catalog")
async def get_agent_catalog(current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.read")
    return {"agents": await agent_definition_service.get_agent_catalog()}


@router.get("/agents")
async def list_agents(status: Optional[str] = None, category: Optional[str] = None, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.read")
    return {"agents": await agent_definition_service.list_agents(status, category)}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, version: Optional[int] = None, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.read")
    result = await agent_definition_service.get_agent(agent_id, version)
    if result is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return result


class CreateAgentPayload(BaseModel):
    payload: Dict[str, Any]


@router.post("/agents")
async def create_agent(body: CreateAgentPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.create")
    result = await agent_definition_service.create_draft(body.payload, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class UpdateAgentPayload(BaseModel):
    updates: Dict[str, Any]


@router.put("/agents/{agent_id}/draft")
async def update_agent_draft(agent_id: str, body: UpdateAgentPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.edit")
    result = await agent_definition_service.update_draft(agent_id, body.updates, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/agents/{agent_id}/publish")
async def publish_agent(agent_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.publish")
    result = await agent_definition_service.publish(agent_id, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/agents/{agent_id}/versions/{version}/rollback")
async def rollback_agent(agent_id: str, version: int, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.publish")
    result = await agent_definition_service.rollback(agent_id, version, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/agents/{agent_id}/versions/{version}/clone")
async def clone_agent(agent_id: str, version: int, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.create")
    result = await agent_definition_service.clone(agent_id, version, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/agents/{agent_id}/versions/{v1}/compare/{v2}")
async def compare_agent(agent_id: str, v1: int, v2: int, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.read")
    result = await agent_definition_service.compare(agent_id, v1, v2)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/agents/{agent_id}/archive")
async def archive_agent(agent_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.edit")
    result = await agent_definition_service.archive(agent_id, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class TestAgentPayload(BaseModel):
    input: Dict[str, Any] = {}


@router.post("/agents/{agent_id}/test")
async def test_agent(agent_id: str, body: TestAgentPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.read")
    result = await react_engine.run_agent(
        agent_id, body.input, triggered_by_kind="manual_test",
        triggered_by_ref=current_user.get("email"), actor=current_user,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/agent-executions/{agent_execution_id}")
async def get_agent_execution(agent_execution_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "agent.read")
    from ..core.database import db
    doc = await db.agent_executions.find_one({"agent_execution_id": agent_execution_id}, {"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404, detail="agent execution not found")
    return doc


__all__ = ["router"]
