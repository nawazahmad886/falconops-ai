"""AI Operations — Tool Catalog routes. See services/tool_catalog_service.py
and services/tool_binding_dispatch.py for the actual CRUD/dispatch logic;
this file is thin request/response plumbing + RBAC gating only."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services import tool_catalog_service
from ..services.tool_binding_dispatch import dispatch_tool
from ..services.rbac_service import check_permission
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/v1/tools", tags=["Tool Catalog"])


async def _require(current_user: dict, permission: str) -> None:
    if not await check_permission(current_user, permission):
        raise HTTPException(status_code=403, detail=f"requires '{permission}' permission")


@router.get("/binding-kinds")
async def get_binding_kinds(current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.read")
    return {"binding_kinds": tool_catalog_service.list_binding_kinds()}


@router.get("")
async def list_tools(category: Optional[str] = None, status: Optional[str] = None, risk_tier: Optional[str] = None,
                      current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.read")
    return {"tools": await tool_catalog_service.list_tools(category, status, risk_tier)}


@router.get("/{tool_id}")
async def get_tool(tool_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.read")
    tool = await tool_catalog_service.get_tool(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="tool not found")
    return tool


class CreateToolPayload(BaseModel):
    payload: Dict[str, Any]


@router.post("")
async def create_tool(body: CreateToolPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.create")
    result = await tool_catalog_service.create_tool(body.payload, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class UpdateToolPayload(BaseModel):
    updates: Dict[str, Any]


@router.put("/{tool_id}")
async def update_tool(tool_id: str, body: UpdateToolPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.edit")
    result = await tool_catalog_service.update_tool(tool_id, body.updates, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{tool_id}/version")
async def new_tool_version(tool_id: str, body: UpdateToolPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.edit")
    result = await tool_catalog_service.new_tool_version(tool_id, body.updates, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{tool_id}/disable")
async def disable_tool(tool_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.edit")
    result = await tool_catalog_service.set_tool_status(tool_id, "disabled", current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{tool_id}/enable")
async def enable_tool(tool_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.edit")
    result = await tool_catalog_service.set_tool_status(tool_id, "active", current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class TestToolPayload(BaseModel):
    input: Dict[str, Any] = {}


@router.post("/{tool_id}/test")
async def test_tool(tool_id: str, body: TestToolPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "tool.read")
    tool = await tool_catalog_service.get_tool(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="tool not found")
    result = await dispatch_tool(tool_id, body.input, actor=current_user)
    result_dict = result.model_dump()
    await tool_catalog_service.record_test_run(tool_id, tool.get("version", 1), body.input, result_dict, current_user.get("email", "unknown"))
    return result_dict


__all__ = ["router"]
