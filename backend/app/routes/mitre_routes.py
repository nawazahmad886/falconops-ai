"""
FalconOps AI - MITRE ATT&CK Routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..utils.auth import get_current_user
from ..services.mitre_mapping_service import get_mitre_matrix, get_technique_catalog

router = APIRouter(prefix="/api/mitre", tags=["MITRE ATT&CK"])


@router.get("/matrix")
async def mitre_matrix(
    hours: int = Query(24, description="Lookback window in hours"),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Get MITRE ATT&CK matrix heatmap: technique counts grouped by tactic."""
    tenant_id = current_user.get("tenant_id") if current_user else None
    return await get_mitre_matrix(hours, tenant_id)


@router.get("/techniques")
async def mitre_techniques(current_user: Optional[dict] = Depends(get_current_user)):
    """Get the full MITRE ATT&CK technique catalog known to FalconOps."""
    return {"techniques": get_technique_catalog()}
