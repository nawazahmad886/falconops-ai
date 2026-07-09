"""
FalconOps AI - Report Scheduler Service
Automated weekly/monthly report generation and email delivery
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_db = None


def init_scheduler(db_instance):
    """Initialize the scheduler with db reference."""
    global _db
    _db = db_instance
    if not scheduler.running:
        scheduler.start()
        logger.info("Report scheduler started")
    _sync_schedules_from_db()


def _sync_schedules_from_db():
    """Load existing schedules from DB into APScheduler on startup."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_load_schedules())
        else:
            loop.run_until_complete(_load_schedules())
    except Exception as e:
        logger.warning(f"Could not sync schedules on startup: {e}")


async def _load_schedules():
    """Load active schedules from MongoDB."""
    if _db is None:
        return
    schedules = await _db.report_schedules.find({"enabled": True}, {"_id": 0}).to_list(length=100)
    for sch in schedules:
        _register_job(sch)
    logger.info(f"Loaded {len(schedules)} active report schedules")


def _register_job(schedule: Dict):
    """Register or update a scheduled job in APScheduler."""
    job_id = f"report_{schedule['id']}"

    # Remove existing if any
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)

    freq = schedule.get("frequency", "weekly")
    day_of_week = schedule.get("day_of_week", "mon")
    hour = schedule.get("hour", 8)
    day_of_month = schedule.get("day_of_month", 1)

    if freq == "weekly":
        trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=0)
    elif freq == "monthly":
        trigger = CronTrigger(day=day_of_month, hour=hour, minute=0)
    elif freq == "daily":
        trigger = CronTrigger(hour=hour, minute=0)
    else:
        trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=0)

    scheduler.add_job(
        _execute_scheduled_report,
        trigger=trigger,
        id=job_id,
        args=[schedule["id"]],
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(f"Registered schedule job: {job_id} ({freq})")


async def _execute_scheduled_report(schedule_id: str):
    """Execute a scheduled report: generate + email."""
    if _db is None:
        return

    schedule = await _db.report_schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not schedule or not schedule.get("enabled"):
        return

    logger.info(f"Executing scheduled report: {schedule.get('name', schedule_id)}")

    try:
        # Get the analysis
        analysis_id = schedule.get("analysis_id")
        if not analysis_id:
            # Use the latest analysis
            latest = await _db.event_analyses.find_one(
                {}, {"_id": 0, "id": 1}, sort=[("analyzed_at", -1)]
            )
            if not latest:
                logger.warning("No analysis found for scheduled report")
                return
            analysis_id = latest["id"]

        analysis = await _db.event_analyses.find_one({"id": analysis_id}, {"_id": 0})
        if not analysis:
            logger.warning(f"Analysis {analysis_id} not found")
            return

        result = analysis.get("result", {})
        events_data = await _db.event_data.find_one(
            {"upload_id": analysis.get("upload_id")}, {"_id": 0}
        )
        events = events_data.get("events", []) if events_data else []

        branding = schedule.get("branding", {})
        fmt = schedule.get("format", "pdf")

        from .event_report_service import generate_pdf_report, generate_excel_report

        if fmt == "excel":
            buf = generate_excel_report(result, events, branding)
            filename = f"FalconOps_Report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            buf = generate_pdf_report(result, events, branding)
            filename = f"FalconOps_Report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
            content_type = "application/pdf"

        # Try sending email
        recipients = schedule.get("recipients", [])
        email_sent = False
        if recipients:
            email_sent = await _send_report_email(
                recipients=recipients,
                subject=schedule.get("email_subject", f"FalconOps AI - Scheduled Report ({schedule.get('frequency', 'weekly').title()})"),
                report_buf=buf,
                filename=filename,
                content_type=content_type,
                branding=branding,
            )

        # Log execution
        await _db.report_schedule_logs.insert_one({
            "schedule_id": schedule_id,
            "analysis_id": analysis_id,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "format": fmt,
            "recipients": recipients,
            "email_sent": email_sent,
            "status": "success",
        })

        # Update last_run
        await _db.report_schedules.update_one(
            {"id": schedule_id},
            {"$set": {
                "last_run": datetime.now(timezone.utc).isoformat(),
                "last_status": "success",
                "run_count": schedule.get("run_count", 0) + 1,
            }}
        )

        logger.info(f"Scheduled report executed successfully. Email sent: {email_sent}")

    except Exception as e:
        logger.error(f"Scheduled report failed: {e}")
        await _db.report_schedules.update_one(
            {"id": schedule_id},
            {"$set": {"last_status": f"error: {str(e)[:200]}", "last_run": datetime.now(timezone.utc).isoformat()}}
        )


async def _send_report_email(
    recipients: list,
    subject: str,
    report_buf,
    filename: str,
    content_type: str,
    branding: dict = None,
) -> bool:
    """Send report email via SendGrid."""
    try:
        sendgrid_key = os.environ.get("SENDGRID_API_KEY")
        sender_email = os.environ.get("SENDER_EMAIL", "reports@falconapps.com")

        if not sendgrid_key:
            logger.info(f"SendGrid not configured. Report generated for: {', '.join(recipients)} (file: {filename})")
            # Still log it as queued
            if _db is not None:
                await _db.report_email_queue.insert_one({
                    "id": str(uuid.uuid4()),
                    "recipients": recipients,
                    "subject": subject,
                    "filename": filename,
                    "status": "queued_no_sendgrid",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            return False

        import base64
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Mail, Attachment, FileContent, FileName, FileType, Disposition
        )

        report_buf.seek(0)
        encoded = base64.b64encode(report_buf.read()).decode()
        attachment = Attachment(
            FileContent(encoded),
            FileName(filename),
            FileType(content_type),
            Disposition("attachment"),
        )

        brand = branding or {}
        company = brand.get("company", "FalconOps AI")

        for recipient in recipients:
            message = Mail(
                from_email=sender_email,
                to_emails=recipient,
                subject=subject,
                html_content=f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #0F172A; padding: 24px; text-align: center;">
                        <h1 style="color: #00E0FF; margin: 0;">FalconOps AI</h1>
                        <p style="color: #94A3B8; margin: 4px 0 0;">Enterprise AIOps Platform</p>
                    </div>
                    <div style="padding: 24px; background: #F8FAFC;">
                        <p>Hello,</p>
                        <p>Please find your scheduled <strong>{company}</strong> report attached.</p>
                        <p>This report was automatically generated by FalconOps AI on {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}.</p>
                        <p style="color: #6B7280; font-size: 12px; margin-top: 24px;">
                            {brand.get('footer', 'FalconOps AI - Enterprise AIOps Platform | Confidential')}
                        </p>
                    </div>
                </div>
                """,
            )
            message.attachment = attachment

            sg = SendGridAPIClient(sendgrid_key)
            sg.send(message)

        logger.info(f"Report email sent to {len(recipients)} recipients")
        return True

    except Exception as e:
        logger.error(f"Failed to send report email: {e}")
        return False


# ── CRUD for schedules ──

async def create_schedule(data: Dict[str, Any]) -> Dict:
    """Create a new report schedule."""
    schedule = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "Unnamed Schedule"),
        "analysis_id": data.get("analysis_id"),
        "frequency": data.get("frequency", "weekly"),
        "day_of_week": data.get("day_of_week", "mon"),
        "day_of_month": data.get("day_of_month", 1),
        "hour": data.get("hour", 8),
        "format": data.get("format", "pdf"),
        "recipients": data.get("recipients", []),
        "email_subject": data.get("email_subject", "FalconOps AI - Scheduled Report"),
        "branding": data.get("branding", {}),
        "enabled": data.get("enabled", True),
        "created_by": data.get("created_by", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
        "last_status": None,
        "run_count": 0,
    }

    if _db is not None:
        doc = {k: v for k, v in schedule.items()}
        await _db.report_schedules.insert_one(doc)

    _register_job(schedule)
    return schedule


async def update_schedule(schedule_id: str, data: Dict[str, Any]) -> Optional[Dict]:
    """Update an existing schedule."""
    if _db is None:
        return None

    update_fields = {}
    for key in ["name", "frequency", "day_of_week", "day_of_month", "hour",
                 "format", "recipients", "email_subject", "branding", "enabled", "analysis_id"]:
        if key in data:
            update_fields[key] = data[key]

    if not update_fields:
        return None

    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db.report_schedules.update_one({"id": schedule_id}, {"$set": update_fields})

    schedule = await _db.report_schedules.find_one({"id": schedule_id}, {"_id": 0})
    if schedule:
        if schedule.get("enabled"):
            _register_job(schedule)
        else:
            job_id = f"report_{schedule_id}"
            existing = scheduler.get_job(job_id)
            if existing:
                scheduler.remove_job(job_id)

    return schedule


async def delete_schedule(schedule_id: str) -> bool:
    """Delete a schedule."""
    if _db is None:
        return False

    job_id = f"report_{schedule_id}"
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)

    result = await _db.report_schedules.delete_one({"id": schedule_id})
    return result.deleted_count > 0


async def get_schedules(user_id: str = None) -> list:
    """Get all schedules."""
    if _db is None:
        return []
    query = {}
    schedules = await _db.report_schedules.find(query, {"_id": 0}).to_list(length=100)
    return schedules


async def get_schedule_logs(schedule_id: str, limit: int = 20) -> list:
    """Get execution logs for a schedule."""
    if _db is None:
        return []
    logs = await _db.report_schedule_logs.find(
        {"schedule_id": schedule_id}, {"_id": 0}
    ).sort("executed_at", -1).to_list(length=limit)
    return logs


async def run_schedule_now(schedule_id: str) -> Dict:
    """Manually trigger a scheduled report."""
    await _execute_scheduled_report(schedule_id)
    schedule = await _db.report_schedules.find_one({"id": schedule_id}, {"_id": 0})
    return schedule or {}
