"""
Approval-expiry sweep: a DESTRUCTIVE-action approval request that gets no
response within APPROVAL_EXPIRY_MINUTES auto-escalates, per
SOP-NOC-AD-001 [AD-001-4].

This module only exposes the check function. Wiring it to run on an
interval (e.g. via APScheduler, already pinned in requirements.txt and used
elsewhere in this codebase for scheduled jobs — see
weekly_report_scheduler_service.py for the existing pattern) is an
app-startup concern in server.py/main.py that this build does not touch:
that file wasn't read while authoring this phase, and guessing at the wrong
FastAPI startup-hook shape for an unfamiliar file risks a worse outcome than
leaving one explicit integration TODO. Wire with something like:

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler.add_job(check_expired_approvals, "interval", minutes=1)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from ..actions.registry import APPROVAL_EXPIRY_MINUTES
from .runner import resume_investigation

logger = logging.getLogger(__name__)


async def check_expired_approvals() -> List[str]:
    """Finds every investigation stuck in awaiting_approval past the expiry
    window and resumes each with an auto-rejection. Returns the incident_ids
    escalated this sweep."""
    from ....core.database import db

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=APPROVAL_EXPIRY_MINUTES)
    cursor = db.rased_investigations.find(
        {"status": "awaiting_approval", "updated_at": {"$lt": cutoff}}, {"_id": 0, "incident_id": 1},
    )
    expired_ids = [doc["incident_id"] async for doc in cursor]

    for incident_id in expired_ids:
        try:
            final_state = await resume_investigation(
                incident_id, {"approved": False, "reason": "auto-escalated: approval expired"},
            )
            doc = final_state.model_dump()
            doc["updated_at"] = datetime.now(timezone.utc)
            await db.rased_investigations.update_one({"incident_id": incident_id}, {"$set": doc}, upsert=True)
        except Exception as exc:
            logger.warning(f"rased approval-expiry resume failed for {incident_id}: {exc}")

    return expired_ids


__all__ = ["check_expired_approvals"]
