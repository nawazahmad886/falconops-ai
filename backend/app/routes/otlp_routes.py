"""
FalconOps AI — OTLP HTTP Ingestion
Accepts OpenTelemetry OTLP/HTTP JSON payloads from customer APM agents (traces,
metrics, logs) and stores them for real use elsewhere in the platform:
  - traces  → db.otel_spans / db.otel_traces, plus auto-discovered service
              dependency edges in both db.service_dependencies and
              db.topology_nodes/db.topology_edges (the latter feeds
              smart_correlation_engine.py / ai_correlation.py's topology-aware
              alert correlation).
  - metrics → real datapoint values (gauge/sum/histogram/summary) into
              db.metrics_timeseries, the same store anomaly_detection_engine.py
              reads — not just a discarded counter.
  - logs    → db.otel_logs for the existing log analyzer.

Endpoints:
  POST /v1/traces
  POST /v1/metrics
  POST /v1/logs

Only OTLP/HTTP+JSON is supported (not protobuf/gRPC), so exporters must be
configured with OTEL_EXPORTER_OTLP_PROTOCOL=http/json.
"""
import logging
import uuid
import jwt
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Request, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..core.database import db
from ..core.config import JWT_SECRET, JWT_ALGORITHM
from ..utils.auth import require_auth
from ..services import trace_rca_service, trace_alert_engine, call_flow_broadcaster
from ..services.metrics_timeseries_service import metrics_timeseries_service

logger = logging.getLogger(__name__)

# Public OTLP endpoints — under /api/otel/v1 so kubernetes ingress routes them to backend.
# Customer APM agents configure: OTEL_EXPORTER_OTLP_ENDPOINT=https://your-host.com/api/otel
otlp_router = APIRouter(prefix="/api/otel/v1", tags=["OTLP Ingestion"])

# Admin/UI endpoints (under /api)
trace_router = APIRouter(prefix="/api/traces", tags=["Trace Viewer"])


# ─────────────────────────────────────────────────────
#  OTLP span normalisation — moved to trace_persistence_service.py so
#  oneagent_routes.py's trace ingest path can call the exact same
#  persistence logic (see that module's docstring for why).
# ─────────────────────────────────────────────────────

from ..services.trace_persistence_service import (  # noqa: E402
    attr_to_value as _attr_to_value,
    attrs_to_dict as _attrs_to_dict,
    ns_to_iso as _ns_to_iso,
    ns_diff_ms as _ns_diff_ms,
    extract_exception as _extract_exception,
    normalize_span as _normalize_span,
    persist_normalized_spans as _persist_spans,
)


def _numeric_point_value(point: Dict) -> Optional[float]:
    """OTLP numeric data points carry either asDouble or asInt (string)."""
    if "asDouble" in point:
        return point["asDouble"]
    if "asInt" in point:
        try:
            return float(point["asInt"])
        except (TypeError, ValueError):
            return None
    return None


def _normalize_metric_points(body: Dict) -> List[Dict]:
    """Flatten an OTLP/HTTP metrics payload into metrics_timeseries_service.ingest_batch() rows."""
    points: List[Dict] = []
    for resource_metric in body.get("resourceMetrics", []):
        resource_attrs = _attrs_to_dict(resource_metric.get("resource", {}).get("attributes", []))
        service = resource_attrs.get("service.name") or resource_attrs.get("service") or "unknown-service"
        for scope_metric in resource_metric.get("scopeMetrics", []):
            for metric in scope_metric.get("metrics", []):
                name = metric.get("name") or "unknown_metric"
                unit = metric.get("unit", "")

                for dp in (metric.get("gauge") or {}).get("dataPoints", []):
                    value = _numeric_point_value(dp)
                    if value is None:
                        continue
                    points.append({
                        "name": name, "value": value, "unit": unit, "type": "gauge",
                        "timestamp": _ns_to_iso(dp.get("timeUnixNano", "0")),
                        "tags": {"service": service, **_attrs_to_dict(dp.get("attributes") or [])},
                    })

                for dp in (metric.get("sum") or {}).get("dataPoints", []):
                    value = _numeric_point_value(dp)
                    if value is None:
                        continue
                    points.append({
                        "name": name, "value": value, "unit": unit, "type": "counter",
                        "timestamp": _ns_to_iso(dp.get("timeUnixNano", "0")),
                        "tags": {"service": service, **_attrs_to_dict(dp.get("attributes") or [])},
                    })

                for dp in (metric.get("histogram") or {}).get("dataPoints", []):
                    count = dp.get("count", 0) or 0
                    total = dp.get("sum", 0) or 0
                    if not count:
                        continue
                    points.append({
                        "name": name, "value": total / count, "unit": unit, "type": "histogram",
                        "timestamp": _ns_to_iso(dp.get("timeUnixNano", "0")),
                        "tags": {"service": service, "sample_count": count, **_attrs_to_dict(dp.get("attributes") or [])},
                    })

                for dp in (metric.get("summary") or {}).get("dataPoints", []):
                    count = dp.get("count", 0) or 0
                    total = dp.get("sum", 0) or 0
                    if not count:
                        continue
                    points.append({
                        "name": name, "value": total / count, "unit": unit, "type": "summary",
                        "timestamp": _ns_to_iso(dp.get("timeUnixNano", "0")),
                        "tags": {"service": service, "sample_count": count, **_attrs_to_dict(dp.get("attributes") or [])},
                    })
    return points


