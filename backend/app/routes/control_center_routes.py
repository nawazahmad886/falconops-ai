"""
FalconOps AI Platform Control Center API.

Federates existing pages rather than duplicating them: platform health
reuses self_monitor.py's own checks (see platform_overview.py), configuration
management stays on AdminControlConsole/feature_flags_service, and the
monitored-service dependency graph stays on TopologyPage/topology_service.py.
What's genuinely new here: real pause/resume for FalconOps's own background
jobs (job_control.py — see that module's docstring for exactly which
mechanism backs each job and why), and a unified activity timeline
aggregating eight existing audit trails that previously had no cross-cutting
view.

Read routes: require_auth. Job pause/resume: require_admin — these are real
state changes to real running background work, not previews.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..services.control_center import activity_timeline, job_control, platform_overview
from ..utils.auth import require_admin, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control-center", tags=["Control Center"])


@router.get("/overview")
async def get_overview(current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return await platform_overview.get_overview()


@router.get("/dependencies")
async def get_dependencies(current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return platform_overview.get_dependency_map()


@router.get("/components")
async def get_components(current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Every internal application component with a real green/warning/red
    status (see platform_overview.get_service_components's docstring for
    exactly what each color means)."""
    return {"components": await platform_overview.get_service_components()}


@router.get("/jobs")
async def list_jobs(current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return {"jobs": await job_control.list_jobs()}


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str, current_user: dict = Depends(require_admin)) -> Dict[str, Any]:
    try:
        result = await job_control.pause_job(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    logger.info(f"Control Center: {current_user.get('email')} paused job '{job_id}': {result}")
    return result


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str, current_user: dict = Depends(require_admin)) -> Dict[str, Any]:
    try:
        result = await job_control.resume_job(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    logger.info(f"Control Center: {current_user.get('email')} resumed job '{job_id}': {result}")
    return result


@router.get("/activity")
async def get_activity(limit: int = 100, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await activity_timeline.get_activity_timeline(limit=min(limit, 500))
    return {"events": events, "count": len(events)}


__all__ = ["router"]
