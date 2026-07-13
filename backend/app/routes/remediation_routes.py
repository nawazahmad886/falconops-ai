"""
FalconOps AI - Auto-Remediation Routes

/execute is a DRY-RUN / PLAN-PREVIEW ONLY endpoint — it resolves and records the
command that would run but never executes anything against real infrastructure.
See app.services.remediation_service module docstring.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access
from ..services.remediation_service import (
    suggest_remediation,
    execute_remediation,
    get_action_library,
    get_remediation_history,
    get_remediation_stats,
)

router = APIRouter(prefix="/api/remediation", tags=["Auto-Remediation"])


class ExecuteRequest(BaseModel):
    action_id: str
    params: dict
    trigger: Optional[str] = "manual"


class SuggestRequest(BaseModel):
    root_cause: str
    context: Optional[dict] = None


@router.get("/actions")
async def list_actions(current_user: dict = Depends(require_auth)):
    """Get available remediation action library"""
    return await get_action_library()


@router.post("/suggest")
async def suggest(
    req: SuggestRequest,
    current_user: dict = Depends(require_auth),
):
    """Suggest remediation actions for a root cause"""
    return await suggest_remediation(req.root_cause, req.context)


@router.post("/execute")
async def execute(
    req: ExecuteRequest,
    current_user: dict = Depends(require_write_access),
):
    """Preview a remediation action (dry-run — does not execute against real infrastructure)"""
    return await execute_remediation(
        req.action_id, req.params, req.trigger, current_user.get("email", "system")
    )


@router.get("/history")
async def history(
    limit: int = Query(50, le=200),
    current_user: dict = Depends(require_auth),
):
    """Get remediation execution history"""
    return await get_remediation_history(limit)


@router.get("/stats")
async def stats(current_user: dict = Depends(require_auth)):
    """Get remediation statistics"""
    return await get_remediation_stats()
