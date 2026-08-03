"""
Step-by-step execution trace for the Agentic AI Workflow module (Supervisor +
Diagnoser). One run_id per handle_query()/run_diagnoser() invocation; each
real stage of that run emits one event here as it actually happens — this is
not a scripted animation timed to look busy, the events ARE the execution.

Same atomic-counter pattern as RASED's TraceRecorder
(app/services/rased/graph/trace.py): seq is assigned via a Mongo
find_one_and_update $inc rather than an in-memory counter, so concurrent
emits (evidence gathering and future parallel steps) still get distinct,
correctly-ordered seq values.

Three collections, deliberately separate:
- db.agentic_trace          — one document per stage event (this module's core)
- db.agentic_trace_counters — the atomic per-run_id seq counter
- db.agentic_runs           — one document per run: status/result/error, so a
                               late-joining client (or the non-streaming
                               GET /trace/{run_id}) can see the outcome without
                               replaying every event.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import ReturnDocument

from ..core.database import db

logger = logging.getLogger(__name__)


async def start_run() -> str:
    return str(uuid.uuid4())


async def emit(
    run_id: str,
    agent: str,
    stage: str,
    title: str,
    detail: Optional[Dict[str, Any]] = None,
    status: str = "done",
    duration_ms: Optional[int] = None,
) -> None:
    """Never raises — a trace-emission failure must not take down the actual
    agent work it's describing."""
    try:
        counter_doc = await db.agentic_trace_counters.find_one_and_update(
            {"run_id": run_id},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        await db.agentic_trace.insert_one({
            "run_id": run_id,
            "seq": counter_doc["seq"],
            "agent": agent,
            "stage": stage,
            "title": title,
            "detail": detail or {},
            "status": status,
            "duration_ms": duration_ms,
            "at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning("agentic trace emit failed for run %s (%s/%s): %s", run_id, agent, stage, e)


async def list_trace(run_id: str) -> List[Dict[str, Any]]:
    return await db.agentic_trace.find({"run_id": run_id}, {"_id": 0}).sort("seq", 1).to_list(200)


async def list_trace_after(run_id: str, after_seq: int = 0) -> List[Dict[str, Any]]:
    return await db.agentic_trace.find(
        {"run_id": run_id, "seq": {"$gt": after_seq}}, {"_id": 0},
    ).sort("seq", 1).to_list(100)


async def mark_running(run_id: str, kind: str, target: str) -> None:
    await db.agentic_runs.update_one(
        {"run_id": run_id},
        {"$set": {
            "run_id": run_id, "kind": kind, "target": target, "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


async def mark_done(run_id: str, result: Dict[str, Any]) -> None:
    await db.agentic_runs.update_one(
        {"run_id": run_id},
        {"$set": {"status": "done", "result": result, "completed_at": datetime.now(timezone.utc).isoformat()}},
    )


async def mark_error(run_id: str, error: str) -> None:
    await db.agentic_runs.update_one(
        {"run_id": run_id},
        {"$set": {"status": "error", "error": error[:500], "completed_at": datetime.now(timezone.utc).isoformat()}},
    )


async def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return await db.agentic_runs.find_one({"run_id": run_id}, {"_id": 0})


__all__ = [
    "start_run", "emit", "list_trace", "list_trace_after",
    "mark_running", "mark_done", "mark_error", "get_run",
]
