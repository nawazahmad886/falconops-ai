"""
FalconOps AI - Report Scheduler Routes
CRUD and execution endpoints for automated report scheduling
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services import report_scheduler_service as sched

router = APIRouter(prefix="/api/report-schedules", tags=["Report Schedules"])


class ScheduleCreate(BaseModel):
    name: str
    analysis_id: Optional[str] = None
    frequency: str = "weekly"
    day_of_week: str = "mon"
    day_of_month: int = 1
    hour: int = 8
    format: str = "pdf"
    recipients: List[str] = []
    email_subject: str = "FalconOps AI - Scheduled Report"
    branding: dict = {}
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    analysis_id: Optional[str] = None
    frequency: Optional[str] = None
    day_of_week: Optional[str] = None
    day_of_month: Optional[int] = None
    hour: Optional[int] = None
    format: Optional[str] = None
    recipients: Optional[List[str]] = None
    email_subject: Optional[str] = None
    branding: Optional[dict] = None
    enabled: Optional[bool] = None


@router.get("")
async def list_schedules(user: dict = Depends(require_auth)):
    """List all report schedules."""
    schedules = await sched.get_schedules(user.get("user_id"))
    return {"schedules": schedules}


@router.post("")
async def create_schedule(body: ScheduleCreate, user: dict = Depends(require_auth)):
    """Create a new report schedule."""
    data = body.dict()
    data["created_by"] = user.get("email", "")
    schedule = await sched.create_schedule(data)
    return schedule


@router.put("/{schedule_id}")
async def update_schedule(schedule_id: str, body: ScheduleUpdate, user: dict = Depends(require_auth)):
    """Update a report schedule."""
    data = {k: v for k, v in body.dict().items() if v is not None}
    result = await sched.update_schedule(schedule_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return result


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str, user: dict = Depends(require_auth)):
    """Delete a report schedule."""
    deleted = await sched.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"deleted": True}


@router.post("/{schedule_id}/run")
async def run_now(schedule_id: str, user: dict = Depends(require_auth)):
    """Manually trigger a scheduled report."""
    result = await sched.run_schedule_now(schedule_id)
    return {"status": "executed", "schedule": result}


@router.get("/{schedule_id}/logs")
async def get_logs(schedule_id: str, user: dict = Depends(require_auth)):
    """Get execution logs for a schedule."""
    logs = await sched.get_schedule_logs(schedule_id)
    return {"logs": logs}