# ─────────────────────────────────────────────────────
#  OTLP endpoints (public — what APM agents POST to)
# ─────────────────────────────────────────────────────

@otlp_router.post("/traces")
async def otlp_traces(request: Request):
    """Accept OTLP/HTTP traces from any standard OpenTelemetry exporter."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    spans_to_save: List[Dict] = []
    for resource_span in body.get("resourceSpans", []):
        resource_attrs = _attrs_to_dict(resource_span.get("resource", {}).get("attributes", []))
        for scope_span in resource_span.get("scopeSpans", []):
            scope_name = (scope_span.get("scope") or {}).get("name", "")
            for span in scope_span.get("spans", []):
                spans_to_save.append(_normalize_span(span, resource_attrs, scope_name))

    if spans_to_save:
        await _persist_spans(spans_to_save)
    return {"accepted": len(spans_to_save)}


@otlp_router.post("/metrics")
async def otlp_metrics(request: Request):
    """Accept OTLP/HTTP metrics (gauge/sum/histogram/summary) and store real datapoint
    values into the same metrics_timeseries store the anomaly-detection engine reads —
    so metrics collected by real OTel exporters (including OneAgent) actually flow into
    real anomaly detection, not just a discarded counter."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    points = _normalize_metric_points(body)
    if points:
        await metrics_timeseries_service.ingest_batch(points)
    return {"accepted": len(points)}


