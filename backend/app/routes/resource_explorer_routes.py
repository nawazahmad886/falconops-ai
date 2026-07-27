"""
FalconOps AI - Enterprise Resource Explorer API

Extends db.topology_nodes (via resource_explorer_service.py) as the
canonical Resource model. See the Resource Explorer plan for the full
architecture writeup.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..core.config import JWT_ALGORITHM, JWT_SECRET
from ..core.database import db
from ..services import resource_explorer_service as res_svc
from ..services import runbook_engine as runbook_engine_module
from ..services.resource_explorer_broadcaster import resource_manager
from ..services.topology_service import topology_service
from ..utils.auth import require_admin, require_auth, require_write_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resources", tags=["Resource Explorer"])


class RetireRequest(BaseModel):
    reason: Optional[str] = None


class RunbookExecRequest(BaseModel):
    runbook_id: str


# ─────────────────────────────────────────────────────
#  List / facets / sync / live  (literal paths — must precede "/{resource_id}")
# ─────────────────────────────────────────────────────

@router.get("")
async def list_resources_route(
    category: Optional[str] = None,
    technology: Optional[str] = None,
    environment: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    lifecycle_status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query("last_seen", pattern="^(last_seen|name|health_score|created_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    include_retired: bool = False,
    limit: int = Query(50, le=500),
    offset: int = 0,
    current_user: dict = Depends(require_auth),
):
    tenant_id = current_user.get("tenant_id")
    return await res_svc.list_resources(
        category=category, technology=technology, environment=environment, owner=owner,
        tags=tags, lifecycle_status=lifecycle_status, search=search, sort_by=sort_by,
        sort_order=sort_order, include_retired=include_retired, limit=limit, offset=offset,
        tenant_id=tenant_id,
    )


@router.get("/facets")
async def facets_route(current_user: dict = Depends(require_auth)):
    return await res_svc.get_facets(tenant_id=current_user.get("tenant_id"))


@router.post("/sync")
async def sync_route(current_user: dict = Depends(require_admin)):
    return await res_svc.sync_all_resources()


async def _resources_authenticate(ws: WebSocket) -> bool:
    """Lightweight token gate — pass `?token=<jwt>`, same pattern as
    /api/problems/live and /api/traces/live."""
    token = ws.query_params.get("token") or ""
    if not token:
        await ws.send_json({"type": "error", "error": "missing token"})
        await ws.close()
        return False
    try:
        import jwt
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        await ws.send_json({"type": "error", "error": "invalid token"})
        await ws.close()
        return False
    return True


resource_manager.authenticate = _resources_authenticate


@router.websocket("/live")
async def resources_live(ws: WebSocket):
    if not await resource_manager.connect(ws):
        return
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await resource_manager.disconnect(ws)


# ─────────────────────────────────────────────────────
#  Detail + tabs + actions (dynamic "/{resource_id}" — registered after the
#  literal paths above)
# ─────────────────────────────────────────────────────

@router.get("/{resource_id}")
async def get_resource_route(resource_id: str, current_user: dict = Depends(require_auth)):
    resource = await res_svc.get_resource(resource_id, tenant_id=current_user.get("tenant_id"))
    if not resource:
        raise HTTPException(404, "Resource not found")
    return resource


async def _load_resource_or_404(resource_id: str, current_user: dict) -> dict:
    resource = await topology_service.get_service_node(resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    tenant_id = current_user.get("tenant_id")
    if tenant_id and resource.get("tenant_id") not in (None, tenant_id):
        raise HTTPException(404, "Resource not found")
    return resource


@router.get("/{resource_id}/metrics")
async def resource_metrics_route(
    resource_id: str, hours: int = Query(24, ge=1, le=168), current_user: dict = Depends(require_auth)
):
    resource = await _load_resource_or_404(resource_id, current_user)
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    source_refs = resource.get("source_refs") or []

    if resource.get("resource_category") == "database":
        db_ref = next((r for r in source_refs if r.get("collection") == "db_instances"), None)
        if not db_ref:
            return {"metrics": [], "reason": "no linked db_instances record for this resource"}
        rows = await db.db_metrics.find(
            {"instance_id": db_ref["id"], "timestamp": {"$gte": since}}, {"_id": 0}
        ).sort("timestamp", -1).limit(1000).to_list(1000)
        return {"metrics": rows}

    server_ref = next((r for r in source_refs if r.get("collection") == "servers"), None)
    if server_ref:
        rows = await db.server_metrics.find(
            {"server_id": server_ref["id"], "timestamp": {"$gte": since}}, {"_id": 0}
        ).sort("timestamp", -1).limit(1000).to_list(1000)
        return {"metrics": rows}
    return {"metrics": [], "reason": "no linked db.servers record for this resource — metrics unavailable in Phase 1"}


@router.get("/{resource_id}/logs")
async def resource_logs_route(
    resource_id: str, limit: int = Query(100, le=1000), current_user: dict = Depends(require_auth)
):
    resource = await _load_resource_or_404(resource_id, current_user)
    if resource.get("resource_category") != "infrastructure":
        return {"logs": [], "reason": "no log ingestion exists for non-infrastructure resources in Phase 1"}
    rows = await db.logs.find({"host": resource.get("name")}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"logs": rows}


@router.get("/{resource_id}/events")
async def resource_events_route(resource_id: str, current_user: dict = Depends(require_auth)):
    resource = await _load_resource_or_404(resource_id, current_user)
    from ..services import problems_service
    result = await problems_service.list_problems(
        service=resource.get("name"), source="soc_event", limit=20, tenant_id=current_user.get("tenant_id")
    )
    return {"events": result["problems"]}


@router.get("/{resource_id}/alerts")
async def resource_alerts_route(resource_id: str, current_user: dict = Depends(require_auth)):
    resource = await _load_resource_or_404(resource_id, current_user)
    from ..services import problems_service
    result = await problems_service.list_problems(
        service=resource.get("name"), limit=50, tenant_id=current_user.get("tenant_id")
    )
    return {"alerts": result["problems"], "total": result["total"]}


@router.get("/{resource_id}/traces")
async def resource_traces_route(resource_id: str, current_user: dict = Depends(require_auth)):
    resource = await _load_resource_or_404(resource_id, current_user)
    if resource.get("resource_category") not in ("application", None):
        return {"traces": [], "reason": "traces are only meaningful for application-category resources emitting distributed traces"}
    rows = await db.otel_traces.find(
        {"services": resource.get("name")}, {"_id": 0}
    ).sort("received_at", -1).limit(20).to_list(20)
    return {"traces": rows}


@router.get("/{resource_id}/topology")
async def resource_topology_route(resource_id: str, current_user: dict = Depends(require_auth)):
    await _load_resource_or_404(resource_id, current_user)
    deps = await topology_service.get_service_dependencies(resource_id, direction="both")
    nodes = {resource_id: True}
    edges = []
    for entry in deps["upstream_dependencies"]:
        nodes[entry["service"]["id"]] = True
        edges.append(entry["connection"])
    for entry in deps["downstream_dependents"]:
        nodes[entry["service"]["id"]] = True
        edges.append(entry["connection"])
    return {"node_ids": list(nodes.keys()), "edges": edges}


@router.get("/{resource_id}/dependencies")
async def resource_dependencies_route(
    resource_id: str, direction: str = Query("both", pattern="^(both|upstream|downstream)$"),
    current_user: dict = Depends(require_auth),
):
    await _load_resource_or_404(resource_id, current_user)
    return await topology_service.get_service_dependencies(resource_id, direction=direction)


@router.get("/{resource_id}/configuration")
async def resource_configuration_route(resource_id: str, current_user: dict = Depends(require_auth)):
    resource = await _load_resource_or_404(resource_id, current_user)
    return {
        "configuration": resource.get("metadata") or {},
        "configuration_note": "Phase 1 passthrough of the bridged source document's fields — not a real configuration-management feature.",
    }


@router.post("/{resource_id}/enable-monitoring")
async def enable_monitoring_route(resource_id: str, current_user: dict = Depends(require_write_access)):
    result = await res_svc.set_monitoring(resource_id, True, current_user.get("email"))
    if not result:
        raise HTTPException(404, "Resource not found")
    return result


@router.post("/{resource_id}/disable-monitoring")
async def disable_monitoring_route(resource_id: str, current_user: dict = Depends(require_write_access)):
    result = await res_svc.set_monitoring(resource_id, False, current_user.get("email"))
    if not result:
        raise HTTPException(404, "Resource not found")
    return result


@router.post("/{resource_id}/retire")
async def retire_route(resource_id: str, req: RetireRequest, current_user: dict = Depends(require_write_access)):
    result = await res_svc.retire_resource(resource_id, req.reason, current_user.get("email"))
    if not result:
        raise HTTPException(404, "Resource not found")
    return result


@router.post("/{resource_id}/restore")
async def restore_route(resource_id: str, current_user: dict = Depends(require_write_access)):
    result = await res_svc.restore_resource(resource_id, current_user.get("email"))
    if not result:
        raise HTTPException(404, "Resource not found")
    return result


@router.post("/{resource_id}/restart-agent")
async def restart_agent_route(resource_id: str, current_user: dict = Depends(require_write_access)):
    try:
        return await res_svc.get_restart_instruction(resource_id)
    except LookupError as e:
        raise HTTPException(404, str(e))


@router.post("/{resource_id}/execute-runbook")
async def execute_runbook_route(resource_id: str, req: RunbookExecRequest, current_user: dict = Depends(require_write_access)):
    resource = await _load_resource_or_404(resource_id, current_user)
    return await runbook_engine_module.runbook_engine.execute_runbook(
        req.runbook_id,
        trigger_source="resource_explorer",
        user_email=current_user.get("email", "system"),
        tenant_id=current_user.get("tenant_id"),
        entity_id=resource_id,
        entity_type=resource.get("resource_category"),
        entity_name=resource.get("name"),
    )
