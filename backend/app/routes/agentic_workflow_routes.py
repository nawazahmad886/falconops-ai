"""
FalconOps AI — Agentic AI Workflow API (Phase 1: read path + Copilot at L0)

Every route here is read-only. There is deliberately no POST/execute endpoint
anywhere in this file — action_broker_schema.execute() always raises
NotImplementedError, and the only action-related route is a dry-run preview.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..services import action_broker_schema
from ..services import agentic_trace_service
from ..services import agentic_workflow_service
from ..utils.auth import require_admin, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agentic-workflow", tags=["Agentic AI Workflow"])


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    incident_id: Optional[str] = None


@router.post("/ask")
async def ask(req: AskRequest, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return await agentic_workflow_service.handle_query(req.query, incident_id=req.incident_id, user=user)


@router.get("/diagnose/{service_or_incident}")
async def diagnose(service_or_incident: str, hours: int = Query(24, ge=1, le=168),
                   user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return await agentic_workflow_service.run_diagnoser(service_or_incident, hours=hours, user=user)


# ─────────────────────────────────────────────────────
#  Live pipeline trace — trigger a run in the background, watch its real
#  Supervisor/Diagnoser stage events arrive via SSE. The synchronous /ask and
#  /diagnose/{target} routes above still work unchanged and now also produce
#  a trace (viewable after the fact via GET /trace/{run_id}) — these /trigger
#  routes exist so a client can watch it happen live instead of only seeing
#  the final result.
# ─────────────────────────────────────────────────────

class DiagnoseTriggerRequest(BaseModel):
    service_or_incident: str = Field(..., min_length=1)
    hours: int = Field(24, ge=1, le=168)


async def _run_diagnoser_background(run_id: str, service_or_incident: str, hours: int, user: dict) -> None:
    await agentic_trace_service.mark_running(run_id, "diagnoser", service_or_incident)
    try:
        result = await agentic_workflow_service.run_diagnoser(
            service_or_incident, hours=hours, user=user, run_id=run_id,
        )
        await agentic_trace_service.mark_done(run_id, result)
    except Exception as e:
        logger.exception("agentic diagnoser background run %s failed", run_id)
        await agentic_trace_service.emit(run_id, "system", "error", f"Run failed: {e}", status="error")
        await agentic_trace_service.mark_error(run_id, str(e))


async def _run_ask_background(run_id: str, query: str, incident_id: Optional[str], user: dict) -> None:
    await agentic_trace_service.mark_running(run_id, "supervisor", query)
    try:
        result = await agentic_workflow_service.handle_query(query, incident_id=incident_id, user=user, run_id=run_id)
        await agentic_trace_service.mark_done(run_id, result)
    except Exception as e:
        logger.exception("agentic supervisor background run %s failed", run_id)
        await agentic_trace_service.emit(run_id, "system", "error", f"Run failed: {e}", status="error")
        await agentic_trace_service.mark_error(run_id, str(e))


@router.post("/diagnose/trigger")
async def diagnose_trigger(req: DiagnoseTriggerRequest, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    run_id = await agentic_trace_service.start_run()
    asyncio.create_task(_run_diagnoser_background(run_id, req.service_or_incident, req.hours, user))
    return {"run_id": run_id}


@router.post("/ask/trigger")
async def ask_trigger(req: AskRequest, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    run_id = await agentic_trace_service.start_run()
    asyncio.create_task(_run_ask_background(run_id, req.query, req.incident_id, user))
    return {"run_id": run_id}


@router.get("/trace/{run_id}")
async def get_trace(run_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await agentic_trace_service.list_trace(run_id)
    run = await agentic_trace_service.get_run(run_id)
    if run is None and not events:
        raise HTTPException(404, f"Unknown run_id: {run_id}")
    return {"run_id": run_id, "events": events, "run": run}


@router.get("/trace/{run_id}/stream")
async def stream_trace(run_id: str, request: Request, user: dict = Depends(require_auth)):
    """SSE: polls for new stage events (short-lived runs, single viewer —
    a Redis pub/sub fan-out isn't warranted at this scale, unlike RASED's
    investigation stream). Emits a final 'final' event carrying the run's
    status/result/error once done or errored, then closes."""

    async def event_generator():
        last_seq = 0
        while True:
            if await request.is_disconnected():
                return
            new_events = await agentic_trace_service.list_trace_after(run_id, last_seq)
            for ev in new_events:
                last_seq = ev["seq"]
                yield {"event": "trace", "data": json.dumps(ev, default=str)}

            run = await agentic_trace_service.get_run(run_id)
            if run and run.get("status") in ("done", "error"):
                yield {"event": "final", "data": json.dumps(run, default=str)}
                return

            await asyncio.sleep(0.4)

    return EventSourceResponse(event_generator())


@router.get("/forecast")
async def forecast(
    metric: str = Query("cpu_usage"),
    host: Optional[str] = None,
    service: Optional[str] = None,
    horizon: str = Query("24h", pattern="^(1h|6h|24h|7d|30d)$"),
    user: dict = Depends(require_auth),
) -> Dict[str, Any]:
    return await agentic_workflow_service.run_forecaster(metric, host=host, service=service, horizon=horizon)


@router.get("/blast-radius/{service_name}")
async def blast_radius(service_name: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    tenant_id = user.get("tenant_id")
    result = await agentic_workflow_service.get_blast_radius(service_name, tenant_id=tenant_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/similar-incidents")
async def similar_incidents(q: str, service: Optional[str] = None,
                            user: dict = Depends(require_auth)) -> Dict[str, Any]:
    results = await agentic_workflow_service.find_similar_incidents(q, service=service)
    return {"query": q, "results": results, "count": len(results)}


@router.get("/decision-log")
async def decision_log(limit: int = Query(50, ge=1, le=500), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    rows = await agentic_workflow_service.list_decision_log(limit=limit)
    return {"decisions": rows, "count": len(rows)}


@router.get("/actions")
async def list_actions(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    levels = await action_broker_schema.get_all_autonomy_levels()
    actions = []
    for name, definition in action_broker_schema.ACTION_REGISTRY.items():
        actions.append({**definition.model_dump(), "current_autonomy_level": levels.get(name)})
    return {"actions": actions, "autonomy_levels": action_broker_schema.AUTONOMY_LEVELS}


@router.get("/actions/{name}/dry-run")
async def dry_run_action(name: str, service: Optional[str] = None, instance: Optional[str] = None,
                         user: dict = Depends(require_auth)) -> Dict[str, Any]:
    if name not in action_broker_schema.ACTION_REGISTRY:
        raise HTTPException(404, f"Unknown action '{name}'")
    params = {k: v for k, v in {"service": service, "instance": instance}.items() if v is not None}
    return await action_broker_schema.dry_run(name, params)


class AutonomyLevelRequest(BaseModel):
    level: str


@router.post("/actions/{name}/autonomy-level")
async def set_action_autonomy_level(name: str, req: AutonomyLevelRequest,
                                    user: dict = Depends(require_admin)) -> Dict[str, Any]:
    """The ONLY mutating route in this module — it changes a config value
    (the declared, not-yet-consumed, autonomy level for an action), never
    triggers execution. Admin-only, audit-logged via feature_flags_service."""
    try:
        return await action_broker_schema.set_autonomy_level(name, req.level, user)
    except ValueError as e:
        raise HTTPException(400, str(e))