@otlp_router.post("/logs")
async def otlp_logs(request: Request):
    """Accept OTLP/HTTP logs and write to event_data for the existing analyser."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    logs_to_save: List[Dict] = []
    for resource_log in body.get("resourceLogs", []):
        resource_attrs = _attrs_to_dict(resource_log.get("resource", {}).get("attributes", []))
        service = resource_attrs.get("service.name") or "unknown-service"
        for scope_log in resource_log.get("scopeLogs", []):
            for log_record in scope_log.get("logRecords", []):
                body_val = log_record.get("body", {}).get("stringValue", "")
                severity = log_record.get("severityText") or "INFO"
                doc = {
                    "id": str(uuid.uuid4()),
                    "timestamp": _ns_to_iso(log_record.get("timeUnixNano", "0")),
                    "service": service,
                    "severity": severity,
                    "body": body_val,
                    "attributes": _attrs_to_dict(log_record.get("attributes", [])),
                    "received_at": datetime.now(timezone.utc).isoformat(),
                }
                # OTel LogRecords carry trace_id/span_id at the top level per spec —
                # previously silently dropped here even though real exporters send
                # them, breaking Trace<->Log navigation. Real correlation only:
                # absent when the exporter didn't attach one, never invented.
                if log_record.get("traceId"):
                    doc["trace_id"] = log_record["traceId"]
                if log_record.get("spanId"):
                    doc["span_id"] = log_record["spanId"]
                logs_to_save.append(doc)
    if logs_to_save:
        await db.otel_logs.insert_many(logs_to_save, ordered=False)
    return {"accepted": len(logs_to_save)}


# ─────────────────────────────────────────────────────
#  Trace Viewer endpoints (under /api/traces — auth required)
# ─────────────────────────────────────────────────────

@trace_router.get("")
async def list_traces(
    hours: int = Query(1, ge=1, le=8760),  # up to 1 year
    service: Optional[str] = None,
    status: Optional[str] = Query(None, regex="^(OK|ERROR)$"),
    limit: int = Query(100, le=500),
    user: dict = Depends(require_auth),
):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    # Filter on received_at (when we got it) instead of start_time (which is the app's clock)
    q: Dict = {"received_at": {"$gte": cutoff}}
    if service:
        q["services"] = service
    if status:
        q["status"] = status
    cursor = db.otel_traces.find(q, {"_id": 0}).sort("received_at", -1).limit(limit)
    traces = await cursor.to_list(length=limit)
    return {"traces": traces, "count": len(traces)}


@trace_router.get("/{trace_id}")
async def get_trace(trace_id: str, user: dict = Depends(require_auth)):
    trace = await db.otel_traces.find_one({"trace_id": trace_id}, {"_id": 0})
    if not trace:
        raise HTTPException(404, "Trace not found")
    spans = await db.otel_spans.find({"trace_id": trace_id}, {"_id": 0}).sort("start_time", 1).to_list(length=2000)
    # Build span tree
    by_id = {s["span_id"]: {**s, "children": []} for s in spans}
    roots = []
    for s in by_id.values():
        if s["parent_span_id"] and s["parent_span_id"] in by_id:
            by_id[s["parent_span_id"]]["children"].append(s)
        else:
            roots.append(s)
    return {"trace": trace, "spans": spans, "tree": roots}


@trace_router.get("/services/list")
async def list_services(user: dict = Depends(require_auth)):
    services = await db.otel_traces.distinct("services")
    return {"services": [s for s in services if s]}


async def _service_latency_metrics(cutoff: str) -> Dict[str, Dict[str, Any]]:
    """Per-service latency + error rate, grouped directly from real otel_spans in the
    given window — same sorted-percentile style trace_rca_service.analyze_window uses
    for (service, operation) groups, just rolled up per-service instead."""
    spans = await db.otel_spans.find(
        {"received_at": {"$gte": cutoff}},
        {"_id": 0, "service": 1, "duration_ms": 1, "status": 1},
    ).to_list(length=20000)

    by_service: Dict[str, Dict[str, Any]] = {}
    for s in spans:
        name = s.get("service")
        if not name:
            continue
        g = by_service.setdefault(name, {"durations": [], "errors": 0})
        g["durations"].append(s.get("duration_ms") or 0)
        if s.get("status") == "ERROR":
            g["errors"] += 1

    metrics: Dict[str, Dict[str, Any]] = {}
    for name, g in by_service.items():
        durations = sorted(g["durations"])
        n = len(durations)
        p95 = durations[max(0, int(n * 0.95) - 1)] if durations else 0
        metrics[name] = {
            "call_count": n,
            "error_count": g["errors"],
            "error_rate_pct": round((g["errors"] / n) * 100, 2) if n else 0,
            "avg_latency_ms": round(sum(durations) / n, 2) if n else 0,
            "p95_latency_ms": round(p95, 2),
        }
    return metrics


@trace_router.get("/services/dependencies")
async def list_dependencies(hours: int = Query(24, ge=1, le=168),
                            user: dict = Depends(require_auth)):
    """Real service dependency graph auto-built from incoming trace parent/child spans,
    with per-node latency/error% computed from real span durations in the same window —
    powers the Service Map's node badges (previously call/error count only)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    cursor = db.service_dependencies.find({"last_seen": {"$gte": cutoff}}, {"_id": 0})
    edges = await cursor.to_list(length=2000)
    node_names = {s for e in edges for s in (e.get("service"), e.get("depends_on")) if s}

    node_metrics = await _service_latency_metrics(cutoff)
    empty_metrics = {"call_count": 0, "error_count": 0, "error_rate_pct": 0,
                      "avg_latency_ms": 0, "p95_latency_ms": 0}
    nodes = [{"name": name, **node_metrics.get(name, empty_metrics)} for name in node_names]

    return {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}


# ─────────────────────────────────────────────────────
#  Live Call Flow — WebSocket push of real-time cross-service call events
# ─────────────────────────────────────────────────────

async def _call_flow_authenticate(ws: WebSocket) -> bool:
    """Lightweight token gate — pass `?token=<jwt>` to authenticate, same
    pattern as /api/ai-monitoring/live."""
    token = ws.query_params.get("token") or ""
    if not token:
        await ws.send_json({"type": "error", "error": "missing token"})
        await ws.close()
        return False
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        await ws.send_json({"type": "error", "error": "invalid token"})
        await ws.close()
        return False
    return True


call_flow_broadcaster.call_flow_manager.authenticate = _call_flow_authenticate


