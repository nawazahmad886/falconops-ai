"""FalconOps AI — Onboarding checklist API."""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..services import onboarding_service
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.get("/status")
async def status(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return await onboarding_service.get_onboarding_status(user.get("tenant_id"), user["id"])


@router.post("/dismiss")
async def dismiss(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    await onboarding_service.dismiss_onboarding(user["id"])
    return {"ok": True}


__all__ = ["router"]
