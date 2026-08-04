"""
Unified activity timeline for the Control Center.

FalconOps already logs administrative/operational activity — it's just
scattered across nine independent subsystems, each with its own collection
and its own narrow, subsystem-specific view (RBAC's audit page, the Admin
Console's config-audit tab, etc.). Nothing here is a new writer; this reads
each existing trail (reusing an existing getter function wherever one
exists) and normalizes into one shape, merged and sorted by time. If a
subsystem's own dedicated view needs more detail than this summary line,
that view is still the right place to look — this is a cross-cutting feed,
not a replacement for any of them.
"""
import asyncio
import logging
from typing import Any, Dict, List

from ..agentic_workflow_service import list_decision_log
from ..connector_dispatcher import get_dispatch_logs
from ..feature_flags_service import list_audit_log as list_feature_audit_log
from ..rbac_service import get_audit_logs as get_rbac_audit_logs
from ..remediation_service import get_remediation_history

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_HOURS = 168  # 7 days


def _safe(kind: str):
    """Decorator-less guard: one subsystem's read failure (bad data, a
    down dependency) must not blank out the other seven."""
    def wrap(fn):
        async def inner(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                logger.warning(f"activity timeline: {kind} read failed: {e}")
                return []
        return inner
    return wrap


@_safe("agentic_decision_log")
async def _agentic_events(limit: int) -> List[Dict[str, Any]]:
    rows = await list_decision_log(limit=limit)
    return [{
        "kind": "agentic_decision", "title": f"Supervisor routed to {r.get('routed_to')}",
        "detail": r.get("output_summary"), "actor": "system", "at": r.get("created_at"),
        "severity": "info",
    } for r in rows]


@_safe("remediation_history")
async def _remediation_events(limit: int) -> List[Dict[str, Any]]:
    rows = await get_remediation_history(limit=limit)
    return [{
        "kind": "remediation", "title": f"Remediation previewed: {r.get('action_name')}",
        "detail": r.get("result"), "actor": r.get("triggered_by"), "at": r.get("started_at"),
        "severity": "warning" if r.get("status") == "failed" else "info",
    } for r in rows]


@_safe("feature_audit_log")
async def _feature_flag_events(limit: int) -> List[Dict[str, Any]]:
    rows = await list_feature_audit_log(limit=limit)
    return [{
        "kind": "config_change", "title": f"Platform configuration changed ({r.get('diff_count', 0)} field(s))",
        "detail": r.get("diffs"), "actor": r.get("changed_by"), "at": r.get("changed_at"),
        "severity": "info",
    } for r in rows]


@_safe("audit_logs")
async def _rbac_events(limit: int, window_hours: int) -> List[Dict[str, Any]]:
    result = await get_rbac_audit_logs(hours=window_hours, limit=limit)
    return [{
        "kind": "security", "title": f"{r.get('action')} — {r.get('resource', '')}".strip(" —"),
        "detail": r.get("detail"), "actor": r.get("user_email"), "at": r.get("timestamp"),
        "severity": "critical" if r.get("status") == "failed" else "info",
    } for r in result.get("logs", [])]


@_safe("dispatch_logs")
async def _dispatch_events(limit: int) -> List[Dict[str, Any]]:
    rows = await get_dispatch_logs(limit=limit)
    return [{
        "kind": "integration_dispatch", "title": f"{r.get('event_type')} dispatched via {r.get('integration_id')}",
        "detail": r.get("detail"), "actor": "system", "at": r.get("timestamp"),
        "severity": "warning" if not r.get("success", True) else "info",
    } for r in rows]


@_safe("report_schedule_logs")
async def _report_schedule_events(limit: int) -> List[Dict[str, Any]]:
    from ...core.database import db
    rows = await db.report_schedule_logs.find({}, {"_id": 0}).sort("executed_at", -1).limit(limit).to_list(limit)
    return [{
        "kind": "report_execution", "title": f"Scheduled report executed ({r.get('format', 'unknown format')})",
        "detail": {"recipients": r.get("recipients"), "email_sent": r.get("email_sent")},
        "actor": "scheduler", "at": r.get("executed_at"),
        "severity": "warning" if r.get("status") not in (None, "success", "sent") else "info",
    } for r in rows]


@_safe("runbook_logs")
async def _runbook_events(limit: int) -> List[Dict[str, Any]]:
    from ...core.database import db
    rows = await db.runbook_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return [{
        "kind": "runbook_execution", "title": r.get("message") or "Runbook step executed",
        "detail": {"execution_id": r.get("execution_id")}, "actor": "runbook_engine", "at": r.get("timestamp"),
        "severity": "critical" if r.get("level") == "error" else ("warning" if r.get("level") == "warn" else "info"),
    } for r in rows]


@_safe("event_log")
async def _kafka_events(limit: int) -> List[Dict[str, Any]]:
    from ...core.database import db
    rows = await db.event_log.find({}, {"_id": 0}).sort("consumed_at", -1).limit(limit).to_list(limit)
    return [{
        "kind": "platform_event", "title": f"{r.get('topic')}: {r.get('event')}",
        "detail": None, "actor": "event_bus", "at": r.get("consumed_at"),
        "severity": "info",
    } for r in rows]


@_safe("control_center_events")
async def _watchdog_events(limit: int) -> List[Dict[str, Any]]:
    from ...core.database import db
    rows = await db.control_center_events.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return [{
        "kind": "job_auto_restart", "title": f"Job '{r.get('job_id')}' auto-restarted (was {r.get('prior_status')})",
        "detail": {"result": r.get("result"), "attempt_count_in_window": r.get("attempt_count_in_window")},
        "actor": "job_watchdog", "at": r.get("timestamp"),
        "severity": "warning" if not (r.get("result") or {}).get("ok", True) else "info",
    } for r in rows]


@_safe("backup_history")
async def _backup_events(limit: int) -> List[Dict[str, Any]]:
    from ...core.database import db
    rows = await db.backup_history.find({}, {"_id": 0}).sort("started_at", -1).limit(limit).to_list(limit)
    return [{
        "kind": "backup", "title": f"Database backup {'succeeded' if r.get('ok') else 'FAILED'}",
        "detail": {"path": r.get("path"), "size_bytes": r.get("size_bytes"), "error": r.get("error")},
        "actor": r.get("triggered_by", "scheduler"),
        "at": r["started_at"].isoformat() if hasattr(r.get("started_at"), "isoformat") else r.get("started_at"),
        "severity": "info" if r.get("ok") else "critical",
    } for r in rows]


async def get_activity_timeline(limit: int = 100, window_hours: int = DEFAULT_WINDOW_HOURS) -> List[Dict[str, Any]]:
    """Merged, time-sorted feed across all ten subsystems. Each source is
    queried for up to `limit` of its own rows (bounded per-source, not
    globally) so one very chatty subsystem can't crowd out the others before
    the final sort+truncate."""
    per_source_limit = max(10, limit // 4)

    results = await asyncio.gather(
        _agentic_events(per_source_limit),
        _remediation_events(per_source_limit),
        _feature_flag_events(per_source_limit),
        _rbac_events(per_source_limit, window_hours),
        _dispatch_events(per_source_limit),
        _report_schedule_events(per_source_limit),
        _runbook_events(per_source_limit),
        _kafka_events(per_source_limit),
        _watchdog_events(per_source_limit),
        _backup_events(per_source_limit),
    )

    merged: List[Dict[str, Any]] = [event for source_events in results for event in source_events]
    merged.sort(key=lambda e: e.get("at") or "", reverse=True)
    return merged[:limit]


__all__ = ["get_activity_timeline", "DEFAULT_WINDOW_HOURS"]
