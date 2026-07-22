"""
FalconOps AI — AI Intelligence Layer: Tooling Interface
Exposes existing FalconOps observability data as safe, parameterized tools.
Agents MUST use these tools — no direct DB access from prompts.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)


def _cutoff(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


# ─────────────────────────────────────────────
#  Tools
# ─────────────────────────────────────────────

async def get_logs(service: Optional[str] = None, minutes: int = 60,
                   level: Optional[str] = None, search: Optional[str] = None,
                   limit: int = 50) -> Dict[str, Any]:
    """Query application logs (db.logs)."""
    q: Dict[str, Any] = {"timestamp": {"$gte": _cutoff(minutes)}}
    if service:
        q["service"] = service
    if level:
        lv = level.upper()
        if lv in ("ERROR", "CRITICAL", "FATAL"):
            q["level"] = {"$in": ["ERROR", "CRITICAL", "FATAL"]}
        else:
            q["level"] = lv
    if search:
        q["message"] = {"$regex": re.escape(search), "$options": "i"}
    limit = min(int(limit), 200)
    rows = await db.logs.find(q, {"_id": 0, "embedding": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    total = await db.logs.count_documents(q)
    by_level: Dict[str, int] = {}
    for r in rows:
        by_level[r.get("level", "UNKNOWN")] = by_level.get(r.get("level", "UNKNOWN"), 0) + 1
    return {
        "tool": "get_logs",
        "params": {"service": service, "minutes": minutes, "level": level, "search": search},
        "count": total,
        "returned": len(rows),
        "by_level": by_level,
        "data": [{"id": r.get("id"), "timestamp": r.get("timestamp"), "level": r.get("level"),
                  "service": r.get("service"), "message": (r.get("message") or "")[:300],
                  "host": r.get("host")} for r in rows],
        "summary": f"{total} log(s) matched in last {minutes}m" + (f" for service '{service}'" if service else ""),
    }


async def get_metrics(service: Optional[str] = None, metric_name: Optional[str] = None,
                      minutes: int = 60) -> Dict[str, Any]:
    """Query metrics timeseries. If metric_name given → aggregated series; else catalog + latest values."""
    from .metrics_timeseries_service import metrics_timeseries_service
    params = {"service": service, "metric_name": metric_name, "minutes": minutes}
    start = _cutoff(minutes)
    if metric_name:
        tags = {"service": service} if service else None
        result = await metrics_timeseries_service.query_metrics(
            metric_name=metric_name, start_time=start, tags=tags, aggregation="avg", bucket="5m")
        series = result.get("series", result.get("data", []))
        vals = [p.get("value") for p in series if isinstance(p, dict) and p.get("value") is not None]
        stats = {}
        if vals:
            stats = {"min": round(min(vals), 2), "max": round(max(vals), 2),
                     "avg": round(sum(vals) / len(vals), 2), "latest": round(vals[-1], 2)}
        return {"tool": "get_metrics", "params": params, "count": len(series),
                "data": series[-60:], "stats": stats,
                "summary": f"Metric '{metric_name}': {stats or 'no data'} over last {minutes}m"}
    # Catalog mode: latest value per metric name
    q: Dict[str, Any] = {"timestamp": {"$gte": start}}
    if service:
        q["tags.service"] = service
    pipeline = [
        {"$match": q},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$name", "latest": {"$first": "$value"},
                    "unit": {"$first": "$unit"}, "count": {"$sum": 1},
                    "avg": {"$avg": "$value"}, "max": {"$max": "$value"}}},
        {"$limit": 30},
    ]
    rows = await db.metrics_timeseries.aggregate(pipeline).to_list(30)
    data = [{"name": r["_id"], "latest": round(r["latest"], 2), "avg": round(r["avg"], 2),
             "max": round(r["max"], 2), "unit": r.get("unit"), "points": r["count"]} for r in rows]
    return {"tool": "get_metrics", "params": params, "count": len(data), "data": data,
            "summary": f"{len(data)} metric(s) reporting in last {minutes}m" + (f" for '{service}'" if service else "")}


async def get_traces(service: Optional[str] = None, trace_id: Optional[str] = None,
                     minutes: int = 60, errors_only: bool = False, limit: int = 20) -> Dict[str, Any]:
    """Query distributed traces (OTLP). trace_id → full span tree; else recent traces."""
    params = {"service": service, "trace_id": trace_id, "minutes": minutes, "errors_only": errors_only}
    if trace_id:
        trace = await db.otel_traces.find_one({"trace_id": trace_id}, {"_id": 0})
        spans = await db.otel_spans.find({"trace_id": trace_id}, {"_id": 0}).sort("start_time", 1).to_list(500)
        return {"tool": "get_traces", "params": params, "count": len(spans),
                "data": {"trace": trace, "spans": [
                    {"span_name": s.get("name"), "service": s.get("service_name"),
                     "duration_ms": s.get("duration_ms"), "status": s.get("status"),
                     "start_time": s.get("start_time")} for s in spans]},
                "summary": f"Trace {trace_id}: {len(spans)} spans"}
    q: Dict[str, Any] = {"received_at": {"$gte": _cutoff(minutes)}}
    if service:
        q["services"] = service
    if errors_only:
        q["has_error"] = True
    limit = min(int(limit), 100)
    rows = await db.otel_traces.find(q, {"_id": 0}).sort("received_at", -1).limit(limit).to_list(limit)
    err_count = sum(1 for r in rows if r.get("has_error"))
    durations = [r.get("duration_ms") for r in rows if r.get("duration_ms") is not None]
    return {"tool": "get_traces", "params": params, "count": len(rows),
            "errors": err_count,
            "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else None,
            "data": [{"trace_id": r.get("trace_id"), "root": r.get("root_span_name"),
                      "services": r.get("services"), "duration_ms": r.get("duration_ms"),
                      "has_error": r.get("has_error"), "received_at": r.get("received_at")} for r in rows],
            "summary": f"{len(rows)} trace(s), {err_count} with errors, in last {minutes}m"}


async def get_deployments(service: Optional[str] = None, minutes: int = 1440) -> Dict[str, Any]:
    """Detect deployment / release / rollout events from logs."""
    q: Dict[str, Any] = {"timestamp": {"$gte": _cutoff(minutes)},
                         "message": {"$regex": r"deploy|rollout|release|version bump|config change", "$options": "i"}}
    if service:
        q["service"] = service
    rows = await db.logs.find(q, {"_id": 0, "embedding": 0}).sort("timestamp", -1).limit(50).to_list(50)
    return {"tool": "get_deployments", "params": {"service": service, "minutes": minutes},
            "count": len(rows),
            "data": [{"id": r.get("id"), "timestamp": r.get("timestamp"), "service": r.get("service"),
                      "message": (r.get("message") or "")[:200], "host": r.get("host")} for r in rows],
            "summary": f"{len(rows)} deployment-related event(s) in last {minutes}m" + (f" for '{service}'" if service else "")}


async def get_incidents(service: Optional[str] = None, status: Optional[str] = None,
                        limit: int = 10) -> Dict[str, Any]:
    """Query the incidents collection (open + recent)."""
    q: Dict[str, Any] = {}
    if service:
        q["service"] = service
    if status:
        q["status"] = status
    limit = min(int(limit), 50)
    rows = await db.incidents.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"tool": "get_incidents", "params": {"service": service, "status": status},
            "count": len(rows),
            "data": [{"id": r.get("id"), "title": r.get("title"), "severity": r.get("severity"),
                      "status": r.get("status"), "service": r.get("service"),
                      "root_cause": ((r.get("ai_analysis") or {}).get("root_cause") or "")[:300],
                      "created_at": r.get("created_at")} for r in rows],
            "summary": f"{len(rows)} incident(s)" + (f" for '{service}'" if service else "")}


HEARTBEAT_STALE_AFTER_SECONDS = 180  # 3x OneAgent's 60s heartbeat interval


async def get_agent_status(service: Optional[str] = None, host: Optional[str] = None) -> Dict[str, Any]:
    """Check OneAgent (telemetry collector) health for a service/host — explains
    'no data' gaps (collector stale/offline) instead of implying the service itself is fine."""
    q: Dict[str, Any] = {}
    if host:
        q["host"] = host
    if service:
        q["services.name"] = service
    rows = await db.oneagent_agents.find(q, {"_id": 0}).sort("last_seen", -1).to_list(50)
    now = datetime.now(timezone.utc)
    data = []
    for r in rows:
        last_seen = r.get("last_seen")
        age_s: Optional[float] = None
        try:
            dt = datetime.fromisoformat(last_seen)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_s = (now - dt).total_seconds()
        except Exception:
            pass
        status = "stale" if age_s is None or age_s > HEARTBEAT_STALE_AFTER_SECONDS else "healthy"
        data.append({
            "host": r.get("host"),
            "agent_version": r.get("agent_version"),
            "services": [s.get("name") for s in (r.get("services") or []) if isinstance(s, dict)],
            "last_seen": last_seen,
            "seconds_since_heartbeat": round(age_s) if age_s is not None else None,
            "status": status,
        })
    any_healthy = any(d["status"] == "healthy" for d in data)
    if not data:
        summary = ("No OneAgent has ever reported" + (f" for service '{service}'" if service else "") +
                   " — missing telemetry likely means no collector is installed/connected, not that the service is healthy.")
    elif any_healthy:
        summary = f"{len(data)} OneAgent(s) found" + (f" for '{service}'" if service else "") + ", at least one reporting normally."
    else:
        summary = f"{len(data)} OneAgent(s) found" + (f" for '{service}'" if service else "") + f", but none has reported in the last {HEARTBEAT_STALE_AFTER_SECONDS}s — telemetry for this window may be incomplete."
    return {"tool": "get_agent_status", "params": {"service": service, "host": host},
            "count": len(data), "data": data, "any_healthy": any_healthy, "summary": summary}


async def get_threats(status: Optional[str] = "active", severity: Optional[str] = None,
                      limit: int = 50) -> Dict[str, Any]:
    """Query detected security threats (db.security_threats)."""
    from .security_service import get_threats as _get_threats
    rows = await _get_threats(status=status, severity=severity, limit=limit)
    return {"tool": "get_threats", "params": {"status": status, "severity": severity, "limit": limit},
            "count": len(rows), "data": rows,
            "summary": f"{len(rows)} threat(s)" + (f" with status '{status}'" if status else "")}


async def get_security_events(hours: int = 24, category: Optional[str] = None,
                              severity: Optional[str] = None, search: Optional[str] = None,
                              limit: int = 100) -> Dict[str, Any]:
    """Query raw security events (db.security_events)."""
    from .security_service import get_security_events as _get_security_events
    result = await _get_security_events(hours=hours, category=category, severity=severity,
                                        search=search, limit=limit)
    rows = result.get("events", [])
    return {"tool": "get_security_events", "params": {"hours": hours, "category": category, "severity": severity},
            "count": result.get("total", len(rows)), "data": rows,
            "summary": f"{result.get('total', len(rows))} security event(s) in last {hours}h"}


async def get_ueba_profiles(hours: int = 168, insider_only: bool = False) -> Dict[str, Any]:
    """Query UEBA behavioral risk profiles, optionally filtered to insider-threat candidates."""
    from .ueba_service import build_user_profiles, get_insider_threat_candidates
    rows = await (get_insider_threat_candidates(hours) if insider_only else build_user_profiles(hours))
    return {"tool": "get_ueba_profiles", "params": {"hours": hours, "insider_only": insider_only},
            "count": len(rows), "data": rows[:30],
            "summary": f"{len(rows)} user profile(s)" + (" (insider-threat candidates only)" if insider_only else "")}


async def get_vulnerabilities(limit: int = 20) -> Dict[str, Any]:
    """Query prioritized vulnerabilities (CVSS + real topology-derived asset criticality)."""
    from .vulnerability_service import get_vulnerability_dashboard
    dash = await get_vulnerability_dashboard()
    rows = dash.get("top_priority", [])[:limit]
    return {"tool": "get_vulnerabilities", "params": {"limit": limit},
            "count": dash.get("total_vulnerabilities", len(rows)), "data": rows,
            "summary": f"{dash.get('total_vulnerabilities', 0)} known vulnerabilit(y/ies), "
                       f"top priority shown"}


async def get_mitre_matrix(hours: int = 24) -> Dict[str, Any]:
    """Query the MITRE ATT&CK matrix: technique counts grouped by tactic over the window."""
    from .mitre_mapping_service import get_mitre_matrix as _get_mitre_matrix
    matrix = await _get_mitre_matrix(hours=hours)
    return {"tool": "get_mitre_matrix", "params": {"hours": hours},
            "count": matrix.get("total_tagged_events", 0), "data": matrix.get("tactics", []),
            "summary": f"{matrix.get('total_tagged_events', 0)} MITRE-tagged event(s) in last {hours}h"}


async def get_compliance_status(framework: Optional[str] = None) -> Dict[str, Any]:
    """Query compliance control status (SOC2/ISO27001) — controls without a real backing
    signal report status 'unknown', never a fabricated pass."""
    from .compliance_service import get_compliance_dashboard, evaluate_compliance
    if framework:
        result = await evaluate_compliance(framework)
        rows = result.get("controls", [])
        return {"tool": "get_compliance_status", "params": {"framework": framework},
                "count": len(rows), "data": rows,
                "summary": f"{framework}: {result.get('compliance_score')}% controls passing"}
    dash = await get_compliance_dashboard()
    return {"tool": "get_compliance_status", "params": {"framework": None},
            "count": len(dash.get("frameworks", [])), "data": dash.get("frameworks", []),
            "summary": "Compliance overview across all frameworks"}


async def get_topology_summary() -> Dict[str, Any]:
    """Query the service topology (nodes/edges) and overall system risk score."""
    from .topology_service import topology_service
    from .impact_analysis_engine import impact_analysis_engine
    topo = await topology_service.get_topology()
    risk = await impact_analysis_engine.get_system_risk_summary()
    return {"tool": "get_topology_summary", "params": {},
            "count": topo.get("node_count", 0), "data": {"topology": topo, "system_risk": risk},
            "summary": f"{topo.get('node_count', 0)} service(s) in topology, "
                       f"system risk {risk.get('risk_level')} ({risk.get('risk_score')})"}


async def get_api_operation_stats(service: Optional[str] = None, minutes: int = 60,
                                  limit: int = 15) -> Dict[str, Any]:
    """Per-operation (endpoint) latency + error stats, grouped directly from real span
    data (db.otel_spans) — same real tracing backbone get_traces uses, just grouped by
    operation instead of by trace, ranked worst-first (error rate then p95 latency)."""
    q: Dict[str, Any] = {"received_at": {"$gte": _cutoff(minutes)}}
    if service:
        q["service"] = service
    spans = await db.otel_spans.find(
        q, {"_id": 0, "service": 1, "operation": 1, "duration_ms": 1, "status": 1}
    ).to_list(20000)

    by_op: Dict[Any, Dict[str, Any]] = {}
    for s in spans:
        key = (s.get("service"), s.get("operation"))
        g = by_op.setdefault(key, {"durations": [], "errors": 0})
        g["durations"].append(s.get("duration_ms") or 0)
        if s.get("status") == "ERROR":
            g["errors"] += 1

    rows = []
    for (svc, op), g in by_op.items():
        n = len(g["durations"])
        durations = sorted(g["durations"])
        p95 = durations[max(0, int(n * 0.95) - 1)] if durations else 0
        rows.append({
            "service": svc, "operation": op, "call_count": n, "error_count": g["errors"],
            "error_rate_pct": round((g["errors"] / n) * 100, 2) if n else 0,
            "avg_duration_ms": round(sum(durations) / n, 2) if n else 0,
            "p95_duration_ms": round(p95, 2),
        })
    rows.sort(key=lambda r: (r["error_rate_pct"], r["p95_duration_ms"]), reverse=True)
    rows = rows[:limit]
    return {"tool": "get_api_operation_stats", "params": {"service": service, "minutes": minutes},
            "count": len(rows), "data": rows,
            "summary": f"{len(rows)} API operation(s) analyzed in last {minutes}m" + (f" for '{service}'" if service else "")}


async def get_capacity_forecast(threshold: float = 90, horizon: str = "24h") -> Dict[str, Any]:
    """Real linear-regression capacity forecast (CPU/memory/disk) — reuses
    capacity_prediction_engine's already-computed trend + time-to-threshold analysis
    rather than a new forecasting model."""
    from .capacity_prediction_engine import capacity_prediction_engine
    alerts = await capacity_prediction_engine.get_capacity_alerts(threshold=threshold, horizon=horizon)
    return {"tool": "get_capacity_forecast", "params": {"threshold": threshold, "horizon": horizon},
            "count": len(alerts), "data": alerts,
            "summary": f"{len(alerts)} host/metric combination(s) approaching capacity thresholds within {horizon}"}


async def get_sla_risk(limit: int = 20) -> Dict[str, Any]:
    """Open incidents with a real, already-computed SLA breach deadline
    (incident_engine's severity-based sla_breach_at), sorted soonest-breach-first."""
    now = datetime.now(timezone.utc)
    q = {"sla_breach_at": {"$ne": None}, "is_sla_breached": False,
         "status": {"$nin": ["resolved", "closed"]}}
    rows = await db.incidents_engine.find(q, {"_id": 0}).sort("sla_breach_at", 1).limit(limit).to_list(limit)

    data = []
    for r in rows:
        minutes_remaining = None
        try:
            breach_at = datetime.fromisoformat(r["sla_breach_at"].replace("Z", "+00:00"))
            minutes_remaining = round((breach_at - now).total_seconds() / 60, 1)
        except Exception:
            pass
        data.append({
            "id": r.get("id"), "title": r.get("title"), "severity": r.get("severity"),
            "status": r.get("status"), "sla_breach_at": r.get("sla_breach_at"),
            "minutes_until_breach": minutes_remaining,
        })
    at_risk = sum(1 for d in data if d["minutes_until_breach"] is not None and d["minutes_until_breach"] < 30)
    return {"tool": "get_sla_risk", "params": {"limit": limit}, "count": len(data), "data": data,
            "summary": f"{len(data)} open incident(s) with an SLA deadline, {at_risk} breaching within 30 minutes"}


async def get_ops_summary(days: int = 7) -> Dict[str, Any]:
    """Composite ops health snapshot: incident volume/MTTR (db.incidents +
    db.incidents_engine) and real automation-outcome success rate
    (db.incident_outcomes, written by autonomous_ops_orchestrator.record_outcome) —
    mirrors how executive_routes.py composes the security executive dashboard, for
    operational health instead. Reports 'n/a' rather than fabricating a rate when no
    outcomes have been recorded yet."""
    cutoff = _cutoff(days * 1440)
    legacy = await db.incidents.find(
        {"created_at": {"$gte": cutoff}}, {"_id": 0, "mttr_seconds": 1, "status": 1}
    ).to_list(2000)
    engine = await db.incidents_engine.find(
        {"created_at": {"$gte": cutoff}}, {"_id": 0, "status": 1}
    ).to_list(2000)
    outcomes = await db.incident_outcomes.find(
        {"recorded_at": {"$gte": cutoff}}, {"_id": 0, "was_effective": 1}
    ).to_list(2000)

    mttr_values = [i["mttr_seconds"] for i in legacy if i.get("mttr_seconds")]
    avg_mttr_minutes = round(sum(mttr_values) / len(mttr_values) / 60, 1) if mttr_values else None

    resolved_outcomes = [o for o in outcomes if o.get("was_effective") is not None]
    effective_count = sum(1 for o in resolved_outcomes if o.get("was_effective"))
    automation_success_rate_pct = round((effective_count / len(resolved_outcomes)) * 100, 1) if resolved_outcomes else None

    total_incidents = len(legacy) + len(engine)
    open_incidents = (sum(1 for i in legacy if i.get("status") not in ("resolved", "closed")) +
                       sum(1 for i in engine if i.get("status") not in ("resolved", "closed")))

    return {
        "tool": "get_ops_summary", "params": {"days": days}, "count": total_incidents,
        "data": {
            "total_incidents": total_incidents, "open_incidents": open_incidents,
            "avg_mttr_minutes": avg_mttr_minutes,
            "automation_success_rate_pct": automation_success_rate_pct,
            "automation_outcomes_recorded": len(resolved_outcomes),
        },
        "summary": (f"{total_incidents} incident(s) in last {days}d, {open_incidents} open, "
                    f"avg MTTR {avg_mttr_minutes if avg_mttr_minutes is not None else 'n/a'}min, "
                    f"automation success rate "
                    f"{automation_success_rate_pct if automation_success_rate_pct is not None else 'n/a (no recorded outcomes)'}"
                    f"{'%' if automation_success_rate_pct is not None else ''}"),
    }


async def list_services() -> List[str]:
    """Known services across logs + traces."""
    try:
        log_svcs = await db.logs.distinct("service")
    except Exception:
        log_svcs = []
    try:
        trace_svcs = await db.otel_traces.distinct("services")
    except Exception:
        trace_svcs = []
    return sorted({s for s in (log_svcs + trace_svcs) if s})


# ─────────────────────────────────────────────
#  Registry + dispatcher
# ─────────────────────────────────────────────

TOOL_DEFS: List[Dict[str, Any]] = [
    {"name": "get_logs", "description": "Query application logs. Filter by service, level (error/warn/info), free-text search, time window in minutes.",
     "params": {"service": "string?", "minutes": "int (default 60)", "level": "string?", "search": "string?", "limit": "int (default 50)"}},
    {"name": "get_metrics", "description": "Query metrics. With metric_name → time series + stats. Without → catalog of reporting metrics with latest/avg/max.",
     "params": {"service": "string?", "metric_name": "string?", "minutes": "int (default 60)"}},
    {"name": "get_traces", "description": "Query distributed traces. With trace_id → full span breakdown. Otherwise recent traces, optionally errors_only.",
     "params": {"service": "string?", "trace_id": "string?", "minutes": "int (default 60)", "errors_only": "bool", "limit": "int (default 20)"}},
    {"name": "get_deployments", "description": "Recent deployment / release / config-change events per service (last 24h default).",
     "params": {"service": "string?", "minutes": "int (default 1440)"}},
    {"name": "get_incidents", "description": "Open and recent incidents with AI root-cause analysis if available.",
     "params": {"service": "string?", "status": "string? (open/resolved)", "limit": "int (default 10)"}},
    {"name": "get_agent_status", "description": "Check OneAgent (telemetry collector) health for a service/host — use this to tell "
     "apart 'service is healthy' from 'no data because the collector is stale/offline'.",
     "params": {"service": "string?", "host": "string?"}},
    {"name": "get_threats", "description": "Query detected security threats (brute force, malicious IP, lateral movement, etc.).",
     "params": {"status": "string? (default active)", "severity": "string?", "limit": "int (default 50)"}},
    {"name": "get_security_events", "description": "Query raw security events (logins, privileged actions, data access) with filters.",
     "params": {"hours": "int (default 24)", "category": "string?", "severity": "string?", "search": "string?", "limit": "int (default 100)"}},
    {"name": "get_ueba_profiles", "description": "Query UEBA behavioral risk profiles per user, optionally filtered to insider-threat candidates.",
     "params": {"hours": "int (default 168)", "insider_only": "bool (default false)"}},
    {"name": "get_vulnerabilities", "description": "Query prioritized vulnerabilities (CVSS + real topology-derived asset criticality).",
     "params": {"limit": "int (default 20)"}},
    {"name": "get_mitre_matrix", "description": "Query the MITRE ATT&CK matrix: technique counts grouped by tactic.",
     "params": {"hours": "int (default 24)"}},
    {"name": "get_compliance_status", "description": "Query compliance control status (SOC2/ISO27001); one framework or an overview.",
     "params": {"framework": "string?"}},
    {"name": "get_topology_summary", "description": "Query the service topology (nodes/edges) and overall system risk score.",
     "params": {}},
    {"name": "get_api_operation_stats", "description": "Per-operation (endpoint) latency + error rate, ranked worst-first, from real trace span data.",
     "params": {"service": "string?", "minutes": "int (default 60)", "limit": "int (default 15)"}},
    {"name": "get_capacity_forecast", "description": "Real linear-regression capacity forecast (CPU/memory/disk) — hosts/metrics approaching threshold.",
     "params": {"threshold": "float (default 90)", "horizon": "string (default 24h)"}},
    {"name": "get_sla_risk", "description": "Open incidents with a real SLA breach deadline, sorted soonest-breach-first.",
     "params": {"limit": "int (default 20)"}},
    {"name": "get_ops_summary", "description": "Composite ops health snapshot: incident volume, MTTR, and automation success rate.",
     "params": {"days": "int (default 7)"}},
]

_TOOL_FUNCS = {
    "get_logs": get_logs,
    "get_metrics": get_metrics,
    "get_traces": get_traces,
    "get_deployments": get_deployments,
    "get_incidents": get_incidents,
    "get_agent_status": get_agent_status,
    "get_threats": get_threats,
    "get_security_events": get_security_events,
    "get_ueba_profiles": get_ueba_profiles,
    "get_vulnerabilities": get_vulnerabilities,
    "get_mitre_matrix": get_mitre_matrix,
    "get_compliance_status": get_compliance_status,
    "get_topology_summary": get_topology_summary,
    "get_api_operation_stats": get_api_operation_stats,
    "get_capacity_forecast": get_capacity_forecast,
    "get_sla_risk": get_sla_risk,
    "get_ops_summary": get_ops_summary,
}

_ALLOWED_PARAMS = {
    "get_logs": {"service", "minutes", "level", "search", "limit"},
    "get_metrics": {"service", "metric_name", "minutes"},
    "get_traces": {"service", "trace_id", "minutes", "errors_only", "limit"},
    "get_deployments": {"service", "minutes"},
    "get_incidents": {"service", "status", "limit"},
    "get_agent_status": {"service", "host"},
    "get_threats": {"status", "severity", "limit"},
    "get_security_events": {"hours", "category", "severity", "search", "limit"},
    "get_ueba_profiles": {"hours", "insider_only"},
    "get_vulnerabilities": {"limit"},
    "get_mitre_matrix": {"hours"},
    "get_compliance_status": {"framework"},
    "get_topology_summary": set(),
    "get_api_operation_stats": {"service", "minutes", "limit"},
    "get_capacity_forecast": {"threshold", "horizon"},
    "get_sla_risk": {"limit"},
    "get_ops_summary": {"days"},
}


async def execute_tool(name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Safely dispatch a tool call with parameter whitelisting."""
    fn = _TOOL_FUNCS.get(name)
    if fn is None:
        return {"tool": name, "error": f"unknown tool '{name}'", "data": [], "summary": "unknown tool"}
    clean = {k: v for k, v in (params or {}).items() if k in _ALLOWED_PARAMS[name] and v is not None}
    try:
        return await fn(**clean)
    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return {"tool": name, "error": str(e)[:200], "data": [], "summary": f"tool '{name}' failed"}
