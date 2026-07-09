"""
FalconOps AI - Detection Rules & Incident Intelligence Routes
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_admin
from ..services.detection_rules_service import (
    get_rules, create_rule, update_rule, delete_rule,
    get_incidents_with_intelligence, get_detection_stats,
)

router = APIRouter(prefix="/api/detection", tags=["Detection Rules"])


class CreateRuleRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    metric: str
    operator: str = "gt"
    threshold: float
    severity: str = "warning"
    cooldown_min: int = 10
    enabled: bool = True
    category: str = "custom"


class UpdateRuleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    severity: Optional[str] = None
    cooldown_min: Optional[int] = None
    enabled: Optional[bool] = None
    category: Optional[str] = None


@router.get("/rules")
async def list_rules(current_user: dict = Depends(require_auth)):
    return await get_rules()


@router.post("/rules")
async def add_rule(req: CreateRuleRequest, current_user: dict = Depends(require_admin)):
    return await create_rule(req.dict())


@router.put("/rules/{rule_id}")
async def edit_rule(rule_id: str, req: UpdateRuleRequest, current_user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    return await update_rule(rule_id, updates)


@router.delete("/rules/{rule_id}")
async def remove_rule(rule_id: str, current_user: dict = Depends(require_admin)):
    ok = await delete_rule(rule_id)
    if not ok:
        return {"error": "Cannot delete system rule or rule not found"}
    return {"deleted": True}


@router.get("/incidents")
async def incidents(
    hours: int = Query(24),
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth),
):
    return await get_incidents_with_intelligence(hours, limit)


@router.get("/stats")
async def stats(
    hours: int = Query(24),
    current_user: dict = Depends(require_auth),
):
    return await get_detection_stats(hours)
