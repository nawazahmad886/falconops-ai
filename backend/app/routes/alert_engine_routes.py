"""
FalconOps AI - Alert Engine Routes
Enterprise alert lifecycle management API
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access
from ..services.alert_engine import alert_engine

router = APIRouter(prefix="/api/alert-engine", tags=["Alert Engine"])


# ======================== MODELS ========================

class AlertCreateRequest(BaseModel):
    title: str
    description: str
    severity: str = "medium"
    source: str = "manual"
    entity_type: str = "service"
    entity_id: str
    entity_name: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    rule_id: Optional[str] = None
    tags: Optional[dict] = None
    auto_resolve_minutes: Optional[int] = None


class AlertActionRequest(BaseModel):
    notes: Optional[str] = None


# ======================== ENDPOINTS ========================

@router.get("/stats")
async def get_alert_stats(current_user: dict = Depends(require_auth)):
    """Get alert statistics"""
    stats = await alert_engine.get_alert_stats(
        tenant_id=current_user.get("tenant_id")
    )
    return stats


@router.get("/active")
async def get_active_alerts(current_user: dict = Depends(require_auth)):
    """Get all active (triggered + acknowledged) alerts"""
    alerts = await alert_engine.get_active_alerts(
        tenant_id=current_user.get("tenant_id")
    )
    return {"alerts": alerts, "total": len(alerts)}


@router.get("")
async def get_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_user: dict = Depends(require_auth)
):
    """Get alerts with filtering and pagination"""
    result = await alert_engine.get_alerts(
        status=status,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        source=source,
        start_time=start_time,
        end_time=end_time,
        tenant_id=current_user.get("tenant_id"),
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return result


@router.post("")
async def create_alert(
    request: AlertCreateRequest,
    current_user: dict = Depends(require_write_access)
):
    """Create a new alert"""
    alert = await alert_engine.create_alert(
        title=request.title,
        description=request.description,
        severity=request.severity,
        source=request.source,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        entity_name=request.entity_name,
        metric_name=request.metric_name,
        metric_value=request.metric_value,
        threshold=request.threshold,
        rule_id=request.rule_id,
        tags=request.tags,
        tenant_id=current_user.get("tenant_id"),
        auto_resolve_minutes=request.auto_resolve_minutes
    )
    return alert


@router.get("/{alert_id}")
async def get_alert(alert_id: str, current_user: dict = Depends(require_auth)):
    """Get a single alert by ID"""
    alert = await alert_engine.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: AlertActionRequest = AlertActionRequest(),
    current_user: dict = Depends(require_write_access)
):
    """Acknowledge an alert"""
    result = await alert_engine.acknowledge_alert(
        alert_id=alert_id,
        user_id=current_user.get("id", ""),
        user_email=current_user["email"],
        notes=request.notes
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found or not in triggered state")
    return result


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    request: AlertActionRequest = AlertActionRequest(),
    current_user: dict = Depends(require_write_access)
):
    """Resolve an alert"""
    result = await alert_engine.resolve_alert(
        alert_id=alert_id,
        user_id=current_user.get("id", ""),
        user_email=current_user["email"],
        resolution_notes=request.notes
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found or already resolved")
    return result


@router.post("/{alert_id}/close")
async def close_alert(
    alert_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Close a resolved alert"""
    result = await alert_engine.close_alert(
        alert_id=alert_id,
        user_id=current_user.get("id", ""),
        user_email=current_user["email"]
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found or not in resolved state")
    return result


@router.post("/{alert_id}/escalate")
async def escalate_alert(
    alert_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Escalate an alert"""
    result = await alert_engine.escalate_alert(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.post("/auto-resolve")
async def auto_resolve_stale(current_user: dict = Depends(require_write_access)):
    """Auto-resolve alerts past their auto_resolve_at time"""
    count = await alert_engine.auto_resolve_stale_alerts()
    return {"message": f"Auto-resolved {count} alerts", "resolved_count": count}
