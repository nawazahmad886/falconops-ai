"""
FalconOps AI - Autonomous Ops Orchestrator

Wires together existing real building blocks (context_engine, intelligence_agents_service,
ai_agents_service, remediation_service, k8s_healing_service, alert_engine,
connector_dispatcher) into one autonomous loop: investigate -> recommend -> validate ->
escalate -> learn.

IMPORTANT — by explicit product decision, this module NEVER executes a remediation
action automatically. investigate_and_recommend() always stops at a persisted
recommendation; a human always triggers execution through the existing (already
dry-run-labeled) Remediation / K8s-Healing preview pages. See remediation_service.py's
and k8s_healing_service.py's module docstrings for why those remain dry-run only.
"""
import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.database import db
from . import context_engine
from . import intelligence_agents_service
from . import ai_agents_service
from . import remediation_service
from . import k8s_healing_service
from . import connector_dispatcher
from .incident_engine import incident_engine
from .alert_engine import alert_engine

logger = logging.getLogger(__name__)

VALIDATION_DELAY_SECONDS = int(os.environ.get("INCIDENT_VALIDATION_DELAY_SECONDS", "120"))
SLA_CHECK_INTERVAL_SECONDS = int(os.environ.get("SLA_CHECK_INTERVAL_SECONDS", "300"))

# Keyword bridge from free-text RCA narrative to remediation_service.RCA_REMEDIATION_MAP's
# canonical keys (a dict lookup on exact strings like "high_cpu"/"disk_full" — free text
# would never match it directly). Same honest keyword-matching style already used
# elsewhere in this codebase (ai_correlation.py's _root_cause_and_actions,
# correlation.py's _determine_root_cause) — not ML classification, just a documented
# heuristic bridge between two real components.
_ROOT_CAUSE_KEYWORDS: List[tuple] = [
    ("high_cpu", ("cpu", "processor")),
    ("high_memory", ("memory", "oom", "out of memory", "ram")),
    ("disk_full", ("disk", "storage full", "no space", "volume full")),
    ("connection_leak", ("connection leak", "connection pool", "too many connections")),
    ("cache_stale", ("cache", "stale data")),
    ("brute_force", ("brute force", "brute-force", "repeated login", "failed logins")),
    ("credential_compromise", ("credential", "compromised account", "leaked credential")),
    ("privilege_escalation", ("privilege escalation",)),
    ("data_exfiltration", ("exfiltrat", "unusual data transfer")),
    ("port_scan", ("port scan", "scanning activity")),
    ("impossible_travel", ("impossible travel",)),
    ("malicious_ip", ("malicious ip", "known bad ip", "blocklisted ip")),
    ("service_down", ("service down", "unreachable", "unavailable", "crash")),
]


def _classify_root_cause_key(text: str) -> Optional[str]:
    lower = (text or "").lower()
    for key, keywords in _ROOT_CAUSE_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return key
    return None


def _fingerprint_incident(incident: Dict[str, Any]) -> str:
    """Same fingerprint scheme as ai_agents_service._fingerprint, and critically the
    same field NAMES as the crew_data dict built in investigate_and_recommend() below
    (service/description/severity) — _fingerprint sorts+joins "key=value" pairs, so
    matching key names (not just similar content) is what makes recall_similar_outcomes()
    actually find these records from run_agent()'s memory lookup."""
    return ai_agents_service._fingerprint({
        "service": (incident.get("affected_services") or [""])[0] if incident else "",
        "description": (incident or {}).get("title", ""),
        "severity": (incident or {}).get("severity", ""),
    })


# ======================== 1. INVESTIGATE + RECOMMEND ========================