@trace_router.websocket("/live")
async def call_flow_live(ws: WebSocket):
    """WebSocket: one message per real cross-service span detected during
    trace ingestion (see the broadcast call inside
    trace_persistence_service.persist_normalized_spans, shared by both the
    OTLP and OneAgent ingest paths). No initial-state replay — the base graph is served by
    GET /api/traces/services/dependencies on page load; individual call
    events are inherently transient."""
    if not await call_flow_broadcaster.call_flow_manager.connect(ws):
        return
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await call_flow_broadcaster.call_flow_manager.disconnect(ws)


@trace_router.get("/services/{service_name}/correlation")
async def service_correlation(service_name: str, hours: int = Query(24, ge=1, le=168),
                              user: dict = Depends(require_auth)):
    """Drill-down for one service-map node: its own latency/error metrics, its real
    upstream callers + downstream dependencies (from service_dependencies), and recent
    traces that pass through it anywhere in their call chain — click one of those
    traces and GET /api/traces/{trace_id} renders the actual source-to-destination
    span waterfall through the backend."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    upstream = await db.service_dependencies.find(
        {"depends_on": service_name, "last_seen": {"$gte": cutoff}}, {"_id": 0}
    ).to_list(length=200)
    downstream = await db.service_dependencies.find(
        {"service": service_name, "last_seen": {"$gte": cutoff}}, {"_id": 0}
    ).to_list(length=200)

    node_metrics = (await _service_latency_metrics(cutoff)).get(service_name, {
        "call_count": 0, "error_count": 0, "error_rate_pct": 0,
        "avg_latency_ms": 0, "p95_latency_ms": 0,
    })

    recent_traces = await db.otel_traces.find(
        {"services": service_name, "received_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("received_at", -1).limit(20).to_list(length=20)

    return {
        "service": service_name,
        "node_metrics": node_metrics,
        "upstream": upstream,
        "downstream": downstream,
        "recent_traces": recent_traces,
    }


async def _service_error_breakdown(service_name: str, minutes: int = 120) -> Dict[str, Any]:
    """Real per-operation error breakdown for one service, grouped by exception type
    when the instrumented app actually recorded one (see _extract_exception) —
    otherwise honestly reports no exception detail rather than inventing a message."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    spans = await db.otel_spans.find(
        {"service": service_name, "status": "ERROR", "received_at": {"$gte": cutoff}},
        {"_id": 0, "operation": 1, "exception_type": 1, "exception_message": 1, "start_time": 1},
    ).to_list(5000)

    groups: Dict[Any, Dict[str, Any]] = {}
    any_detail = False
    for s in spans:
        key = (s.get("operation"), s.get("exception_type"))
        g = groups.setdefault(key, {"count": 0, "sample_message": None, "last_seen": None})
        g["count"] += 1
        if s.get("exception_type"):
            any_detail = True
            if not g["sample_message"] and s.get("exception_message"):
                g["sample_message"] = s["exception_message"][:500]
        if not g["last_seen"] or (s.get("start_time") or "") > g["last_seen"]:
            g["last_seen"] = s.get("start_time")

    rows = [
        {"operation": op, "exception_type": exc_type, "count": g["count"],
         "sample_message": g["sample_message"], "last_seen": g["last_seen"]}
        for (op, exc_type), g in groups.items()
    ]
    rows.sort(key=lambda r: r["count"], reverse=True)
    return {"service": service_name, "count": len(spans), "errors": rows, "detail_available": any_detail}


