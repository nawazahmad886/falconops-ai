"""
FalconOps AI — Troubleshooting Command Center API.

Every command in the catalog is read-only (risk="low") — see
troubleshooting_service.py's module docstring for exactly what each category
is scoped to and why. require_auth only; no destructive-action approval gate
needed here because nothing here can be destructive by construction.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services import troubleshooting_service
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/troubleshooting", tags=["Troubleshooting"])


@router.get("/commands")
async def list_commands(category: Optional[str] = None, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return {"commands": troubleshooting_service.list_commands(category)}


class RunCommandRequest(BaseModel):
    params: Dict[str, Any] = {}


@router.post("/commands/{command_id}/run")
async def run_command(command_id: str, req: RunCommandRequest, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    try:
        return await troubleshooting_service.run_command(command_id, req.params)
    except ValueError as e:
        raise HTTPException(404, str(e))


__all__ = ["router"]
