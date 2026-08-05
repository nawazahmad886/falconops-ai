"""
Live evidence adapter — reads REAL data collected by OneAgent instead of
RASED's seeded synthetic scenario data. This is the swap-the-adapter-class
extension point RASED's own architecture already documents (base.py: "Live
variants are new Adapter subclasses selected by config, not a branch inside
[the mock] one") — the first one actually implemented.

Selected the same way every other adapter is: TelemetryRetrievalAgent fans
out params (now including service/host, see agents/telemetry.py) to every
registered adapter concurrently. For a synthetic-scenario investigation this
adapter simply finds no matching host and returns success=False with an
honest reason — it never fabricates a reading. For an investigation whose
alert carries a real `host` that matches a live db.oneagent_agents entry, it
returns real, current metrics/network data.

Scoped to metrics + network for this pass — logs/traces live-adapter parity
is a natural follow-up using the same pattern, not attempted here.
"""
from datetime import datetime, timezone
from typing import Any, Dict

from ....models.rased_schemas import Source, ToolResult
from .base import Adapter


class OneAgentLiveAdapter(Adapter):
    source: Source = "oneagent_live"

    async def query(self, params: Dict[str, Any]) -> ToolResult:
        from ....core.database import db

        started = datetime.now(timezone.utc)
        host = params.get("host")
        service = params.get("service")

        if not host and not service:
            return ToolResult(
                source=self.source, query="no host/service in investigation params",
                success=False, data=None, error="no host or service to scope a live OneAgent query to",
                latency_ms=0, retrieved_at=datetime.now(timezone.utc),
            )

        agent_doc = None
        if host:
            agent_doc = await db.oneagent_agents.find_one({"host": host}, {"_id": 0})
        if agent_doc is None:
            target = host or service
            return ToolResult(
                source=self.source, query=f"oneagent_agents host={host!r}",
                success=False, data=None,
                error=f"no OneAgent reporting for host '{target}' — this investigation has no live telemetry source",
                latency_ms=self._elapsed_ms(started), retrieved_at=datetime.now(timezone.utc),
            )

        metrics_query: Dict[str, Any] = {"tags.host": host}
        if service:
            metrics_query = {"$or": [{"tags.host": host}, {"tags.service": service}]}
        metric_docs = await db.metrics_timeseries.find(
            metrics_query, {"_id": 0, "name": 1, "value": 1, "unit": 1, "timestamp": 1, "tags": 1},
        ).sort("timestamp", -1).limit(50).to_list(50)

        netflow_docs = await db.oneagent_netflows.find(
            {"host": host}, {"_id": 0},
        ).sort("received_at", -1).limit(20).to_list(20)

        return ToolResult(
            source=self.source, query=f"oneagent live: host={host} service={service}",
            success=True,
            data={
                "host": host, "agent_version": agent_doc.get("agent_version"),
                "last_seen": agent_doc.get("last_seen"),
                "recent_metrics": metric_docs, "recent_connections": netflow_docs,
                "note": "real, currently-collected OneAgent telemetry, not synthetic scenario data",
            },
            latency_ms=self._elapsed_ms(started), retrieved_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _elapsed_ms(started: datetime) -> int:
        return int((datetime.now(timezone.utc) - started).total_seconds() * 1000)


__all__ = ["OneAgentLiveAdapter"]
