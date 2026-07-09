"""
FalconOps AI - AI Correlation Routes
API endpoints for the AI correlation engine
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from ..utils.auth import require_auth, require_write_access
from ..services.ai_correlation import (
    run_correlation_cycle,
    get_correlation_rules,
    get_correlation_stats,
    deduplicate_alert,
    correlate_alerts
)

router = APIRouter(prefix="/api/correlation", tags=["AI Correlation"])


@router.get("/rules")
async def list_correlation_rules(current_user: dict = Depends(require_auth)):
    """Get all correlation rules"""
    rules = await get_correlation_rules()
    return rules


@router.get("/stats")
async def correlation_statistics(current_user: dict = Depends(require_auth)):
    """Get correlation engine statistics"""
    stats = await get_correlation_stats()
    return stats


@router.post("/run")
async def trigger_correlation(
    time_window_minutes: int = 15,
    current_user: dict = Depends(require_write_access)
):
    """Manually trigger a correlation cycle"""
    result = await run_correlation_cycle()
    return result


@router.post("/correlate")
async def correlate_alerts_endpoint(
    time_window_minutes: int = 15,
    current_user: dict = Depends(require_write_access)
):
    """Run alert correlation and return created incidents"""
    incidents = await correlate_alerts(time_window_minutes)
    return {
        "success": True,
        "incidents_created": len(incidents),
        "incidents": incidents
    }



# ======================== HEALTH RULE VIOLATION CORRELATION ========================

import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from ..core.database import db

# Try importing LLM for AI-powered RCA
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

import os


@router.post("/correlate-violations")
async def correlate_health_violations(
    time_window_minutes: int = 60,
    min_group_size: int = 1,
    current_user: dict = Depends(require_write_access),
):
    """
    Correlate health rule violations into grouped incidents.
    Groups by: same source, same metric family, temporal proximity, severity cascade.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)).isoformat()

    violations = await db["db.health_violations"].find(
        {"state": {"$in": ["active", "critical", "warning"]}, "timestamp": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("timestamp", -1).to_list(500)

    if not violations:
        return {"incidents_created": 0, "violations_processed": 0, "groups": [], "summary": "No active violations in time window"}

    # ── Multi-dimensional grouping ──
    groups = []

    # Strategy 1: Same source (same server/DB instance)
    by_source = defaultdict(list)
    for v in violations:
        by_source[v.get("source_id", "unknown")].append(v)

    for source_id, vlist in by_source.items():
        if len(vlist) >= min_group_size:
            groups.append({
                "strategy": "same_source",
                "key": source_id,
                "source_name": vlist[0].get("source_name", source_id),
                "violations": vlist,
                "confidence": min(0.95, 0.7 + len(vlist) * 0.05),
            })

    # Strategy 2: Same metric family across different sources
    by_metric = defaultdict(list)
    for v in violations:
        by_metric[v.get("metric", "unknown")].append(v)

    for metric, vlist in by_metric.items():
        sources = set(v.get("source_id") for v in vlist)
        if len(sources) > 1:
            groups.append({
                "strategy": "same_metric_fleet",
                "key": metric,
                "source_name": f"{metric} across {len(sources)} sources",
                "violations": vlist,
                "confidence": min(0.90, 0.6 + len(sources) * 0.1),
            })

    # Strategy 3: Severity cascade (critical + warning on same source)
    for source_id, vlist in by_source.items():
        severities = set(v.get("severity") for v in vlist)
        if "critical" in severities and "warning" in severities:
            groups.append({
                "strategy": "severity_cascade",
                "key": f"cascade_{source_id}",
                "source_name": vlist[0].get("source_name", source_id),
                "violations": vlist,
                "confidence": 0.85,
            })

    # Deduplicate groups (keep highest confidence per unique violation set)
    seen_keys = set()
    unique_groups = []
    for g in sorted(groups, key=lambda x: -x["confidence"]):
        key = g["key"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique_groups.append(g)

    # ── Build incident summaries ──
    incidents = []
    for g in unique_groups:
        vlist = g["violations"]
        critical = sum(1 for v in vlist if v.get("severity") == "critical")
        warning = sum(1 for v in vlist if v.get("severity") == "warning")
        metrics = list(set(v.get("metric", "") for v in vlist))
        rules = list(set(v.get("rule_name", "") for v in vlist))
        sources = list(set(v.get("source_name", v.get("source_id", "")) for v in vlist))

        # Determine root cause (highest severity, most common metric)
        root_cause = "Unknown"
        if g["strategy"] == "same_source":
            root_cause = f"Multiple threshold breaches on {g['source_name']} ({', '.join(metrics[:3])})"
        elif g["strategy"] == "same_metric_fleet":
            root_cause = f"Fleet-wide {g['key']} issue across {len(sources)} sources — likely systemic"
        elif g["strategy"] == "severity_cascade":
            root_cause = f"Severity cascade on {g['source_name']} — critical ({critical}) + warning ({warning}) violations"

        incident_id = str(uuid.uuid4())[:12]
        incidents.append({
            "id": incident_id,
            "strategy": g["strategy"],
            "root_cause": root_cause,
            "confidence": round(g["confidence"], 2),
            "severity": "critical" if critical > 0 else "warning",
            "violation_count": len(vlist),
            "critical_count": critical,
            "warning_count": warning,
            "metrics": metrics,
            "rules": rules,
            "sources": sources,
            "fingerprints": [v.get("fingerprint", v.get("id", "")[:12]) for v in vlist[:10]],
            "timestamp": vlist[0].get("timestamp"),
            "suggested_actions": _suggest_actions(g["strategy"], metrics, root_cause),
        })

    return {
        "incidents_created": len(incidents),
        "violations_processed": len(violations),
        "time_window_minutes": time_window_minutes,
        "groups": incidents,
        "summary": f"Correlated {len(violations)} violations into {len(incidents)} incident groups using 3 strategies",
    }


def _suggest_actions(strategy, metrics, root_cause):
    actions = []
    if "cpu" in " ".join(metrics).lower():
        actions.extend(["Scale up CPU resources or add instances", "Identify CPU-intensive processes", "Check for runaway threads"])
    if "memory" in " ".join(metrics).lower():
        actions.extend(["Investigate memory leaks", "Increase memory allocation", "Restart affected services"])
    if "disk" in " ".join(metrics).lower():
        actions.extend(["Clean up log files and temp data", "Expand disk volume", "Set up log rotation"])
    if "latency" in " ".join(metrics).lower() or "response" in " ".join(metrics).lower():
        actions.extend(["Check database query performance", "Review network connectivity", "Scale application tier"])
    if strategy == "same_metric_fleet":
        actions.insert(0, "Investigate shared infrastructure (network, storage, DNS)")
    if strategy == "severity_cascade":
        actions.insert(0, "Address critical violations first — cascading failure likely")
    if not actions:
        actions = ["Review metric trends for anomalies", "Check recent deployments or config changes", "Engage on-call team"]
    return actions[:5]


@router.post("/rca-violations")
async def rca_for_violations(
    current_user: dict = Depends(require_write_access),
):
    """
    AI-powered Root Cause Analysis on current active health rule violations.
    Uses LLM to analyze patterns and suggest root causes.
    """
    violations = await db["db.health_violations"].find(
        {"state": {"$in": ["active", "critical", "warning"]}},
        {"_id": 0},
    ).sort("timestamp", -1).to_list(100)

    if not violations:
        return {"status": "no_violations", "analysis": "No active violations to analyze."}

    # Build context
    critical = [v for v in violations if v.get("severity") == "critical"]
    warning = [v for v in violations if v.get("severity") == "warning"]

    metrics_affected = list(set(v.get("metric", "") for v in violations))
    sources_affected = list(set(v.get("source_name", v.get("source_id", "")) for v in violations))
    rules_triggered = list(set(v.get("rule_name", "") for v in violations))

    context_text = f"""
Active Health Rule Violations Summary:
- Total active violations: {len(violations)}
- Critical: {len(critical)}
- Warning: {len(warning)}
- Metrics affected: {', '.join(metrics_affected)}
- Sources affected: {', '.join(sources_affected)}
- Rules triggered: {', '.join(rules_triggered)}

Violation details:
"""
    for v in violations[:20]:
        context_text += f"\n- [{v.get('severity','info').upper()}] {v.get('rule_name','')} on {v.get('source_name','')} "
        context_text += f"| metric={v.get('metric','')} value={v.get('actual_value','')} (threshold: {v.get('operator','')} {v.get('threshold','')})"

    # Try LLM analysis
    llm_analysis = None
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("LLM_API_KEY")
    if LLM_AVAILABLE and api_key:
        try:
            llm = LlmChat(api_key=api_key, session_id=str(uuid.uuid4()))
            llm = llm.with_model("anthropic", "claude-sonnet-4-20250514")
            llm = llm.with_system_message(
                "You are an expert AIOps engineer. Analyze the following health rule violations and provide:\n"
                "1. ROOT CAUSE: The most likely root cause\n"
                "2. IMPACT: Business and technical impact\n"
                "3. CORRELATION: How these violations are related\n"
                "4. ACTIONS: Top 5 recommended actions in priority order\n"
                "5. PREDICTION: What will happen if not addressed\n"
                "Be concise, technical, and actionable. Format with markdown headers."
            )
            response = await llm.chat(UserMessage(text=context_text))
            llm_analysis = response.text
        except Exception as e:
            llm_analysis = None

    # Fallback rule-based analysis
    rule_analysis = {
        "root_cause": _determine_root_cause(violations, metrics_affected, sources_affected),
        "impact": f"{len(critical)} critical and {len(warning)} warning violations across {len(sources_affected)} source(s)",
        "correlation_patterns": [],
        "recommended_actions": [],
        "prediction": "",
    }

    # Detect correlation patterns
    if len(sources_affected) == 1 and len(metrics_affected) > 1:
        rule_analysis["correlation_patterns"].append(
            f"Single source ({sources_affected[0]}) with multiple metric violations — likely host-level issue"
        )
    if len(sources_affected) > 1 and len(metrics_affected) == 1:
        rule_analysis["correlation_patterns"].append(
            f"Fleet-wide {metrics_affected[0]} issue across {len(sources_affected)} sources — systemic problem"
        )
    if len(critical) > 0 and len(warning) > 0:
        rule_analysis["correlation_patterns"].append(
            "Severity cascade detected — critical violations may be causing warning-level downstream effects"
        )

    rule_analysis["recommended_actions"] = _suggest_actions(
        "same_source" if len(sources_affected) == 1 else "same_metric_fleet",
        metrics_affected, rule_analysis["root_cause"]
    )

    if len(critical) > 2:
        rule_analysis["prediction"] = "High risk of service degradation or outage if not addressed within 15 minutes"
    elif len(critical) > 0:
        rule_analysis["prediction"] = "Potential for escalation to more critical state within 30 minutes"
    else:
        rule_analysis["prediction"] = "Warning-level issues may escalate if underlying trend continues"

    return {
        "status": "analyzed",
        "ai_powered": llm_analysis is not None,
        "llm_analysis": llm_analysis,
        "rule_analysis": rule_analysis,
        "context": {
            "total_violations": len(violations),
            "critical": len(critical),
            "warning": len(warning),
            "metrics": metrics_affected,
            "sources": sources_affected,
            "rules": rules_triggered,
        },
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


def _determine_root_cause(violations, metrics, sources):
    """Heuristic root cause determination."""
    if any("cpu" in m.lower() for m in metrics) and any("memory" in m.lower() for m in metrics):
        return "Resource saturation — CPU and memory under heavy load simultaneously"
    if any("cpu" in m.lower() for m in metrics):
        return "CPU saturation — compute resources exhausted"
    if any("memory" in m.lower() for m in metrics):
        return "Memory pressure — potential memory leak or insufficient allocation"
    if any("disk" in m.lower() for m in metrics):
        return "Disk space exhaustion — storage capacity critically low"
    if any("latency" in m.lower() or "response" in m.lower() for m in metrics):
        return "Performance degradation — high latency across services"
    if any("error" in m.lower() for m in metrics):
        return "Elevated error rate — application errors impacting reliability"
    if any("connection" in m.lower() for m in metrics):
        return "Connection exhaustion — DB or network connection pool depleted"
    if len(sources) > 2:
        return f"Widespread issue across {len(sources)} sources — likely infrastructure-level root cause"
    return "Multiple threshold violations detected — further investigation needed"
