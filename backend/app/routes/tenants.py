"""
FalconOps AI - Tenant Management Routes
Multi-tenancy support for enterprise deployments
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ..core.database import db
from ..utils.auth import require_auth, require_admin, require_write_access, hash_password

router = APIRouter(prefix="/api/tenants", tags=["Multi-Tenancy"])


# ======================== MODELS ========================

class TenantCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    contact_email: Optional[str] = None
    plan: str = "starter"  # starter, professional, enterprise
    max_users: int = 10
    max_servers: int = 50
    max_monitors: int = 100

class TenantResponse(BaseModel):
    id: str
    name: str
    domain: Optional[str]
    contact_email: Optional[str]
    plan: str
    max_users: int
    max_servers: int
    max_monitors: int
    user_count: int
    server_count: int
    monitor_count: int
    status: str
    created_at: str

class TenantUserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "user"  # admin, user, viewer


# ======================== TENANT CRUD ========================

@router.get("")
async def list_tenants(current_user: dict = Depends(require_admin)):
    """List all tenants (admin only)"""
    tenants = await db.tenants.find({}, {"_id": 0}).to_list(100)
    
    # Enrich with counts
    for tenant in tenants:
        tenant["user_count"] = await db.users.count_documents({"tenant_id": tenant["id"]})
        tenant["server_count"] = await db.servers.count_documents({"tenant_id": tenant["id"]})
        tenant["monitor_count"] = await db.monitors.count_documents({"tenant_id": tenant["id"]})
    
    return tenants


@router.post("")
async def create_tenant(tenant: TenantCreate, current_user: dict = Depends(require_admin)):
    """Create a new tenant (admin only)"""
    # Check if tenant name already exists
    existing = await db.tenants.find_one({"name": tenant.name})
    if existing:
        raise HTTPException(status_code=400, detail="Tenant name already exists")
    
    tenant_id = str(uuid.uuid4())
    tenant_doc = {
        "id": tenant_id,
        "name": tenant.name,
        "domain": tenant.domain,
        "contact_email": tenant.contact_email,
        "plan": tenant.plan,
        "max_users": tenant.max_users,
        "max_servers": tenant.max_servers,
        "max_monitors": tenant.max_monitors,
        "status": "active",
        "settings": {
            "alert_notifications": True,
            "report_frequency": "weekly",
            "timezone": "UTC"
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"]
    }
    
    await db.tenants.insert_one(tenant_doc)
    
    return {k: v for k, v in tenant_doc.items() if k != "_id"}


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, current_user: dict = Depends(require_auth)):
    """Get tenant details"""
    # Users can only view their own tenant unless admin
    if current_user.get("role") != "admin" and current_user.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Add counts
    tenant["user_count"] = await db.users.count_documents({"tenant_id": tenant_id})
    tenant["server_count"] = await db.servers.count_documents({"tenant_id": tenant_id})
    tenant["monitor_count"] = await db.monitors.count_documents({"tenant_id": tenant_id})
    
    return tenant


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    tenant: TenantCreate,
    current_user: dict = Depends(require_admin)
):
    """Update tenant settings (admin only)"""
    existing = await db.tenants.find_one({"id": tenant_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    update_doc = {
        "name": tenant.name,
        "domain": tenant.domain,
        "contact_email": tenant.contact_email,
        "plan": tenant.plan,
        "max_users": tenant.max_users,
        "max_servers": tenant.max_servers,
        "max_monitors": tenant.max_monitors,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.tenants.update_one({"id": tenant_id}, {"$set": update_doc})
    
    return {"message": "Tenant updated successfully"}


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, current_user: dict = Depends(require_admin)):
    """Delete a tenant (admin only) - WARNING: Deletes all tenant data"""
    existing = await db.tenants.find_one({"id": tenant_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Delete all tenant data
    await db.users.delete_many({"tenant_id": tenant_id})
    await db.servers.delete_many({"tenant_id": tenant_id})
    await db.server_metrics.delete_many({"tenant_id": tenant_id})
    await db.monitors.delete_many({"tenant_id": tenant_id})
    await db.alerts.delete_many({"tenant_id": tenant_id})
    await db.incidents.delete_many({"tenant_id": tenant_id})
    await db.tenants.delete_one({"id": tenant_id})
    
    return {"message": "Tenant and all associated data deleted"}


# ======================== TENANT USER MANAGEMENT ========================

@router.get("/{tenant_id}/users")
async def list_tenant_users(tenant_id: str, current_user: dict = Depends(require_auth)):
    """List users in a tenant"""
    # Check access
    if current_user.get("role") != "admin" and current_user.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    users = await db.users.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "hashed_password": 0, "password_hash": 0}
    ).to_list(100)
    
    return users


@router.post("/{tenant_id}/users")
async def create_tenant_user(
    tenant_id: str,
    user: TenantUserCreate,
    current_user: dict = Depends(require_write_access)
):
    """Create a new user in a tenant"""
    # Check access
    if current_user.get("role") != "admin" and current_user.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # A non-global-admin creating a user within their own tenant must not be able to
    # self-escalate by minting a new "admin" (or any other elevated) account — "admin"
    # is a global flag here (checked by require_admin everywhere), not tenant-scoped.
    if user.role not in ("user", "viewer") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only a global admin can assign elevated roles")

    # Check tenant exists and user limit
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    user_count = await db.users.count_documents({"tenant_id": tenant_id})
    if user_count >= tenant.get("max_users", 10):
        raise HTTPException(status_code=400, detail="User limit reached for this tenant")
    
    # Check if email already exists
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": user.email,
        "full_name": user.full_name,
        "hashed_password": hash_password(user.password),
        "role": user.role,
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"]
    }
    
    await db.users.insert_one(user_doc)
    
    return {
        "id": user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": tenant_id,
        "created_at": user_doc["created_at"]
    }


@router.delete("/{tenant_id}/users/{user_id}")
async def delete_tenant_user(
    tenant_id: str,
    user_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Remove a user from tenant"""
    # Check access
    if current_user.get("role") != "admin" and current_user.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Prevent self-deletion
    if current_user["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    result = await db.users.delete_one({"id": user_id, "tenant_id": tenant_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}


# ======================== TENANT STATISTICS ========================

@router.get("/{tenant_id}/stats")
async def get_tenant_statistics(tenant_id: str, current_user: dict = Depends(require_auth)):
    """Get tenant statistics and usage"""
    # Check access
    if current_user.get("role") != "admin" and current_user.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Get counts
    user_count = await db.users.count_documents({"tenant_id": tenant_id})
    server_count = await db.servers.count_documents({"tenant_id": tenant_id})
    monitor_count = await db.monitors.count_documents({"tenant_id": tenant_id})
    alert_count = await db.alerts.count_documents({"tenant_id": tenant_id})
    incident_count = await db.incidents.count_documents({"tenant_id": tenant_id})
    
    # Get online/offline server counts
    online_servers = await db.servers.count_documents({"tenant_id": tenant_id, "status": "online"})
    
    # Get active alerts
    active_alerts = await db.alerts.count_documents({"tenant_id": tenant_id, "status": "open"})
    
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant.get("name"),
        "plan": tenant.get("plan"),
        "usage": {
            "users": {"current": user_count, "max": tenant.get("max_users", 10)},
            "servers": {"current": server_count, "max": tenant.get("max_servers", 50)},
            "monitors": {"current": monitor_count, "max": tenant.get("max_monitors", 100)}
        },
        "health": {
            "online_servers": online_servers,
            "offline_servers": server_count - online_servers,
            "active_alerts": active_alerts,
            "total_incidents": incident_count
        },
        "status": tenant.get("status", "active")
    }



