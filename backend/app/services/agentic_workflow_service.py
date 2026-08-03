"""
FalconOps AI — Agentic AI Workflow (Phase 1: read path + Copilot at L0)

The Supervisor: classifies an incoming natural-language query (or an incident
id) and routes it to the right existing specialist rather than reinventing
one. Reuses, does not duplicate:
  - Copilot        -> intelligence_agents_service.ask() (real citations, bounded tool loop)
  - Forecaster     -> capacity_prediction_engine.predict_capacity() (real regression + confidence)
  - Blast radius   -> impact_analysis_engine.get_blast_radius() (the live engine, not the
                      orphaned impact_analysis_service.py duplicate)
  - Incident memory-> rag_service.find_similar_incidents() (already-wired ChromaDB RAG)

The one genuinely new capability is the Diagnoser: today's RCA engines
(rca_engine.py, rca_chain_service.py) return a single root cause, never a
ranked list of competing hypotheses. run_diagnoser() adds exactly that one
new synthesis step on top of intelligence_agents_service's existing
evidence-gathering, using the same multi-hypothesis prompt shape already
proven in trace_rca_service.analyze_window() (for traces) — applied here to
incidents/services instead.

Every call to handle_query() is written to db.agentic_decision_log
(insert-only, never updated/deleted) — the append-only decision trail the
spec asks for. This module makes zero write/mutating calls anywhere; see
action_broker_schema.py for the (also non-executing) action broker schema.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.database import db
from . import agentic_trace_service
from . import intelligence_agents_service
from . import rag_service
from .capacity_prediction_engine import capacity_prediction_engine
from .impact_analysis_engine import impact_analysis_engine
from .llm_provider_service import chat_completion

logger = logging.getLogger(__name__)

_FORECAST_KEYWORDS = re.compile(
    r"\b(predict|forecast|trend|run\s*out\s*of|capacity|will\s+.*\s+(reach|hit|breach)|projection)\b",
    re.IGNORECASE,
)
_BLAST_RADIUS_KEYWORDS = re.compile(
    r"\b(blast\s*radius|what\s+depends\s+on|who\s+depends\s+on|downstream\s+impact|impact\s+of)\b",
    re.IGNORECASE,
)
_MEMORY_KEYWORDS = re.compile(
    r"\b(seen\s+this\s+before|similar\s+incidents?|has\s+this\s+happened|past\s+incidents?)\b",
    re.IGNORECASE,
)
_DIAGNOSE_KEYWORDS = re.compile(
    r"\b(why|root\s*cause|rca|diagnose|down|failing|failure|degraded|broken|crash|outage)\b",
    re.IGNORECASE,
)

_indexes_ready = False


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await db.agentic_decision_log.create_index([("created_at", -1)])
        await db.agentic_decision_log.create_index("classification")
    except Exception as e:
        logger.warning("agentic_decision_log index creation skipped: %s", e)
    _indexes_ready = True


def classify_query(query: str, incident_id: Optional[str] = None) -> Dict[str, str]:
    """Lightweight keyword classifier — same shape as
    autonomous_ops_orchestrator._classify_root_cause_key. An incident_id always
    routes to the diagnoser regardless of query text."""
    if incident_id:
        return {"route": "diagnoser", "reason": "an incident_id was provided"}
    q = query or ""
    if _MEMORY_KEYWORDS.search(q):
        return {"route": "memory", "reason": "query asks about past/similar incidents"}
    if _BLAST_RADIUS_KEYWORDS.search(q):
        return {"route": "blast_radius", "reason": "query asks about dependency/impact scope"}
    if _FORECAST_KEYWORDS.search(q):
        return {"route": "forecaster", "reason": "query asks about a future trend/prediction"}
    if _DIAGNOSE_KEYWORDS.search(q):
        return {"route": "diagnoser", "reason": "query asks about a root cause / current failure"}
    return {"route": "copilot", "reason": "general status/Q&A question"}


def _extract_service_name(query: str) -> Optional[str]:
    m = re.search(r"\bof\s+([a-zA-Z0-9_-]+)\b", query or "")
    return m.group(1) if m else None


async def run_copilot(query: str, user: Optional[Dict] = None) -> Dict[str, Any]:
    # intelligence_agents_service.ask() has no session_id concept of its own —
    # it generates its own per-call session ids internally.
    return await intelligence_agents_service.ask(query, mode="auto", user=user)


async def run_forecaster(metric_name: str, host: Optional[str] = None, service: Optional[str] = None,
                         horizon: str = "24h", threshold: float = 90) -> Dict[str, Any]:
    return await capacity_prediction_engine.predict_capacity(
        metric_name=metric_name, host=host, service=service, horizon=horizon, threshold=threshold,
    )


async def get_blast_radius(service_name: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    return await impact_analysis_engine.get_blast_radius(service_name, tenant_id=tenant_id)


async def find_similar_incidents(query: str, service: Optional[str] = None) -> List[Dict[str, Any]]:
    return await rag_service.find_similar_incidents(query, top_k=5, service=service)


DIAGNOSER_SYSTEM_PROMPT = """You are the FalconOpsAI Diagnoser — a senior SRE producing a RANKED list of
competing root-cause hypotheses for an incident, not a single answer.

