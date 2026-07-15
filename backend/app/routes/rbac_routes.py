"""
FalconOps AI - RBAC & Audit Log Routes
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from ..utils.auth import require_auth, require_admin
from ..services.rbac_service import (
    get_all_roles,
    get_role,
    create_role,
    update_role,
    delete_role,
    get_all_permissions,
    init_default_roles,
    check_permission,
    log_audit,
    get_audit_logs,
    get_audit_stats,
)

router = APIRouter(prefix="/api/rbac", tags=["RBAC & Audit"])


class CreateRoleRequest(BaseModel):
    role_id: str
    name: str
    description: str
    permissions: List[str]


class UpdateRoleRequest(BaseModel):
    permissions: List[str]


# ======================== ROLES ========================

@router.get("/roles")
async def list_roles(current_user: dict = Depends(require_auth)):
    await init_default_roles()
    return await get_all_roles()


@router.get("/roles/{role_id}")
async def get_single_role(role_id: str, current_user: dict = Depends(require_auth)):
    role = await get_role(role_id)
    if not role:
        return {"error": "Role not found"}
    return role


@router.post("/roles")
async def create_new_role(req: CreateRoleRequest, request: Request, current_user: dict = Depends(require_admin)):
    result = await create_role(req.role_id, req.name, req.description, req.permissions)
    await log_audit(current_user, "create_role", "rbac", f"Created role {req.role_id}", ip=request.client.host if request.client else "")
    return result


@router.put("/roles/{role_id}")
async def update_existing_role(role_id: str, req: UpdateRoleRequest, request: Request, current_user: dict = Depends(require_admin)):
    result = await update_role(role_id, req.permissions)
    await log_audit(current_user, "update_role", "rbac", f"Updated role {role_id}", ip=request.client.host if request.client else "")
    return result


@router.delete("/roles/{role_id}")
async def delete_existing_role(role_id: str, request: Request, current_user: dict = Depends(require_admin)):
    result = await delete_role(role_id)
    await log_audit(current_user, "delete_role", "rbac", f"Deleted role {role_id}", ip=request.client.host if request.client else "")
    return result


# ======================== PERMISSIONS ========================

@router.get("/permissions")
async def list_permissions(current_user: dict = Depends(require_auth)):
    return get_all_permissions()


@router.get("/check-permission")
async def check_user_permission(
    permission: str = Query(...),
    current_user: dict = Depends(require_auth),
):
    has = await check_permission(current_user, permission)
    return {"permission": permission, "granted": has}


# ======================== AUDIT LOGS ========================

@router.get("/audit")
async def list_audit_logs(
    hours: int = Query(24),
    user_email: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    current_user: dict = Depends(require_admin),
):
    """Admin-only: the audit trail spans all tenants (user emails, actions, IPs), so
    this must not be reachable by a regular authenticated user of any tenant."""
    return await get_audit_logs(hours, user_email, action, resource, limit, offset)


@router.get("/audit/stats")
async def audit_stats(
    hours: int = Query(24),
    current_user: dict = Depends(require_admin),
):
    return await get_audit_stats(hours)
