"""
FalconOps AI - Integration Management Routes
Admin API for managing external integrations and API keys
"""
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services.integration_management_service import (
    get_catalog,
    get_integration,
    save_integration,
    toggle_integration,
    delete_integration,
    test_integration,
)

router = APIRouter(prefix="/api/admin/integrations", tags=["Admin Integrations"])


class IntegrationSaveRequest(BaseModel):
    config: dict
    enabled: bool = True


class IntegrationToggleRequest(BaseModel):
    enabled: bool


@router.get("/catalog")
async def integration_catalog(current_user: dict = Depends(require_auth)):
    """Get available integrations with configuration status"""
    return await get_catalog()


@router.get("/{integration_id}")
async def get_integration_config(
    integration_id: str,
    current_user: dict = Depends(require_auth),
):
    """Get integration configuration (secrets masked)"""
    result = await get_integration(integration_id)
    if not result:
        return {"error": "Not configured"}
    return result


@router.put("/{integration_id}")
async def save_integration_config(
    integration_id: str,
    req: IntegrationSaveRequest,
    current_user: dict = Depends(require_auth),
):
    """Save or update integration configuration"""
    if current_user.get("role") != "admin":
        return {"error": "Admin access required"}
    return await save_integration(integration_id, req.config, req.enabled, current_user.get("email"))


@router.patch("/{integration_id}/toggle")
async def toggle_integration_status(
    integration_id: str,
    req: IntegrationToggleRequest,
    current_user: dict = Depends(require_auth),
):
    """Toggle integration enabled/disabled"""
    if current_user.get("role") != "admin":
        return {"error": "Admin access required"}
    return await toggle_integration(integration_id, req.enabled)


@router.delete("/{integration_id}")
async def remove_integration(
    integration_id: str,
    current_user: dict = Depends(require_auth),
):
    """Delete integration configuration"""
    if current_user.get("role") != "admin":
        return {"error": "Admin access required"}
    return await delete_integration(integration_id)


@router.post("/{integration_id}/test")
async def test_integration_connection(
    integration_id: str,
    current_user: dict = Depends(require_auth),
):
    """Test integration connectivity"""
    return await test_integration(integration_id)
