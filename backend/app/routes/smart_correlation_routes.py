"""
FalconOps AI - Smart Correlation Routes
Topology-aware event correlation API
"""
from fastapi import APIRouter, Depends, Query

from ..utils.auth import require_auth, require_write_access
from ..services.smart_correlation_engine import smart_correlation_engine

router = APIRouter(prefix="/api/smart-correlation", tags=["Smart Correlation"])


@router.post("/run")
async def run_correlation(
    time_window_minutes: int = Query(10, ge=1, le=60),
    min_signals: int = Query(2, ge=2, le=10),
    current_user: dict = Depends(require_write_access),
):
    """Run smart topology-aware correlation"""
    return await smart_correlation_engine.correlate(
        time_window_minutes=time_window_minutes,
        min_signals=min_signals,
        tenant_id=current_user.get("tenant_id"),
    )
