"""
FalconOps AI - Alert Routes
Alert ingestion, management, and notification with full multi-tenancy support
"""
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query

from ..core.database import db
from ..models.schemas import AlertCreate, AlertResponse, SendAlertNotificationRequest
from ..utils.auth import require_auth, require_write_access, get_current_user, build_tenant_query
from ..services.websocket_manager import ws_manager
from ..services.notification_service import send_alert_email, send_teams_notification

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.post("/webhook", response_model=AlertResponse)
async def ingest_alert(alert: AlertCreate, tenant_id: Optional[str] = Query(None)):
    """Ingest alert from external monitoring tools (public endpoint for webhooks)"""
    alert_hash = hashlib.sha256(f"{alert.source}:{alert.service}:{alert.title}:{alert.severity}".encode()).hexdigest()[:32]
    
    # Check for deduplication
    dedup_query = {"hash": alert_hash, "status": "open"}
    if tenant_id:
        dedup_query["tenant_id"] = tenant_id
        
    existing = await db.alerts.find_one(dedup_query)
    if existing:
        await db.alerts.update_one(
            {"id": existing["id"]},
            {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"occurrence_count": 1}}
        )
        return AlertResponse(**{k: v for k, v in existing.items() if k != "_id"})
    
    alert_id = str(uuid.uuid4())
    alert_doc = {
        "id": alert_id,
        "tenant_id": tenant_id,  # Multi-tenancy support
        "source": alert.source,
        "severity": alert.severity,
        "title": alert.title,
        "description": alert.description,
        "service": alert.service,
        "host": alert.host,
        "metric_name": alert.metric_name,
        "metric_value": alert.metric_value,
        "threshold": alert.threshold,
        "tags": alert.tags or {},
        "raw_payload": alert.raw_payload,
        "hash": alert_hash,
        "status": "open",
        "incident_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_at": None,
        "resolved_at": None,
        "acknowledged_by": None,
        "occurrence_count": 1
    }
    
    await db.alerts.insert_one(alert_doc)
    
    response_doc = {k: v for k, v in alert_doc.items() if k != "_id"}
    await ws_manager.broadcast({"type": "new_alert", "data": response_doc})
    
    return AlertResponse(**response_doc)


@router.get("", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    service: Optional[str] = Query(None, description="Filter by service"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get all alerts with optional filters (tenant-aware)"""
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    if service:
        query["service"] = service
    
    # Apply tenant filter if user has tenant_id
    if current_user and current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    return [AlertResponse(**a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str, current_user: Optional[dict] = Depends(get_current_user)):
    """Get single alert by ID (tenant-aware)"""
    query = {"id": alert_id}
    if current_user and current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    alert = await db.alerts.find_one(query, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse(**alert)


@router.patch("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: dict = Depends(require_write_access)):
    """Acknowledge an alert (tenant-aware)"""
    query = {"id": alert_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    alert = await db.alerts.find_one(query)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    await db.alerts.update_one(
        {"id": alert_id},
        {"$set": {
            "status": "acknowledged",
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            "acknowledged_by": current_user["email"]
        }}
    )
    
    updated = await db.alerts.find_one({"id": alert_id}, {"_id": 0})
    await ws_manager.broadcast({"type": "alert_updated", "data": updated})
    
    return {"message": "Alert acknowledged", "alert": updated}


@router.patch("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, current_user: dict = Depends(require_write_access)):
    """Resolve an alert (tenant-aware)"""
    query = {"id": alert_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    alert = await db.alerts.find_one(query)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    await db.alerts.update_one(
        {"id": alert_id},
        {"$set": {
            "status": "resolved",
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    updated = await db.alerts.find_one({"id": alert_id}, {"_id": 0})
    await ws_manager.broadcast({"type": "alert_resolved", "data": updated})
    
    return {"message": "Alert resolved", "alert": updated}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, current_user: dict = Depends(require_write_access)):
    """Delete an alert (tenant-aware)"""
    query = {"id": alert_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    result = await db.alerts.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert deleted"}


@router.post("/{alert_id}/notify")
async def send_notification(alert_id: str, request: SendAlertNotificationRequest, current_user: dict = Depends(require_write_access)):
    """Send notification for an alert (tenant-aware)"""
    query = {"id": alert_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    alert = await db.alerts.find_one(query, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    channel = request.channel.lower()
    success = False
    
    if channel == "email":
        recipient = request.recipient or current_user.get("email")
        if recipient:
            success = await send_alert_email(
                recipient=recipient,
                subject=f"[{alert['severity'].upper()}] {alert['title']}",
                alert_data=alert
            )
    elif channel == "teams":
        import os
        webhook_url = request.recipient or os.environ.get("TEAMS_WEBHOOK_URL")
        if webhook_url:
            success = await send_teams_notification(webhook_url, alert)
    
    if success:
        return {"message": f"Notification sent via {channel}"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to send notification via {channel}")


@router.get("/stats/summary")
async def get_alert_stats(current_user: Optional[dict] = Depends(get_current_user)):
    """Get alert statistics (tenant-aware)"""
    query = {}
    if current_user and current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    total = await db.alerts.count_documents(query)
    open_alerts = await db.alerts.count_documents({**query, "status": "open"})
    acknowledged = await db.alerts.count_documents({**query, "status": "acknowledged"})
    resolved = await db.alerts.count_documents({**query, "status": "resolved"})
    
    # By severity
    critical = await db.alerts.count_documents({**query, "severity": "critical"})
    warning = await db.alerts.count_documents({**query, "severity": "warning"})
    info = await db.alerts.count_documents({**query, "severity": "info"})
    
    return {
        "total": total,
        "open": open_alerts,
        "acknowledged": acknowledged,
        "resolved": resolved,
        "by_severity": {
            "critical": critical,
            "warning": warning,
            "info": info
        }
    }
