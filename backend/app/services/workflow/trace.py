"""
Workflow trace emission — a third instance of RASED's TraceRecorder pattern
(db.rased_trace's atomic-seq-counter + best-effort Redis publish + SSE
replay-then-follow), already duplicated once for the unrelated
agentic_trace_service.py. A third, workflow-scoped instance here is
consistent with this project's own no-silent-refactor stance rather than
retroactively extracting a shared base class now.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import ReturnDocument

logger = logging.getLogger(__name__)

REDIS_CHANNEL_PREFIX = "workflow:trace:"


class WorkflowTraceRecorder:
    def __init__(self, execution_id: str):
        self.execution_id = execution_id

    async def emit(
        self, node_id: Optional[str], node_type: Optional[str], kind: str, title: str,
        detail: Optional[Dict[str, Any]] = None, duration_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        seq = await self._next_seq()
        event = {
            "execution_id": self.execution_id, "seq": seq, "node_id": node_id, "node_type": node_type,
            "kind": kind, "title": title, "detail": detail or {}, "duration_ms": duration_ms,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        await self._persist(event)
        await self._publish(event)
        return event

    async def _next_seq(self) -> int:
        from ...core.database import db
        try:
            doc = await db.workflow_trace_counters.find_one_and_update(
                {"execution_id": self.execution_id}, {"$inc": {"seq": 1}},
                upsert=True, return_document=ReturnDocument.AFTER,
            )
            return doc["seq"]
        except Exception as exc:
            logger.warning(f"workflow trace seq counter failed for {self.execution_id}: {exc}")
            return int(datetime.now(timezone.utc).timestamp() * 1000)

    async def _persist(self, event: Dict[str, Any]) -> None:
        from ...core.database import db
        try:
            await db.workflow_trace.insert_one(dict(event))
        except Exception as exc:
            logger.warning(f"workflow trace persist failed for {self.execution_id}: {exc}")

    async def _publish(self, event: Dict[str, Any]) -> None:
        try:
            from ...services.metrics_timeseries_service import metrics_timeseries_service
            redis_client = await metrics_timeseries_service.get_redis()
            if redis_client is None:
                return
            await redis_client.publish(f"{REDIS_CHANNEL_PREFIX}{self.execution_id}", json.dumps(event, default=str))
        except Exception as exc:
            logger.warning(f"workflow trace publish failed for {self.execution_id}: {exc}")


__all__ = ["WorkflowTraceRecorder", "REDIS_CHANNEL_PREFIX"]
