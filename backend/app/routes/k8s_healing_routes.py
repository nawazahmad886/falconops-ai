"""
FalconOps AI - Kubernetes Auto-Healing Routes
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_admin
from ..services.k8s_healing_service import (
    get_playbooks, generate_commands, create_execution,
    approve_execution, reject_execution, get_executions, get_k8s_stats,
)

router = APIRouter(prefix="/api/k8s", tags=["K8s Auto-Healing"])


class GenerateRequest(BaseModel):
    playbook_id: str
    params: dict


class ExecuteRequest(BaseModel):
    playbook_id: str
    params: dict
    auto_approve: bool = False


@router.get("/playbooks")
async def list_playbooks(current_user: dict = Depends(require_auth)):
    return get_playbooks()


@router.post("/generate")
async def generate(req: GenerateRequest, current_user: dict = Depends(require_auth)):
    return generate_commands(req.playbook_id, req.params)


@router.post("/execute")
async def execute(req: ExecuteRequest, current_user: dict = Depends(require_admin)):
    return await create_execution(req.playbook_id, req.params, current_user.get("email", ""), req.auto_approve)


@router.post("/executions/{execution_id}/approve")
async def approve(execution_id: str, current_user: dict = Depends(require_admin)):
    return await approve_execution(execution_id, current_user.get("email", ""))


@router.post("/executions/{execution_id}/reject")
async def reject(execution_id: str, current_user: dict = Depends(require_admin)):
    return await reject_execution(execution_id, current_user.get("email", ""))


@router.get("/executions")
async def list_executions(
    status: Optional[str] = Query(None),
    limit: int = Query(30, le=100),
    current_user: dict = Depends(require_auth),
):
    return await get_executions(status, limit)


@router.get("/stats")
async def stats(current_user: dict = Depends(require_auth)):
    return await get_k8s_stats()
