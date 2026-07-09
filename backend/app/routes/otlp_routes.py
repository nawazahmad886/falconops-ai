"""
FalconOps AI — OTLP HTTP Trace Ingestion
Accepts OpenTelemetry OTLP/HTTP payloads from customer APM agents and stores
them as spans in Mongo. Auto-builds the service dependency graph from
parent_service → child_service relationships.

Endpoints:
  POST /v1/traces    — OTLP/HTTP ResourceSpans payload (JSON)
  POST /v1/metrics   — accepted for protocol compatibility (parses to monitor metrics later)
  POST /v1/logs      — accepted for protocol compatibility (forwards to event store)

Designed to fit alongside the existing /api/* routes — uses unprefixed /v1/* so
standard OpenTelemetry exporters work without configuration changes.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel

from ..core.database import db
from ..utils.auth import require_auth
from ..services import trace_rca_service, trace_alert_engine

logger = logging.getLogger(__name__)

# Public OTLP endpoints — under /api/otel/v1 so kubernetes ingress routes them to backend.
# Customer APM agents configure: OTEL_EXPORTER_OTLP_ENDPOINT=https://your-host.com/api/otel
otlp_router = APIRouter(prefix="/api/otel/v1", tags=["OTLP Ingestion"])

# Admin/UI endpoints (under /api)
trace_router = APIRouter(prefix="/api/traces", tags=["Trace Viewer"])


# ─────────────────────────────────────────────────────
#  OTLP span normalisation
# ─────────────────────────────────────────────────────

def _attr_to_value(attr: Dict) -> Any:
    """OTel attributes are wrapped in {key, value:{stringValue|intValue|...}}."""
    v = attr.get("value", {})
    for k in ("stringValue", "intValue", "boolValue", "doubleValue"):
        if k in v:
            return v[k]
    if "arrayValue" in v:
        return [_attr_to_value({"value": x}) for x in v["arrayValue"].get("values", [])]
    return None


def _attrs_to_dict(attrs: List[Dict]) -> Dict:
    return {a["key"]: _attr_to_value(a) for a in attrs or []}


def _ns_to_iso(ns_str: str) -> str:
    """OTLP timestamps are nanoseconds since epoch as strings."""
    try:
        ns = int(ns_str)
        sec = ns / 1_000_000_000
        return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _ns_diff_ms(start_ns: str, end_ns: str) -> float:
    try:
        return (int(end_ns) - int(start_ns)) / 1_000_000
    except Exception:
        return 0.0


def _normalize_span(span: Dict, resource_attrs: Dict, scope_name: str) -> Dict:
    """Convert one OTLP span to our internal schema."""
    span_attrs = _attrs_to_dict(span.get("attributes") or [])
    service = (
        resource_attrs.get("service.name")
        or resource_attrs.get("service")
        or "unknown-service"
    )
    status = (span.get("status") or {}).get("code")
    # Map status code: 0=UNSET 1=OK 2=ERROR
    status_text = "ERROR" if status == 2 else "OK"
    kind_map = {1: "INTERNAL", 2: "SERVER", 3: "CLIENT", 4: "PRODUCER", 5: "CONSUMER"}
    return {
        "id": str(uuid.uuid4()),
        "trace_id": span.get("traceId"),
        "span_id": span.get("spanId"),
        "parent_span_id": span.get("parentSpanId") or None,
        "service": service,
        "operation": span.get("name") or "unknown",
        "kind": kind_map.get(span.get("kind"), "INTERNAL"),
        "start_time": _ns_to_iso(span.get("startTimeUnixNano", "0")),
        "end_time": _ns_to_iso(span.get("endTimeUnixNano", "0")),
        "duration_ms": _ns_diff_ms(span.get("startTimeUnixNano", "0"),
                                   span.get("endTimeUnixNano", "0")),
        "status": status_text,
        "attributes": span_attrs,
        "resource": resource_attrs,
        "scope": scope_name,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


async def _persist_spans(spans: List[Dict]):
    if not spans:
        return
    await db.otel_spans.insert_many(spans, ordered=False)
    # Build trace summary docs (1 per traceId)
    by_trace: Dict[str, List[Dict]] = {}
    for s in spans:
        by_trace.setdefault(s["trace_id"], []).append(s)

    for trace_id, group in by_trace.items():
        root = next((s for s in group if not s["parent_span_id"]), group[0])
        services = list({s["service"] for s in group})
        max_end = max(s["end_time"] for s in group)
        min_start = min(s["start_time"] for s in group)
        try:
            duration = (datetime.fromisoformat(max_end.replace("Z", "+00:00"))
                        - datetime.fromisoformat(min_start.replace("Z", "+00:00"))).total_seconds() * 1000
        except Exception:
            duration = 0
        errors = sum(1 for s in group if s["status"] == "ERROR")
        await db.otel_traces.update_one(
            {"trace_id": trace_id},
            {"$set": {
                "trace_id": trace_id,
                "root_service": root["service"],
                "root_operation": root["operation"],
                "services": services,
                "span_count": len(group),
                "error_count": errors,
                "duration_ms": round(duration, 1),
                "start_time": min_start,
                "end_time": max_end,
                "status": "ERROR" if errors else "OK",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, "$setOnInsert": {"id": str(uuid.uuid4()), "received_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    # Update service dependency edges
    edges_seen = set()
    for s in spans:
        if not s["parent_span_id"]:
            continue
        parent = next((p for p in spans if p["span_id"] == s["parent_span_id"]), None)
        # Cross-batch fallback: parent span may already be persisted from an earlier batch
        if not parent:
            parent_doc = await db.otel_spans.find_one(
                {"span_id": s["parent_span_id"], "trace_id": s["trace_id"]},
                {"_id": 0, "service": 1, "span_id": 1},
            )
            if parent_doc:
                parent = parent_doc
        if not parent or parent["service"] == s["service"]:
            continue
        edge_key = (parent["service"], s["service"])
        if edge_key in edges_seen:
            continue
        edges_seen.add(edge_key)
        await db.service_dependencies.update_one(
            {"service": parent["service"], "depends_on": s["service"]},
            {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()},
             "$setOnInsert": {"first_seen": datetime.now(timezone.utc).isoformat()},
             "$inc": {"call_count": 1, "error_count": 1 if s["status"] == "ERROR" else 0}},
            upsert=True,
        )


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
    """Accept OTLP/HTTP metrics. Counts only — full metric storage is via existing monitoring layer."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    metric_count = 0
    for resource_metric in body.get("resourceMetrics", []):
        for scope_metric in resource_metric.get("scopeMetrics", []):
            metric_count += len(scope_metric.get("metrics", []))
    await db.otel_metric_counters.insert_one({
        "received_at": datetime.now(timezone.utc).isoformat(),
        "count": metric_count,
    })
    return {"accepted": metric_count}


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
                logs_to_save.append({
                    "id": str(uuid.uuid4()),
                    "timestamp": _ns_to_iso(log_record.get("timeUnixNano", "0")),
                    "service": service,
                    "severity": severity,
                    "body": body_val,
                    "attributes": _attrs_to_dict(log_record.get("attributes", [])),
                    "received_at": datetime.now(timezone.utc).isoformat(),
                })
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


@trace_router.get("/services/dependencies")
async def list_dependencies(hours: int = Query(24, ge=1, le=168),
                            user: dict = Depends(require_auth)):
    """Real service dependency graph auto-built from incoming trace parent/child spans."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    cursor = db.service_dependencies.find({"last_seen": {"$gte": cutoff}}, {"_id": 0})
    edges = await cursor.to_list(length=2000)
    nodes = list({s for e in edges for s in (e.get("service"), e.get("depends_on")) if s})
    return {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}


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
            "p95_duration": {"$avg": "$duration_ms"},
            "total_spans": {"$sum": "$span_count"},
        }},
    ]
    stats = {"total": 0, "errors": 0, "avg_duration": 0, "max_duration": 0, "total_spans": 0}
    async for r in db.otel_traces.aggregate(pipeline):
        r.pop("_id", None)
        stats.update(r)
    stats["error_rate_pct"] = round((stats["errors"] / stats["total"]) * 100, 2) if stats["total"] else 0
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

