"""
FalconOps AI - Monitoring Routes
Monitor CRUD, results, and dashboard
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query

from ..core.database import db
from ..models.schemas import (
    MonitorCreate, MonitorResponse, MonitorResultResponse, 
    MonitoringDashboardResponse, SyntheticMonitorCreate, TracerouteResponse
)
from ..utils.auth import require_auth, require_write_access, get_current_user
from ..services.monitoring_service import run_monitor_check, is_monitoring_running

router = APIRouter(prefix="/api/monitors", tags=["Monitoring"])


def _tid(user):
    return user.get("tenant_id") if user else None


@router.get("/dashboard", response_model=MonitoringDashboardResponse)
async def get_monitoring_dashboard(current_user: Optional[dict] = Depends(get_current_user)):
    """Get comprehensive monitoring dashboard data"""
    tid = _tid(current_user)
    base_q = {"enabled": True}
    if tid:
        base_q["tenant_id"] = tid
    monitors = await db.monitors.find(base_q, {"_id": 0}).to_list(500)
    
    total = len(monitors)
    up = sum(1 for m in monitors if m.get("status") == "up")
    down = sum(1 for m in monitors if m.get("status") in ["down", "timeout"])
    degraded = sum(1 for m in monitors if m.get("status") == "degraded")
    
    latencies = [m.get("last_latency_ms") for m in monitors if m.get("last_latency_ms")]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0
    
    type_counts = {}
    env_counts = {}
    for m in monitors:
        t = m.get("monitor_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        e = m.get("environment", "production")
        env_counts[e] = env_counts.get(e, 0) + 1
    
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    results = await db.monitor_results.find(
        {"created_at": {"$gte": since}, **({"tenant_id": tid} if tid else {})}, {"_id": 0}
    ).to_list(10000)
    
    up_results = sum(1 for r in results if r.get("status") == "up")
    overall_uptime = round((up_results / len(results)) * 100, 2) if results else 100
    
    sla_met = sum(1 for m in monitors if m.get("status") == "up")
    sla_compliance = round((sla_met / total) * 100, 2) if total > 0 else 100
    
    incidents = await db.incidents.find(
        {"status": {"$ne": "resolved"}, "created_at": {"$gte": since}, **({"tenant_id": tid} if tid else {})}, {"_id": 0}
    ).sort("created_at", -1).to_list(10)
    
    return MonitoringDashboardResponse(
        total_monitors=total,
        monitors_up=up,
        monitors_down=down,
        monitors_degraded=degraded,
        overall_uptime_percent=overall_uptime,
        avg_latency_ms=avg_latency,
        sla_compliance_percent=sla_compliance,
        active_outages=down,
        monitors_by_type=type_counts,
        monitors_by_environment=env_counts,
        recent_incidents=[{"id": i["id"], "title": i["title"], "severity": i["severity"]} for i in incidents],
        latency_trend=[]
    )


@router.get("", response_model=List[MonitorResponse])
async def get_monitors(
    environment: Optional[str] = Query(None),
    monitor_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get all monitors with optional filters"""
    query = {}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    if environment:
        query["environment"] = environment
    if monitor_type:
        query["monitor_type"] = monitor_type
    if status:
        query["status"] = status
    if enabled is not None:
        query["enabled"] = enabled
    
    monitors = await db.monitors.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [MonitorResponse(**m) for m in monitors]


@router.post("", response_model=MonitorResponse)
async def create_monitor(monitor: MonitorCreate, current_user: dict = Depends(require_write_access)):
    """Create a new monitor"""
    monitor_id = str(uuid.uuid4())
    monitor_doc = {
        "id": monitor_id,
        "name": monitor.name,
        "target": monitor.target,
        "monitor_type": monitor.monitor_type,
        "interval_seconds": monitor.interval_seconds,
        "timeout_seconds": monitor.timeout_seconds,
        "port": monitor.port,
        "expected_status_code": monitor.expected_status_code,
        "environment": monitor.environment,
        "sla_uptime_percent": monitor.sla_uptime_percent,
        "sla_max_latency_ms": monitor.sla_max_latency_ms,
        "tags": monitor.tags or {},
        "enabled": monitor.enabled,
        "notification_email": monitor.notification_email,
        "status": "pending",
        "last_check": None,
        "last_latency_ms": None,
        "uptime_percent_24h": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"],
        "tenant_id": current_user.get("tenant_id")
    }
    
    await db.monitors.insert_one(monitor_doc)
    return MonitorResponse(**monitor_doc)