async def _service_health_score(service_name: str, hours: int = 1) -> Dict[str, Any]:
    """Real weighted-composite service health score — same shape as
    executive_routes._compute_security_score, but any component with no real signal for
    this service is dropped from the average (never defaulted/fabricated), and the
    response says exactly which components were actually available."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    metrics = (await _service_latency_metrics(cutoff)).get(service_name)

    components: Dict[str, float] = {}

    if metrics and metrics.get("call_count"):
        components["latency"] = round(max(0.0, 100 - (metrics.get("avg_latency_ms") or 0) / 20), 1)
        components["error_rate"] = round(max(0.0, 100 - (metrics.get("error_rate_pct") or 0) * 5), 1)

    upstream = await db.service_dependencies.find({"depends_on": service_name}, {"_id": 0}).to_list(200)
    downstream = await db.service_dependencies.find({"service": service_name}, {"_id": 0}).to_list(200)
    edge_error_rates = [
        (e.get("error_count", 0) / e["call_count"]) * 100
        for e in (upstream + downstream) if e.get("call_count")
    ]
    if edge_error_rates:
        avg_edge_error = sum(edge_error_rates) / len(edge_error_rates)
        components["dependency_health"] = round(max(0.0, 100 - avg_edge_error * 5), 1)

    try:
        from ..services.capacity_prediction_engine import capacity_prediction_engine
        alerts = await capacity_prediction_engine.get_capacity_alerts()
        matched = [a for a in alerts if service_name.lower() in (a.get("host") or "").lower()]
        if matched:
            risk_penalty = {"critical": 40, "high": 25, "medium": 10}
            penalty = max(risk_penalty.get(a.get("risk_level"), 0) for a in matched)
            components["capacity_risk"] = round(max(0.0, 100 - penalty), 1)
    except Exception as e:
        logger.debug(f"Capacity component skipped for {service_name}: {e}")

    if not components:
        return {"composite_score": None, "components": {}, "available_components": [],
                "note": "No real signal available for this service in the selected window."}

    composite = round(sum(components.values()) / len(components), 1)
    return {"composite_score": composite, "components": components,
            "available_components": list(components.keys())}


@trace_router.get("/services/{service_name}/operations")
async def service_operations(service_name: str, minutes: int = Query(60, ge=1, le=10080),
                             limit: int = Query(15, le=50),
                             user: dict = Depends(require_auth)):
    """Per-operation (endpoint) latency + error stats for one service — thin route over
    the same ai_tools_service.get_api_operation_stats tool the AI agents use, so the
    Transactions tab and the agents see identical numbers."""
    from ..services import ai_tools_service
    result = await ai_tools_service.get_api_operation_stats(service=service_name, minutes=minutes, limit=limit)
    return {"service": service_name, "operations": result.get("data", []), "count": result.get("count", 0)}


@trace_router.get("/services/{service_name}/errors")
async def service_errors(service_name: str, minutes: int = Query(120, ge=1, le=10080),
                         user: dict = Depends(require_auth)):
    """Real per-operation error breakdown for one service — see _service_error_breakdown."""
    return await _service_error_breakdown(service_name, minutes)


@trace_router.get("/services/{service_name}/health-score")
async def service_health_score(service_name: str, hours: int = Query(1, ge=1, le=168),
                               user: dict = Depends(require_auth)):
    """Real weighted-composite health score for one service — see _service_health_score."""
    return await _service_health_score(service_name, hours)


@trace_router.get("/services/{service_name}/overview")
async def service_overview(service_name: str, hours: int = Query(1, ge=1, le=168),
                           user: dict = Depends(require_auth)):
    """One-call aggregator for the Service Detail Page header: real latency/error
    metrics, health score, recent error counts, and dependency counts."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    metrics = (await _service_latency_metrics(cutoff)).get(service_name, {
        "call_count": 0, "error_count": 0, "error_rate_pct": 0,
        "avg_latency_ms": 0, "p95_latency_ms": 0,
    })
    health = await _service_health_score(service_name, hours)
    error_breakdown = await _service_error_breakdown(service_name, hours * 60)
    upstream_count = await db.service_dependencies.count_documents({"depends_on": service_name})
    downstream_count = await db.service_dependencies.count_documents({"service": service_name})

    return {
        "service": service_name,
        "metrics": metrics,
        "health": health,
        "recent_error_groups": len(error_breakdown["errors"]),
        "recent_errors_total": error_breakdown["count"],
        "upstream_count": upstream_count,
        "downstream_count": downstream_count,
    }


@trace_router.get("/services/{service_name}/root-cause")
async def service_root_cause(service_name: str, hours: int = Query(2, ge=1, le=168),
                             user: dict = Depends(require_auth)):
    """On-demand AI root cause for one service — reuses the existing single-shot RCA
    engine (intelligence_agents_service.incident_analysis) scoped to this service,
    without requiring a pre-existing incident."""
    from ..services.intelligence_agents_service import incident_analysis
    return await incident_analysis(
        query=f"Why is {service_name} slow or erroring?", service=service_name,
        time_range_minutes=hours * 60, user=user,
    )


@trace_router.get("/services/{service_name}/recommendations")
async def service_recommendations(service_name: str, user: dict = Depends(require_auth)):
    """On-demand AI recommendations for one service — reuses the existing
    api_performance ops agent (no new agent logic)."""
    from ..services.ops_agents_service import run_ops_agent
    result = await run_ops_agent(
        "api_performance", f"What should we do to improve {service_name}'s performance and reliability?",
        tenant_id=user.get("tenant_id"),
    )
    return result or {"summary": "Ops agent unavailable", "recommended_actions": []}


