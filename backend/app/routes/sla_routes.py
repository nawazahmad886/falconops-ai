"""
FalconOps AI - SLA Dashboard Routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services.sla_service import (
    get_sla_summary, get_sla_overview, set_sla_target, get_incident_timeline,
)

router = APIRouter(prefix="/api/sla", tags=["SLA Dashboard"])


class SetSLATargetRequest(BaseModel):
    monitor_id: str
    target: str


@router.get("/overview")
async def sla_overview(
    months: int = Query(1),
    current_user: dict = Depends(require_auth),
):
    return await get_sla_overview(months)


@router.get("/monitor/{monitor_id}")
async def monitor_sla(
    monitor_id: str,
    months: int = Query(3),
    current_user: dict = Depends(require_auth),
):
    return await get_sla_summary(monitor_id, months)


@router.post("/target")
async def set_target(req: SetSLATargetRequest, current_user: dict = Depends(require_auth)):
    return await set_sla_target(req.monitor_id, req.target)


@router.get("/incidents/{monitor_id}")
async def incidents(
    monitor_id: str,
    days: int = Query(30),
    current_user: dict = Depends(require_auth),
):
    return await get_incident_timeline(monitor_id, days)
