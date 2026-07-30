"""
FalconOps AI — AI Intelligence Layer REST routes
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.database import db
from ..services import ai_tools_service, intelligence_agents_service, rag_service
from ..utils.auth import require_auth, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-intelligence", tags=["AI Intelligence Layer"])


class AskIn(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    mode: str = Field("auto", pattern="^(auto|incident|copilot)$")
    service: Optional[str] = None
    time_range_minutes: int = Field(60, ge=5, le=10080)


class ToolExecIn(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)


@router.post("/ask")
async def ask(body: AskIn, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Unified NL entry: auto-routes to Incident Analysis Agent or Monitoring Copilot Agent."""
    result = await intelligence_agents_service.ask(
        body.query, mode=body.mode, service=body.service,
        time_range_minutes=body.time_range_minutes, user=user)
    result.pop("_id", None)
    return result


@router.get("/tools")
async def list_tools(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return {"tools": ai_tools_service.TOOL_DEFS}


@router.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, body: ToolExecIn, user: dict = Depends(require_admin)) -> Dict[str, Any]:
    """Admin-only: this bypasses the narrow-agent layer and hands any caller raw
    access to tools like get_ueba_profiles/get_threats/get_vulnerabilities —
    previously reachable by any authenticated user regardless of role, a real
    excessive-data-exposure gap the narrow-agent design elsewhere is meant to
    prevent."""
    return await ai_tools_service.execute_tool(tool_name, body.params, tenant_id=user.get("tenant_id"))


@router.get("/services")
async def services(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return {"services": await ai_tools_service.list_services()}


@router.get("/history")
async def history(user: dict = Depends(require_auth),
                  mode: Optional[str] = Query(None),
                  limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    tid = user.get("tenant_id")
    q: Dict[str, Any] = {"tenant_id": tid} if tid else {}
    if mode:
        q["mode"] = mode
    rows = await db.ai_intelligence_analyses.find(q, {"_id": 0, "structured_data": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    return {"analyses": rows, "count": len(rows)}


@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    tid = user.get("tenant_id")
    query: Dict[str, Any] = {"id": analysis_id}
    if tid:
        query["tenant_id"] = tid
    doc = await db.ai_intelligence_analyses.find_one(query, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="analysis not found")
    return doc


@router.get("/rag/stats")
async def rag_stats(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return await rag_service.rag_stats()


@router.post("/rag/reindex")
async def rag_reindex(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    result = await rag_service.reindex_all()
    return {"status": "ok", **result}
