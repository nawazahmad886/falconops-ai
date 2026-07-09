"""
FalconOps AI - Impact Analysis Routes
Business impact quantification API
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..utils.auth import require_auth
from ..services.impact_analysis_engine import impact_analysis_engine

router = APIRouter(prefix="/api/impact", tags=["Impact Analysis"])


@router.get("/incident/{incident_id}")
async def analyze_incident_impact(
    incident_id: str,
    current_user: dict = Depends(require_auth),
):
    """Full impact analysis for an incident"""
    return await impact_analysis_engine.analyze_incident_impact(
        incident_id=incident_id,
        tenant_id=current_user.get("tenant_id"),
    )


@router.get("/blast-radius")
async def get_blast_radius(
    service_name: str = Query(...),
    current_user: dict = Depends(require_auth),
):
    """Calculate blast radius if a service fails"""
    return await impact_analysis_engine.get_blast_radius(
        service_name=service_name,
        tenant_id=current_user.get("tenant_id"),
    )


@router.get("/system-risk")
async def system_risk_summary(
    current_user: dict = Depends(require_auth),
):
    """Overall system risk score"""
    return await impact_analysis_engine.get_system_risk_summary(
        tenant_id=current_user.get("tenant_id"),
    )
