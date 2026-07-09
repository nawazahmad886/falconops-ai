"""
FalconOps AI - Impact Analysis Routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services.impact_analysis_service import (
    analyze_blast_radius,
    get_impact_history,
    get_impact_stats,
)

router = APIRouter(prefix="/api/impact", tags=["Impact Analysis"])


class AnalyzeRequest(BaseModel):
    host: Optional[str] = ""
    service: Optional[str] = ""
    severity: Optional[str] = "warning"
    type: Optional[str] = "incident"
    source_ip: Optional[str] = ""
    user: Optional[str] = ""


@router.post("/analyze")
async def analyze(
    req: AnalyzeRequest,
    current_user: dict = Depends(require_auth),
):
    """Analyze blast radius of an incident"""
    return await analyze_blast_radius(req.dict())


@router.get("/history")
async def history(
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth),
):
    """Get recent impact analyses"""
    return await get_impact_history(limit)


@router.get("/stats")
async def stats(current_user: dict = Depends(require_auth)):
    """Get impact analysis statistics"""
    return await get_impact_stats()
