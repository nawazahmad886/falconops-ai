"""
FalconOps AI - Analytics Routes
Dashboard analytics and metrics
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..core.database import db
from ..models.schemas import AnalyticsResponse
from ..utils.auth import get_current_user

router = APIRouter(prefix="/api", tags=["Analytics"])


def _tid(user):
    return user.get("tenant_id") if user else None


# Services endpoint for dashboard service health
@router.get("/services")
async def get_services_health(current_user: Optional[dict] = Depends(get_current_user)):
    """Get service health summary from alerts"""
    tid = _tid(current_user)
    q = {"status": "open"}
    if tid:
        q["tenant_id"] = tid
    alerts = await db.alerts.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    service_counts = {}
    for alert in alerts:
        service = alert.get("service", "Unknown")
        if service not in service_counts:
            service_counts[service] = {"critical": 0, "warning": 0, "info": 0, "total": 0}
        severity = alert.get("severity", "info")
        service_counts[service][severity] = service_counts[service].get(severity, 0) + 1
        service_counts[service]["total"] += 1
    
    services = []
    for service_name, counts in service_counts.items():
        if counts["critical"] > 0:
            health = "critical"
        elif counts["warning"] > 0:
            health = "warning"
        else:
            health = "healthy"
        
        services.append({
            "name": service_name,
            "health": health,
            "open_alerts": counts["total"],
            "critical_alerts": counts["critical"],
            "warning_alerts": counts["warning"]
        })
    
    return sorted(services, key=lambda x: (0 if x["health"] == "critical" else 1 if x["health"] == "warning" else 2, -x["open_alerts"]))


@router.get("/analytics/dashboard")
async def get_dashboard_analytics(
    days: int = Query(7, ge=1, le=90),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get dashboard analytics data - main dashboard endpoint"""
    return await get_analytics(days=days, current_user=current_user)


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(7, ge=1, le=90),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get comprehensive analytics dashboard data"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    tid = _tid(current_user)
    tq = {"tenant_id": tid} if tid else {}
    
    # Alerts statistics
    all_alerts = await db.alerts.find({**tq, "created_at": {"$gte": since}}, {"_id": 0, "status": 1, "severity": 1, "service": 1, "created_at": 1}).to_list(5000)
    recent_alerts = all_alerts
    
    total_alerts = len(recent_alerts)
    open_alerts = sum(1 for a in recent_alerts if a.get("status") == "open")
    resolved_alerts = sum(1 for a in recent_alerts if a.get("status") == "resolved")
    
    severity_counts = {}
    service_counts = {}
    for alert in recent_alerts:
        sev = alert.get("severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        svc = alert.get("service", "unknown")
        service_counts[svc] = service_counts.get(svc, 0) + 1
    
    # Incidents statistics
    all_incidents = await db.incidents.find({**tq, "created_at": {"$gte": since}}, {"_id": 0, "status": 1, "created_at": 1, "mttr_seconds": 1}).to_list(2000)
    recent_incidents = all_incidents
    
    total_incidents = len(recent_incidents)
    open_incidents = sum(1 for i in recent_incidents if i.get("status") != "resolved")
    
    # MTTR calculation
    resolved = [i for i in recent_incidents if i.get("mttr_seconds")]
    avg_mttr = sum(i["mttr_seconds"] for i in resolved) / len(resolved) if resolved else 0
    
    # Incidents trend (by day)
    incidents_trend = []
    for i in range(days):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        count = sum(1 for inc in recent_incidents if inc.get("created_at", "")[:10] == day)
        incidents_trend.append({"date": day, "count": count})
    incidents_trend.reverse()
    
    # SLA compliance
    await db.monitors.find({"enabled": True, **tq}, {"_id": 0}).to_list(500)
    results = await db.monitor_results.find({"created_at": {"$gte": since}, **tq}, {"_id": 0, "status": 1}).to_list(10000)
    
    up_count = sum(1 for r in results if r.get("status") == "up")
    sla_compliance = round((up_count / len(results)) * 100, 2) if results else 100
    
    return AnalyticsResponse(
        total_alerts=total_alerts,
        open_alerts=open_alerts,
        resolved_alerts=resolved_alerts,
        total_incidents=total_incidents,
        open_incidents=open_incidents,
        avg_mttr_seconds=round(avg_mttr, 2),
        alerts_by_severity=severity_counts,
        alerts_by_service=service_counts,
        incidents_trend=incidents_trend,
        sla_compliance=sla_compliance
    )


@router.get("/analytics/summary")
async def get_quick_summary(current_user: Optional[dict] = Depends(get_current_user)):
    """Get quick summary for dashboard cards"""
    tid = _tid(current_user)
    tq = {"tenant_id": tid} if tid else {}
    # Count documents
    alerts_count = await db.alerts.count_documents({"status": "open", **tq})
    incidents_count = await db.incidents.count_documents({"status": {"$ne": "resolved"}, **tq})
    monitors_count = await db.monitors.count_documents({"enabled": True, **tq})
    
    # Get recent critical alerts
    critical = await db.alerts.find(
        {"severity": "critical", "status": "open", **tq}, {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    return {
        "open_alerts": alerts_count,
        "open_incidents": incidents_count,
        "active_monitors": monitors_count,
        "recent_critical": [{"id": a["id"], "title": a["title"], "service": a["service"]} for a in critical]
    }
