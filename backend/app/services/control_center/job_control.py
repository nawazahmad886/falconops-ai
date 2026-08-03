"""
Real pause/resume for FalconOps's background scheduler jobs.

FalconOps is one FastAPI process (main.py mounts all ~90 route modules onto
a single app) — there is no fleet of independent microservices to start/stop.
What DOES genuinely and safely exist as independent, controllable units are
the background asyncio loops and schedulers living inside that one process.
Confirmed by reading main.py directly: three control mechanisms, matched to
how each job actually already works — nothing here is invented:

1. "start_stop_fn" — three jobs (monitoring, uptime monitor, legacy report
   scheduler) already have start_X_scheduler()/stop_X_scheduler() pairs that
   main.py itself calls on every boot/shutdown. Pause/resume here just calls
   those same existing functions on demand instead of only at process
   lifecycle boundaries.
2. "asyncio_task" — ten raw `asyncio.create_task()` loops declared as
   module-level globals in main.py (metrics processor, event-bus consumer,
   SLA-breach/threat-intel/vuln-sync/compliance/generic-ingestion schedulers,
   connector poll, resource-explorer bridge, runbook schedule-trigger).
   Pause cancels the existing Task exactly as main.py's own shutdown path
   already does; resume re-creates it by calling the identical coroutine
   factory main.py's lifespan() used at startup, and reassigns the same
   main.py global — so self_monitor.py's existing status check (which reads
   that same global) keeps working correctly afterward.
3. "apscheduler" — two jobs (report_scheduler_service, weekly_report_scheduler_service)
   are already AsyncIOScheduler instances. Pause/resume calls the library's
   own real pause()/resume() — lower risk than hand-rolling control for
   these two, since APScheduler already does this correctly.

Every pause/resume call is a real state change to a real running coroutine —
there is no "preview" mode here, unlike remediation_service.py/
k8s_healing_service.py/action_broker_schema.py. That is deliberate: unlike
those (which propose actions against infrastructure this app doesn't
control), these jobs run inside this exact process, so pausing one has a
knowable, bounded, reversible blast radius — the job stops polling/consuming
until resumed, nothing else is affected.
"""
import asyncio
import importlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..autonomous_ops_orchestrator import sla_breach_scheduler
from ..compliance_service import compliance_snapshot_scheduler
from ..kafka_pipeline import consumer as kafka_consumer
from ..metrics_timeseries_service import metrics_timeseries_service
from ..monitoring_service import start_monitoring_scheduler, stop_monitoring_scheduler
from ..reports_service import start_report_scheduler, stop_report_scheduler
from ..resource_explorer_service import resource_bridge_scheduler
from ..soc_ingestion_service import generic_ingestion_scheduler
from ..threat_intel_service import threat_intel_refresh_scheduler
from ..uptime_monitor_service import start_uptime_scheduler, stop_uptime_scheduler
from ..vulnerability_service import vulnerability_sync_scheduler
from ..workflow_trigger_service import runbook_schedule_scheduler
from ...connectors.scheduler import connector_poll_scheduler

logger = logging.getLogger(__name__)

# Watchdog: checks every asyncio_task-kind job once per interval and
# auto-resumes any that crashed (task.exception() is not None) or stopped
# unexpectedly — but bounded, so a job that's crash-looping (bad config, dead
# downstream dependency) doesn't spin CPU/log noise forever. After
# AUTO_RESTART_MAX_ATTEMPTS restarts within AUTO_RESTART_WINDOW_MINUTES, the
# watchdog stops touching that job and leaves it crashed for a human to look
# at — visible via list_jobs() and the activity timeline, never silent.
WATCHDOG_INTERVAL_SECONDS = 60
AUTO_RESTART_MAX_ATTEMPTS = 3
AUTO_RESTART_WINDOW_MINUTES = 60
WATCHDOG_JOB_ID = "job_watchdog"

