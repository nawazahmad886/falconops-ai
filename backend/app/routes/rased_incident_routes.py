"""
RASED Phase 5 routes: incident trigger, feed, detail, SSE trace stream,
approve/reject, and value-card metrics. Prefix /api/v1/rased, distinct from
Phase 0's /api/rased/scenarios admin routes.

trigger_incident() persists the initial state synchronously, then drives the
graph in a background asyncio task — the request returns immediately with an
incident_id, and the SSE stream is how a client watches it progress. This
route file is downstream of every LangGraph-API-surface risk already flagged
in graph/checkpointer.py, graph/workflow.py, graph/runner.py, and
agents/action.py — none of that is re-flagged per call site here, see those
modules for the specifics.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..models.rased_schemas import Alert, InvestigationState
from ..services.rased.config import EXECUTION_MODE
from ..services.rased.graph.runner import resume_investigation, run_investigation
from ..services.rased.graph.trace import REDIS_CHANNEL_PREFIX
from ..utils.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rased", tags=["RASED Incidents"])


class TriggerAlertPayload(BaseModel):
    """KeepHQ-shaped webhook payload — one alert per call. RASED's own
    orchestrator handles dedup/storm grouping server-side, so the webhook
    contract stays flat rather than requiring the caller to pre-batch."""
    alert_id: Optional[str] = None
    signature: str
    source: str
    service: str
    host: Optional[str] = None
    severity: str
    title: str
    description: str
    tenant_id: Optional[str] = None
    raw: Dict[str, Any] = {}


async def _persist_state(state: InvestigationState) -> None:
    from ..core.database import db
    doc = state.model_dump()
    doc["updated_at"] = datetime.now(timezone.utc)
    await db.rased_investigations.update_one({"incident_id": state.incident_id}, {"$set": doc}, upsert=True)


async def _drive_and_persist(initial_state: InvestigationState) -> None:
    try:
        final_state = await run_investigation(initial_state)
    except Exception as exc:
        logger.exception(f"rased investigation {initial_state.incident_id} failed")
        final_state = initial_state.model_copy(update={"status": "escalated", "error": str(exc)})
    await _persist_state(final_state)


@router.post("/incidents/trigger")
async def trigger_incident(payload: TriggerAlertPayload, current_user: dict = Depends(require_auth)):
    incident_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id=payload.alert_id or f"{incident_id}-alert-01",
        signature=payload.signature, source=payload.source, service=payload.service,
        host=payload.host, severity=payload.severity, title=payload.title,
        description=payload.description, tenant_id=payload.tenant_id,
        observed_at=now, raw=payload.raw,
    )
    initial_state = InvestigationState(
        incident_id=incident_id, tenant_id=payload.tenant_id, execution_mode=EXECUTION_MODE,
        alerts=[alert], created_at=now, updated_at=now,
    )

    await _persist_state(initial_state)
    asyncio.create_task(_drive_and_persist(initial_state))

    return {"incident_id": incident_id, "status": initial_state.status, "execution_mode": EXECUTION_MODE}


@router.get("/incidents")
async def list_incidents(limit: int = 50, current_user: dict = Depends(require_auth)):
    from ..core.database import db
    docs = await db.rased_investigations.find({}, {"_id": 0}).sort("updated_at", -1).limit(limit).to_list(limit)
    return {"incidents": docs}


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, current_user: dict = Depends(require_auth)):
    from ..core.database import db
    doc = await db.rased_investigations.find_one({"incident_id": incident_id}, {"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Unknown incident_id: {incident_id}")
    return doc


async def _get_redis():
    from ..services.metrics_timeseries_service import metrics_timeseries_service
    return await metrics_timeseries_service.get_redis()


@router.get("/incidents/{incident_id}/stream")
async def stream_incident(incident_id: str, request: Request, current_user: dict = Depends(require_auth)):
    """SSE: replays db.rased_trace history for this incident first (a
    reconnecting client just replays from Mongo again — no gap, some
    duplication is acceptable for a demo trace feed), then follows new
    events published to Redis. Ends the stream if Redis is unavailable
    rather than hanging open with nothing to send."""

    async def event_generator():
        from ..core.database import db

        cursor = db.rased_trace.find({"incident_id": incident_id}, {"_id": 0}).sort("seq", 1)
        async for doc in cursor:
            if await request.is_disconnected():
                return
            yield {"event": "trace", "data": json.dumps(doc, default=str)}

        redis_client = await _get_redis()
        if redis_client is None:
            yield {"event": "end", "data": json.dumps({"reason": "no_redis_live_feed"})}
            return

        pubsub = redis_client.pubsub()
        channel = f"{REDIS_CHANNEL_PREFIX}{incident_id}"
        await pubsub.subscribe(channel)
        try:
            while True:
                if await request.is_disconnected():
                    return
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if message and message.get("type") == "message":
                    yield {"event": "trace", "data": message["data"]}
        finally:
            await pubsub.unsubscribe(channel)

    return EventSourceResponse(event_generator())


class ApprovalDecisionPayload(BaseModel):
    reason: Optional[str] = None


async def _decide(incident_id: str, approved: bool, reason: Optional[str], decided_by: str) -> Dict[str, Any]:
    from ..core.database import db
    doc = await db.rased_investigations.find_one({"incident_id": incident_id}, {"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Unknown incident_id: {incident_id}")
    if doc.get("status") != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"incident {incident_id} is not awaiting approval (status={doc.get('status')})",
        )

    try:
        final_state = await resume_investigation(
            incident_id, {"approved": approved, "reason": reason, "decided_by": decided_by},
        )
    except Exception as exc:
        logger.exception(f"rased resume failed for {incident_id}")
        raise HTTPException(status_code=500, detail=f"failed to resume investigation: {exc}")

    await _persist_state(final_state)
    return {"incident_id": incident_id, "status": final_state.status, "approved": approved}


@router.post("/incidents/{incident_id}/approve")
async def approve_incident_action(
    incident_id: str, payload: ApprovalDecisionPayload, current_user: dict = Depends(require_auth),
):
    # ActionAgent (agents/action.py) only ever interrupts for DESTRUCTIVE-tier
    # actions — status=="awaiting_approval" implies DESTRUCTIVE by construction,
    # no need to separately inspect the pending action's tier here. Rejecting
    # doesn't need this higher bar (declining a risky action is the safe
    # direction); only approving one does.
    from ..services.rbac_service import check_permission
    if not await check_permission(current_user, "remediation.approve_destructive"):
        raise HTTPException(status_code=403, detail="requires remediation.approve_destructive permission")
    return await _decide(incident_id, approved=True, reason=payload.reason, decided_by=current_user.get("email", "unknown"))


@router.post("/incidents/{incident_id}/reject")
async def reject_incident_action(
    incident_id: str, payload: ApprovalDecisionPayload, current_user: dict = Depends(require_auth),
):
    return await _decide(incident_id, approved=False, reason=payload.reason, decided_by=current_user.get("email", "unknown"))


@router.get("/metrics")
async def get_rased_metrics(current_user: dict = Depends(require_auth)):
    """Value-card numbers computed from actual run data, not hardcoded."""
    from ..core.database import db

    total = await db.rased_investigations.count_documents({})
    suppressed = await db.rased_investigations.count_documents({"status": "suppressed"})
    resolved = await db.rased_investigations.count_documents({"status": "resolved"})
    escalated = await db.rased_investigations.count_documents({"status": "escalated"})

    actions_auto_executed = 0
    async for doc in db.rased_investigations.find(
        {"action_results": {"$exists": True, "$ne": []}}, {"_id": 0, "action_results": 1},
    ):
        actions_auto_executed += len(doc.get("action_results", []))

    return {
        "execution_mode": EXECUTION_MODE,
        "total_investigations": total,
        "suppressed": suppressed,
        "resolved": resolved,
        "escalated": escalated,
        "actions_auto_executed": actions_auto_executed,
        "alerts_suppressed_pct": round((suppressed / total) * 100, 1) if total else 0.0,
    }


__all__ = ["router"]
