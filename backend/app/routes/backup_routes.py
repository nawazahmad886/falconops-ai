"""
FalconOps AI — Database Backup API.

Read routes: require_auth. Triggering an on-demand backup: require_admin — it's a
real subprocess run against the live database, not a preview.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..services import backup_service
from ..utils.auth import require_admin, require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backup", tags=["Backup"])


@router.get("/status")
async def status(current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return await backup_service.get_backup_status()


@router.get("/history")
async def history(limit: int = 30, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    return {"backups": await backup_service.get_backup_history(limit=min(limit, 100))}


@router.post("/run")
async def run_now(current_user: dict = Depends(require_admin)) -> Dict[str, Any]:
    result = await backup_service.run_backup_once(triggered_by=current_user.get("email", "admin"))
    logger.info(f"Backup manually triggered by {current_user.get('email')}: ok={result.get('ok')}")
    return result


__all__ = ["router"]
