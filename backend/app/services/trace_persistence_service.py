"""
Trace persistence — the single place a batch of normalized spans gets turned
into everything downstream depends on: db.otel_spans, db.otel_traces
summaries, db.service_dependencies edges, live call-flow WebSocket events,
and (via topology_service.auto_discover_from_traces) real db.topology_nodes/
db.topology_edges entries.

Moved out of otlp_routes.py (where it originated as _persist_spans) so
oneagent_routes.py's trace ingest path can call the exact same logic instead
of maintaining its own narrower, divergent persistence — previously,
spans arriving via OneAgent never built topology edges or service
dependencies, only directly-OTLP-exported spans did, even though both land
in the same collections. Behavior for the existing OTLP call site is
unchanged: same function bodies, just relocated so both ingest paths can
share them without routes-importing-routes.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def attr_to_value(attr: Dict) -> Any:
    """OTel attributes are wrapped in {key, value:{stringValue|intValue|...}}."""
    v = attr.get("value", {})
    for k in ("stringValue", "intValue", "boolValue", "doubleValue"):
        if k in v:
            return v[k]
    if "arrayValue" in v:
        return [attr_to_value({"value": x}) for x in v["arrayValue"].get("values", [])]
    return None


def attrs_to_dict(attrs: List[Dict]) -> Dict:
    return {a["key"]: attr_to_value(a) for a in attrs or []}


def ns_to_iso(ns_str: str) -> str:
    """OTLP timestamps are nanoseconds since epoch as strings."""
    try:
        ns = int(ns_str)
        sec = ns / 1_000_000_000
        return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def ns_diff_ms(start_ns: str, end_ns: str) -> float:
    try:
        return (int(end_ns) - int(start_ns)) / 1_000_000
    except Exception:
        return 0.0


def extract_exception(span: Dict) -> Dict[str, Optional[str]]:
    """OTel semantic convention: an exception recorded on a span appears as a span
    event named 'exception' carrying exception.type/exception.message attributes.
    Real data if the instrumented app actually recorded one; None otherwise — never
    fabricated."""
    for event in span.get("events") or []:
        if event.get("name") == "exception":
            attrs = attrs_to_dict(event.get("attributes") or [])
            return {
                "exception_type": attrs.get("exception.type"),
                "exception_message": attrs.get("exception.message"),
            }
    return {"exception_type": None, "exception_message": None}


def normalize_span(span: Dict, resource_attrs: Dict, scope_name: str) -> Dict:
    """Convert one OTLP span to our internal schema."""
    span_attrs = attrs_to_dict(span.get("attributes") or [])
    service = (
        resource_attrs.get("service.name")
        or resource_attrs.get("service")
        or "unknown-service"
    )
    status = (span.get("status") or {}).get("code")
    # Map status code: 0=UNSET 1=OK 2=ERROR
    status_text = "ERROR" if status == 2 else "OK"
    kind_map = {1: "INTERNAL", 2: "SERVER", 3: "CLIENT", 4: "PRODUCER", 5: "CONSUMER"}
    exc = extract_exception(span)
    return {
        "id": str(uuid.uuid4()),
        "trace_id": span.get("traceId"),
        "span_id": span.get("spanId"),
        "parent_span_id": span.get("parentSpanId") or None,
        "service": service,
        "operation": span.get("name") or "unknown",
        "kind": kind_map.get(span.get("kind"), "INTERNAL"),
        "start_time": ns_to_iso(span.get("startTimeUnixNano", "0")),
        "end_time": ns_to_iso(span.get("endTimeUnixNano", "0")),
        "duration_ms": ns_diff_ms(span.get("startTimeUnixNano", "0"),
                                   span.get("endTimeUnixNano", "0")),
        "status": status_text,
        "exception_type": exc["exception_type"],
        "exception_message": exc["exception_message"],
        "attributes": span_attrs,
        "resource": resource_attrs,
        "scope": scope_name,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


def normalized_span_from_oneagent_item(item: Dict, host: str, default_service: str) -> Optional[Dict]:
    """OneAgent's own batch shape ({service, timestamp, trace_id, span_id,
    parent_span_id, name, duration_ms, status, attributes} — see
    oneagent/pkg/plugins/traces) is already flat/normalized, just under
    slightly different keys than the OTLP-derived shape normalize_span()
    produces. This adapts it into the exact same internal schema so both
    ingest paths can call persist_normalized_spans() with one shared shape."""
    trace_id = item.get("trace_id")
    if not trace_id:
        return None
    start_iso = item.get("timestamp") or datetime.now(timezone.utc).isoformat()
    duration_ms = float(item.get("duration_ms") or 0)
    status_text = "ERROR" if str(item.get("status", "")).upper() == "ERROR" else "OK"
    try:
        start_dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        end_iso = (start_dt.timestamp() + duration_ms / 1000)
        end_iso = datetime.fromtimestamp(end_iso, tz=timezone.utc).isoformat()
    except Exception:
        end_iso = start_iso
    return {
        "id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "span_id": item.get("span_id"),
        "parent_span_id": item.get("parent_span_id") or None,
        "service": item.get("service") or default_service,
        "operation": item.get("name") or "span",
        "kind": "INTERNAL",
        "start_time": start_iso,
        "end_time": end_iso,
        "duration_ms": duration_ms,
        "status": status_text,
        "exception_type": None,
        "exception_message": None,
        "attributes": item.get("attributes") or {},
        "resource": {"host": host, "service.name": item.get("service") or default_service},
        "scope": "oneagent",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


async def persist_normalized_spans(spans: List[Dict]) -> None:
    """Persists a batch of already-normalized spans (normalize_span()'s or
    normalized_span_from_oneagent_item()'s output shape) and derives
    everything downstream from them: trace summaries, service-dependency
    edges, live call-flow broadcast, and real topology auto-discovery."""
    if not spans:
        return
    from .core.database import db
    from . import call_flow_broadcaster
    from .topology_service import topology_service

    await db.otel_spans.insert_many(spans, ordered=False)

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
    trace_pairs: List[Dict] = []
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

        try:
            await call_flow_broadcaster.broadcast_call_event(
                source=parent["service"], target=s["service"], status=s["status"],
                duration_ms=s.get("duration_ms"), operation=s.get("operation") or "",
                trace_id=s["trace_id"], span_id=s["span_id"],
            )
        except Exception as e:
            logger.debug(f"call_flow broadcast failed (non-fatal): {e}")

        edge_key = (parent["service"], s["service"])
        if edge_key in edges_seen:
            continue
        edges_seen.add(edge_key)
        trace_pairs.append({"service": s["service"], "parent_service": parent["service"]})
        await db.service_dependencies.update_one(
            {"service": parent["service"], "depends_on": s["service"]},
            {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()},
             "$setOnInsert": {"first_seen": datetime.now(timezone.utc).isoformat()},
             "$inc": {"call_count": 1, "error_count": 1 if s["status"] == "ERROR" else 0}},
            upsert=True,
        )

    if trace_pairs:
        try:
            await topology_service.auto_discover_from_traces(trace_pairs)
        except Exception as e:
            logger.warning(f"Topology auto-discovery from traces failed (non-fatal): {e}")


__all__ = [
    "attr_to_value", "attrs_to_dict", "ns_to_iso", "ns_diff_ms", "extract_exception",
    "normalize_span", "normalized_span_from_oneagent_item", "persist_normalized_spans",
]
