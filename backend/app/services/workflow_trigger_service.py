"""
FalconOps AI - Workflow Trigger Evaluation
Evaluates 'problem' / 'event' / 'ai_anomaly' / 'schedule' triggers on runbooks (the
generalized trigger model added alongside the workflow canvas builder) and fires the
matching ones through the existing real runbook_engine — no parallel execution engine,
this only decides *whether* to call runbook_engine.execute_runbook.

Cooldown-gated, fire-and-forget shape mirrors ai_agents_service's existing
_pipeline_cooldowns/trigger_pipeline pattern so a burst of alerts/events can't re-fire
the same runbook every few milliseconds.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.database import db
from .runbook_engine import runbook_engine

logger = logging.getLogger(__name__)

# Minimum seconds between two automatic firings of the same runbook, regardless of
# which trigger type caused it — prevents a burst of alerts/events from re-running an
# agent call (LLM cost + noise) far more often than useful.
COOLDOWN_SECONDS = 300

_cooldowns: Dict[str, float] = {}

_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "warning": 2, "high": 3, "critical": 4}


def _should_fire(runbook_id: str) -> bool:
    now = time.monotonic()
    last = _cooldowns.get(runbook_id, 0.0)
    if now - last < COOLDOWN_SECONDS:
        return False
    _cooldowns[runbook_id] = now
    return True


def derive_legacy_schedule(trigger: Optional[Dict]) -> Optional[Dict]:
    """Convert a structured trigger.schedule (mode: cron|interval|fixed_time) into the
    legacy {enabled, cron_expression, next_run} shape that execute_due_runbooks (and the
    pre-existing manual /scheduled/execute endpoint) already know how to evaluate — one
    real due-computation path instead of three parallel ones."""
    if not trigger or trigger.get("type") != "schedule":
        return None
    sched = trigger.get("schedule") or {}
    mode = sched.get("mode", "cron")

    if mode == "interval":
        try:
            minutes = max(1, int(sched.get("interval_minutes", 60)))
        except (TypeError, ValueError):
            minutes = 60
        cron_expr = f"*/{minutes} * * * *"
    elif mode == "fixed_time":
        raw = str(sched.get("fixed_time") or "00:00")
        parts = raw.split(":")
        try:
            hh, mm = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            hh, mm = 0, 0
        cron_expr = f"{mm} {hh} * * *"
    else:
        cron_expr = sched.get("cron_expression") or "0 * * * *"

    next_run = datetime.now(timezone.utc).isoformat()
    try:
        from croniter import croniter
        next_run = croniter(cron_expr, datetime.now(timezone.utc)).get_next(datetime).isoformat()
    except Exception as e:
        logger.debug(f"croniter unavailable for next_run computation: {e}")

    return {"enabled": True, "cron_expression": cron_expr, "timezone": "UTC", "next_run": next_run}


async def _fire(runbook: Dict, trigger_source: str, trigger_context: Dict) -> None:
    if not _should_fire(runbook["id"]):
        return
    try:
        await runbook_engine.execute_runbook(
            runbook_id=runbook["id"],
            trigger_source=trigger_source,
            trigger_context=trigger_context,
            user_email="system:workflow_trigger",
            tenant_id=runbook.get("tenant_id"),
        )
    except Exception as e:
        logger.warning(f"Workflow trigger execution failed for runbook {runbook['id']}: {e}")


async def evaluate_problem_triggers(alert: Dict) -> None:
    """Fire every 'problem' trigger runbook whose filter matches this alert. Called
    fire-and-forget from alert_engine.create_alert alongside _auto_investigate — must
    never affect alert creation itself."""
    try:
        runbooks = await db.runbooks.find(
            {"trigger.type": "problem"}, {"_id": 0}
        ).to_list(200)
    except Exception as e:
        logger.warning(f"Problem-trigger lookup failed: {e}")
        return

    severity = (alert.get("severity") or "").lower()
    service = alert.get("service")

    for rb in runbooks:
        pf = (rb.get("trigger") or {}).get("problem_filter") or {}
        allowed_severities = [s.lower() for s in pf.get("severity", [])] if pf.get("severity") else None
        allowed_services = pf.get("service") or None

        if allowed_severities and severity not in allowed_severities:
            continue
        if allowed_services and service not in allowed_services:
            continue

        await _fire(rb, "problem", alert)


async def evaluate_event_triggers(event: Dict) -> None:
    """Fire every 'event' trigger runbook whose filter matches this ingested SOC event.
    Called fire-and-forget from soc_ingestion_service.ingest_event."""
    try:
        runbooks = await db.runbooks.find(
            {"trigger.type": "event"}, {"_id": 0}
        ).to_list(200)
    except Exception as e:
        logger.warning(f"Event-trigger lookup failed: {e}")
        return

    source = (event.get("source") or "").lower()
    message = (event.get("message") or "").lower()

    for rb in runbooks:
        ef = (rb.get("trigger") or {}).get("event_filter") or {}
        want_source = (ef.get("source") or "").lower().strip()
        want_keyword = (ef.get("keyword") or "").lower().strip()

        if want_source and want_source not in source:
            continue
        if want_keyword and want_keyword not in message:
            continue

        await _fire(rb, "event", event)


async def evaluate_anomaly_triggers(threat: Dict) -> None:
    """Fire every 'ai_anomaly' trigger runbook whose min-severity filter is met by this
    real detected threat/anomaly record. Called fire-and-forget from
    security_service.ThreatDetectionEngine._store_threat."""
    try:
        runbooks = await db.runbooks.find(
            {"trigger.type": "ai_anomaly"}, {"_id": 0}
        ).to_list(200)
    except Exception as e:
        logger.warning(f"Anomaly-trigger lookup failed: {e}")
        return

    severity_rank = _SEVERITY_RANK.get((threat.get("severity") or "").lower(), 0)

    for rb in runbooks:
        af = (rb.get("trigger") or {}).get("anomaly_filter") or {}
        min_rank = _SEVERITY_RANK.get((af.get("min_severity") or "low").lower(), 1)

        if severity_rank < min_rank:
            continue

        await _fire(rb, "ai_anomaly", threat)


async def execute_due_runbooks(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Shared due-runbook execution logic — used by both the manual
    POST /runbooks/scheduled/execute endpoint and the automatic background scheduler
    below, so there is exactly one implementation of 'what counts as due'."""
    from ..utils.auth import build_tenant_query

    now = datetime.now(timezone.utc).isoformat()
    query: Dict[str, Any] = {
        "schedule.enabled": True,
        "schedule.next_run": {"$lte": now},
    }
    if tenant_id:
        query = build_tenant_query(tenant_id, query)

    due_runbooks = await db.runbooks.find(query, {"_id": 0}).to_list(50)

    results: List[Dict[str, Any]] = []
    for runbook in due_runbooks:
        result = await runbook_engine.execute_runbook(
            runbook_id=runbook["id"],
            trigger_source="scheduled",
            trigger_context={"scheduled_at": now},
            user_email="scheduler",
            tenant_id=runbook.get("tenant_id"),
        )

        try:
            from croniter import croniter
            cron = croniter(runbook["schedule"]["cron_expression"], datetime.now(timezone.utc))
            next_run = cron.get_next(datetime).isoformat()
            await db.runbooks.update_one(
                {"id": runbook["id"]},
                {"$set": {"schedule.next_run": next_run}},
            )
        except Exception as e:
            logger.debug(f"next_run computation skipped for runbook {runbook['id']}: {e}")

        results.append({
            "runbook_id": runbook["id"],
            "runbook_name": runbook["name"],
            "success": result.get("success", False),
        })

    return {"executed": len(results), "results": results}


async def runbook_schedule_scheduler() -> None:
    """Background scheduler that actually calls execute_due_runbooks on a timer — closes
    the previously-real gap where schedule.next_run was computed and stored but nothing
    ever polled for due runbooks automatically (only the manual endpoint did). Same
    while/sleep + broad try/except shape as the other schedulers registered in
    main.py's lifespan (e.g. autonomous_ops_orchestrator.sla_breach_scheduler)."""
    while True:
        try:
            await execute_due_runbooks()
        except Exception as e:
            logger.warning(f"runbook_schedule_scheduler tick failed: {e}")
        await asyncio.sleep(60)
