"""
FalconOps AI — Database Backup Automation.

Before this, backup/restore was documentation-only (docs/ADMIN_GUIDE.md's manual
`docker compose exec mongo mongodump` instructions) — no code ever ran it. This is
a real, scheduled `mongodump` job: runs on an interval, writes a gzip archive to a
persistent volume, records every attempt (success or failure) to db.backup_history
so failures are visible instead of silently not happening, and rotates old backups
by count.

Deliberately scoped to backup creation only, not restore — restoring overwrites a
live database and needs its own explicit, carefully-confirmed workflow (the manual
`mongorestore` path in ADMIN_GUIDE.md remains the documented way to restore).

Reuses the Control Center's existing job-control/watchdog infrastructure (see
job_control.py) rather than building a second scheduling mechanism: registered
there as an asyncio_task, so it's pausable/resumable from the Control Center UI
and auto-restarted by the watchdog like every other background job.
"""
import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/var/backups/falconops"))
BACKUP_INTERVAL_HOURS = float(os.environ.get("BACKUP_INTERVAL_HOURS", "24"))
BACKUP_RETENTION_COUNT = int(os.environ.get("BACKUP_RETENTION_COUNT", "7"))

_indexes_ready = False


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await db.backup_history.create_index([("started_at", -1)], name="backup_history_started")
        _indexes_ready = True
    except Exception as e:
        logger.warning("backup_history index creation skipped: %s", e)


def _mongo_uri_and_db() -> Optional[Dict[str, str]]:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return None
    return {"uri": mongo_url, "db": db_name}


async def run_backup_once(triggered_by: str = "scheduler") -> Dict[str, Any]:
    """One backup attempt. Always records a db.backup_history entry — success or
    failure — so a broken backup job is visible on the Control Center / activity
    timeline instead of just quietly not running."""
    await _ensure_indexes()
    started = datetime.now(timezone.utc)
    record: Dict[str, Any] = {
        "id": f"bkp_{started.strftime('%Y%m%d%H%M%S')}",
        "started_at": started,
        "triggered_by": triggered_by,
        "ok": False,
    }

    mongodump_path = shutil.which("mongodump")
    if not mongodump_path:
        record["error"] = ("mongodump not found on PATH — install the mongodb-database-tools "
                            "package in the backend image (see Dockerfile)")
        await db.backup_history.insert_one(dict(record))
        logger.error(record["error"])
        return record

    conn = _mongo_uri_and_db()
    if conn is None:
        record["error"] = "MONGO_URL/DB_NAME not set — cannot determine what to back up"
        await db.backup_history.insert_one(dict(record))
        logger.error(record["error"])
        return record

    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        record["error"] = f"cannot create/access {BACKUP_DIR}: {e}"
        await db.backup_history.insert_one(dict(record))
        logger.error(record["error"])
        return record

    archive_path = BACKUP_DIR / f"{record['id']}.archive.gz"
    cmd = [
        mongodump_path, f"--uri={conn['uri']}", f"--db={conn['db']}",
        "--gzip", f"--archive={archive_path}",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
        finished = datetime.now(timezone.utc)
        record["finished_at"] = finished
        record["duration_seconds"] = round((finished - started).total_seconds(), 1)
        if proc.returncode == 0:
            record["ok"] = True
            record["path"] = str(archive_path)
            record["size_bytes"] = archive_path.stat().st_size if archive_path.exists() else None
            logger.info(f"Backup succeeded: {archive_path} ({record['size_bytes']} bytes, "
                        f"{record['duration_seconds']}s)")
        else:
            record["error"] = (stderr or b"").decode(errors="replace")[:2000]
            logger.error(f"mongodump exited {proc.returncode}: {record['error']}")
    except asyncio.TimeoutError:
        record["error"] = "mongodump timed out after 30 minutes"
        logger.error(record["error"])
    except Exception as e:
        record["error"] = str(e)[:2000]
        logger.error(f"Backup failed: {e}")

    await db.backup_history.insert_one(dict(record))
    if record["ok"]:
        await _rotate_old_backups()
    return record


async def _rotate_old_backups() -> None:
    """Keep only the most recent BACKUP_RETENTION_COUNT successful backups on disk —
    deletes the actual .gz files for older ones, but leaves their backup_history
    rows intact (a record that a backup happened and was later rotated out is still
    useful audit trail, distinct from the file no longer existing)."""
    successful = await db.backup_history.find(
        {"ok": True}, {"_id": 0, "id": 1, "path": 1},
    ).sort("started_at", -1).to_list(length=1000)
    for old in successful[BACKUP_RETENTION_COUNT:]:
        path = old.get("path")
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Rotated out old backup: {path}")
            except Exception as e:
                logger.warning(f"Failed to remove old backup {path}: {e}")


async def get_backup_history(limit: int = 30) -> List[Dict[str, Any]]:
    return await db.backup_history.find({}, {"_id": 0}).sort("started_at", -1).limit(limit).to_list(limit)


async def get_backup_status() -> Dict[str, Any]:
    last = await db.backup_history.find_one({}, {"_id": 0}, sort=[("started_at", -1)])
    last_success = await db.backup_history.find_one({"ok": True}, {"_id": 0}, sort=[("started_at", -1)])
    return {
        "configured": shutil.which("mongodump") is not None,
        "backup_dir": str(BACKUP_DIR),
        "interval_hours": BACKUP_INTERVAL_HOURS,
        "retention_count": BACKUP_RETENTION_COUNT,
        "last_attempt": last,
        "last_success": last_success,
    }


async def backup_loop() -> None:
    """Runs forever as its own asyncio_task (see job_control.JOB_REGISTRY's
    backup_scheduler entry) — pausable/resumable/auto-restarted through the same
    Control Center machinery as every other background job."""
    while True:
        try:
            await run_backup_once(triggered_by="scheduler")
        except Exception as e:
            logger.error(f"backup_loop pass failed: {e}")
        await asyncio.sleep(BACKUP_INTERVAL_HOURS * 3600)


__all__ = ["run_backup_once", "get_backup_history", "get_backup_status", "backup_loop"]