# ======================== TENANT BRANDING (Enterprise Reports) ========================

import base64

class BrandingUpdate(BaseModel):
    logo_base64: Optional[str] = None   # data:image/png;base64,....
    primary_color: Optional[str] = "#00E0FF"
    secondary_color: Optional[str] = "#F5B841"
    footer_text: Optional[str] = "Confidential - SOC Report"


BRAND_LOGO_DIR = "/tmp/falconops_branding"

import os as _os
_os.makedirs(BRAND_LOGO_DIR, exist_ok=True)


@router.get("/{tenant_id}/branding")
async def get_branding(tenant_id: str, current_user: dict = Depends(require_auth)):
    """Return branding for a tenant (primary_color, secondary_color, footer_text, logo_url)"""
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    branding = tenant.get("branding") or {}
    from ..services.storage_service import branding_exists
    has_logo = branding_exists(branding.get("logo_url"))
    return {
        "tenant_id": tenant_id,
        "company_name": tenant.get("name"),
        "primary_color": branding.get("primary_color", "#00E0FF"),
        "secondary_color": branding.get("secondary_color", "#F5B841"),
        "footer_text": branding.get("footer_text", f"Confidential - {tenant.get('name')} SOC"),
        "has_logo": has_logo,
    }


@router.put("/{tenant_id}/branding")
async def update_branding(tenant_id: str, payload: BrandingUpdate, current_user: dict = Depends(require_admin)):
    """Update tenant branding (admin only). Logo accepted as base64 data URL."""
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    branding_doc = tenant.get("branding") or {}
    if payload.primary_color:
        branding_doc["primary_color"] = payload.primary_color
    if payload.secondary_color:
        branding_doc["secondary_color"] = payload.secondary_color
    if payload.footer_text is not None:
        branding_doc["footer_text"] = payload.footer_text

    if payload.logo_base64:
        # Parse data URL
        raw = payload.logo_base64
        if "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            img_bytes = base64.b64decode(raw)
            if len(img_bytes) > 2 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Logo too large (max 2MB)")
            from ..services.storage_service import save_branding_logo
            branding_doc["logo_url"] = save_branding_logo(tenant_id, img_bytes)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid logo image: {e}")

    await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": {"branding": branding_doc, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    from ..services.storage_service import branding_exists
    return {"message": "Branding updated", "branding": {k: v for k, v in branding_doc.items() if k != "logo_url"}, "has_logo": branding_exists(branding_doc.get("logo_url"))}
