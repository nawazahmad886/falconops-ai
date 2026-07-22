"""
FalconOps AI - Multi-Agent RCA Chain
Chains 3 real, purpose-built steps to investigate one incident, mirroring a
"Root Cause Agent -> Root Cause Details Agent -> Data Analysis Agent" progressive
investigation: identify the root-cause service via the existing single-shot RCA engine
(intelligence_agents_service.incident_analysis), pull real topology facts for that
entity (topology_service), then fetch correlated logs — retrying once with a widened
window if the first pass returns weak evidence. Each step's own output is recorded
(not just the final answer) so the frontend can render the chain, matching the
"Root Cause Agent -> Root Cause Details Agent -> Data Analysis Agent" screenshot.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.database import db
from . import ai_tools_service as tools
from .intelligence_agents_service import incident_analysis, _normalize_result, _parse_json_block
from .llm_provider_service import chat_completion
from .topology_service import topology_service

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """You are the FalconOps Root Cause Synthesis Agent. You are
given the outputs of three prior investigation steps (root cause identification, entity
details, and correlated log analysis) for one incident. Respond with ONLY a JSON object
(no prose outside JSON):
{
  "summary": "clear root-cause narrative in 2-4 sentences",
  "evidence": ["specific supporting evidence item", "..."],
  "confidence": 0.0-1.0,
  "recommended_actions": ["concrete action 1", "concrete action 2"]
}
Rules:
- Base everything ONLY on the three steps' evidence provided below. Never invent
  services, log lines, or entities not present in that evidence.
- If the steps found weak/no evidence, say so in summary and set confidence <= 0.4."""


async def run_rca_chain(incident_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Run the 3-step RCA chain against one incident, persist the trace, and update the
    incident's existing root_cause_analysis/resolution_steps fields (no new incident
    schema — just a new rca_chain_trace field alongside them)."""
    incident = await db.incidents_engine.find_one({"id": incident_id}, {"_id": 0})
    collection = db.incidents_engine
    if not incident:
        incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
        collection = db.incidents
    if not incident:
        return {"error": "Incident not found"}

    trace: List[Dict[str, Any]] = []
    affected_services = incident.get("affected_services") or []
    primary_service = affected_services[0] if affected_services else incident.get("service")

    # ---- Step 1: Root Cause Agent ----
    t0 = time.monotonic()
    rca = await incident_analysis(
        query=f"{incident.get('title', '')} — {incident.get('description', '')}",
        service=primary_service,
        time_range_minutes=120,
    )
    root_service = rca.get("service") or primary_service
    trace.append({
        "step": 1, "agent_name": "Root Cause Agent",
        "summary": rca.get("summary", ""), "confidence": rca.get("confidence"),
        "duration_ms": round((time.monotonic() - t0) * 1000, 1),
    })

    # ---- Step 2: Root Cause Details Agent (deterministic — real topology facts, no LLM call) ----
    t0 = time.monotonic()
    node = await topology_service.get_service_by_name(root_service) if root_service else None
    impacted = await topology_service.get_impacted_services(node["id"], depth=2) if node else []
    if node:
        details_summary = (
            f"Root cause entity: {node['name']} (type={node.get('type', 'service')}, "
            f"status={node.get('status', 'unknown')}, health_score={node.get('health_score', 'n/a')}). "
            f"{len(impacted)} downstream service(s) potentially impacted: "
            f"{', '.join(i.get('name', '') for i in impacted[:5]) or 'none'}."
        )
    else:
        details_summary = f"No topology entity found for '{root_service}' — entity details unavailable."
    trace.append({
        "step": 2, "agent_name": "Root Cause Details Agent",
        "summary": details_summary, "confidence": 0.9 if node else 0.3,
        "duration_ms": round((time.monotonic() - t0) * 1000, 1),
    })

    # ---- Step 3: Data Analysis Agent — correlated logs, retry-on-weak-evidence ----
    t0 = time.monotonic()
    logs = await tools.get_logs(service=root_service, minutes=120, level="error", limit=30)
    relevant = [r for r in (logs.get("data") or []) if r.get("service") == root_service]
    retried = False
    if len(relevant) < 3 and root_service:
        retried = True
        logs = await tools.get_logs(service=root_service, minutes=360, level="error", limit=30)
        relevant = [r for r in (logs.get("data") or []) if r.get("service") == root_service]
    if relevant:
        data_summary = (
            f"Found {len(relevant)} error log(s) directly attributable to {root_service} "
            f"(searched {'a widened 6h window after the initial search returned weak evidence' if retried else 'the last 2h'})."
        )
    else:
        data_summary = (
            f"No error logs directly attributable to {root_service} were found"
            f"{' even after widening the search window' if retried else ''} — evidence is topology-only."
        )
    trace.append({
        "step": 3, "agent_name": "Data Analysis Agent",
        "summary": data_summary, "confidence": 0.8 if relevant else 0.4,
        "duration_ms": round((time.monotonic() - t0) * 1000, 1), "retried": retried,
    })

    # ---- Final synthesis ----
    t0 = time.monotonic()
    evidence_block = {
        "root_cause_step": trace[0],
        "entity_details_step": trace[1],
        "log_analysis_step": {**trace[2], "sample_logs": [
            {"timestamp": r.get("timestamp"), "level": r.get("level"), "message": r.get("message")}
            for r in relevant[:10]
        ]},
    }
    messages = [
        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": f"Incident: {incident.get('title')}\n\nStep evidence:\n{evidence_block}"},
    ]
    llm = await chat_completion(messages, session_id=f"rca-chain-{incident_id}")
    final = _normalize_result(_parse_json_block(llm.get("response", "")), llm.get("response", ""))
    trace.append({
        "step": 4, "agent_name": "Synthesis",
        "summary": final.get("summary", ""), "confidence": final.get("confidence"),
        "duration_ms": round((time.monotonic() - t0) * 1000, 1),
    })

    now_iso = datetime.now(timezone.utc).isoformat()
    update = {
        "root_cause_analysis": final.get("summary"),
        "resolution_steps": final.get("recommended_actions", []),
        "rca_chain_trace": trace,
        "rca_chain_run_at": now_iso,
    }
    await collection.update_one({"id": incident_id}, {"$set": update})

    return {"incident_id": incident_id, **update}
