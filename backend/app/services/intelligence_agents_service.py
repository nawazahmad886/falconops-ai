"""
FalconOps AI — AI Intelligence Layer: Agents
Two agents on top of the tooling interface + RAG:
  1. Incident Analysis Agent — deep RCA: correlates logs, metrics, traces, deployments,
     incidents + similar past incidents (RAG) → structured root-cause output.
  2. Monitoring Copilot Agent — natural language → tool query → structured + human answer.

All LLM calls go through llm_provider_service.chat_completion which already provides:
  - pre-flight injection guard, Ollama/on-prem support, provider fallback,
  - automatic AI self-observability instrumentation (prompt/output/latency/failures).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.database import db
from . import ai_tools_service as tools
from . import rag_service
from .llm_provider_service import chat_completion

logger = logging.getLogger(__name__)

RCA_KEYWORDS = re.compile(
    r"\b(why|slow|root\s*cause|rca|down|failing|failure|degraded|broken|crash|outage|latency|timeout|investigate|diagnose)\b",
    re.IGNORECASE,
)


def detect_mode(query: str) -> str:
    return "incident" if RCA_KEYWORDS.search(query or "") else "copilot"


async def _extract_service(query: str) -> Optional[str]:
    known = await tools.list_services()
    ql = (query or "").lower()
    for svc in known:
        if svc.lower() in ql:
            return svc
    # loose match on tokens like "payment" → payment-api
    for svc in known:
        stem = svc.lower().split("-")[0]
        if len(stem) >= 4 and stem in ql:
            return svc
    return None


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
        try:
            return json.loads(raw.replace("\n", " ").replace(",}", "}").replace(",]", "]"))
        except Exception:
            return None


_EVIDENCE_HANDLE_RE = re.compile(r"^\s*\[([A-Za-z]{1,2}\d+)\]\s*")


def _normalize_result(parsed: Optional[Dict], raw_text: str,
                      evidence_pool: Optional[Dict[str, Dict[str, Any]]] = None,
                      agent_healthy: Optional[bool] = None) -> Dict[str, Any]:
    """Force the canonical response contract.

    evidence_pool: {handle -> {kind, id, service, timestamp}} built from the tool results
      for this request (see _tag_tool_result). Evidence bullets the LLM prefixes with a
      matching handle (e.g. "[L3] ...") get resolved into a verifiable evidence_ref instead
      of being trusted as free-form prose.
    agent_healthy: OneAgent status for the analysis target — None means no OneAgent was ever
      registered for it (ambiguous: could be monitored via another collector, don't penalize),
      True/False means one was found and is/isn't currently reporting. Used to put a
      deterministic ceiling on the LLM's self-reported confidence when telemetry is known-stale,
      rather than trusting the LLM's own confidence estimate at face value.
    """
    parsed = parsed or {}
    summary = str(parsed.get("summary") or raw_text or "No analysis produced.")[:3000]
    evidence = parsed.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = [str(evidence)]
    evidence = [str(e)[:500] for e in evidence[:10]]

    evidence_pool = evidence_pool or {}
    evidence_refs: List[Optional[Dict[str, Any]]] = []
    for e in evidence:
        m = _EVIDENCE_HANDLE_RE.match(e)
        ref = evidence_pool.get(m.group(1)) if m else None
        evidence_refs.append({"handle": m.group(1), **ref} if ref else None)

    try:
        confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    cap = 1.0
    if not evidence:
        cap = 0.3
    stale_note_needed = False
    if agent_healthy is False:
        cap = min(cap, 0.4)
        if not any(re.search(r"onea?gent|telemetry|stale", e, re.IGNORECASE) for e in evidence):
            stale_note_needed = True
    confidence = min(confidence, cap)

    if stale_note_needed:
        evidence.append("OneAgent telemetry for this target is stale/offline — this analysis may be based on incomplete data.")
        evidence_refs.append(None)

    actions = parsed.get("recommended_actions") or []
    if not isinstance(actions, list):
        actions = [str(actions)]
    actions = [str(a)[:300] for a in actions[:8]]
    return {"summary": summary, "evidence": evidence, "evidence_refs": evidence_refs,
            "confidence": round(confidence, 2), "recommended_actions": actions}


def _tag_tool_result(result: Dict[str, Any], pool: Dict[str, Dict[str, Any]],
                     counters: Dict[str, int]) -> Dict[str, Any]:
    """Return a copy of a tool result with a short citable handle (L1, T1, I1, ...) injected
    into each row that looks like a log/trace/incident record, registering each handle's
    source (kind, id, service, timestamp) in `pool` for later resolution in _normalize_result."""
    prefix = {"get_logs": "L", "get_deployments": "D", "get_traces": "T", "get_incidents": "I"}.get(result.get("tool"))
    rows = result.get("data")
    if not prefix or not isinstance(rows, list):
        return result
    tagged_rows = []
    for row in rows[:15]:
        if not isinstance(row, dict):
            tagged_rows.append(row)
            continue
        counters[prefix] = counters.get(prefix, 0) + 1
        handle = f"{prefix}{counters[prefix]}"
        pool[handle] = {
            "kind": result.get("tool"),
            "id": row.get("id") or row.get("trace_id"),
            "service": row.get("service") or row.get("service_name"),
            "timestamp": row.get("timestamp") or row.get("start_time") or row.get("received_at") or row.get("created_at"),
        }
        tagged_rows.append({"handle": handle, **row})
    return {**result, "data": tagged_rows}


def _plan_signature(plan: Dict[str, Any]) -> tuple:
    return (plan.get("tool"), tuple(sorted((plan.get("params") or {}).items())))


# ─────────────────────────────────────────────
#  1. Incident Analysis Agent
# ─────────────────────────────────────────────

INCIDENT_SYSTEM_PROMPT = """You are the FalconOpsAI Incident Analysis Agent — a senior SRE performing root cause analysis.
You are given observability evidence gathered via tools (logs, metrics, traces, deployments, incidents) plus similar past incidents from memory.
Correlate the evidence and determine the most likely root cause.

Respond with ONLY a JSON object (no prose outside JSON):
{
  "summary": "clear root cause explanation in 2-4 sentences",
  "evidence": ["specific supporting evidence item with numbers/timestamps", "..."],
  "confidence": 0.0-1.0,
  "recommended_actions": ["concrete action 1", "concrete action 2"]
}
Rules:
- Base evidence ONLY on the data provided. Never invent log lines or metrics.
- If evidence is weak/absent, say so in summary and set confidence <= 0.4.
- Prefer correlations: deployment just before error spike, error logs matching slow traces, etc.
- Evidence rows are tagged with a citable handle (e.g. "handle": "L3"). When a bullet is backed by a
  specific row, prefix it with that handle, e.g. "[L3] 500 error at 14:32:10 on payment-api"."""


async def incident_analysis(query: str, service: Optional[str] = None,
                            time_range_minutes: int = 60, user: Optional[Dict] = None) -> Dict[str, Any]:
    started = datetime.now(timezone.utc)
    if not service:
        service = await _extract_service(query)

    # Gather evidence via tools — in parallel. get_agent_status closes a real blind spot:
    # without it, a stale/offline OneAgent just looks like "no logs/metrics/traces" and the
    # agent has no way to tell that apart from "the service is healthy".
    tid = (user or {}).get("tenant_id")
    logs_t, err_logs_t, metrics_t, traces_t, deploys_t, incidents_t, agent_status_t = await asyncio.gather(
        tools.get_logs(service=service, minutes=time_range_minutes, limit=30, tenant_id=tid),
        tools.get_logs(service=service, minutes=time_range_minutes, level="error", limit=40, tenant_id=tid),
        tools.get_metrics(service=service, minutes=time_range_minutes, tenant_id=tid),
        tools.get_traces(service=service, minutes=max(time_range_minutes, 120), limit=20),
        tools.get_deployments(service=service, tenant_id=tid),
        tools.get_incidents(service=service, limit=5, tenant_id=tid),
        tools.get_agent_status(service=service),
    )
    similar = await rag_service.find_similar_incidents(query, top_k=3, service=service)

    tool_trace = [
        {"tool": t["tool"], "params": t.get("params"), "summary": t.get("summary"), "count": t.get("count")}
        for t in (logs_t, err_logs_t, metrics_t, traces_t, deploys_t, incidents_t, agent_status_t)
    ]

    pool: Dict[str, Dict[str, Any]] = {}
    counters: Dict[str, int] = {}
    tagged_err_logs = _tag_tool_result(err_logs_t, pool, counters)
    tagged_traces = _tag_tool_result(traces_t, pool, counters)
    tagged_deploys = _tag_tool_result(deploys_t, pool, counters)
    tagged_incidents = _tag_tool_result(incidents_t, pool, counters)

    evidence_block = json.dumps({
        "target_service": service or "all services",
        "time_window_minutes": time_range_minutes,
        "log_overview": {"total": logs_t["count"], "by_level": logs_t.get("by_level")},
        "error_logs": tagged_err_logs["data"][:25],
        "metrics": metrics_t["data"][:20] if isinstance(metrics_t.get("data"), list) else metrics_t.get("data"),
        "traces": {"summary": traces_t["summary"], "errors": traces_t.get("errors"),
                   "avg_duration_ms": traces_t.get("avg_duration_ms"),
                   "recent": tagged_traces["data"][:10] if isinstance(tagged_traces.get("data"), list) else tagged_traces.get("data")},
        "recent_deployments": tagged_deploys["data"][:10],
        "related_incidents": tagged_incidents["data"][:5],
        "similar_past_incidents": [{"text": s["text"], "similarity": s["similarity"]} for s in similar],
        "collector_status": agent_status_t.get("summary"),
    }, default=str)[:14000]

    messages = [
        {"role": "system", "content": INCIDENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"User question: {query}\n\nEvidence gathered by tools:\n{evidence_block}"},
    ]
    llm = await chat_completion(messages, session_id=f"incident-agent-{uuid.uuid4().hex[:8]}")
    agent_rows = agent_status_t.get("data") or []
    # None (no OneAgent ever seen for this target) is deliberately NOT penalized — the service
    # may well be monitored via a different collector/integration. Only a KNOWN stale agent
    # caps confidence.
    agent_healthy = agent_status_t.get("any_healthy") if agent_rows else None
    result = _normalize_result(_parse_json_block(llm.get("response", "")), llm.get("response", ""),
                               evidence_pool=pool, agent_healthy=agent_healthy)

    analysis_id = str(uuid.uuid4())
    doc = {
        "id": analysis_id,
        "mode": "incident",
        "query": query,
        "service": service,
        "time_range_minutes": time_range_minutes,
        **result,
        "similar_incidents": similar,
        "tool_trace": tool_trace,
        "llm_provider": llm.get("provider"),
        "llm_model": llm.get("model"),
        "blocked": bool(llm.get("blocked")),
        "duration_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
        "user_email": (user or {}).get("email"),
        "tenant_id": (user or {}).get("tenant_id"),
        "created_at": started.isoformat(),
    }
    await db.ai_intelligence_analyses.insert_one({**doc})
    # feed the new analysis back into incident memory (fire-and-forget)
    asyncio.create_task(_index_analysis_safe(doc))
    return doc


async def _index_analysis_safe(doc: Dict) -> None:
    try:
        col = rag_service._collection(rag_service.INCIDENTS_COLLECTION)
        if col is None:
            return
        text = f"Q: {doc['query']} | RCA: {doc['summary']} | actions: {', '.join(doc['recommended_actions'][:3])}"[:1500]
        emb = await rag_service._embed(text)
        if emb is None:
            return
        col.upsert(ids=[f"analysis:{doc['id']}"], embeddings=[emb], documents=[text],
                   metadatas=[{"kind": "past_analysis", "service": doc.get("service") or "",
                               "confidence": float(doc.get("confidence") or 0),
                               "created_at": doc.get("created_at") or ""}])
    except Exception as e:
        logger.debug("analysis indexing skipped: %s", e)


# ─────────────────────────────────────────────
#  2. Monitoring Copilot Agent
# ─────────────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """You are the FalconOpsAI Monitoring Copilot planner.
Translate the user's natural-language monitoring question into ONE tool call.

Available tools:
{tools}

Known services: {services}

Respond with ONLY JSON: {{"tool": "<tool_name>", "params": {{...}}}}
If the question needs no data (greeting/general), respond {{"tool": "none", "params": {{}}}}.
Time phrases: "last 10 minutes" → minutes=10, "past hour" → minutes=60, "today" → minutes=1440.
"show errors" → get_logs with level="error". "which service is failing" → get_logs level="error" (no service filter)."""

ANSWER_SYSTEM_PROMPT = """You are the FalconOpsAI Monitoring Copilot. You already ran one or more tools; summarize the results for an SRE.
Respond with ONLY JSON:
{
  "summary": "direct human-readable answer to the question, referencing real numbers",
  "evidence": ["key data point 1", "key data point 2"],
  "confidence": 0.0-1.0,
  "recommended_actions": ["optional next step"]
}
Never invent data not present in the tool result(s). If the tools returned nothing, say so plainly.
Rows are tagged with a citable handle (e.g. "handle": "L3"). When a bullet is backed by a specific
row, prefix it with that handle, e.g. "[L3] 500 error at 14:32:10 on payment-api"."""

CONTINUE_PLANNER_SYSTEM_PROMPT = """You are the FalconOpsAI Monitoring Copilot planner, deciding whether
ANOTHER tool call is needed before you can answer the user's question.

Available tools:
{tools}

Known services: {services}

Tool calls already made this turn:
{history}

If you already have enough evidence to answer, respond with ONLY JSON: {{"tool": "none", "params": {{}}}}
Otherwise pick ONE more tool call that fills a real gap (e.g. you saw error logs and now want traces or
recent deployments for the same service/window to correlate). Never repeat an identical tool+params call
you already made. Respond with ONLY JSON: {{"tool": "<tool_name>", "params": {{...}}}}"""

MAX_COPILOT_STEPS = 3


def _fallback_plan(query: str, service: Optional[str]) -> Dict[str, Any]:
    ql = (query or "").lower()
    mins = 60
    m = re.search(r"last\s+(\d+)\s*(minute|min|hour|hr|day)", ql)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        mins = n * (60 if unit.startswith(("hour", "hr")) else 1440 if unit.startswith("day") else 1)
    if "trace" in ql:
        return {"tool": "get_traces", "params": {"service": service, "minutes": mins}}
    if "metric" in ql or "cpu" in ql or "memory" in ql or "latency" in ql:
        return {"tool": "get_metrics", "params": {"service": service, "minutes": mins}}
    if "deploy" in ql or "release" in ql:
        return {"tool": "get_deployments", "params": {"service": service}}
    if "incident" in ql:
        return {"tool": "get_incidents", "params": {"service": service}}
    if ("no data" in ql or "not reporting" in ql
            or any(p in ql for p in ("oneagent", "one agent", "collector", "agent status", "agent down", "agent offline"))
            or ("monitoring" in ql and any(w in ql for w in ("working", "down", "status", "broken")))):
        return {"tool": "get_agent_status", "params": {"service": service}}
    level = "error" if ("error" in ql or "fail" in ql) else None
    return {"tool": "get_logs", "params": {"service": service, "minutes": mins, "level": level}}


async def copilot_query(query: str, user: Optional[Dict] = None) -> Dict[str, Any]:
    """Bounded multi-step tool-calling loop (up to MAX_COPILOT_STEPS tool calls): plan → execute →
    ask the LLM if another tool call would help (e.g. errors seen, now check traces/deployments for
    the same window) → execute → ... → once satisfied (or budget exhausted), answer from everything
    gathered. This replaces the old single plan-then-answer shot with genuine follow-up reasoning."""
    started = datetime.now(timezone.utc)
    service = await _extract_service(query)
    services = await tools.list_services()

    planner_messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT.format(
            tools=json.dumps(tools.TOOL_DEFS), services=", ".join(services))},
        {"role": "user", "content": query},
    ]
    plan_llm = await chat_completion(planner_messages, session_id=f"copilot-planner-{uuid.uuid4().hex[:8]}")
    plan = _parse_json_block(plan_llm.get("response", ""))
    if not plan or not plan.get("tool") or plan.get("tool") not in list(tools._TOOL_FUNCS) + ["none"]:
        plan = _fallback_plan(query, service)
    if plan.get("params", {}).get("service") is None and service:
        plan.setdefault("params", {})["service"] = service

    pool: Dict[str, Dict[str, Any]] = {}
    counters: Dict[str, int] = {}
    tool_trace: List[Dict[str, Any]] = []
    tagged_results: List[Dict[str, Any]] = []
    seen_signatures = set()
    provider, model, blocked = plan_llm.get("provider"), plan_llm.get("model"), bool(plan_llm.get("blocked"))
    resolved_service = service

    step = 0
    while plan.get("tool") not in (None, "none") and step < MAX_COPILOT_STEPS:
        sig = _plan_signature(plan)
        if sig in seen_signatures:
            break  # loop guard: LLM repeated an identical call, stop instead of spinning
        seen_signatures.add(sig)

        raw_result = await tools.execute_tool(plan["tool"], plan.get("params") or {},
                                              tenant_id=(user or {}).get("tenant_id"))
        tagged_results.append(_tag_tool_result(raw_result, pool, counters))
        tool_trace.append({"tool": plan["tool"], "params": plan.get("params"),
                           "summary": raw_result.get("summary"), "count": raw_result.get("count")})
        resolved_service = (plan.get("params") or {}).get("service") or resolved_service
        step += 1
        if step >= MAX_COPILOT_STEPS:
            break

        history = "\n".join(f"- {t['tool']}({t['params']}) → {t['summary']}" for t in tool_trace)
        continue_messages = [
            {"role": "system", "content": CONTINUE_PLANNER_SYSTEM_PROMPT.format(
                tools=json.dumps(tools.TOOL_DEFS), services=", ".join(services), history=history)},
            {"role": "user", "content": query},
        ]
        continue_llm = await chat_completion(continue_messages, session_id=f"copilot-planner-{uuid.uuid4().hex[:8]}")
        next_plan = _parse_json_block(continue_llm.get("response", ""))
        if not next_plan or not next_plan.get("tool") or next_plan.get("tool") not in list(tools._TOOL_FUNCS) + ["none"]:
            break  # malformed/uncertain continuation — stop rather than guess
        if next_plan.get("params", {}).get("service") is None and service:
            next_plan.setdefault("params", {})["service"] = service
        plan = next_plan

    if tagged_results:
        tool_payload = json.dumps(tagged_results, default=str)[:12000]
        answer_messages = [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nTool call(s) executed:\n{tool_payload}"},
        ]
        ans_llm = await chat_completion(answer_messages, session_id=f"copilot-answer-{uuid.uuid4().hex[:8]}")
        agent_result = next((r for r in tagged_results if r.get("tool") == "get_agent_status"), None)
        agent_healthy = agent_result.get("any_healthy") if agent_result and agent_result.get("data") else None
        result = _normalize_result(_parse_json_block(ans_llm.get("response", "")), ans_llm.get("response", ""),
                                   evidence_pool=pool, agent_healthy=agent_healthy)
        provider, model = ans_llm.get("provider"), ans_llm.get("model")
        blocked = bool(ans_llm.get("blocked"))
    else:
        result = _normalize_result(None, plan_llm.get("response", ""))

    doc = {
        "id": str(uuid.uuid4()),
        "mode": "copilot",
        "query": query,
        "service": resolved_service,
        **result,
        "tool_trace": tool_trace,
        "structured_data": {k: v for k, v in (tagged_results[-1] if tagged_results else {}).items()
                            if k in ("data", "by_level", "stats", "errors", "avg_duration_ms")},
        "llm_provider": provider,
        "llm_model": model,
        "blocked": blocked,
        "duration_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
        "user_email": (user or {}).get("email"),
        "tenant_id": (user or {}).get("tenant_id"),
        "created_at": started.isoformat(),
    }
    await db.ai_intelligence_analyses.insert_one({**doc})
    return doc


async def ask(query: str, mode: str = "auto", service: Optional[str] = None,
              time_range_minutes: int = 60, user: Optional[Dict] = None) -> Dict[str, Any]:
    """Unified entry point. mode: auto | incident | copilot."""
    if mode == "auto":
        mode = detect_mode(query)
    if mode == "incident":
        return await incident_analysis(query, service=service,
                                       time_range_minutes=time_range_minutes, user=user)
    return await copilot_query(query, user=user)
