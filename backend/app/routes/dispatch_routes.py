"""
FalconOps AI - Connector Dispatcher Routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..utils.auth import require_auth
from ..services.connector_dispatcher import get_dispatch_logs

router = APIRouter(prefix="/api/dispatch", tags=["Connector Dispatch"])


@router.get("/logs")
async def dispatch_logs(
    limit: int = Query(50, le=200),
    current_user: dict = Depends(require_auth),
):
    """Get recent event dispatch logs"""
    return await get_dispatch_logs(limit)