@router.get("/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(monitor_id: str, current_user: Optional[dict] = Depends(get_current_user)):
    """Get single monitor by ID"""
    monitor = await db.monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return MonitorResponse(**monitor)


@router.put("/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(monitor_id: str, monitor: MonitorCreate, current_user: dict = Depends(require_write_access)):
    """Update a monitor"""
    existing = await db.monitors.find_one({"id": monitor_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    update_data = {
        "name": monitor.name,
        "target": monitor.target,
        "monitor_type": monitor.monitor_type,
        "interval_seconds": monitor.interval_seconds,
        "timeout_seconds": monitor.timeout_seconds,
        "port": monitor.port,
        "expected_status_code": monitor.expected_status_code,
        "environment": monitor.environment,
        "sla_uptime_percent": monitor.sla_uptime_percent,
        "sla_max_latency_ms": monitor.sla_max_latency_ms,
        "tags": monitor.tags or {},
        "enabled": monitor.enabled,
        "notification_email": monitor.notification_email,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.monitors.update_one({"id": monitor_id}, {"$set": update_data})
    updated = await db.monitors.find_one({"id": monitor_id}, {"_id": 0})
    return MonitorResponse(**updated)


@router.delete("/{monitor_id}")
async def delete_monitor(monitor_id: str, current_user: dict = Depends(require_write_access)):
    """Delete a monitor"""
    result = await db.monitors.delete_one({"id": monitor_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    await db.monitor_results.delete_many({"monitor_id": monitor_id})
    
    return {"message": "Monitor deleted successfully"}


@router.post("/{monitor_id}/check")
async def trigger_check(monitor_id: str, current_user: dict = Depends(require_auth)):
    """Manually trigger a monitor check"""
    monitor = await db.monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    result = await run_monitor_check(monitor)
    
    result_doc = {
        "id": str(uuid.uuid4()),
        "monitor_id": monitor_id,
        "status": result["status"],
        "latency_ms": result.get("latency_ms"),
        "status_code": result.get("status_code"),
        "packet_loss": result.get("packet_loss"),
        "error_message": result.get("error_message"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.monitor_results.insert_one(result_doc)
    
    await db.monitors.update_one(
        {"id": monitor_id},
        {"$set": {
            "status": result["status"],
            "last_check": datetime.now(timezone.utc).isoformat(),
            "last_latency_ms": result.get("latency_ms")
        }}
    )
    
    return {"message": "Check completed", "result": result}


@router.get("/{monitor_id}/results", response_model=List[MonitorResultResponse])
async def get_monitor_results(
    monitor_id: str,
    hours: int = Query(24, ge=1, le=168),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get monitor check results for the specified period"""
    monitor = await db.monitors.find_one({"id": monitor_id})
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    results = await db.monitor_results.find(
        {"monitor_id": monitor_id, "created_at": {"$gte": since}}, {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    return [MonitorResultResponse(**r) for r in results]


@router.get("/{monitor_id}/uptime")
async def get_monitor_uptime(
    monitor_id: str,
    days: int = Query(7, ge=1, le=90),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get uptime statistics for a monitor"""
    monitor = await db.monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    results = await db.monitor_results.find(
        {"monitor_id": monitor_id, "created_at": {"$gte": since}}, {"_id": 0}
    ).to_list(50000)
    
    if not results:
        return {"uptime_percent": 100, "total_checks": 0, "up_checks": 0, "down_checks": 0}
    
    up = sum(1 for r in results if r.get("status") == "up")
    down = sum(1 for r in results if r.get("status") in ["down", "timeout"])
    uptime = round((up / len(results)) * 100, 4)
    
    latencies = [r.get("latency_ms") for r in results if r.get("latency_ms")]
    
    return {
        "uptime_percent": uptime,
        "total_checks": len(results),
        "up_checks": up,
        "down_checks": down,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "sla_target": monitor.get("sla_uptime_percent", 99.9),
        "sla_met": uptime >= monitor.get("sla_uptime_percent", 99.9)
    }


@router.get("/status/health")
async def get_scheduler_health():
    """Get monitoring scheduler health status"""
    return {"monitoring_scheduler_running": is_monitoring_running()}
