"""
FalconOps AI — Live Call Flow broadcaster.

Fans out one real-time event per real cross-service span detected during OTLP
trace ingestion (see otlp_routes.py's _persist_spans), so a "Live Call Flow"
UI can animate individual real calls as they happen. No tenant field on the
payload — OTLP trace ingestion has no tenant scoping anywhere in its pipeline
today, so this doesn't invent filtering that doesn't exist elsewhere in it.
"""
from datetime import datetime, timezone
from typing import Optional

from .broadcast_manager import BroadcastManager

call_flow_manager = BroadcastManager(name="call-flow")


async def broadcast_call_event(
    *,
    source: str,
    target: str,
    status: str,
    duration_ms: Optional[float],
    operation: str,
    trace_id: str,
    span_id: str,
) -> None:
    await call_flow_manager.broadcast({
        "type": "call_flow.event",
        "source": source,
        "target": target,
        "status": status,  # "OK" | "ERROR"
        "duration_ms": round(duration_ms or 0.0, 1),
        "operation": operation,
        "trace_id": trace_id,
        "span_id": span_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
