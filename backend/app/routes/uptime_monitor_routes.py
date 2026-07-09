"""
FalconOps AI - Uptime Monitor Routes
URL/HTTP monitoring CRUD, alerts, multi-region, check-now, history, stats,
advanced assertions, and time-series metrics.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access, require_admin
from ..services.uptime_monitor_service import (
    create_monitor, get_monitors, get_monitor, delete_monitor,
    toggle_monitor, check_now, get_check_history, get_uptime_stats,
    get_regions, get_alert_history, update_monitor_config, get_region_stats,
    get_monitor_timeseries, backfill_safe_defaults,
)

router = APIRouter(prefix="/api/uptime", tags=["Uptime Monitor"])


class AssertionSpec(BaseModel):
    type: str  # contains | not_contains | json_path_eq | json_path_neq | status_in
    value: Optional[object] = None
    path: Optional[str] = None
    case_sensitive: Optional[bool] = False


class CreateMonitorRequest(BaseModel):
    name: str
    url: str
    interval: int = 60
    method: str = "GET"
    expected_status: int = 200
    timeout: int = 10
    headers: Optional[dict] = None
    regions: Optional[List[str]] = None
    alert_channels: Optional[List[dict]] = None
    consecutive_failures: int = 3
    assertions: Optional[List[dict]] = None
    max_response_time_ms: Optional[int] = None
    ssl_expiry_warn_days: Optional[int] = 14
    apply_safe_defaults: Optional[bool] = True


class UpdateMonitorRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    interval: Optional[int] = None
    method: Optional[str] = None
    expected_status: Optional[int] = None
    timeout: Optional[int] = None
    regions: Optional[List[str]] = None
    alert_channels: Optional[List[dict]] = None
    consecutive_failures: Optional[int] = None
    assertions: Optional[List[dict]] = None
    max_response_time_ms: Optional[int] = None
    ssl_expiry_warn_days: Optional[int] = None
    apply_safe_defaults: Optional[bool] = None


@router.get("/regions")
async def list_regions(current_user: dict = Depends(require_auth)):
    return get_regions()


@router.get("/monitors")
async def list_monitors(current_user: dict = Depends(require_auth)):
    return await get_monitors()


@router.post("/monitors")
async def add_monitor(req: CreateMonitorRequest, current_user: dict = Depends(require_write_access)):
    return await create_monitor(
        req.name, req.url, req.interval, req.method,
        req.expected_status, req.timeout, req.headers,
        current_user.get("email", ""),
        req.regions, req.alert_channels, req.consecutive_failures,
        req.assertions, req.max_response_time_ms,
        req.ssl_expiry_warn_days or 14,
        req.apply_safe_defaults if req.apply_safe_defaults is not None else True,
    )


@router.get("/monitors/{monitor_id}")
async def get_single_monitor(monitor_id: str, current_user: dict = Depends(require_auth)):
    mon = await get_monitor(monitor_id)
    if not mon:
        return {"error": "Not found"}
    return mon


@router.put("/monitors/{monitor_id}")
async def update_monitor(monitor_id: str, req: UpdateMonitorRequest, current_user: dict = Depends(require_write_access)):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    return await update_monitor_config(monitor_id, updates)


@router.delete("/monitors/{monitor_id}")
async def remove_monitor(monitor_id: str, current_user: dict = Depends(require_write_access)):
    ok = await delete_monitor(monitor_id)
    return {"deleted": ok}


@router.post("/monitors/{monitor_id}/toggle")
async def toggle(monitor_id: str, current_user: dict = Depends(require_write_access)):
    return await toggle_monitor(monitor_id)


@router.post("/monitors/{monitor_id}/check")
async def check_monitor_now(monitor_id: str, current_user: dict = Depends(require_auth)):
    return await check_now(monitor_id)


@router.get("/monitors/{monitor_id}/history")
async def monitor_history(
    monitor_id: str,
    hours: int = Query(24),
    limit: int = Query(100, le=500),
    current_user: dict = Depends(require_auth),
):
    return await get_check_history(monitor_id, hours, limit)


@router.get("/monitors/{monitor_id}/timeseries")
async def monitor_timeseries(
    monitor_id: str,
    hours: int = Query(24, ge=1, le=720),
    bucket_minutes: int = Query(0, ge=0, le=1440),
    current_user: dict = Depends(require_auth),
):
    """Return bucketed time-series for response time + uptime %."""
    return await get_monitor_timeseries(monitor_id, hours, bucket_minutes)


@router.post("/monitors/backfill-safe-defaults")
async def backfill_defaults(admin_user: dict = Depends(require_admin)):
    """Apply safe-default assertions (catch 5xx in body, tracebacks, etc.) to existing monitors."""
    return await backfill_safe_defaults()


@router.get("/monitors/{monitor_id}/regions")
async def monitor_region_stats(
    monitor_id: str,
    hours: int = Query(24),
    current_user: dict = Depends(require_auth),
):
    return await get_region_stats(monitor_id, hours)


@router.get("/alerts")
async def alert_history(
    monitor_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    current_user: dict = Depends(require_auth),
):
    return await get_alert_history(monitor_id, limit)


@router.get("/stats")
async def uptime_stats(
    hours: int = Query(24),
    current_user: dict = Depends(require_auth),
):
    return await get_uptime_stats(hours)