@trace_router.get("/stats/summary")
async def trace_stats(hours: int = Query(1, ge=1, le=8760), user: dict = Depends(require_auth)):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    pipeline = [
        {"$match": {"received_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "errors": {"$sum": {"$cond": [{"$eq": ["$status", "ERROR"]}, 1, 0]}},
            "avg_duration": {"$avg": "$duration_ms"},
            "max_duration": {"$max": "$duration_ms"},
            "total_spans": {"$sum": "$span_count"},
        }},
    ]
    stats = {"total": 0, "errors": 0, "avg_duration": 0, "max_duration": 0, "total_spans": 0}
    async for r in db.otel_traces.aggregate(pipeline):
        r.pop("_id", None)
        stats.update(r)
    stats["error_rate_pct"] = round((stats["errors"] / stats["total"]) * 100, 2) if stats["total"] else 0

    # Real p95, not $avg mislabeled as p95 — same bounded-fetch-then-sort approach
    # trace_rca_service.analyze_window() already uses for the same collection.
    durations = sorted([
        d["duration_ms"] or 0 for d in await db.otel_traces.find(
            {"received_at": {"$gte": cutoff}}, {"_id": 0, "duration_ms": 1},
        ).to_list(length=10000)
    ])
    stats["p95_duration"] = durations[max(0, int(len(durations) * 0.95) - 1)] if durations else 0

    services = await db.otel_traces.distinct("services", {"received_at": {"$gte": cutoff}})
    stats["services_count"] = len([s for s in services if s])
    return stats


# ─────────────────────────────────────────────────────
#  Trace RCA (AI-powered)
# ─────────────────────────────────────────────────────

@trace_router.post("/{trace_id}/rca")
async def trace_rca(trace_id: str, user: dict = Depends(require_auth)):
    """Run the AI-powered root cause analysis pipeline on this trace."""
    report = await trace_rca_service.analyze_trace(trace_id)
    if "error" in report:
        raise HTTPException(404, report["error"])
    return report


@trace_router.get("/anomalies/report")
async def trace_anomaly_report(
    hours: int = Query(24, ge=1, le=720),
    user: dict = Depends(require_auth),
):
    """Bulk AI anomaly report across all traces in the time window."""
    return await trace_rca_service.analyze_window(hours=hours)


# ─────────────────────────────────────────────────────
#  Trace-driven alert rules
# ─────────────────────────────────────────────────────

class TraceAlertRule(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    service: str
    operation: Optional[str] = None
    rule_type: str = "latency"           # latency | error_rate
    threshold_ms: Optional[float] = 0
    threshold_pct: Optional[float] = 0
    metric: str = "p95"                   # p95 | avg | max (latency only)
    window_minutes: int = 5
    min_traces: int = 5
    severity: str = "high"
    enabled: bool = True
    tenant_id: Optional[str] = None


trace_alerts_router = APIRouter(prefix="/api/traces/alert-rules", tags=["Trace Alerts"])


@trace_alerts_router.get("")
async def list_alert_rules(tenant_id: Optional[str] = None, user: dict = Depends(require_auth)):
    rules = await trace_alert_engine.list_rules(tenant_id)
    return {"rules": rules, "count": len(rules)}


@trace_alerts_router.post("")
async def create_alert_rule(rule: TraceAlertRule, user: dict = Depends(require_auth)):
    try:
        saved = await trace_alert_engine.upsert_rule(rule.model_dump(exclude_unset=False))
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    return saved


@trace_alerts_router.put("/{rule_id}")
async def update_alert_rule(rule_id: str, rule: TraceAlertRule, user: dict = Depends(require_auth)):
    try:
        payload = rule.model_dump(exclude_unset=False)
        payload["id"] = rule_id
        saved = await trace_alert_engine.upsert_rule(payload)
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    return saved


@trace_alerts_router.delete("/{rule_id}")
async def delete_alert_rule(rule_id: str, user: dict = Depends(require_auth)):
    deleted = await trace_alert_engine.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(404, "Rule not found")
    return {"deleted": True, "id": rule_id}


@trace_alerts_router.post("/evaluate")
async def evaluate_now(user: dict = Depends(require_auth)):
    """Manually trigger evaluation of all enabled rules (admin testing)."""
    return await trace_alert_engine.evaluate_all()

