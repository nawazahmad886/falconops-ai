"""
FalconOps AI - Weekly Enterprise Report Scheduler
Runs the report generator on a configurable cron (default: Sun & Mon 9AM UTC)
and emails branded PDF/DOCX/Excel attachments via Resend.
Schedule is per-global; can be extended per-tenant later.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..core.database import db
from .report_generator_service import (
    fetch_from_soc, fetch_sla_metrics, fetch_tenant_branding,
    generate_ai_summary, generate_docx_report, generate_excel_report,
    generate_pdf_report, store_report,
)
from .email_service import send_report_email, _report_email_html, get_sender_email

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
GLOBAL_JOB_ID = "weekly_enterprise_report"
SETTINGS_DOC_ID = "global"


def _tenant_job_id(tenant_id: str) -> str:
    return f"weekly_enterprise_report:tenant:{tenant_id}"


DEFAULT_SETTINGS = {
    "doc_id": SETTINGS_DOC_ID,
    "enabled": True,
    "days_of_week": ["sun", "mon"],       # list of cron day codes
    "hour": 9,
    "minute": 0,
    "timezone": "UTC",
    "period_days": 7,
    "recipients": [],                     # admin edits in UI
    "sender_email": "onboarding@resend.dev",
    "portal_base_url": "",                # optional — prepended to share links in email
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


# ============ SETTINGS CRUD (Global + Per-Tenant) ============

async def get_schedule_settings(tenant_id: Optional[str] = None) -> Dict:
    """Return global settings if tenant_id is None, else per-tenant settings (falling back to global)."""
    if tenant_id:
        doc = await db.tenant_schedule_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if doc:
            return doc
        # Seed per-tenant from global (so tenant admins see sensible defaults)
        base = await get_schedule_settings(None)
        seed = {k: v for k, v in base.items() if k not in ("doc_id",)}
        seed.update({"tenant_id": tenant_id, "enabled": False})  # opt-in by default
        seed["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.tenant_schedule_settings.insert_one(seed.copy())
        return seed

    doc = await db.report_schedule_settings.find_one({"doc_id": SETTINGS_DOC_ID}, {"_id": 0})
    if not doc:
        await db.report_schedule_settings.insert_one(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()
    return doc


async def update_schedule_settings(patch: Dict, tenant_id: Optional[str] = None) -> Dict:
    """Update global or per-tenant schedule settings."""
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    if tenant_id:
        await db.tenant_schedule_settings.update_one(
            {"tenant_id": tenant_id},
            {"$set": patch},
            upsert=True,
        )
        return await get_schedule_settings(tenant_id)
    await db.report_schedule_settings.update_one(
        {"doc_id": SETTINGS_DOC_ID},
        {"$set": patch},
        upsert=True,
    )
    return await get_schedule_settings(None)


async def list_tenant_schedules() -> List[Dict]:
    """List all tenant-specific schedule settings."""
    return await db.tenant_schedule_settings.find({}, {"_id": 0}).to_list(500)


# ============ SCHEDULE LOGS ============

async def log_run(status: str, detail: Dict, tenant_id: Optional[str] = None) -> None:
    doc = {
        "status": status,
        "detail": detail,
        "tenant_id": tenant_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.report_schedule_logs.insert_one(doc)


async def get_run_logs(limit: int = 20, tenant_id: Optional[str] = None) -> List[Dict]:
    q = {"tenant_id": tenant_id} if tenant_id else {}
    return await db.report_schedule_logs.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


# ============ CORE RUNNER ============

async def run_weekly_report(tenant_id: Optional[str] = None, recipients_override: Optional[List[str]] = None) -> Dict:
    """Generate + store + email a weekly report. Called by cron or manual trigger.
    If tenant_id is provided, uses that tenant's schedule settings and scopes the log.
    """
    settings = await get_schedule_settings(tenant_id=tenant_id)
    period_days = settings.get("period_days", 7)
    recipients = recipients_override if recipients_override else settings.get("recipients", [])
    sender = settings.get("sender_email") or get_sender_email()
    portal_base = (settings.get("portal_base_url") or "").rstrip("/")

    # 1) Fetch alerts + SLA
    parsed = await fetch_from_soc(period_days)
    sla = await fetch_sla_metrics(period_days)
    branding = await fetch_tenant_branding(tenant_id)

    # 2) AI executive summary
    ai_summary = await generate_ai_summary(parsed, sla=sla, executive=True)

    # 3) Generate artifacts
    now = datetime.now(timezone.utc)
    period_label = f"{(now - timedelta(days=period_days)).strftime('%d %b')} – {now.strftime('%d %b %Y')}"
    docx_bytes = generate_docx_report(parsed, ai_summary, period_label)
    excel_bytes = generate_excel_report(parsed, ai_summary)
    pdf_bytes = generate_pdf_report(parsed, ai_summary, sla, branding, period_label)

    # 4) Persist
    report = await store_report(
        parsed, ai_summary, docx_bytes, excel_bytes, period_label,
        pdf_bytes=pdf_bytes, sla=sla, branding=branding,
    )
    report_id = report["report_id"]

    # 5) Build portal URL (points to /portal/:token — token created lazily by /share API)
    #    For scheduled emails, we auto-create a 30-day public share link.
    portal_url = ""
    try:
        from .client_portal_service import create_share_link
        token = await create_share_link(
            report_id=report_id,
            created_by="scheduler",
            expiry_days=30,
            password=None,
        )
        if portal_base:
            portal_url = f"{portal_base}/portal/{token}"
        else:
            portal_url = f"/portal/{token}"
    except Exception as e:
        logger.warning(f"share link create failed: {e}")

    email_result = {"skipped": True, "reason": "no recipients"}
    if recipients:
        html = _report_email_html(
            company=branding.get("company_name", "FalconOps AI"),
            period=period_label,
            stats=sla,
            ai_summary=ai_summary,
            portal_url=portal_url or None,
        )
        attachments = [
            {"filename": f"FalconOps_Report_{report_id}.pdf", "content": pdf_bytes},
            {"filename": f"FalconOps_Report_{report_id}.docx", "content": docx_bytes},
            {"filename": f"FalconOps_Report_{report_id}.xlsx", "content": excel_bytes},
        ]
        email_result = await send_report_email(
            recipients=recipients,
            subject=f"Weekly SOC Report · {period_label} · {branding.get('company_name', 'FalconOps AI')}",
            html_body=html,
            attachments=attachments,
            sender=sender,
        )

    detail = {
        "report_id": report_id,
        "period": period_label,
        "recipients": recipients,
        "email": email_result,
        "portal_url": portal_url,
        "total_alerts": report["total_alerts"],
        "critical_count": report["critical_count"],
        "tenant_id": tenant_id,
    }
    await log_run("success" if email_result.get("ok") or email_result.get("skipped") else "failed", detail, tenant_id=tenant_id)
    return detail


# ============ SCHEDULER LIFECYCLE ============

async def _rebuild_global_job():
    settings = await get_schedule_settings(None)
    assert _scheduler is not None

    try:
        _scheduler.remove_job(GLOBAL_JOB_ID)
    except Exception:
        pass

    if not settings.get("enabled"):
        logger.info("Weekly enterprise report scheduler (global) DISABLED")
        return

    days = settings.get("days_of_week") or ["sun", "mon"]
    trigger = CronTrigger(
        day_of_week=",".join(days),
        hour=settings.get("hour", 9),
        minute=settings.get("minute", 0),
        timezone=settings.get("timezone") or "UTC",
    )
    _scheduler.add_job(run_weekly_report, trigger, id=GLOBAL_JOB_ID,
                       replace_existing=True, misfire_grace_time=3600)
    logger.info(f"Global weekly report scheduled: {days} @ {settings.get('hour')}:{settings.get('minute'):02d} {settings.get('timezone')}")


async def _rebuild_tenant_job(tenant_id: str):
    settings = await get_schedule_settings(tenant_id=tenant_id)
    job_id = _tenant_job_id(tenant_id)

    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass

    if not settings.get("enabled"):
        logger.info(f"Tenant {tenant_id} schedule DISABLED")
        return

    days = settings.get("days_of_week") or ["sun", "mon"]
    trigger = CronTrigger(
        day_of_week=",".join(days),
        hour=settings.get("hour", 9),
        minute=settings.get("minute", 0),
        timezone=settings.get("timezone") or "UTC",
    )
    _scheduler.add_job(
        run_weekly_report,
        trigger, id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,
        kwargs={"tenant_id": tenant_id},
    )
    logger.info(f"Tenant {tenant_id} scheduled: {days} @ {settings.get('hour')}:{settings.get('minute'):02d}")


async def _rebuild_job():
    """Rebuild ALL jobs (global + every tenant)."""
    await _rebuild_global_job()
    tenant_schedules = await list_tenant_schedules()
    for s in tenant_schedules:
        if s.get("tenant_id"):
            await _rebuild_tenant_job(s["tenant_id"])


async def refresh_tenant_scheduler(tenant_id: str):
    if _scheduler is None:
        await init_scheduler()
    else:
        await _rebuild_tenant_job(tenant_id)


async def init_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    await _rebuild_job()


async def refresh_scheduler():
    if _scheduler is None:
        await init_scheduler()
    else:
        await _rebuild_job()
