"""
FalconOps AI — Unified AI Pipeline
The "brain" that ties Context Engine + Agents + RCA + Auto-Remediation into one call.

process_event(event) → enrich → noise-reduce → run agents → RCA → suggest action
                    → return one consolidated insight {root_cause, action, prediction, confidence}

Stores every insight in `ai_insights` for the AI Insight Panel.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db
from . import context_engine, noise_reducer, prevention_engine, cost_optimizer
from .feature_flags_service import is_module_enabled

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────
#  Lightweight rule-based agents (work without LLM)
# ─────────────────────────────────────────────────────

def sre_agent(enriched: Dict) -> Optional[Dict]:
    ev = enriched.get("event", {}) or {}
    severity = str(ev.get("severity", "")).lower()
    if "crit" in severity:
        return {
            "agent": "sre",
            "verdict": "investigate_immediately",
            "priority": "high",
            "confidence": 0.85,
            "rationale": f"Critical severity event on {enriched.get('service','?')}.",
        }
    if "warn" in severity or "high" in severity:
        return {
            "agent": "sre",
            "verdict": "investigate",
            "priority": "medium",
            "confidence": 0.70,
            "rationale": f"Warning severity on {enriched.get('service','?')}.",
        }
    return None


def security_agent(enriched: Dict) -> Optional[Dict]:
    alert = (enriched.get("alert") or "").lower()
    if any(k in alert for k in ["brute force", "failed login", "auth attack", "ddos", "rate limit exceeded"]):
        return {
            "agent": "security",
            "verdict": "block_potential_threat",
            "priority": "high",
            "confidence": 0.92,
            "rationale": "Pattern matches known attack signature.",
        }
    if any(k in alert for k in ["ssl", "certificate", "tls"]):
        return {
            "agent": "security",
            "verdict": "rotate_certificate",
            "priority": "medium",
            "confidence": 0.80,
            "rationale": "Certificate-related alert detected.",
        }
    return None


def cost_agent_for_event(enriched: Dict) -> Optional[Dict]:
    metrics = enriched.get("event", {}).get("metrics") or {}
    cpu = metrics.get("cpu") or metrics.get("cpu_pct")
    if cpu is not None and float(cpu) < 20:
        return {
            "agent": "cost",
            "verdict": "scale_down",
            "priority": "low",
            "confidence": 0.75,
            "rationale": f"CPU {cpu}% — under-utilized resource.",
            "estimated_savings": "30%",
        }
    return None


# ─────────────────────────────────────────────────────
#  Root-cause inference (heuristic; LLM upgrade is a future)
# ─────────────────────────────────────────────────────

def infer_root_cause(enriched: Dict) -> Dict:
    """Walk the topology + history to suggest a likely root cause."""
    topo = enriched.get("topology", {}) or {}
    upstream = topo.get("upstream", [])
    history = enriched.get("history", []) or []
    alert = (enriched.get("alert") or "").lower()
    service = enriched.get("service") or "(unknown)"

    if "database" in alert or "db" in alert or "connection pool" in alert:
        return {
            "summary": f"Database-tier failure cascading from {service}",
            "evidence": ["Alert mentions DB/connection pool", f"Topology has {len(upstream)} upstream service(s)"],
            "confidence": 0.78,
        }
    if upstream:
        # Check if any upstream had a recent critical event
        recent_upstream_crit = [h for h in history[:20] if str(h.get("severity", "")).lower().startswith("crit")
                                and h.get("service") in upstream]
        if recent_upstream_crit:
            return {
                "summary": f"Upstream dependency failure: {recent_upstream_crit[0].get('service')}",
                "evidence": [f"{recent_upstream_crit[0].get('alert')} fired on upstream", "Failure cascading down dependency chain"],
                "confidence": 0.82,
            }
    if "timeout" in alert or "response time" in alert:
        return {
            "summary": f"Latency degradation in {service}",
            "evidence": ["Timeout/latency alert", "Likely capacity or external-dep issue"],
            "confidence": 0.65,
        }
    return {
        "summary": f"Investigating {service} — insufficient signal for high-confidence RCA",
        "evidence": ["Run a multi-step synthetic check", "Check logs for stack traces"],
        "confidence": 0.40,
    }


# ─────────────────────────────────────────────────────
#  Action suggestions (gated by Auto-Action Allowlist)
# ─────────────────────────────────────────────────────

# Risk classification — lower = safer to auto-execute
ACTION_RISK = {
    "alert_ack": "low",
    "lower_check_interval": "low",
    "deduplicate_monitors": "low",
    "rotate_certificate": "medium",
    "scale_down": "medium",
    "scale_up": "medium",
    "block_potential_threat": "high",  # network change
    "restart_service": "high",
    "investigate_immediately": "informational",
    "investigate": "informational",
}


async def suggest_action(enriched: Dict, agent_verdicts: List[Dict]) -> Dict:
    """Pick the highest-confidence verdict and return it as an action proposal.
    Always returns a dict — when no agent fires, returns a structured no_action shape
    so UI consumers don't need null-guards."""
    if not agent_verdicts:
        return {
            "kind": "no_action",
            "agent": None,
            "rationale": "No agent fired for this event — likely informational severity or no actionable signal.",
            "confidence": 0.0,
            "risk": "none",
            "auto_executable": False,
            "approval_required": False,
        }
    sorted_v = sorted(agent_verdicts, key=lambda v: v.get("confidence", 0), reverse=True)
    top = sorted_v[0]
    action_kind = top.get("verdict")
    risk = ACTION_RISK.get(action_kind, "medium")

    # Read auto-action allowlist from feature flags
    allow_auto = False
    try:
        from .feature_flags_service import get_config
        cfg = await get_config()
        allowlist = (cfg.get("limits", {}) or {}).get("auto_action_allowlist", []) or []
        allow_auto = action_kind in allowlist and risk in ("low",)
    except Exception:
        pass

    return {
        "kind": action_kind,
        "agent": top.get("agent"),
        "rationale": top.get("rationale"),
        "confidence": top.get("confidence"),
        "risk": risk,
        "auto_executable": allow_auto,
        "approval_required": not allow_auto,
    }


