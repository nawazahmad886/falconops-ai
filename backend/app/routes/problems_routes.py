"""
FalconOps AI - Problems console API

Unifies db.alerts_engine + db.incidents_engine + db.soc_events + db.soc_incidents
into one Problem view via app/services/problems_service.py's read-time
federation. See the Problems console plan for the full architecture writeup.
"""
import io
import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.config import JWT_ALGORITHM, JWT_SECRET
from ..services import problems_service
from ..services.problems_broadcaster import problems_manager
from ..utils.auth import require_auth, require_write_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/problems", tags=["Problems"])


class AssignRequest(BaseModel):
    assigned_to: Optional[str] = None
    assignment_group: Optional[str] = None


class ResolveRequest(BaseModel):
    notes: Optional[str] = None


class SuppressRequest(BaseModel):
    reason: str
    expires_at: Optional[str] = None


# ─────────────────────────────────────────────────────
#  List / statistics / timeline / search  (literal paths — must be registered
#  before the dynamic "/{problem_id}" route below, or FastAPI would try to
#  match e.g. "statistics" as a problem_id)
# ─────────────────────────────────────────────────────

@router.get("")
async def list_problems_route(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    service: Optional[str] = None,
    assigned_to: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    sort_by: str = Query("started_at", pattern="^(started_at|severity)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    include_suppressed: bool = False,
    limit: int = Query(50, le=500),
    offset: int = 0,
    current_user: dict = Depends(require_auth),
):
    tenant_id = current_user.get("tenant_id")
    resolved_assigned_to = current_user.get("email") if assigned_to == "me" else assigned_to
    try:
        return await problems_service.list_problems(
            status=status, severity=severity, source=source, service=service,
            assigned_to=resolved_assigned_to, start_time=start_time, end_time=end_time,
            sort_by=sort_by, sort_order=sort_order, include_suppressed=include_suppressed,
            limit=limit, offset=offset, tenant_id=tenant_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/statistics")
async def statistics_route(current_user: dict = Depends(require_auth)):
    tenant_id = current_user.get("tenant_id")
    return await problems_service.get_statistics(tenant_id=tenant_id)


@router.get("/timeline")
async def timeline_route(
    hours: int = Query(24, ge=1, le=720),
    bucket_minutes: int = Query(60, ge=5),
    current_user: dict = Depends(require_auth),
):
    tenant_id = current_user.get("tenant_id")
    return await problems_service.get_timeline(hours=hours, bucket_minutes=bucket_minutes, tenant_id=tenant_id)


@router.get("/search")
async def search_route(q: str = Query(..., min_length=1), current_user: dict = Depends(require_auth)):
    tenant_id = current_user.get("tenant_id")
    return {"problems": await problems_service.search_problems(q, tenant_id=tenant_id)}


@router.post("/export")
async def export_route(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    service: Optional[str] = None,
    assigned_to: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    include_suppressed: bool = False,
    current_user: dict = Depends(require_auth),
):
    tenant_id = current_user.get("tenant_id")
    resolved_assigned_to = current_user.get("email") if assigned_to == "me" else assigned_to
    rows = await problems_service.export_rows(
        status=status, severity=severity, source=source, service=service,
        assigned_to=resolved_assigned_to, start_time=start_time, end_time=end_time,
        include_suppressed=include_suppressed, tenant_id=tenant_id,
    )
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=problems_export.csv"},
    )


# ─────────────────────────────────────────────────────
#  Live feed
# ─────────────────────────────────────────────────────

async def _problems_authenticate(ws: WebSocket) -> bool:
    """Lightweight token gate — pass `?token=<jwt>` to authenticate. Same
    pattern as /api/traces/live — Problems data is tenant-sensitive, unlike
    the older unauthenticated /ws/alerts and /ws/soc-feed channels."""
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


problems_manager.authenticate = _problems_authenticate


@router.websocket("/live")
async def problems_live(ws: WebSocket):
    if not await problems_manager.connect(ws):
        return
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await problems_manager.disconnect(ws)


# ─────────────────────────────────────────────────────
#  Detail + actions (dynamic "/{problem_id}" — registered after the literal
#  paths above)
# ─────────────────────────────────────────────────────

@router.get("/{problem_id}")
async def get_problem_route(problem_id: str, current_user: dict = Depends(require_auth)):
    tenant_id = current_user.get("tenant_id")
    try:
        problem = await problems_service.get_problem(problem_id, tenant_id=tenant_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not problem:
        raise HTTPException(404, "Problem not found")
    return problem


@router.post("/{problem_id}/acknowledge")
async def acknowledge_route(problem_id: str, current_user: dict = Depends(require_write_access)):
    try:
        result = await problems_service.acknowledge_problem(problem_id, current_user.get("email"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not result:
        raise HTTPException(404, "Problem not found or not in an acknowledgeable state")
    return result


@router.post("/{problem_id}/resolve")
async def resolve_route(problem_id: str, req: ResolveRequest, current_user: dict = Depends(require_write_access)):
    try:
        result = await problems_service.resolve_problem(problem_id, current_user.get("email"), notes=req.notes)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not result:
        raise HTTPException(404, "Problem not found or not in a resolvable state")
    return result


@router.post("/{problem_id}/close")
async def close_route(problem_id: str, current_user: dict = Depends(require_write_access)):
    try:
        result = await problems_service.close_problem(problem_id, current_user.get("email"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not result:
        raise HTTPException(404, "Problem not found or not in a closeable state")
    return result


@router.post("/{problem_id}/assign")
async def assign_route(problem_id: str, req: AssignRequest, current_user: dict = Depends(require_write_access)):
    try:
        result = await problems_service.assign_problem(
            problem_id, req.assigned_to, req.assignment_group, current_user.get("email"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not result:
        raise HTTPException(404, "Problem not found")
    return result


@router.post("/{problem_id}/suppress")
async def suppress_route(problem_id: str, req: SuppressRequest, current_user: dict = Depends(require_write_access)):
    return await problems_service.suppress_problem(problem_id, req.reason, current_user.get("email"), req.expires_at)


@router.post("/{problem_id}/unsuppress")
async def unsuppress_route(problem_id: str, current_user: dict = Depends(require_write_access)):
    return await problems_service.unsuppress_problem(problem_id)


@router.post("/{problem_id}/escalate")
async def escalate_route(problem_id: str, current_user: dict = Depends(require_write_access)):
    try:
        return await problems_service.escalate_problem(problem_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))
