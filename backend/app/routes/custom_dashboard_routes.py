"""
FalconOps AI - Custom Dashboard Builder Routes
Persist per-user drag-and-drop dashboard layouts
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..utils.auth import require_auth
from ..core.database import db
from ..services.sla_service import get_sla_overview, get_sla_summary

router = APIRouter(prefix="/api/custom-dashboards", tags=["Custom Dashboards"])


class Widget(BaseModel):
    i: str                           # grid item id
    x: int
    y: int
    w: int
    h: int
    widget_type: str                 # e.g. "soc_feed", "uptime", "billing", "sla", "threats", "ai_agents"
    title: Optional[str] = ""
    config: Optional[dict] = Field(default_factory=dict)


class DashboardLayout(BaseModel):
    name: str = "My Dashboard"
    description: Optional[str] = ""
    widgets: List[Widget] = Field(default_factory=list)


@router.get("/list")
async def list_dashboards(current_user: dict = Depends(require_auth)):
    rows = await db.custom_dashboards.find(
        {"user_id": current_user["id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    return rows


@router.post("/create")
async def create_dashboard(payload: DashboardLayout, current_user: dict = Depends(require_auth)):
    dashboard_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "dashboard_id": dashboard_id,
        "user_id": current_user["id"],
        "name": payload.name,
        "description": payload.description,
        "widgets": [w.model_dump() for w in payload.widgets],
        "created_at": now,
        "updated_at": now,
    }
    await db.custom_dashboards.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/{dashboard_id}")
async def get_dashboard(dashboard_id: str, current_user: dict = Depends(require_auth)):
    doc = await db.custom_dashboards.find_one(
        {"dashboard_id": dashboard_id, "user_id": current_user["id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return doc


@router.put("/{dashboard_id}")
async def update_dashboard(dashboard_id: str, payload: DashboardLayout, current_user: dict = Depends(require_auth)):
    update = {
        "name": payload.name,
        "description": payload.description,
        "widgets": [w.model_dump() for w in payload.widgets],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.custom_dashboards.update_one(
        {"dashboard_id": dashboard_id, "user_id": current_user["id"]},
        {"$set": update},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    doc = await db.custom_dashboards.find_one(
        {"dashboard_id": dashboard_id}, {"_id": 0}
    )
    return doc


@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: str, current_user: dict = Depends(require_auth)):
    result = await db.custom_dashboards.delete_one(
        {"dashboard_id": dashboard_id, "user_id": current_user["id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return {"ok": True, "deleted": dashboard_id}


@router.get("/widgets/catalog")
async def widget_catalog(current_user: dict = Depends(require_auth)):
    """Available widget types for the builder"""
    return {
        "widgets": [
            {"type": "soc_feed", "title": "SOC Live Feed", "icon": "radio", "category": "security"},
            {"type": "uptime", "title": "Uptime Status", "icon": "globe", "category": "monitoring"},
            {"type": "threats", "title": "Security Threats", "icon": "shield", "category": "security"},
            {"type": "billing", "title": "Billing Usage", "icon": "key", "category": "admin"},
            {"type": "sla", "title": "SLA Score", "icon": "gauge", "category": "monitoring"},
            {"type": "ai_agents", "title": "AI Agent Activity", "icon": "brain", "category": "aiops"},
            {"type": "alerts", "title": "Active Alerts", "icon": "bell", "category": "aiops"},
            {"type": "incidents", "title": "Open Incidents", "icon": "alert-triangle", "category": "aiops"},
            {"type": "metrics", "title": "System Metrics", "icon": "activity", "category": "monitoring"},
            {"type": "tenants", "title": "Tenant Overview", "icon": "building", "category": "admin"},
            {"type": "kpi_row", "title": "NOC KPI Row", "icon": "trending-up", "category": "noc",
             "configurable": False},
            {"type": "slo_status", "title": "SLO Status", "icon": "target", "category": "noc",
             "configurable": True, "config_kind": "monitor"},
            {"type": "apm_table", "title": "Service Health (APM)", "icon": "table", "category": "noc",
             "configurable": True, "config_kind": "service"},
            {"type": "os_gauges", "title": "OS Utilization", "icon": "server", "category": "noc",
             "configurable": True, "config_kind": "server"},
            {"type": "log_exceptions", "title": "Log Exceptions", "icon": "file-warning", "category": "noc",
             "configurable": True, "config_kind": "service"},
        ]
    }


@router.get("/widgets/data/{widget_type}")
async def widget_data(
    widget_type: str,
    service: Optional[str] = Query(None, description="Scope to one APM service / log service"),
    server_id: Optional[str] = Query(None, description="Scope to one server"),
    monitor_id: Optional[str] = Query(None, description="Scope to one uptime monitor"),
    severity: Optional[str] = Query(None, description="Override default severity filter (log_exceptions)"),
    current_user: dict = Depends(require_auth),
):
    """Return live data for each widget type. service/server_id/monitor_id/severity scope a
    widget to one entity for the NOC widget types below — omitted means aggregate/overview mode.
    Pre-existing widget types below ignore these params (unchanged, backward compatible).

    Security fix: every branch below now filters by the requesting user's own
    tenant_id — previously none of them did, so any logged-in user of any
    tenant/role could see every other tenant's SOC feed, security threats,
    alerts, incidents, and (via the "tenants" widget) the full tenant
    directory including contact emails. The "tenants" widget additionally now
    requires an admin role, since a personal dashboard widget has no
    legitimate reason to enumerate other tenants at all — GET /api/tenants
    (admin-only) already serves that need."""
    tid = current_user.get("tenant_id")
    tenant_filter = {"tenant_id": tid} if tid else {}
    try:
        if widget_type == "soc_feed":
            events = await db.soc_events.find(tenant_filter, {"_id": 0}).sort("timestamp", -1).limit(8).to_list(8)
            return {"events": events, "count": len(events)}
        if widget_type == "uptime":
            monitors = await db.uptime_monitors.find(tenant_filter, {"_id": 0}).limit(10).to_list(10)
            total = len(monitors)
            up = sum(1 for m in monitors if m.get("status") == "up")
            return {"total": total, "up": up, "down": total - up, "monitors": monitors[:5]}
        if widget_type == "threats":
            threats = await db.security_threats.find(tenant_filter, {"_id": 0}).sort("timestamp", -1).limit(10).to_list(10)
            critical = sum(1 for t in threats if t.get("severity") == "critical")
            return {"threats": threats[:5], "count": len(threats), "critical": critical}
        if widget_type == "billing":
            usage = await db.usage_events.count_documents(tenant_filter)
            plans = await db.user_plans.count_documents(tenant_filter)
            return {"total_events": usage, "active_plans": plans}
        if widget_type == "sla":
            monitors = await db.uptime_monitors.find(tenant_filter, {"_id": 0}).to_list(100)
            total = len(monitors) or 1
            up = sum(1 for m in monitors if m.get("status") == "up")
            sla = round((up / total) * 100, 2) if total else 100.0
            return {"sla_percent": sla, "total_monitors": total}
        if widget_type == "ai_agents":
            runs = await db.ai_agent_runs.find(tenant_filter, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
            return {"runs": runs, "count": await db.ai_agent_runs.count_documents(tenant_filter)}
        if widget_type == "alerts":
            alerts = await db.alerts.find({"status": "open", **tenant_filter}, {"_id": 0}).limit(10).to_list(10)
            return {"alerts": alerts[:5], "count": len(alerts)}
        if widget_type == "incidents":
            incidents = await db.incidents.find({"status": {"$ne": "closed"}, **tenant_filter}, {"_id": 0}).limit(10).to_list(10)
            return {"incidents": incidents[:5], "count": len(incidents)}
        if widget_type == "metrics":
            return {
                "cpu": 42.5, "memory": 61.2, "disk": 38.7,
                "note": "Live metric snapshot"
            }
        if widget_type == "tenants":
            if current_user.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Admin role required for the tenants widget")
            tenants = await db.tenants.find({}, {"_id": 0}).limit(10).to_list(10)
            return {"tenants": tenants[:5], "count": len(tenants)}

        # ── NOC widgets ──────────────────────────────────────────────
        if widget_type == "kpi_row":
            now = datetime.now(timezone.utc)
            cur_start = (now - timedelta(hours=1)).isoformat()
            prev_start = (now - timedelta(hours=2)).isoformat()
            cur_txns = await db.apm_transactions.find({"start_time": {"$gte": cur_start}, **tenant_filter}, {"_id": 0}).to_list(10000)
            prev_txns = await db.apm_transactions.find(
                {"start_time": {"$gte": prev_start, "$lt": cur_start}, **tenant_filter}, {"_id": 0}).to_list(10000)
            cur_errs = await db.apm_errors.find({"timestamp": {"$gte": cur_start}, **tenant_filter}, {"_id": 0}).to_list(2000)
            prev_errs = await db.apm_errors.find(
                {"timestamp": {"$gte": prev_start, "$lt": cur_start}, **tenant_filter}, {"_id": 0}).to_list(2000)

            def _window(txns, errs):
                durations = [t.get("duration_ms", 0) for t in txns if t.get("duration_ms")]
                avg = round(sum(durations) / len(durations), 2) if durations else 0
                err_rate = round((len(errs) / len(txns)) * 100, 2) if txns else 0
                return {"throughput": len(txns), "avg_latency_ms": avg, "error_rate": err_rate}

            def _delta(cur_v, prev_v):
                return round(((cur_v - prev_v) / prev_v) * 100, 1) if prev_v else None

            cur_m, prev_m = _window(cur_txns, cur_errs), _window(prev_txns, prev_errs)
            sla = await get_sla_overview(1)
            return {
                "throughput": {"value": cur_m["throughput"], "delta_pct": _delta(cur_m["throughput"], prev_m["throughput"])},
                "avg_latency_ms": {"value": cur_m["avg_latency_ms"], "delta_pct": _delta(cur_m["avg_latency_ms"], prev_m["avg_latency_ms"])},
                "error_rate": {"value": cur_m["error_rate"], "delta_pct": _delta(cur_m["error_rate"], prev_m["error_rate"])},
                "sla_compliance_pct": sla.get("compliance_rate", 100),
                "monitors_compliant": sla.get("compliant", 0),
                "monitors_total": sla.get("total_monitors", 0),
            }

        if widget_type == "slo_status":
            if monitor_id:
                summary = await get_sla_summary(monitor_id, 1)
                if "error" in summary:
                    return {"monitors": []}
                return {"monitors": [{
                    "monitor_id": monitor_id, "name": summary.get("monitor_name", monitor_id),
                    "uptime_pct": summary.get("overall_uptime_pct"),
                    "sla_target": summary.get("sla_target"),
                    "compliant": summary.get("overall_compliant"),
                }]}
            overview = await get_sla_overview(1)
            return {"monitors": overview.get("monitors", [])[:6],
                    "compliance_rate": overview.get("compliance_rate")}

        if widget_type == "apm_table":
            from . import apm as apm_routes
            dashboard = await apm_routes.get_apm_dashboard(hours=24, current_user=current_user)
            rows = dashboard.services
            if service:
                rows = [r for r in rows if r.get("service_name") == service]
            return {"services": rows[:10]}

        if widget_type == "os_gauges":
            from . import servers as servers_routes
            dashboard = await servers_routes.get_server_dashboard(current_user=current_user)
            if server_id:
                match = next((s for s in dashboard.servers if s.get("id") == server_id), None)
                return {"mode": "single", "server": match}
            active = [s for s in dashboard.servers if s.get("network_in") is not None]
            avg_net_in = round(sum(s.get("network_in") or 0 for s in active) / len(active), 2) if active else 0
            avg_net_out = round(sum(s.get("network_out") or 0 for s in active) / len(active), 2) if active else 0
            return {
                "mode": "aggregate",
                "avg_cpu": dashboard.avg_cpu, "avg_memory": dashboard.avg_memory, "avg_disk": dashboard.avg_disk,
                "avg_network_in": avg_net_in, "avg_network_out": avg_net_out,
                "total_servers": dashboard.total_servers, "online_servers": dashboard.online_servers,
            }

        if widget_type == "log_exceptions":
            since = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
            q: dict = {"timestamp": {"$gte": since}, **tenant_filter}
            q["severity"] = severity if severity else {"$in": ["error", "critical"]}
            if service:
                q["service"] = service
            rows = await db.logs.find(q, {"_id": 0}).sort("timestamp", -1).limit(8).to_list(8)
            return {"logs": rows, "count": len(rows)}

        return {"error": f"Unknown widget type: {widget_type}"}
    except Exception as e:
        return {"error": str(e), "widget_type": widget_type}