async def investigate_and_recommend(
    incident_id: str,
    source_signal: Dict[str, Any],
    tenant_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Autonomous "plan -> investigate -> recommend" loop, triggered automatically when a
    real incident or high-severity alert is created. Always stops at a persisted
    recommendation — no action is ever executed here.
    """
    try:
        service = source_signal.get("service") or source_signal.get("entity_name") or ""
        description = (
            source_signal.get("description") or source_signal.get("title")
            or source_signal.get("message") or ""
        )

        # 1. Real cross-source context (history, topology, runbook, baseline).
        context = await context_engine.enrich({"service": service, "description": description})

        # 2. Deepest available RCA: evidence-citing, tool-calling (Ask FalconOps).
        query = description or f"Investigate incident on {service or 'unknown service'}"
        rca = await intelligence_agents_service.incident_analysis(query=query, service=service or None)

        # 3. Multi-agent narrative crew — now including the Healer (previously excluded
        # from auto-trigger since it only ever produced a recommendation, never executed
        # anything; safe to include now that this whole loop is recommendation-only).
        crew_data = {
            "incident_id": incident_id,
            "service": service,
            "description": description,
            "severity": source_signal.get("severity", ""),
            "rca_summary": rca.get("summary", ""),
        }
        crew = await ai_agents_service.run_crew(crew_data, agents=["rca", "summarizer", "healer"], parallel=True)

        # 4. Map the RCA finding to the real action library.
        root_cause_key = _classify_root_cause_key(f"{rca.get('summary', '')} {description}")
        suggested_actions: List[Dict[str, Any]] = []
        if root_cause_key:
            action_context = {"service": service}
            for k in ("host", "ip_address", "username"):
                if source_signal.get(k):
                    action_context[k] = source_signal[k]
            suggested_actions = await remediation_service.suggest_remediation(root_cause_key, action_context)

        # 5. K8s-flavored suggestion, if this looks Kubernetes-related.
        k8s_suggestion = None
        combined = f"{description} {rca.get('summary', '')}".lower()
        if any(kw in combined for kw in ("pod", "deployment", "kubernetes", "k8s", "container")):
            playbook_id = "restart_deployment" if "deployment" in combined else "restart_pod"
            k8s_suggestion = k8s_healing_service.generate_commands(playbook_id, {
                "deployment": service, "namespace": "default",
                "pod_name": service, "app_label": service,
            })

        recommendation = {
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "tenant_id": tenant_id,
            "source_signal": source_signal,
            "root_cause_summary": rca.get("summary", ""),
            "root_cause_key": root_cause_key,
            "confidence": rca.get("confidence", 0.5),
            "evidence": rca.get("evidence", []),
            "evidence_refs": rca.get("evidence_refs", []),
            "agent_narratives": {
                r.get("agent_id"): r.get("analysis")
                for r in crew.get("results", []) if isinstance(r, dict) and r.get("agent_id")
            },
            "suggested_actions": suggested_actions,
            "k8s_suggestion": k8s_suggestion,
            "context_topology": context.get("topology"),
            "status": "pending_review",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.incident_recommendations.insert_one(recommendation)
        recommendation.pop("_id", None)
        logger.info(f"Autonomous recommendation created for incident {incident_id} "
                    f"(root_cause_key={root_cause_key}, confidence={recommendation['confidence']})")
        return recommendation
    except Exception as e:
        logger.error(f"investigate_and_recommend failed for incident {incident_id}: {e}")
        return None


async def get_recommendation(incident_id: str) -> Optional[Dict[str, Any]]:
    return await db.incident_recommendations.find_one(
        {"incident_id": incident_id}, {"_id": 0}, sort=[("created_at", -1)]
    )


# ======================== 2. VALIDATE ========================

async def _recheck_source_signal(source_signal: Dict[str, Any]) -> bool:
    """Real re-check of whether the original problem is still active. Returns True if
    it looks like it's still failing (i.e. the 'resolved' status shouldn't be trusted)."""
    monitor_id = source_signal.get("monitor_id")
    if monitor_id:
        monitor = await db.monitors.find_one({"id": monitor_id}, {"_id": 0, "status": 1})
        if monitor and monitor.get("status") in ("down", "unhealthy"):
            return True

    service = source_signal.get("service") or source_signal.get("entity_name")
    host = source_signal.get("host")
    open_statuses = ["triggered", "acknowledged", "open"]

    if service:
        still_open = await db.alerts_engine.count_documents({
            "status": {"$in": open_statuses}, "entity_name": service
        }) or await db.alerts.count_documents({
            "status": {"$in": open_statuses}, "service": service
        })
        return bool(still_open)
    if host:
        still_open = await db.alerts_engine.count_documents({
            "status": {"$in": open_statuses}, "tags.host": host
        }) or await db.alerts.count_documents({
            "status": {"$in": open_statuses}, "host": host
        })
        return bool(still_open)
    return False


async def validate_resolution(incident_id: str):
    """Fire-and-forget: after a delay, re-check the original triggering signal to
    confirm a 'resolved' incident actually held, instead of trusting the status change
    at face value. Reopens + escalates on mismatch, and records the outcome either way."""
    await asyncio.sleep(VALIDATION_DELAY_SECONDS)
    try:
        recommendation = await get_recommendation(incident_id)
        incident = await incident_engine.get_incident(incident_id)
        if not incident or incident.get("status") not in ("resolved", "closed"):
            return  # reopened / changed again already, nothing to validate

        source_signal = (recommendation or {}).get("source_signal") or {}
        mttr_seconds = None
        try:
            created = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
            resolved = datetime.fromisoformat(incident["resolved_at"].replace("Z", "+00:00"))
            mttr_seconds = (resolved - created).total_seconds()
        except Exception:
            pass

        still_failing = await _recheck_source_signal(source_signal)
        if still_failing:
            await incident_engine.update_status(
                incident_id, "active", user="system:autonomous_validator",
                notes="Auto-reopened: underlying signal has not actually cleared"
            )
            await _escalate(incident_id, reason="Resolution did not hold — signal still failing")
            await record_outcome(incident_id, (recommendation or {}).get("id"),
                                  action_taken=None, was_effective=False, mttr_seconds=mttr_seconds)
        else:
            await record_outcome(incident_id, (recommendation or {}).get("id"),
                                  action_taken=None, was_effective=True, mttr_seconds=mttr_seconds)
    except Exception as e:
        logger.warning(f"validate_resolution failed for {incident_id}: {e}")


# ======================== 3. ESCALATE ========================

async def _escalate(incident_id: str, reason: str):
    incident = await incident_engine.get_incident(incident_id)
    if not incident:
        return
    for alert_id in (incident.get("alert_ids") or [])[:5]:
        try:
            await alert_engine.escalate_alert(alert_id)
        except Exception:
            pass
    try:
        await connector_dispatcher.dispatch_event("incident_escalation", {
            "id": incident_id,
            "title": incident.get("title"),
            "severity": incident.get("severity"),
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, min_severity="warning")
    except Exception as e:
        logger.warning(f"Escalation dispatch failed for {incident_id}: {e}")


async def check_sla_breaches() -> Dict[str, Any]:
    """Scheduled task: db.incidents_engine already computes sla_breach_at/is_sla_breached
    at creation time, but nothing previously read or acted on them. This is what turns
    that inert data into real autonomous escalation."""
    now_iso = datetime.now(timezone.utc).isoformat()
    breached = await db.incidents_engine.find({
        "status": {"$nin": ["resolved", "closed"]},
        "sla_breach_at": {"$ne": None, "$lte": now_iso},
        "is_sla_breached": False,
    }, {"_id": 0, "id": 1, "severity": 1}).to_list(200)

    for inc in breached:
        await db.incidents_engine.update_one({"id": inc["id"]}, {"$set": {"is_sla_breached": True}})
        await _escalate(inc["id"], reason=f"SLA breach — {inc.get('severity', 'incident')} still open past its response deadline")

    return {"breached_count": len(breached)}


async def sla_breach_scheduler():
    """Background loop mirroring monitoring_service.py's monitoring_scheduler() pattern."""
    while True:
        try:
            result = await check_sla_breaches()
            if result["breached_count"]:
                logger.info(f"SLA breach check: escalated {result['breached_count']} incident(s)")
        except Exception as e:
            logger.error(f"SLA breach scheduler error: {e}")
        await asyncio.sleep(SLA_CHECK_INTERVAL_SECONDS)


# ======================== 4. LEARN ========================

async def record_outcome(
    incident_id: str,
    recommendation_id: Optional[str],
    action_taken: Optional[str],
    was_effective: Optional[bool],
    mttr_seconds: Optional[float] = None,
) -> None:
    """Record what actually happened for an incident so future recommendations can
    learn from real outcomes, not just past narratives (extends
    ai_agents_service.recall_similar's fingerprint-similarity memory)."""
    incident = await incident_engine.get_incident(incident_id)
    fingerprint = _fingerprint_incident(incident) if incident else ""
    await db.incident_outcomes.insert_one({
        "id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "recommendation_id": recommendation_id,
        "fingerprint": fingerprint,
        "action_taken": action_taken,
        "was_effective": was_effective,
        "mttr_seconds": mttr_seconds,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })
