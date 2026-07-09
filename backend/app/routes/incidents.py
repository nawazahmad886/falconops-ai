"""
FalconOps AI - Incident Routes
Incident management and AI analysis with full multi-tenancy support
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query

from ..core.database import db
from ..models.schemas import IncidentResponse, AIAnalysisRequest
from ..utils.auth import require_auth, require_write_access, get_current_user, build_tenant_query
from ..services.websocket_manager import ws_manager
from ..services.ai_crew_service import get_aiops_service
from ..services.ai_correlation import run_correlation_cycle, get_correlation_stats, correlate_alerts as smart_correlate

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


# Static routes must come BEFORE dynamic routes with path parameters
@router.get("/correlation-stats")
async def get_correlation_statistics(current_user: dict = Depends(require_auth)):
    """Get correlation engine statistics (tenant-aware)"""
    tenant_id = current_user.get("tenant_id")
    stats = await get_correlation_stats(tenant_id)
    return stats


@router.post("/correlate")
async def correlate_alerts_endpoint(
    use_smart_correlation: bool = Query(True, description="Use AI-powered smart correlation"),
    time_window_minutes: int = Query(15, description="Time window for correlation"),
    current_user: dict = Depends(require_write_access)
):
    """Correlate open alerts into incidents using smart AI correlation (tenant-aware)"""
    tenant_id = current_user.get("tenant_id")
    
    if use_smart_correlation:
        # Use the AI correlation engine
        try:
            incidents = await smart_correlate(time_window_minutes, tenant_id)
            return {
                "message": f"Smart correlation complete. Created {len(incidents)} incidents",
                "incidents_created": len(incidents),
                "incidents": incidents,
                "correlation_type": "smart_rule_based"
            }
        except Exception as e:
            # Fallback to simple correlation
            pass
    
    # Simple correlation by service (fallback)
    query = {"status": "open", "incident_id": None}
    if tenant_id:
        query["tenant_id"] = tenant_id
        
    open_alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    
    if not open_alerts:
        return {"message": "No open alerts to correlate", "incidents_created": 0}
    
    service_groups = {}
    for alert in open_alerts:
        service = alert.get("service", "unknown")
        if service not in service_groups:
            service_groups[service] = []
        service_groups[service].append(alert)
    
    incidents_created = 0
    created_incidents = []
    
    for service, alerts in service_groups.items():
        if len(alerts) == 0:
            continue
        
        severities = [a.get("severity", "info") for a in alerts]
        severity_priority = {"critical": 0, "warning": 1, "info": 2}
        highest_severity = min(severities, key=lambda s: severity_priority.get(s, 3))
        
        incident_id = str(uuid.uuid4())
        incident_doc = {
            "id": incident_id,
            "tenant_id": tenant_id,  # Multi-tenancy support
            "title": f"Incident in {service} - {len(alerts)} related alerts",
            "severity": highest_severity,
            "status": "open",
            "service": service,
            "alert_count": len(alerts),
            "alert_ids": [a["id"] for a in alerts],
            "ai_analysis": None,
            "root_cause": None,
            "suggested_actions": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
            "mttr_seconds": None
        }
        
        await db.incidents.insert_one(incident_doc)
        
        for alert in alerts:
            await db.alerts.update_one(
                {"id": alert["id"]},
                {"$set": {"incident_id": incident_id}}
            )
        
        incidents_created += 1
        created_incidents.append({k: v for k, v in incident_doc.items() if k != "_id"})
        
        await ws_manager.broadcast({
            "type": "new_incident",
            "data": {k: v for k, v in incident_doc.items() if k != "_id"}
        })
    
    return {
        "message": f"Created {incidents_created} incidents",
        "incidents_created": incidents_created,
        "incidents": created_incidents,
        "correlation_type": "simple_service_grouping"
    }


@router.post("/smart-correlate")
async def smart_correlate_endpoint(
    time_window_minutes: int = Query(15, description="Time window for correlation"),
    current_user: dict = Depends(require_write_access)
):
    """Run smart AI-powered correlation engine (tenant-aware)"""
    tenant_id = current_user.get("tenant_id")
    result = await run_correlation_cycle(tenant_id)
    return result


@router.get("", response_model=List[IncidentResponse])
async def get_incidents(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get all incidents with optional filters (tenant-aware)"""
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    
    # Apply tenant filter
    if current_user and current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    incidents = await db.incidents.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    return [IncidentResponse(**i) for i in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, current_user: Optional[dict] = Depends(get_current_user)):
    """Get single incident by ID (tenant-aware)"""
    query = {"id": incident_id}
    if current_user and current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    incident = await db.incidents.find_one(query, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse(**incident)


@router.post("/{incident_id}/analyze")
async def analyze_incident(incident_id: str, current_user: dict = Depends(require_auth)):
    """Trigger AI analysis for an incident (tenant-aware)"""
    query = {"id": incident_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    incident = await db.incidents.find_one(query, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    alert_ids = incident.get("alert_ids", [])
    alerts = await db.alerts.find({"id": {"$in": alert_ids}}, {"_id": 0}).to_list(100)
    
    aiops = get_aiops_service()
    analysis = await aiops.analyze_incident(incident, alerts)
    
    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {
            "ai_analysis": analysis,
            "root_cause": analysis.get("root_cause"),
            "suggested_actions": analysis.get("suggested_actions", []),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    updated = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    await ws_manager.broadcast({"type": "incident_analyzed", "data": updated})
    
    return {"message": "Analysis complete", "analysis": analysis}


@router.patch("/{incident_id}/resolve")
async def resolve_incident(incident_id: str, current_user: dict = Depends(require_write_access)):
    """Resolve an incident (tenant-aware)"""
    query = {"id": incident_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    incident = await db.incidents.find_one(query)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    now = datetime.now(timezone.utc)
    created_at = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
    mttr_seconds = int((now - created_at).total_seconds())
    
    await db.incidents.update_one(
        {"id": incident_id},
        {"$set": {
            "status": "resolved",
            "resolved_at": now.isoformat(),
            "mttr_seconds": mttr_seconds,
            "updated_at": now.isoformat()
        }}
    )
    
    for alert_id in incident.get("alert_ids", []):
        await db.alerts.update_one(
            {"id": alert_id},
            {"$set": {"status": "resolved", "resolved_at": now.isoformat()}}
        )
    
    updated = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    await ws_manager.broadcast({"type": "incident_resolved", "data": updated})
    
    return {"message": "Incident resolved", "incident": updated, "mttr_seconds": mttr_seconds}


@router.patch("/{incident_id}/status")
async def update_incident_status(incident_id: str, status: str = Query(...), current_user: dict = Depends(require_write_access)):
    """Update incident status (tenant-aware)"""
    valid_statuses = ["open", "investigating", "identified", "monitoring", "resolved"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    query = {"id": incident_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    incident = await db.incidents.find_one(query)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    update_data = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if status == "resolved":
        created_at = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        update_data["resolved_at"] = now.isoformat()
        update_data["mttr_seconds"] = int((now - created_at).total_seconds())
    
    await db.incidents.update_one({"id": incident_id}, {"$set": update_data})
    
    updated = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    await ws_manager.broadcast({"type": "incident_updated", "data": updated})
    
    return {"message": f"Incident status updated to {status}", "incident": updated}


@router.delete("/{incident_id}")
async def delete_incident(incident_id: str, current_user: dict = Depends(require_write_access)):
    """Delete an incident (tenant-aware)"""
    query = {"id": incident_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
        
    result = await db.incidents.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"message": "Incident deleted"}


@router.get("/stats/summary")
async def get_incident_stats(current_user: Optional[dict] = Depends(get_current_user)):
    """Get incident statistics (tenant-aware)"""
    query = {}
    if current_user and current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    total = await db.incidents.count_documents(query)
    open_incidents = await db.incidents.count_documents({**query, "status": "open"})
    investigating = await db.incidents.count_documents({**query, "status": "investigating"})
    resolved = await db.incidents.count_documents({**query, "status": "resolved"})
    
    # Calculate average MTTR
    resolved_incidents = await db.incidents.find(
        {**query, "status": "resolved", "mttr_seconds": {"$exists": True}},
        {"mttr_seconds": 1, "_id": 0}
    ).to_list(1000)
    
    avg_mttr = 0
    if resolved_incidents:
        total_mttr = sum(i.get("mttr_seconds", 0) for i in resolved_incidents)
        avg_mttr = total_mttr / len(resolved_incidents)
    
    return {
        "total": total,
        "open": open_incidents,
        "investigating": investigating,
        "resolved": resolved,
        "avg_mttr_seconds": int(avg_mttr),
        "avg_mttr_formatted": f"{int(avg_mttr // 3600)}h {int((avg_mttr % 3600) // 60)}m"
    }
