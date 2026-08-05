"""
Live evidence adapter — reads REAL LLM cost/token/latency/cache data from
db.ai_monitoring_events instead of RASED's seeded synthetic scenario data.
Same swap-the-adapter-class pattern as oneagent_live.py (this session's prior
pass) — RASED's own documented extension point for a live variant.

Selected the same way: TelemetryRetrievalAgent fans params (now including
service/host, see agents/telemetry.py) out to every registered adapter
concurrently. For a synthetic-scenario investigation this adapter simply
finds no matching model/service/provider and returns success=False with an
honest reason — never a fabricated reading. For an investigation whose alert
is actually about an AI/LLM service (service name matches a model/provider
seen in ai_monitoring_events, or params.get("service") names one directly),
it returns real, current cost/token/latency/cache evidence.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from ....models.rased_schemas import Source, ToolResult
from .base import Adapter

LOOKBACK_HOURS = 1


class LLMObservabilityLiveAdapter(Adapter):
    source: Source = "llm_live"

    async def query(self, params: Dict[str, Any]) -> ToolResult:
        from ....core.database import db

        started = datetime.now(timezone.utc)
        service = params.get("service")
        host = params.get("host")
        target = service or host

        if not target:
            return ToolResult(
                source=self.source, query="no service/host in investigation params",
                success=False, data=None, error="no service or host to scope a live LLM observability query to",
                latency_ms=0, retrieved_at=datetime.now(timezone.utc),
            )

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
        # Match on model, provider, or source field containing the target —
        # service names in this codebase are often the model/provider itself
        # (e.g. an "openai" or "gpt-4o" service in an AI-feature incident).
        query = {
            "received_at": {"$gte": cutoff},
            "$or": [{"model": target}, {"provider": target}, {"source": {"$regex": target, "$options": "i"}}],
        }
        events = await db.ai_monitoring_events.find(
            query, {"_id": 0, "model": 1, "provider": 1, "latency_ms": 1, "tokens_total": 1, "tokens_input": 1,
                     "tokens_output": 1, "cached_tokens": 1, "estimated_cost_usd": 1, "cache_savings_usd": 1,
                     "errored": 1, "received_at": 1, "trace_id": 1},
        ).sort("received_at", -1).limit(50).to_list(50)

        if not events:
            return ToolResult(
                source=self.source, query=f"ai_monitoring_events target={target!r} last {LOOKBACK_HOURS}h",
                success=False, data=None,
                error=f"no LLM observability data for '{target}' in the last {LOOKBACK_HOURS}h — "
                      "either not an AI/LLM service, or no recent traffic",
                latency_ms=self._elapsed_ms(started), retrieved_at=datetime.now(timezone.utc),
            )

        errored_count = sum(1 for e in events if e.get("errored"))
        costs = [e["estimated_cost_usd"] for e in events if e.get("estimated_cost_usd") is not None]
        latencies = [e["latency_ms"] for e in events if e.get("latency_ms") is not None]

        return ToolResult(
            source=self.source, query=f"ai_monitoring_events target={target!r} last {LOOKBACK_HOURS}h",
            success=True,
            data={
                "target": target, "event_count": len(events), "errored_count": errored_count,
                "error_rate_pct": round(100 * errored_count / len(events), 1),
                "total_cost_usd": round(sum(costs), 6) if costs else None,
                "priced_event_count": len(costs),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
                "recent_events": events[:10],
                "note": "real, currently-collected LLM observability telemetry, not synthetic scenario data",
            },
            latency_ms=self._elapsed_ms(started), retrieved_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _elapsed_ms(started: datetime) -> int:
        return int((datetime.now(timezone.utc) - started).total_seconds() * 1000)


__all__ = ["LLMObservabilityLiveAdapter"]