# ─────────────────────────────────────────────────────
#  Main pipeline entry
# ─────────────────────────────────────────────────────

async def process_event(event: Dict) -> Dict:
    """Run the full pipeline on a single event."""
    if not await is_module_enabled("ai_agents"):
        return {"skipped": True, "reason": "ai_agents module disabled"}

    enriched = await context_engine.enrich(event)

    # Noise reduction (single-event pass — checks if this would be suppressed)
    nr = await noise_reducer.reduce([event])
    is_duplicate = bool(nr.get("suppressed"))

    # Run agents
    verdicts: List[Dict] = []
    for fn in (sre_agent, security_agent, cost_agent_for_event):
        try:
            v = fn(enriched)
            if v:
                verdicts.append(v)
        except Exception as e:
            logger.warning("agent failed: %s", e)

    rca = infer_root_cause(enriched)
    action = await suggest_action(enriched, verdicts)

    insight = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event_summary": {
            "service": enriched.get("service"),
            "alert": enriched.get("alert"),
            "severity": (event.get("severity") or "").lower(),
        },
        "is_duplicate": is_duplicate,
        "context": {
            "history_count": enriched.get("history_count", 0),
            "topology": enriched.get("topology"),
            "runbook_present": bool(enriched.get("runbook")),
            "is_recurring": (enriched.get("baseline") or {}).get("is_recurring", False),
        },
        "agents_consulted": [v.get("agent") for v in verdicts],
        "verdicts": verdicts,
        "root_cause": rca,
        "recommended_action": action,
        "status": "pending_review" if action and action.get("approval_required") else "informational",
    }

    await db.ai_insights.insert_one(dict(insight))
    insight.pop("_id", None)

    # Persist into vector memory so AI Copilot can recall this incident later
    try:
        from . import vector_memory_service
        memory_text = (
            f"Service: {insight['event_summary'].get('service')}\n"
            f"Alert: {insight['event_summary'].get('alert')}\n"
            f"Severity: {insight['event_summary'].get('severity')}\n"
            f"Root cause: {insight.get('root_cause', {}).get('summary')}\n"
            f"Recommended action: {(insight.get('recommended_action') or {}).get('kind')}\n"
            f"Rationale: {(insight.get('recommended_action') or {}).get('rationale')}"
        )
        await vector_memory_service.remember(
            text=memory_text,
            kind="ai_insight",
            source_id=insight["id"],
            metadata={
                "service": insight["event_summary"].get("service"),
                "severity": insight["event_summary"].get("severity"),
                "agents": insight.get("agents_consulted"),
            },
        )
    except Exception as e:
        logger.debug("vector remember insight failed (non-fatal): %s", e)

    return insight


async def list_recent_insights(hours: int = 24, limit: int = 100) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    cursor = db.ai_insights.find({"created_at": {"$gte": cutoff}}, {"_id": 0}).sort("created_at", -1).limit(limit)
    out = []
    async for i in cursor:
        out.append(i)
    return out


async def get_insight_summary(hours: int = 24) -> Dict:
    """Aggregate metrics for the AI Insight Panel header."""
    insights = await list_recent_insights(hours=hours, limit=500)
    total = len(insights)
    duplicates = sum(1 for i in insights if i.get("is_duplicate"))
    pending = sum(1 for i in insights if i.get("status") == "pending_review")
    by_agent: Dict[str, int] = {}
    for i in insights:
        for a in i.get("agents_consulted") or []:
            by_agent[a] = by_agent.get(a, 0) + 1

    # Cross-reference: prevention warnings + cost recs
    prevention_warnings = await prevention_engine.list_recent_warnings(hours=hours)
    cost_scan = await cost_optimizer.run_cost_scan()

    return {
        "window_hours": hours,
        "insights_total": total,
        "insights_duplicates_suppressed": duplicates,
        "insights_pending_review": pending,
        "insights_by_agent": by_agent,
        "prevention_warnings": len(prevention_warnings),
        "cost_recommendations": cost_scan["summary"]["total_opportunities"],
        "noise_reduction_pct": round((duplicates / total) * 100, 1) if total else 0.0,
    }
