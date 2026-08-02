"""
Trace emission for a RASED investigation run.

Every graph node emits one TraceEvent on entry and one on exit, plus one per
tool call. Events are persisted to db.rased_trace (so a finished or resumed
run is inspectable without re-running anything) and published to Redis on a
per-incident channel so Phase 5's SSE endpoint can follow a run live. Redis
is best-effort: metrics_timeseries_service.get_redis() already returns None
rather than raising when Redis is unreachable, and this module follows the
same null-check-and-continue convention rather than failing a run over a
missing dashboard feed.

seq is assigned via an atomic Mongo counter (db.rased_trace_counters), not an
in-memory attribute: LangGraph invokes each node as a separate call, so a
TraceRecorder constructed fresh per node (the normal usage — nodes only
receive `state`, they have nowhere to keep a shared Python object across
calls) cannot rely on in-memory state to stay monotonic. TelemetryRetrievalAgent
also emits concurrently from an asyncio.gather over seven adapters, which
would race a plain read-then-increment counter; findOneAndUpdate's $inc is
atomic at the database level, so concurrent emits still get distinct,
correctly-ordered seq values.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import ReturnDocument

from ....models.rased_schemas import TraceEvent

logger = logging.getLogger(__name__)

REDIS_CHANNEL_PREFIX = "rased:trace:"


class TraceRecorder:
    """Cheap to construct — safe to instantiate fresh in every node. seq
    ordering is guaranteed by the database, not by object lifetime."""

    def __init__(self, incident_id: str):
        self.incident_id = incident_id

    async def emit(
        self,
        agent: str,
        kind: str,
        title: str,
        detail: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> TraceEvent:
        seq = await self._next_seq()
        event = TraceEvent(
            incident_id=self.incident_id,
            seq=seq,
            agent=agent,
            kind=kind,
            title=title,
            detail=detail or {},
            duration_ms=duration_ms,
            at=datetime.now(timezone.utc),
        )
        await self._persist(event)
        await self._publish(event)
        return event

    async def _next_seq(self) -> int:
        from ....core.database import db
        try:
            doc = await db.rased_trace_counters.find_one_and_update(
                {"incident_id": self.incident_id},
                {"$inc": {"seq": 1}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return doc["seq"]
        except Exception as exc:
            logger.warning(f"rased trace seq counter failed for {self.incident_id}: {exc}")
            return int(datetime.now(timezone.utc).timestamp() * 1000)

    async def _persist(self, event: TraceEvent) -> None:
        from ....core.database import db
        try:
            await db.rased_trace.insert_one(event.model_dump())
        except Exception as exc:
            logger.warning(f"rased trace persist failed for {self.incident_id}: {exc}")

    async def _publish(self, event: TraceEvent) -> None:
        try:
            from ...metrics_timeseries_service import metrics_timeseries_service
            redis_client = await metrics_timeseries_service.get_redis()
            if redis_client is None:
                return
            await redis_client.publish(
                f"{REDIS_CHANNEL_PREFIX}{self.incident_id}",
                json.dumps(event.model_dump(mode="json")),
            )
        except Exception as exc:
            logger.warning(f"rased trace publish failed for {self.incident_id}: {exc}")


__all__ = ["TraceRecorder", "REDIS_CHANNEL_PREFIX"]
