"""
FalconOps AI - UEBA Routes
User & Entity Behavior Analytics API endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..utils.auth import get_current_user
from ..services.ueba_service import (
    build_user_profiles,
    get_user_behavior_timeline,
    get_ueba_summary,
)

router = APIRouter(prefix="/api/security/ueba", tags=["UEBA"])


@router.get("/profiles")
async def user_profiles(
    hours: int = Query(168, description="Lookback window in hours (default 7 days)"),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Get behavioral risk profiles for all users"""
    return await build_user_profiles(hours)


@router.get("/summary")
async def ueba_summary(
    hours: int = Query(168, description="Lookback window in hours"),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Get UEBA summary statistics"""
    return await get_ueba_summary(hours)


@router.get("/user/{username}")
async def user_timeline(
    username: str,
    hours: int = Query(168, description="Lookback window in hours"),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Get detailed behavior timeline for a specific user"""
    return await get_user_behavior_timeline(username, hours)
