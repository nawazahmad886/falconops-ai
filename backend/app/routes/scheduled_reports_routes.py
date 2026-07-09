"""
FalconOps AI - Scheduled Reports Routes
Admin-configurable weekly report schedule + email delivery via Resend.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr

from ..utils.auth import require_auth, require_admin
from ..services.weekly_report_scheduler_service import (
    get_schedule_settings, update_schedule_settings,
    run_weekly_report, get_run_logs, refresh_scheduler,
    list_tenant_schedules, refresh_tenant_scheduler,
)
from ..services.email_service import send_report_email, get_sender_email

router = APIRouter(prefix="/api/scheduled-reports", tags=["Scheduled Reports"])


class ScheduleSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    days_of_week: Optional[List[str]] = None  # ["sun","mon","tue","wed","thu","fri","sat"]
    hour: Optional[int] = None                 # 0-23
    minute: Optional[int] = None               # 0-59
    timezone: Optional[str] = None
    period_days: Optional[int] = None
    recipients: Optional[List[EmailStr]] = None
    sender_email: Optional[EmailStr] = None
    portal_base_url: Optional[str] = None


class TriggerRequest(BaseModel):
    recipients_override: Optional[List[EmailStr]] = None


class TestEmailRequest(BaseModel):
    to: EmailStr


@router.get("/settings")
async def get_settings(current_user: dict = Depends(require_auth)):
    return await get_schedule_settings()


@router.put("/settings")
async def update_settings(payload: ScheduleSettingsUpdate, current_user: dict = Depends(require_admin)):
    # Validate input
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    # Coerce EmailStr -> str for mongo
    if "recipients" in patch:
        patch["recipients"] = [str(e) for e in patch["recipients"]]
    if "sender_email" in patch:
        patch["sender_email"] = str(patch["sender_email"])
    if "days_of_week" in patch:
        valid = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}
        patch["days_of_week"] = [d.lower() for d in patch["days_of_week"] if d.lower() in valid]
    if "hour" in patch and not (0 <= int(patch["hour"]) <= 23):
        raise HTTPException(status_code=400, detail="hour must be 0..23")
    if "minute" in patch and not (0 <= int(patch["minute"]) <= 59):
        raise HTTPException(status_code=400, detail="minute must be 0..59")

    updated = await update_schedule_settings(patch)
    await refresh_scheduler()
    return updated


@router.post("/trigger")
async def trigger_now(payload: TriggerRequest, current_user: dict = Depends(require_admin)):
    """Run the weekly report immediately (for testing)."""
    recipients = [str(r) for r in (payload.recipients_override or [])] if payload.recipients_override else None
    result = await run_weekly_report(tenant_id=current_user.get("tenant_id"), recipients_override=recipients)
    return result


@router.post("/test-email")
async def test_email(payload: TestEmailRequest, current_user: dict = Depends(require_admin)):
    """Send a tiny test email to verify Resend configuration."""
    from ..services.email_service import _DEFAULT_SENDER  # noqa
    html = f"""
    <html><body style="font-family:Helvetica,Arial,sans-serif;">
      <h2 style="color:#0B0E14;">FalconOps AI — Resend Test</h2>
      <p>If you can see this, your Resend integration is working.</p>
      <p style="color:#6B7280;font-size:12px;">Sender: {get_sender_email()}</p>
    </body></html>
    """
    result = await send_report_email(
        recipients=[str(payload.to)],
        subject="FalconOps AI — Test Email",
        html_body=html,
    )
    return result


@router.get("/logs")
async def get_logs(limit: int = Query(20, le=100), current_user: dict = Depends(require_auth)):
    return await get_run_logs(limit)


# ============ PER-TENANT ENDPOINTS ============

@router.get("/tenants")
async def list_all_tenant_schedules(current_user: dict = Depends(require_admin)):
    """Admin only — returns all per-tenant schedule settings."""
    return await list_tenant_schedules()


@router.get("/tenants/{tenant_id}/settings")
async def get_tenant_settings(tenant_id: str, current_user: dict = Depends(require_auth)):
    """Fetch per-tenant schedule. Any auth'd user can view their own tenant; admins can view any."""
    if current_user.get("role") != "admin" and current_user.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return await get_schedule_settings(tenant_id=tenant_id)


@router.put("/tenants/{tenant_id}/settings")
async def update_tenant_settings(
    tenant_id: str,
    payload: ScheduleSettingsUpdate,
    current_user: dict = Depends(require_auth),
):
    """Update per-tenant schedule. Tenant admin for own tenant OR global admin."""
    role = current_user.get("role")
    user_tenant = current_user.get("tenant_id")
    if role != "admin" and not (role == "tenant_admin" and user_tenant == tenant_id):
        # fallback: any admin of the tenant
        if user_tenant != tenant_id:
            raise HTTPException(status_code=403, detail="Access denied")

    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "recipients" in patch:
        patch["recipients"] = [str(e) for e in patch["recipients"]]
    if "sender_email" in patch:
        patch["sender_email"] = str(patch["sender_email"])
    if "days_of_week" in patch:
        valid = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}
        patch["days_of_week"] = [d.lower() for d in patch["days_of_week"] if d.lower() in valid]
    if "hour" in patch and not (0 <= int(patch["hour"]) <= 23):
        raise HTTPException(status_code=400, detail="hour must be 0..23")
    if "minute" in patch and not (0 <= int(patch["minute"]) <= 59):
        raise HTTPException(status_code=400, detail="minute must be 0..59")

    updated = await update_schedule_settings(patch, tenant_id=tenant_id)
    await refresh_tenant_scheduler(tenant_id)
    return updated


@router.post("/tenants/{tenant_id}/trigger")
async def tenant_trigger_now(
    tenant_id: str,
    payload: TriggerRequest,
    current_user: dict = Depends(require_auth),
):
    """Run a per-tenant weekly report immediately."""
    role = current_user.get("role")
    user_tenant = current_user.get("tenant_id")
    if role != "admin" and user_tenant != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    recipients = [str(r) for r in (payload.recipients_override or [])] if payload.recipients_override else None
    result = await run_weekly_report(tenant_id=tenant_id, recipients_override=recipients)
    return result


@router.get("/tenants/{tenant_id}/logs")
async def get_tenant_logs(
    tenant_id: str,
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth),
):
    if current_user.get("role") != "admin" and current_user.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return await get_run_logs(limit, tenant_id=tenant_id)
