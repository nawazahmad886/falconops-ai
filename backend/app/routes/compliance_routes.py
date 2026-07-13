"""
FalconOps AI - Compliance Monitoring Routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from ..utils.auth import get_current_user
from ..services.compliance_service import (
    get_frameworks,
    evaluate_compliance,
    get_compliance_dashboard,
    get_compliance_trend,
)

router = APIRouter(prefix="/api/compliance", tags=["Compliance Monitoring"])


@router.get("/frameworks")
async def list_frameworks(current_user: Optional[dict] = Depends(get_current_user)):
    """List supported compliance frameworks."""
    return {"frameworks": get_frameworks()}


@router.get("/dashboard")
async def compliance_dashboard(current_user: Optional[dict] = Depends(get_current_user)):
    """Compliance score + control status across all frameworks."""
    tenant_id = current_user.get("tenant_id") if current_user else None
    return await get_compliance_dashboard(tenant_id)


@router.get("/trend")
async def compliance_trend(
    days: int = Query(30, description="Lookback window in days"),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Daily compliance-score snapshots for trend display."""
    return await get_compliance_trend(days)


@router.get("/{framework}")
async def framework_compliance(framework: str, current_user: Optional[dict] = Depends(get_current_user)):
    """Evaluate a single compliance framework (e.g. SOC2, ISO27001)."""
    tenant_id = current_user.get("tenant_id") if current_user else None
    if framework not in get_frameworks():
        raise HTTPException(status_code=404, detail=f"Unknown framework '{framework}'")
    return await evaluate_compliance(framework, tenant_id)