You are given real observability evidence (gathered by tools) and similar past incidents.

Respond with ONLY a JSON object (no prose outside JSON):
{
  "hypotheses": [
    {"root_cause": "specific hypothesis", "confidence": 0.0-1.0, "category": "model|prompt|data|infra|deploy|abuse",
     "evidence": ["specific supporting evidence item", "..."]},
    ...
  ]
}
Rules:
- Return up to 4 distinct hypotheses, ordered by descending confidence.
- Base every hypothesis ONLY on the evidence provided. Never invent log lines, metrics, or deploys.
- If the evidence is thin, say so in a hypothesis's evidence list and keep confidence <= 0.4.
- Prefer hypotheses that correlate multiple signals (e.g. a deployment right before an error spike)
  over single-signal guesses.
- Do not present any single hypothesis as certain — this is a ranked list of possibilities, not a verdict."""


async def run_diagnoser(
    service_or_incident: str, hours: int = 24, user: Optional[Dict] = None, run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """New: reuses intelligence_agents_service's evidence-gathering + citation
    plumbing, then adds one new LLM synthesis call (via the central
    llm_provider_service.chat_completion — not a new/duplicate LLM path) prompted
    in the same proven ranked-hypothesis shape trace_rca_service.analyze_window()
    already uses for traces, applied here to an incident/service.

    run_id: pass the Supervisor's run_id when called from handle_query() so
    the classify -> route -> gather -> rank -> done events land on one shared
    trace; omit it (a fresh run_id is generated) when calling this directly,
    e.g. from the synchronous GET /diagnose/{target} route."""
    if run_id is None:
        run_id = await agentic_trace_service.start_run()
    run_started = time.perf_counter()

    await agentic_trace_service.emit(
        run_id, "diagnoser", "start", f"Diagnoser started for {service_or_incident}", status="running",
    )

    t0 = time.perf_counter()
    evidence_doc = await intelligence_agents_service.incident_analysis(
        query=f"Diagnose the root cause of {service_or_incident}",
        service=service_or_incident, time_range_minutes=hours * 60, user=user,
    )
    await agentic_trace_service.emit(
        run_id, "diagnoser", "gather_evidence", "Gathered observability evidence",
        detail={
            "evidence_count": len(evidence_doc.get("evidence") or []),
            "single_answer_confidence": evidence_doc.get("confidence"),
        },
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    t0 = time.perf_counter()
    similar = await rag_service.find_similar_incidents(
        f"root cause of {service_or_incident}", top_k=3, service=service_or_incident,
    )
    await agentic_trace_service.emit(
        run_id, "diagnoser", "search_memory", f"Searched incident memory — {len(similar)} similar past incident(s)",
        detail={"count": len(similar)}, duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    evidence_block = json.dumps({
        "target": service_or_incident,
        "single_answer_summary": evidence_doc.get("summary"),
        "single_answer_evidence": evidence_doc.get("evidence"),
        "single_answer_confidence": evidence_doc.get("confidence"),
        "tool_trace": evidence_doc.get("tool_trace"),
        "similar_past_incidents": [{"text": s["text"], "similarity": s["similarity"]} for s in similar],
    }, default=str)[:12000]

    messages = [
        {"role": "system", "content": DIAGNOSER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Evidence gathered for {service_or_incident}:\n{evidence_block}"},
    ]
    await agentic_trace_service.emit(
        run_id, "diagnoser", "llm_rank", "Ranking competing hypotheses via LLM", status="running",
    )
    t0 = time.perf_counter()
    llm = await chat_completion(messages, session_id=f"diagnoser-{uuid.uuid4().hex[:8]}")
    parsed = _parse_json_block(llm.get("response", "")) or {}
    hypotheses_raw = parsed.get("hypotheses") or []
    if not isinstance(hypotheses_raw, list):
        hypotheses_raw = []

    hypotheses: List[Dict[str, Any]] = []
    for h in hypotheses_raw[:4]:
        if not isinstance(h, dict):
            continue
        try:
            confidence = max(0.0, min(1.0, float(h.get("confidence", 0.3))))
        except (TypeError, ValueError):
            confidence = 0.3
        hypotheses.append({
            "root_cause": str(h.get("root_cause") or "")[:400],
            "confidence": round(confidence, 2),
            "category": (h.get("category") or "infra").lower(),
            "evidence": [str(e)[:300] for e in (h.get("evidence") or [])[:5]],
        })
    hypotheses.sort(key=lambda h: h["confidence"], reverse=True)
    for i, h in enumerate(hypotheses):
        h["rank"] = i + 1

    if not hypotheses:
        # Honest fallback — never fabricate a ranked list the LLM didn't actually produce.
        hypotheses = [{
            "rank": 1, "root_cause": evidence_doc.get("summary") or "No hypothesis could be synthesized",
            "confidence": round(float(evidence_doc.get("confidence") or 0.3), 2),
            "category": "infra", "evidence": evidence_doc.get("evidence") or [],
        }]

    await agentic_trace_service.emit(
        run_id, "diagnoser", "llm_rank", f"Ranked {len(hypotheses)} hypothesis/hypotheses",
        detail={"provider": llm.get("provider"), "model": llm.get("model"), "hypothesis_count": len(hypotheses)},
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    result = {
        "target": service_or_incident,
        "hypotheses": hypotheses,
        "similar_past_incidents": similar,
        "llm_provider": llm.get("provider"),
        "llm_model": llm.get("model"),
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
    }

    top = hypotheses[0]["root_cause"][:80] if hypotheses else "none"
    await agentic_trace_service.emit(
        run_id, "diagnoser", "done", f"Diagnoser complete — top hypothesis: {top}",
        detail={"top_confidence": hypotheses[0]["confidence"] if hypotheses else None},
        duration_ms=int((time.perf_counter() - run_started) * 1000),
    )

    return result


def _parse_json_block(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        m2 = re.search(r"\{.*\}", text, re.DOTALL)
        raw = m2.group(0) if m2 else None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def _log_decision(*, query: str, incident_id: Optional[str], classification: str, routed_to: str,
                        confidence: Optional[float], evidence_refs: Any, output_summary: str) -> str:
    await _ensure_indexes()
    doc = {
        "id": str(uuid.uuid4()),
        "query": query,
        "incident_id": incident_id,
        "classification": classification,
        "routed_to": routed_to,
        "confidence": confidence,
        "evidence_refs": evidence_refs,
        "output_summary": (output_summary or "")[:500],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.agentic_decision_log.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc["id"]


async def handle_query(
    query: str, incident_id: Optional[str] = None, user: Optional[Dict] = None, run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Supervisor entry point: classify -> route -> log. Read-only end to end —
    logging happens on completion (not before), since a read has no side effect
    to guard against; contrast the action broker's write-before-execute rule,
    which exists precisely because that path has real side effects.

    run_id is threaded into whichever specialist gets routed to (currently
    only run_diagnoser() accepts one) so a query that routes to the Diagnoser
    shows as one continuous Supervisor -> Diagnoser trace, not two disjoint
    runs."""
    if run_id is None:
        run_id = await agentic_trace_service.start_run()
    run_started = time.perf_counter()

    await agentic_trace_service.emit(
        run_id, "supervisor", "received", f"Supervisor received query: {query[:100]}", status="running",
    )

    t0 = time.perf_counter()
    classification = classify_query(query, incident_id=incident_id)
    route = classification["route"]
    await agentic_trace_service.emit(
        run_id, "supervisor", "classify", f"Classified as '{route}' — {classification['reason']}",
        detail=classification, duration_ms=int((time.perf_counter() - t0) * 1000),
    )
    await agentic_trace_service.emit(run_id, "supervisor", "route", f"Routing to {route}", status="running")

    if route == "diagnoser":
        target = incident_id or _extract_service_name(query) or query
        result = await run_diagnoser(target, user=user, run_id=run_id)
        confidence = result["hypotheses"][0]["confidence"] if result["hypotheses"] else None
        summary = result["hypotheses"][0]["root_cause"] if result["hypotheses"] else "No hypothesis produced"
        evidence_refs = result["hypotheses"]
    elif route == "forecaster":
        service = _extract_service_name(query)
        result = await run_forecaster(metric_name="cpu_usage", service=service)
        confidence = result.get("prediction", {}).get("confidence")
        summary = f"Forecast for {service or 'cpu_usage'}: {result.get('risk_assessment', {}).get('level', 'unknown')} risk"
        evidence_refs = result.get("threshold_analysis")
    elif route == "blast_radius":
        tokens = query.split()
        service = _extract_service_name(query) or (tokens[-1] if tokens else "")
        result = await get_blast_radius(service)
        confidence = None
        summary = f"{result.get('total_impacted', 0)} services impacted, risk={result.get('risk_level', 'unknown')}" if "error" not in result else result["error"]
        evidence_refs = result.get("impacted_services")
    elif route == "memory":
        service = _extract_service_name(query)
        result_list = await find_similar_incidents(query, service=service)
        result = {"similar_incidents": result_list}
        confidence = result_list[0]["similarity"] if result_list else None
        summary = f"{len(result_list)} similar past incident(s) found"
        evidence_refs = result_list
    else:
        result = await run_copilot(query, user=user)
        confidence = result.get("confidence")
        summary = result.get("summary")
        evidence_refs = result.get("evidence_refs")

    decision_id = await _log_decision(
        query=query, incident_id=incident_id, classification=route, routed_to=route,
        confidence=confidence, evidence_refs=evidence_refs, output_summary=summary,
    )

    await agentic_trace_service.emit(
        run_id, "supervisor", "done", f"Supervisor complete — routed to {route}",
        detail={"decision_id": decision_id}, duration_ms=int((time.perf_counter() - run_started) * 1000),
    )

    return {
        "classification": classification,
        "routed_to": route,
        "result": result,
        "decision_id": decision_id,
        "run_id": run_id,
    }


async def list_decision_log(limit: int = 50) -> List[Dict[str, Any]]:
    await _ensure_indexes()
    return await db.agentic_decision_log.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
