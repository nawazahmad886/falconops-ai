"""
FalconOps AI - Alert Ingestion Routes
Real-time alert ingestion via webhooks and API
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel, Field

from ..core.database import db
from ..utils.auth import require_auth, require_admin
from ..services.knowledge_base_service import knowledge_base
from ..services.event_analyzer_service import EventAnalyzer

router = APIRouter(prefix="/api/ingest", tags=["Alert Ingestion"])


# ======================== SCHEMAS ========================

class AlertPayload(BaseModel):
    """Single alert payload from monitoring tools"""
    service: str = Field(..., description="Service or application name")
    alert: str = Field(..., description="Alert name or message")
    severity: str = Field("warning", description="Alert severity: critical, warning, info")
    timestamp: Optional[str] = None
    host: Optional[str] = None
    source: Optional[str] = None  # e.g., "prometheus", "appdynamics", "elasticsearch"
    tags: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class BatchAlertPayload(BaseModel):
    """Batch alert payload"""
    alerts: List[AlertPayload]
    source: Optional[str] = None


class WebhookConfig(BaseModel):
    """Webhook configuration"""
    name: str
    source_type: str  # prometheus, appdynamics, elasticsearch, grafana, custom
    enabled: bool = True
    auto_analyze: bool = True
    analyze_threshold: int = 10  # Auto-analyze after N alerts


class IncidentResolution(BaseModel):
    """Resolution feedback for learning"""
    incident_id: str
    root_cause: str
    resolution: str
    resolution_time_minutes: Optional[int] = None
    helpful: bool = True
    notes: Optional[str] = None


# ======================== WEBHOOK ENDPOINTS ========================

@router.post("/webhook/{webhook_id}")
async def receive_webhook_alert(
    webhook_id: str,
    payload: AlertPayload,
    background_tasks: BackgroundTasks
):
    """
    Receive alert from monitoring tool webhook.
    No authentication required - uses webhook_id for identification.
    """
    # Verify webhook exists and is enabled
    webhook = await db.webhooks.find_one({"id": webhook_id, "enabled": True}, {"_id": 0})
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found or disabled")
    
    # Normalize and store alert
    alert_record = {
        "id": str(uuid.uuid4()),
        "webhook_id": webhook_id,
        "source": payload.source or webhook.get("source_type", "unknown"),
        "service": payload.service,
        "alert": payload.alert,
        "severity": payload.severity.lower(),
        "timestamp": payload.timestamp or datetime.now(timezone.utc).isoformat(),
        "host": payload.host,
        "tags": payload.tags or {},
        "metadata": payload.metadata or {},
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "analyzed": False
    }
    
    await db.ingested_alerts.insert_one(alert_record)
    
    # Update webhook stats
    await db.webhooks.update_one(
        {"id": webhook_id},
        {
            "$inc": {"alert_count": 1},
            "$set": {"last_alert_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    # Check if auto-analyze threshold reached
    if webhook.get("auto_analyze"):
        unanalyzed_count = await db.ingested_alerts.count_documents({
            "webhook_id": webhook_id,
            "analyzed": False
        })
        
        if unanalyzed_count >= webhook.get("analyze_threshold", 10):
            background_tasks.add_task(auto_analyze_alerts, webhook_id)
    
    # Check knowledge base for instant suggestion
    kb_match = await knowledge_base.get_instant_suggestion(
        [payload.alert],
        [payload.service] if payload.service else None
    )
    
    response = {
        "success": True,
        "alert_id": alert_record["id"],
        "message": "Alert received"
    }
    
    if kb_match and kb_match.get("found"):
        response["instant_suggestion"] = {
            "root_cause": kb_match.get("root_cause"),
            "resolution": kb_match.get("resolution"),
            "confidence": kb_match.get("confidence")
        }
    
    return response


@router.post("/webhook/{webhook_id}/batch")
async def receive_batch_alerts(
    webhook_id: str,
    payload: BatchAlertPayload,
    background_tasks: BackgroundTasks
):
    """Receive batch of alerts from monitoring tool"""
    webhook = await db.webhooks.find_one({"id": webhook_id, "enabled": True}, {"_id": 0})
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found or disabled")
    
    received_count = 0
    
    for alert in payload.alerts:
        alert_record = {
            "id": str(uuid.uuid4()),
            "webhook_id": webhook_id,
            "source": alert.source or payload.source or webhook.get("source_type", "unknown"),
            "service": alert.service,
            "alert": alert.alert,
            "severity": alert.severity.lower(),
            "timestamp": alert.timestamp or datetime.now(timezone.utc).isoformat(),
            "host": alert.host,
            "tags": alert.tags or {},
            "metadata": alert.metadata or {},
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "analyzed": False
        }
        
        await db.ingested_alerts.insert_one(alert_record)
        received_count += 1
    
    # Update webhook stats
    await db.webhooks.update_one(
        {"id": webhook_id},
        {
            "$inc": {"alert_count": received_count},
            "$set": {"last_alert_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    # Auto-analyze if threshold reached
    if webhook.get("auto_analyze"):
        background_tasks.add_task(auto_analyze_alerts, webhook_id)
    
    return {
        "success": True,
        "received": received_count,
        "message": f"Received {received_count} alerts"
    }


async def auto_analyze_alerts(webhook_id: str):
    """Background task to auto-analyze accumulated alerts"""
    try:
        # Get unanalyzed alerts
        alerts = await db.ingested_alerts.find({
            "webhook_id": webhook_id,
            "analyzed": False
        }, {"_id": 0}).to_list(length=1000)
        
        if not alerts:
            return
        
        # Convert to analyzer format
        analyzer = EventAnalyzer()
        analyzer.events = [
            {
                "timestamp": a.get("timestamp"),
                "service": a.get("service"),
                "alert": a.get("alert"),
                "severity": a.get("severity"),
                "host": a.get("host")
            }
            for a in alerts
        ]
        
        # Run analysis
        result = await analyzer.ai_analyze()
        
        # Store analysis
        analysis_record = {
            "id": result.get("analysis_id"),
            "webhook_id": webhook_id,
            "alert_count": len(alerts),
            "result": result,
            "auto_generated": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.auto_analyses.insert_one(analysis_record)
        
        # Mark alerts as analyzed
        alert_ids = [a["id"] for a in alerts]
        await db.ingested_alerts.update_many(
            {"id": {"$in": alert_ids}},
            {"$set": {"analyzed": True, "analysis_id": result.get("analysis_id")}}
        )
        
    except Exception as e:
        print(f"Auto-analysis error: {e}")


# ======================== DIRECT ALERT INGESTION ========================

@router.post("/alert")
async def ingest_single_alert(
    payload: AlertPayload,
    user: dict = Depends(require_auth)
):
    """Ingest a single alert (authenticated)"""
    
    alert_record = {
        "id": str(uuid.uuid4()),
        "user_id": user.get("id"),
        "source": payload.source or "api",
        "service": payload.service,
        "alert": payload.alert,
        "severity": payload.severity.lower(),
        "timestamp": payload.timestamp or datetime.now(timezone.utc).isoformat(),
        "host": payload.host,
        "tags": payload.tags or {},
        "metadata": payload.metadata or {},
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "analyzed": False
    }
    
    await db.ingested_alerts.insert_one(alert_record)
    
    # Check knowledge base
    kb_match = await knowledge_base.get_instant_suggestion(
        [payload.alert],
        [payload.service] if payload.service else None
    )
    
    response = {
        "success": True,
        "alert_id": alert_record["id"]
    }
    
    if kb_match and kb_match.get("found"):
        response["instant_suggestion"] = kb_match
    
    return response


@router.post("/alerts/batch")
async def ingest_batch_alerts(
    payload: BatchAlertPayload,
    user: dict = Depends(require_auth)
):
    """Ingest batch of alerts (authenticated)"""
    
    received = 0
    for alert in payload.alerts:
        alert_record = {
            "id": str(uuid.uuid4()),
            "user_id": user.get("id"),
            "source": alert.source or payload.source or "api",
            "service": alert.service,
            "alert": alert.alert,
            "severity": alert.severity.lower(),
            "timestamp": alert.timestamp or datetime.now(timezone.utc).isoformat(),
            "host": alert.host,
            "tags": alert.tags or {},
            "metadata": alert.metadata or {},
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "analyzed": False
        }
        await db.ingested_alerts.insert_one(alert_record)
        received += 1
    
    return {"success": True, "received": received}


# ======================== WEBHOOK MANAGEMENT ========================

@router.post("/webhooks")
async def create_webhook(
    config: WebhookConfig,
    user: dict = Depends(require_admin)
):
    """Create a new webhook endpoint"""
    
    webhook_id = str(uuid.uuid4())[:12]
    
    webhook_record = {
        "id": webhook_id,
        "name": config.name,
        "source_type": config.source_type,
        "enabled": config.enabled,
        "auto_analyze": config.auto_analyze,
        "analyze_threshold": config.analyze_threshold,
        "alert_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("id"),
        "last_alert_at": None
    }
    
    await db.webhooks.insert_one(webhook_record)
    
    return {
        "success": True,
        "webhook_id": webhook_id,
        "webhook_url": f"/api/ingest/webhook/{webhook_id}",
        "name": config.name
    }


@router.get("/webhooks")
async def list_webhooks(user: dict = Depends(require_auth)):
    """List all webhooks"""
    
    webhooks = await db.webhooks.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).to_list(length=100)
    
    return {"webhooks": webhooks}


@router.get("/webhooks/{webhook_id}")
async def get_webhook(webhook_id: str, user: dict = Depends(require_auth)):
    """Get webhook details"""
    
    webhook = await db.webhooks.find_one({"id": webhook_id}, {"_id": 0})
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return webhook


@router.put("/webhooks/{webhook_id}")
async def update_webhook(
    webhook_id: str,
    config: WebhookConfig,
    user: dict = Depends(require_admin)
):
    """Update webhook configuration"""
    
    result = await db.webhooks.update_one(
        {"id": webhook_id},
        {"$set": {
            "name": config.name,
            "source_type": config.source_type,
            "enabled": config.enabled,
            "auto_analyze": config.auto_analyze,
            "analyze_threshold": config.analyze_threshold,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {"success": True}


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, user: dict = Depends(require_admin)):
    """Delete a webhook"""
    
    result = await db.webhooks.delete_one({"id": webhook_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {"success": True}


# ======================== INGESTED ALERTS MANAGEMENT ========================

@router.get("/alerts")
async def list_ingested_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    source: Optional[str] = None,
    service: Optional[str] = None,
    severity: Optional[str] = None,
    analyzed: Optional[bool] = None,
    user: dict = Depends(require_auth)
):
    """List ingested alerts with filtering"""
    
    query = {}
    if source:
        query["source"] = source
    if service:
        query["service"] = service
    if severity:
        query["severity"] = severity.lower()
    if analyzed is not None:
        query["analyzed"] = analyzed
    
    alerts = await db.ingested_alerts.find(
        query,
        {"_id": 0}
    ).sort("ingested_at", -1).skip(skip).limit(limit).to_list(length=limit)
    
    total = await db.ingested_alerts.count_documents(query)
    
    return {
        "alerts": alerts,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/alerts/analyze")
async def analyze_ingested_alerts(
    alert_ids: Optional[List[str]] = None,
    webhook_id: Optional[str] = None,
    time_range_hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(require_auth)
):
    """Analyze ingested alerts"""
    
    query = {}
    
    if alert_ids:
        query["id"] = {"$in": alert_ids}
    elif webhook_id:
        query["webhook_id"] = webhook_id
        query["analyzed"] = False
    else:
        # Default: unanalyzed alerts from last N hours
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)
        query["ingested_at"] = {"$gte": cutoff.isoformat()}
        query["analyzed"] = False
    
    alerts = await db.ingested_alerts.find(
        query,
        {"_id": 0}
    ).to_list(length=1000)
    
    if not alerts:
        return {"success": False, "message": "No alerts found to analyze"}
    
    # Convert and analyze
    analyzer = EventAnalyzer()
    analyzer.events = [
        {
            "timestamp": a.get("timestamp"),
            "service": a.get("service"),
            "alert": a.get("alert"),
            "severity": a.get("severity"),
            "host": a.get("host")
        }
        for a in alerts
    ]
    
    result = await analyzer.ai_analyze()
    
    # Store analysis
    analysis_record = {
        "id": result.get("analysis_id"),
        "user_id": user.get("id"),
        "alert_count": len(alerts),
        "result": result,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.auto_analyses.insert_one(analysis_record)
    
    # Mark alerts as analyzed
    alert_ids_to_update = [a["id"] for a in alerts]
    await db.ingested_alerts.update_many(
        {"id": {"$in": alert_ids_to_update}},
        {"$set": {"analyzed": True, "analysis_id": result.get("analysis_id")}}
    )
    
    return result


# ======================== KNOWLEDGE BASE & LEARNING ========================

@router.post("/learn")
async def learn_from_resolution(
    resolution: IncidentResolution,
    user: dict = Depends(require_auth)
):
    """
    Record incident resolution for AI learning.
    This improves future suggestions.
    """
    
    # Get the analysis/incident
    analysis = await db.auto_analyses.find_one(
        {"id": resolution.incident_id},
        {"_id": 0}
    )
    
    if not analysis:
        analysis = await db.event_analyses.find_one(
            {"id": resolution.incident_id},
            {"_id": 0}
        )
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Extract alerts from analysis
    result = analysis.get("result", {})
    patterns = result.get("patterns", {})
    
    alerts = [item["alert"] for item in patterns.get("alert_frequency", [])[:10]]
    services = [item["service"] for item in patterns.get("service_frequency", [])[:5]]
    
    if not alerts:
        raise HTTPException(status_code=400, detail="No alerts found in analysis")
    
    # Store in knowledge base
    kb_result = await knowledge_base.store_incident(
        alerts=alerts,
        services=services,
        root_cause=resolution.root_cause,
        resolution=resolution.resolution,
        user_id=user.get("id"),
        severity=result.get("summary", {}).get("status", "warning")
    )
    
    # Record feedback if pattern existed
    if kb_result.get("updated") and resolution.helpful is not None:
        pattern = await db.incident_knowledge.find_one(
            {"pattern_hash": kb_result.get("pattern_hash")},
            {"_id": 0}
        )
        if pattern:
            await knowledge_base.record_feedback(
                pattern_id=pattern["id"],
                helpful=resolution.helpful,
                user_id=user.get("id"),
                resolution_time_minutes=resolution.resolution_time_minutes,
                feedback_notes=resolution.notes
            )
    
    return {
        "success": True,
        "message": "Resolution recorded for AI learning",
        **kb_result
    }


@router.get("/knowledge/stats")
async def get_knowledge_stats(user: dict = Depends(require_auth)):
    """Get knowledge base statistics"""
    return await knowledge_base.get_knowledge_stats()


@router.get("/knowledge/patterns")
async def list_knowledge_patterns(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_auth)
):
    """List learned patterns from knowledge base"""
    
    patterns = await db.incident_knowledge.find(
        {},
        {"_id": 0}
    ).sort("occurrence_count", -1).skip(skip).limit(limit).to_list(length=limit)
    
    total = await db.incident_knowledge.count_documents({})
    
    return {
        "patterns": patterns,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.delete("/knowledge/patterns/{pattern_id}")
async def delete_knowledge_pattern(pattern_id: str, user: dict = Depends(require_admin)):
    """Delete a knowledge base pattern"""
    
    result = await db.incident_knowledge.delete_one({"id": pattern_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    return {"success": True}


# ======================== INGESTION STATS ========================

@router.get("/stats")
async def get_ingestion_stats(user: dict = Depends(require_auth)):
    """Get alert ingestion statistics"""
    
    total_alerts = await db.ingested_alerts.count_documents({})
    unanalyzed = await db.ingested_alerts.count_documents({"analyzed": False})
    analyzed = total_alerts - unanalyzed
    
    # Get by source
    pipeline = [
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    by_source = await db.ingested_alerts.aggregate(pipeline).to_list(length=10)
    
    # Get by severity
    pipeline = [
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
    ]
    by_severity = await db.ingested_alerts.aggregate(pipeline).to_list(length=10)
    
    # Webhook stats
    webhooks = await db.webhooks.find({}, {"_id": 0, "id": 1, "name": 1, "alert_count": 1, "enabled": 1}).to_list(length=100)
    
    return {
        "total_alerts": total_alerts,
        "analyzed": analyzed,
        "unanalyzed": unanalyzed,
        "by_source": [{"source": s["_id"], "count": s["count"]} for s in by_source],
        "by_severity": {s["_id"]: s["count"] for s in by_severity},
        "webhooks": webhooks
    }
