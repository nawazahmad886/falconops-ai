"""AI Operations — Workflow execution routes: run/dry-run/test-run, live
SSE trace (same replay-Mongo-then-follow-Redis pattern as RASED's
rased_incident_routes.py::stream_incident), approvals, observability."""
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..services.workflow import dag_engine, workflow_definition_service, observability_service, approval_service
from ..services.workflow.trace import REDIS_CHANNEL_PREFIX
from ..services.rbac_service import check_permission
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/v1/workflow-executions", tags=["Workflow Executions"])


async def _require(current_user: dict, permission: str) -> None:
    if not await check_permission(current_user, permission):
        raise HTTPException(status_code=403, detail=f"requires '{permission}' permission")


class ExecutePayload(BaseModel):
    trigger_payload: Dict[str, Any] = {}


async def _start(workflow_id: str, mode: str, body: ExecutePayload, current_user: dict) -> Dict[str, Any]:
    record = await workflow_definition_service.get_workflow(workflow_id)
    if record is None or record.get("version") is None:
        raise HTTPException(status_code=404, detail="workflow or version not found")
    version = record["version"]
    execution_id = await dag_engine.start_execution(
        workflow_id, version["version"], {"nodes": version["nodes"], "edges": version["edges"]},
        body.trigger_payload, mode=mode, started_by=current_user.get("email", "unknown"), actor=current_user,
    )
    return {"execution_id": execution_id}


@router.post("/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, body: ExecutePayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.execute")
    return await _start(workflow_id, "run", body, current_user)


@router.post("/{workflow_id}/dry-run")
async def dry_run_workflow(workflow_id: str, body: ExecutePayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.execute")
    return await _start(workflow_id, "dry_run", body, current_user)


@router.post("/{workflow_id}/test-run")
async def test_run_workflow(workflow_id: str, body: ExecutePayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.execute")
    return await _start(workflow_id, "test_run", body, current_user)


@router.get("")
async def list_executions(workflow_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50,
                           current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    from ..core.database import db
    query: Dict[str, Any] = {}
    if workflow_id:
        query["workflow_id"] = workflow_id
    if status:
        query["status"] = status
    docs = await db.workflow_executions.find(query, {"_id": 0}).sort("started_at", -1).limit(limit).to_list(limit)
    return {"executions": docs}


@router.get("/{execution_id}")
async def get_execution(execution_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    from ..core.database import db
    doc = await db.workflow_executions.find_one({"execution_id": execution_id}, {"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404, detail="execution not found")
    node_executions = await db.workflow_node_executions.find({"execution_id": execution_id}, {"_id": 0}).to_list(2000)
    pending_approvals = await approval_service.list_pending_for_execution(execution_id)
    return {"execution": doc, "node_executions": node_executions, "pending_approvals": pending_approvals}


@router.get("/{execution_id}/nodes/{node_id}")
async def get_node_execution(execution_id: str, node_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    from ..core.database import db
    docs = await db.workflow_node_executions.find({"execution_id": execution_id, "node_id": node_id}, {"_id": 0}).to_list(100)
    if not docs:
        raise HTTPException(status_code=404, detail="node execution not found")
    return {"iterations": docs}


@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.execute")
    result = await dag_engine.cancel_execution(execution_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


async def _get_redis():
    from ..services.metrics_timeseries_service import metrics_timeseries_service
    return await metrics_timeseries_service.get_redis()


@router.get("/{execution_id}/stream")
async def stream_execution(execution_id: str, request: Request, current_user: dict = Depends(require_auth)):
    async def event_generator():
        from ..core.database import db

        cursor = db.workflow_trace.find({"execution_id": execution_id}, {"_id": 0}).sort("seq", 1)
        async for doc in cursor:
            if await request.is_disconnected():
                return
            yield {"event": "trace", "data": json.dumps(doc, default=str)}

        redis_client = await _get_redis()
        if redis_client is None:
            yield {"event": "end", "data": json.dumps({"reason": "no_redis_live_feed"})}
            return

        pubsub = redis_client.pubsub()
        channel = f"{REDIS_CHANNEL_PREFIX}{execution_id}"
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


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str, body: ApprovalDecisionPayload, current_user: dict = Depends(require_auth)):
    result = await approval_service.decide(approval_id, True, body.reason, current_user.get("email", "unknown"), actor=current_user)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/approvals/{approval_id}/reject")
async def reject(approval_id: str, body: ApprovalDecisionPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.execute")
    result = await approval_service.decide(approval_id, False, body.reason, current_user.get("email", "unknown"), actor=current_user)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/observability/summary")
async def observability_summary(workflow_id: Optional[str] = None, hours: int = 24, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    return await observability_service.get_summary(workflow_id, hours)


__all__ = ["router"]