# job_id -> list of UTC restart timestamps within the current window. Kept
# in-process (not persisted) deliberately: this is a rate-limit on the
# watchdog's own behavior, not an audit record — control_center_events (via
# _log_auto_restart) is the durable, queryable trail of what happened.
_auto_restart_history: Dict[str, List[datetime]] = {}


def _should_auto_restart(job_id: str) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=AUTO_RESTART_WINDOW_MINUTES)
    history = [ts for ts in _auto_restart_history.get(job_id, []) if ts >= cutoff]
    _auto_restart_history[job_id] = history
    return len(history) < AUTO_RESTART_MAX_ATTEMPTS


async def _log_auto_restart(job_id: str, prior_status: str, result: Dict[str, Any]) -> None:
    from ...core.database import db

    _auto_restart_history.setdefault(job_id, []).append(datetime.now(timezone.utc))
    try:
        await db.control_center_events.insert_one({
            "kind": "job_auto_restart",
            "job_id": job_id,
            "prior_status": prior_status,
            "result": result,
            "attempt_count_in_window": len(_auto_restart_history[job_id]),
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning(f"failed to record auto-restart event for {job_id}: {e}")


def _main():
    # Lazy import to dodge the circular import (main.py -> app.routes ->
    # ... -> this module) — self_monitor.py already does the identical
    # lazy `import main` for the same reason, reading the same globals.
    import main as _main_module
    return _main_module


JOB_REGISTRY: List[Dict[str, Any]] = [
    {"id": "metrics_processor", "label": "Metrics Stream Processor", "kind": "asyncio_task",
     "attr": "metrics_processor_task", "factory": lambda: metrics_timeseries_service.process_stream()},
    {"id": "kafka_consumer", "label": "Event Bus Consumer (Kafka/Mongo fallback)", "kind": "asyncio_task",
     "attr": "kafka_consumer_task", "factory": lambda: kafka_consumer.start_consuming()},
    {"id": "sla_breach", "label": "SLA-Breach Escalation Scheduler", "kind": "asyncio_task",
     "attr": "sla_breach_task", "factory": lambda: sla_breach_scheduler()},
    {"id": "threat_intel", "label": "Threat Intel Feed Refresh", "kind": "asyncio_task",
     "attr": "threat_intel_task", "factory": lambda: threat_intel_refresh_scheduler()},
    {"id": "vuln_sync", "label": "Vulnerability Sync", "kind": "asyncio_task",
     "attr": "vuln_sync_task", "factory": lambda: vulnerability_sync_scheduler()},
    {"id": "compliance_snapshot", "label": "Compliance Snapshot Scheduler", "kind": "asyncio_task",
     "attr": "compliance_snapshot_task", "factory": lambda: compliance_snapshot_scheduler()},
    {"id": "generic_ingestion", "label": "Generic Source Ingestion Poller", "kind": "asyncio_task",
     "attr": "generic_ingestion_task", "factory": lambda: generic_ingestion_scheduler()},
    {"id": "connector_poll", "label": "Connector SDK Poll Scheduler", "kind": "asyncio_task",
     "attr": "connector_poll_task", "factory": lambda: connector_poll_scheduler()},
    {"id": "resource_bridge", "label": "Resource Explorer Bridge/Sync", "kind": "asyncio_task",
     "attr": "resource_bridge_task", "factory": lambda: resource_bridge_scheduler()},
    {"id": "runbook_schedule", "label": "Runbook Schedule-Trigger Executor", "kind": "asyncio_task",
     "attr": "runbook_schedule_task", "factory": lambda: runbook_schedule_scheduler()},
    {"id": "monitoring", "label": "Monitoring Engine Scheduler", "kind": "start_stop_fn",
     "start": start_monitoring_scheduler, "stop": stop_monitoring_scheduler},
    {"id": "uptime_monitor", "label": "Uptime Monitor Scheduler", "kind": "start_stop_fn",
     "start": start_uptime_scheduler, "stop": stop_uptime_scheduler},
    {"id": "legacy_report_scheduler", "label": "Legacy Report Scheduler", "kind": "start_stop_fn",
     "start": start_report_scheduler, "stop": stop_report_scheduler},
    {"id": "report_scheduler", "label": "Report Scheduler (APScheduler)", "kind": "apscheduler",
     "resolver": lambda: importlib.import_module("app.services.report_scheduler_service").scheduler},
    {"id": "weekly_report_scheduler", "label": "Weekly Enterprise Report Scheduler (APScheduler)", "kind": "apscheduler",
     "resolver": lambda: importlib.import_module("app.services.weekly_report_scheduler_service")._scheduler},
    {"id": WATCHDOG_JOB_ID, "label": "Job Watchdog (auto-restart)", "kind": "asyncio_task",
     "attr": "job_watchdog_task", "factory": lambda: watchdog_loop()},
]

_JOBS_BY_ID = {j["id"]: j for j in JOB_REGISTRY}

# "start_stop_fn" jobs wrap module-private scheduler state in their own
# service files (no Task handle to introspect, unlike the asyncio_task
# kind) — there is no live way to check whether e.g. monitoring_service's
# internal task is actually still alive. main.py calls start_X_scheduler()
# for all three of these at every boot, so "running" is the honest default
# assumption until this module's own pause/resume changes it — "unknown"
# would be technically more cautious but actively misleading on first load,
# when in reality all three are almost certainly running.
_START_STOP_LAST_KNOWN: Dict[str, str] = {
    "monitoring": "running", "uptime_monitor": "running", "legacy_report_scheduler": "running",
}


def _find_job(job_id: str) -> Dict[str, Any]:
    job = _JOBS_BY_ID.get(job_id)
    if job is None:
        raise ValueError(f"Unknown job_id: {job_id!r}. Known: {sorted(_JOBS_BY_ID)}")
    return job


def _task_status(task) -> Dict[str, Optional[str]]:
    # None covers two cases we deliberately don't distinguish: explicitly
    # paused via this module, or never started at boot (e.g. Redis was
    # unreachable when metrics_processor_task tried to initialize). Both are
    # correctly "not running, safe to Resume" from the operator's point of
    # view — Resume re-creates the task fresh either way.
    if task is None:
        return {"status": "paused", "error": None}
    if not task.done():
        return {"status": "running", "error": None}
    if task.cancelled():
        return {"status": "paused", "error": None}
    exc = task.exception()
    if exc is not None:
        return {"status": "crashed", "error": str(exc)[:300]}
    return {"status": "stopped_unexpectedly", "error": None}


async def list_jobs() -> List[Dict[str, Any]]:
    m = _main()
    out = []
    for job in JOB_REGISTRY:
        entry = {"id": job["id"], "label": job["label"], "kind": job["kind"]}
        if job["kind"] == "asyncio_task":
            task = getattr(m, job["attr"], None)
            entry.update(_task_status(task))
        elif job["kind"] == "start_stop_fn":
            # No task handle to introspect — these wrap module-private
            # scheduler state in their own service files. Controllable
            # either way; status reflects "we called start" vs "we called
            # stop" most recently rather than live introspection.
            entry["status"] = _START_STOP_LAST_KNOWN.get(job["id"], "unknown")
            entry["error"] = None
        elif job["kind"] == "apscheduler":
            try:
                scheduler = job["resolver"]()
                entry["status"] = "running" if getattr(scheduler, "running", False) else "paused"
                entry["error"] = None
            except Exception as e:
                entry["status"] = "crashed"
                entry["error"] = str(e)[:300]
        out.append(entry)
    return out


async def pause_job(job_id: str) -> Dict[str, Any]:
    job = _find_job(job_id)
    now = datetime.now(timezone.utc).isoformat()

    if job["kind"] == "asyncio_task":
        m = _main()
        task = getattr(m, job["attr"], None)
        if task is None or task.done():
            return {"ok": False, "error": "job is not currently running", "at": now}
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"job {job_id} raised while being cancelled: {e}")
        setattr(m, job["attr"], None)
        return {"ok": True, "status": "paused", "at": now}

    if job["kind"] == "start_stop_fn":
        try:
            job["stop"]()
        except Exception as e:
            return {"ok": False, "error": str(e)[:300], "at": now}
        _START_STOP_LAST_KNOWN[job_id] = "paused"
        return {"ok": True, "status": "paused", "at": now}

    if job["kind"] == "apscheduler":
        try:
            job["resolver"]().pause()
        except Exception as e:
            return {"ok": False, "error": str(e)[:300], "at": now}
        return {"ok": True, "status": "paused", "at": now}

    return {"ok": False, "error": f"unknown job kind {job['kind']}", "at": now}


async def resume_job(job_id: str) -> Dict[str, Any]:
    job = _find_job(job_id)
    now = datetime.now(timezone.utc).isoformat()

    if job["kind"] == "asyncio_task":
        m = _main()
        existing = getattr(m, job["attr"], None)
        if existing is not None and not existing.done():
            return {"ok": False, "error": "job is already running", "at": now}
        try:
            new_task = asyncio.create_task(job["factory"]())
        except Exception as e:
            return {"ok": False, "error": str(e)[:300], "at": now}
        setattr(m, job["attr"], new_task)
        return {"ok": True, "status": "resumed", "at": now}

    if job["kind"] == "start_stop_fn":
        try:
            job["start"]()
        except Exception as e:
            return {"ok": False, "error": str(e)[:300], "at": now}
        _START_STOP_LAST_KNOWN[job_id] = "running"
        return {"ok": True, "status": "resumed", "at": now}

    if job["kind"] == "apscheduler":
        try:
            job["resolver"]().resume()
        except Exception as e:
            return {"ok": False, "error": str(e)[:300], "at": now}
        return {"ok": True, "status": "resumed", "at": now}

    return {"ok": False, "error": f"unknown job kind {job['kind']}", "at": now}


async def check_and_auto_restart_once() -> List[Dict[str, Any]]:
    """One watchdog pass: resume any asyncio_task-kind job that's crashed or
    stopped unexpectedly, subject to the bounded-retry window. Excludes the
    watchdog job itself (it doesn't restart itself)."""
    m = _main()
    actions: List[Dict[str, Any]] = []
    for job in JOB_REGISTRY:
        if job["kind"] != "asyncio_task" or job["id"] == WATCHDOG_JOB_ID:
            continue
        task = getattr(m, job["attr"], None)
        status = _task_status(task)["status"]
        if status not in ("crashed", "stopped_unexpectedly"):
            continue
        if not _should_auto_restart(job["id"]):
            logger.warning(
                f"job {job['id']} is {status} but has hit the auto-restart "
                f"limit ({AUTO_RESTART_MAX_ATTEMPTS} in {AUTO_RESTART_WINDOW_MINUTES}m) "
                "- leaving it down for manual intervention"
            )
            continue
        try:
            result = await resume_job(job["id"])
        except Exception as e:
            result = {"ok": False, "error": str(e)[:300]}
        await _log_auto_restart(job["id"], status, result)
        actions.append({"job_id": job["id"], "prior_status": status, "result": result})
        logger.info(f"watchdog auto-restarted job {job['id']} (was {status}): {result}")
    return actions


async def watchdog_loop() -> None:
    """Runs forever as its own asyncio_task (see JOB_REGISTRY's job_watchdog
    entry) — pausable/resumable through the same pause_job/resume_job API as
    every other job here, so operators can turn auto-restart off entirely."""
    while True:
        try:
            await check_and_auto_restart_once()
        except Exception as e:
            logger.error(f"watchdog pass failed: {e}")
        await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)


__all__ = ["JOB_REGISTRY", "list_jobs", "pause_job", "resume_job", "check_and_auto_restart_once", "watchdog_loop"]
