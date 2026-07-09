"""
FalconOps AI - SOC Live Feed Routes
REST endpoints for SOC feed data; WebSocket is registered in main.py
"""
from fastapi import APIRouter, Depends, Query

from ..utils.auth import require_auth
from ..services.soc_live_feed import get_recent_feed, soc_manager

router = APIRouter(prefix="/api/soc", tags=["SOC Live Feed"])


@router.get("/feed")
async def recent_feed(
    limit: int = Query(30, le=100),
    current_user: dict = Depends(require_auth),
):
    """Get recent SOC feed items for initial page load"""
    return await get_recent_feed(limit)


@router.get("/stats")
async def soc_stats(current_user: dict = Depends(require_auth)):
    """Get SOC live feed stats"""
    return {
        "connected_clients": soc_manager.client_count,
        "status": "active",
    }
