"""
FalconOps AI — Unified AIOps Diagnose Endpoint
A single super-endpoint that fuses every AI signal we have for a service:
  - Context Engine        → recent events, dependency topology, runbook, baseline
  - Trace RCA Service     → recent slow & errored traces for the service
  - Vector Memory         → similar past incidents the AI has seen for this service
  - Swappable LLM         → a Senior-SRE-level diagnosis written in plain English

Returns a single consolidated `diagnosis` payload that the AI Insight panel
can render without making N round-trips.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.database import db
from ..services import (
    context_engine,
    llm_provider_service,
    trace_rca_service,
)
from .auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aiops", tags=["aiops-diagnose"])


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

async def _recent_traces_for_service(service: str, hours: int, limit: int = 25) -> Dict[str, Any]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    base_filter = {
        "$and": [
            {"services": service},
            {"$or": [{"received_at": {"$gte": cutoff}}, {"start_time": {"$gte": cutoff}}]},
        ]
    }
    errored = await db.otel_traces.find(
        {**base_filter, "status": "ERROR"}, {"_id": 0}
    ).sort("received_at", -1).limit(limit).to_list(length=limit)
    slow = await db.otel_traces.find(
        base_filter, {"_id": 0}
    ).sort("duration_ms", -1).limit(limit).to_list(length=limit)
    return {
        "errored": errored,
        "slowest": slow,
        "error_trace_count": len(errored),
        "max_duration_ms": (slow[0].get("duration_ms") if slow else 0),
    }


async def _similar_past_insights(service: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch the most relevant prior AI insights for this service from memory."""
    try:
        cursor = db.ai_insights.find(
            {"event_summary.service": service}, {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception:
        return []


def _section_recent_events(history: List[Dict[str, Any]]) -> List[str]:
    if not history:
        return []
    out = ["\nRECENT EVENTS (most-recent first):"]
    for ev in history[:8]:
        out.append(
            f"  - [{ev.get('severity', '?')}] {ev.get('alert', '')[:120]} · @ {ev.get('timestamp')}"
        )
    return out


def _section_traces(traces: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    if traces["errored"]:
        out.append(f"\nERRORED TRACES IN WINDOW ({traces['error_trace_count']}):")
        for t in traces["errored"][:5]:
            out.append(
                f"  - {t.get('trace_id', '?')[:16]}… root={t.get('root_service')}.{t.get('root_operation')} · "
                f"{t.get('duration_ms', 0):.0f}ms · spans={t.get('span_count')} · errors={t.get('error_count')}"
            )
    if traces["slowest"]:
        out.append("\nSLOWEST TRACES IN WINDOW:")
        for t in traces["slowest"][:5]:
            out.append(
                f"  - {t.get('trace_id', '?')[:16]}… root={t.get('root_service')}.{t.get('root_operation')} · "
                f"{t.get('duration_ms', 0):.0f}ms"
            )
    return out


def _section_runbook(runbook: Optional[Dict[str, Any]]) -> List[str]:
    if not runbook or not runbook.get("steps"):
        return []
    out = ["\nMATCHING RUNBOOK STEPS:"]
    for i, st in enumerate(runbook["steps"][:6], 1):
        out.append(f"  {i}. {st}")
    return out


def _section_prior_insights(past: List[Dict[str, Any]]) -> List[str]:
    if not past:
        return []
    out = ["\nPRIOR AI INSIGHTS FOR THIS SERVICE:"]
    for p in past[:3]:
        out.append(
            f"  - {p.get('created_at', '?')[:19]} → root_cause: "
            f"{(p.get('root_cause') or {}).get('summary') or '(none)'}"
        )
    return out


_OUTPUT_TEMPLATE = (
    "\nProduce a structured diagnosis with EXACTLY these labeled sections (no markdown headers):\n"
    "VERDICT: <one-sentence: is the service healthy / degraded / failing?>\n"
    "ROOT CAUSE: <the most likely single root cause, specific>\n"
    "EVIDENCE:\n- <observation 1>\n- <observation 2>\n- <observation 3>\n"
    "BLAST RADIUS: <which services/users affected>\n"
    "IMMEDIATE ACTION:\n- <step 1>\n- <step 2>\n"
    "LONGER-TERM FIX:\n- <step 1>\n- <step 2>\n"
    "CONFIDENCE: <low|medium|high> — <one-line justification>"
)


def _build_prompt(
    service: str,
    enriched: Dict[str, Any],
    traces: Dict[str, Any],
    past: List[Dict[str, Any]],
    hours: int,
) -> List[Dict[str, str]]:
    topo = enriched.get("topology") or {}
    baseline = enriched.get("baseline") or {}

    parts: List[str] = [
        f"Service under diagnosis: {service}",
        f"Time window: last {hours}h",
        (f"Dependencies — upstream: {', '.join(topo.get('upstream', []) or []) or 'none'} · "
         f"downstream: {', '.join(topo.get('downstream', []) or []) or 'none'}"),
        (f"Baseline: this service+alert has fired {baseline.get('count', 0)} time(s) in last 7d "
         f"({baseline.get('rate_per_day', 0)}/day) — recurring={baseline.get('is_recurring', False)}"),
    ]
    parts.extend(_section_recent_events(enriched.get("history") or []))
    parts.extend(_section_traces(traces))
    parts.extend(_section_runbook(enriched.get("runbook")))
    parts.extend(_section_prior_insights(past))
    parts.append(_OUTPUT_TEMPLATE)

    return [
        {
            "role": "system",
            "content": (
                "You are a Senior Site Reliability Engineer diagnosing a single service "
                "in a distributed system. Be specific, evidence-based, and brief. "
                "Reference concrete trace IDs, event timestamps, and dependency names."
            ),
        },
        {"role": "user", "content": "\n".join(parts)},
    ]


def _parse_section(text: str, label: str) -> str:
    """Robust section extractor — header must be at line start AND followed by ':' or EOL,
    so we don't match a label embedded inside a title or sentence."""
    if not text or not label:
        return ""
    import re as _re
    all_labels = (
        "VERDICT", "ROOT CAUSE", "EVIDENCE", "BLAST RADIUS",
        "IMMEDIATE ACTION", "LONGER-TERM FIX", "LONGER TERM FIX", "CONFIDENCE",
    )
    label_u = label.upper()
    padded = "\n" + text

    def _header(lbl: str):
        pat = rf"(?im)^[\s#*\-•]*{_re.escape(lbl)}\**\s*(?::|$)"
        return _re.search(pat, padded)

    head = _header(label)
    if not head:
        return ""
    head_end = head.end()
    end = len(padded)
    for nxt in all_labels:
        if nxt == label_u:
            continue
        m = _header(nxt)
        if m and m.start() >= head_end and m.start() < end:
            end = m.start()
    chunk = padded[head_end:end].strip()
    chunk = chunk.lstrip("#").lstrip("*").strip()
    return chunk


def _parse_list(text: str, label: str) -> List[str]:
    body = _parse_section(text, label)
    if not body:
        return []
    import re as _re
    items: List[str] = []
    bullet_re = _re.compile(r"^([-•*]+\s*|\d{1,3}[.)]\s+)")
    for line in body.split("\n"):
        s = line.strip()
        if not s:
            continue
        s = bullet_re.sub("", s).strip().strip("*").strip()
        if len(s) >= 6:
            items.append(s)
    return items[:6]


async def _find_sample_event(service: str, hours: int) -> Optional[Dict[str, Any]]:
    """Pull the most-recent event for this service from event_data — best-effort."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    try:
        cur = db.event_data.aggregate([
            {"$unwind": "$events"},
            {"$match": {"events.service": {"$regex": f"^{service}$", "$options": "i"},
                        "events.timestamp": {"$gte": cutoff}}},
            {"$replaceRoot": {"newRoot": "$events"}},
            {"$sort": {"timestamp": -1}},
            {"$limit": 1},
        ])
        async for ev in cur:
            ev.pop("_id", None)
            return ev
    except Exception:
        return None
    return None


async def _run_llm_diagnosis(prompt: List[Dict[str, str]],
                             service: str) -> Dict[str, Any]:
    """Call the swappable LLM and return parsed sections + provider metadata."""
    try:
        resp = await llm_provider_service.chat_completion(prompt, session_id=f"diagnose-{service}")
        text = (resp.get("response") or "").strip()
        provider = resp.get("provider")
        model = resp.get("model")
        fallback = resp.get("fallback_used", False)
    except Exception as e:
        logger.warning("Diagnose LLM failed: %s", e)
        text, provider, model, fallback = "", "rule_based", None, True

    return {
        "verdict": _parse_section(text, "VERDICT")[:400],
        "root_cause": _parse_section(text, "ROOT CAUSE")[:400],
        "evidence": _parse_list(text, "EVIDENCE"),
        "blast_radius": _parse_section(text, "BLAST RADIUS")[:400],
        "immediate_action": _parse_list(text, "IMMEDIATE ACTION"),
        "longer_term_fix": _parse_list(text, "LONGER-TERM FIX") or _parse_list(text, "LONGER TERM FIX"),
        "confidence_note": _parse_section(text, "CONFIDENCE")[:200],
        "raw_llm_text": text,
        "provider": provider,
        "model": model,
        "fallback_used": fallback,
    }


def _apply_deterministic_fallback(
    diagnosis: Dict[str, Any],
    enriched: Dict[str, Any],
    traces: Dict[str, Any],
    hours: int,
) -> None:
    """If the LLM produced nothing parseable, build a usable rule-based diagnosis."""
    if diagnosis["verdict"] or diagnosis["root_cause"]:
        return
    err_n = traces["error_trace_count"]
    slow_max = traces["max_duration_ms"]
    if err_n > 0:
        diagnosis["verdict"] = f"Service is degraded — {err_n} errored trace(s) observed in last {hours}h"
        diagnosis["root_cause"] = "Recent failures detected in this service's distributed traces"
    elif slow_max > 1000:
        diagnosis["verdict"] = f"Service is slow — max trace duration {slow_max:.0f}ms in last {hours}h"
        diagnosis["root_cause"] = "Latency outlier detected — investigate hot operations"
    else:
        diagnosis["verdict"] = "Service appears healthy"
        diagnosis["root_cause"] = "No errors or material latency outliers in the window"
    diagnosis["evidence"] = [
        f"{enriched.get('history_count', 0)} recent event(s) in last 7d",
        f"{err_n} errored trace(s), {len(traces['slowest'])} slow trace(s)",
        f"Upstream: {', '.join((enriched.get('topology') or {}).get('upstream', []) or []) or 'none'}",
    ]
    diagnosis["immediate_action"] = [
        "Check recent deployments to this service",
        "Run the matching runbook" if enriched.get("runbook") else "Inspect logs for stack traces",
    ]
    diagnosis["longer_term_fix"] = ["Add latency SLO + alert rule", "Add circuit breaker around upstream call"]
    diagnosis["confidence_note"] = "rule-based fallback — configure an LLM provider for richer output"


def _build_signals_payload(enriched: Dict[str, Any],
                           traces: Dict[str, Any],
                           past: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Construct the signals block returned alongside the diagnosis."""
    return {
        "history_count": enriched.get("history_count", 0),
        "topology": enriched.get("topology"),
        "baseline": enriched.get("baseline"),
        "runbook_present": bool(enriched.get("runbook")),
        "runbook_steps": (enriched.get("runbook") or {}).get("steps", [])[:6],
        "trace_summary": {
            "errored": traces["error_trace_count"],
            "slowest_count": len(traces["slowest"]),
            "max_duration_ms": traces["max_duration_ms"],
        },
        "errored_traces": [
            {"trace_id": t.get("trace_id"), "duration_ms": t.get("duration_ms"),
             "root_operation": t.get("root_operation"), "received_at": t.get("received_at")}
            for t in traces["errored"][:10]
        ],
        "slowest_traces": [
            {"trace_id": t.get("trace_id"), "duration_ms": t.get("duration_ms"),
             "root_operation": t.get("root_operation"), "received_at": t.get("received_at")}
            for t in traces["slowest"][:10]
        ],
        "prior_insights_count": len(past),
    }


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/diagnose/{service}")
async def diagnose_service(
    service: str,
    hours: int = Query(24, ge=1, le=720),
    current_user: dict = Depends(require_auth),
):
    """Unified AI diagnosis for one service — runs context_engine + trace lookups +
    swappable-LLM reasoning and returns a single consolidated payload."""
    if not service or len(service) > 200:
        raise HTTPException(status_code=400, detail="service is required")

    # Gather signals
    sample_event = await _find_sample_event(service, hours)
    enriched = await context_engine.enrich(sample_event or {"service": service, "alert": "service-diagnosis"})
    traces = await _recent_traces_for_service(service, hours=hours)
    past = await _similar_past_insights(service)

    # Run LLM diagnosis + deterministic fallback
    prompt = _build_prompt(service, enriched, traces, past, hours)
    diagnosis = await _run_llm_diagnosis(prompt, service)
    _apply_deterministic_fallback(diagnosis, enriched, traces, hours)

    payload = {
        "service": service,
        "hours": hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnosis": diagnosis,
        "signals": _build_signals_payload(enriched, traces, past),
    }

    # Persist for the AI Insight panel timeline — best-effort
    try:
        await db.ai_insights.insert_one({
            **payload,
            "kind": "service_diagnosis",
            "created_at": payload["generated_at"],
            "event_summary": {"service": service, "alert": "service-diagnosis", "severity": "info"},
        })
    except Exception:
        pass

    return payload


@router.get("/health")
async def aiops_health(current_user: dict = Depends(require_auth)):
    """Quick view of which AIOps signals + LLM provider are wired up.
    Useful to debug 'why is the AI giving rule-based output?' from one URL."""
    from ..services import llm_provider_service as llm
    provider_health = await llm.health_check()
    counts = {
        "ai_insights": await db.ai_insights.count_documents({}),
        "rca_results": await db.rca_results.count_documents({}),
        "otel_traces": await db.otel_traces.count_documents({}),
        "incidents_engine": await db.incidents_engine.count_documents({}),
    }
    return {
        "llm": provider_health,
        "collection_counts": counts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
