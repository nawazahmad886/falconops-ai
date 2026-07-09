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
]

_TOOL_FUNCS = {
    "get_logs": get_logs,
    "get_metrics": get_metrics,
    "get_traces": get_traces,
    "get_deployments": get_deployments,
    "get_incidents": get_incidents,
    "get_agent_status": get_agent_status,
}

_ALLOWED_PARAMS = {
    "get_logs": {"service", "minutes", "level", "search", "limit"},
    "get_metrics": {"service", "metric_name", "minutes"},
    "get_traces": {"service", "trace_id", "minutes", "errors_only", "limit"},
    "get_deployments": {"service", "minutes"},
    "get_incidents": {"service", "status", "limit"},
    "get_agent_status": {"service", "host"},
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
