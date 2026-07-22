"""
FalconOps AI - Specialized Operations Agents
API Performance, Capacity, SLA Risk, and Executive Ops agents — built on the same real
tool-calling pattern as security_agents_service.py / intelligence_agents_service.py
(parallel tool gathering -> evidence block -> one structured LLM call -> evidence-capped
confidence). Reuses _tag_tool_result/_normalize_result/_parse_json_block directly from
intelligence_agents_service rather than duplicating that logic.

A "Kubernetes Agent" was deliberately NOT added here: k8s_healing_service.py is
dry-run/plan-preview only (no real cluster client anywhere in this repo), so an agent
built on it would have nothing real to reason over — it would just narrate its own
simulated playbook text back as if it were live cluster state. Every agent below is
backed by a real, already-computed signal instead (real trace spans, a real
linear-regression capacity forecast, a real SLA deadline, real incident/outcome
history).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.database import db
from . import ai_tools_service as tools
from .llm_provider_service import chat_completion
from .intelligence_agents_service import _tag_tool_result, _normalize_result, _parse_json_block

logger = logging.getLogger(__name__)

OPS_AGENT_SYSTEM_PROMPT_TEMPLATE = """You are the FalconOpsAI {role} — an operations specialist.
{specialty}

You are given evidence gathered via tools. Respond with ONLY a JSON object (no prose outside JSON):
{{
  "summary": "clear finding in 2-4 sentences",
  "evidence": ["specific supporting evidence item", "..."],
  "confidence": 0.0-1.0,
  "recommended_actions": ["concrete action 1", "concrete action 2"]
}}
Rules:
- Base evidence ONLY on the data provided. Never invent hosts, endpoints, or incidents.
- If evidence is weak/absent, say so in summary and set confidence <= 0.4.
- Evidence rows are tagged with a citable handle (e.g. "handle": "L3"). When a bullet is backed by a
  specific row, prefix it with that handle, e.g. "[L3] failed login for admin at 14:32:10"."""

OPS_AGENTS: Dict[str, Dict] = {
    "api_performance": {
        "name": "API Performance Agent",
        "role": "API Performance Agent",
        "specialty": "You analyze per-endpoint latency and error rates from real distributed "
                     "trace data to identify which API operations are degraded or failing.",
        "tools": ["get_api_operation_stats", "get_traces"],
    },
    "capacity": {
        "name": "Capacity Agent",
        "role": "Capacity Planning Agent",
        "specialty": "You assess real linear-regression capacity forecasts (CPU/memory/disk) "
                     "and flag hosts approaching resource thresholds, with estimated time-to-breach.",
        "tools": ["get_capacity_forecast", "get_metrics"],
    },
    "sla": {
        "name": "SLA Risk Agent",
        "role": "SLA Risk Agent",
        "specialty": "You track open incidents against their real SLA breach deadlines and "
                     "prioritize which are at imminent risk of breaching.",
        "tools": ["get_sla_risk", "get_incidents"],
    },
    "executive_ops": {
        "name": "Executive Ops Agent",
        "role": "Executive Operations Assistant",
        "specialty": "You produce management-level summaries of operational health: incident "
                     "volume, MTTR, automation effectiveness, capacity risk, and SLA exposure.",
        "tools": ["get_ops_summary", "get_sla_risk", "get_capacity_forecast"],
    },
}


def get_agent_catalog() -> List[Dict]:
    return [{"id": aid, "name": a["name"], "specialty": a["specialty"], "tools": a["tools"]}
            for aid, a in OPS_AGENTS.items()]


async def run_ops_agent(agent_id: str, query: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    agent = OPS_AGENTS.get(agent_id)
    if not agent:
        return None
    started = datetime.now(timezone.utc)

    tool_results = await asyncio.gather(
        *[tools.execute_tool(name, {}) for name in agent["tools"]]
    )

    pool: Dict[str, Dict[str, Any]] = {}
    counters: Dict[str, int] = {}
    tagged_results = [_tag_tool_result(r, pool, counters) for r in tool_results]

    evidence_block = json.dumps({
        "query": query,
        "tool_results": [
            {"tool": r.get("tool"), "summary": r.get("summary"), "count": r.get("count"), "data": r.get("data")}
            for r in tagged_results
        ],
    }, default=str)[:14000]

    system_prompt = OPS_AGENT_SYSTEM_PROMPT_TEMPLATE.format(role=agent["role"], specialty=agent["specialty"])
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question: {query}\n\nEvidence gathered by tools:\n{evidence_block}"},
    ]
    llm = await chat_completion(messages, session_id=f"ops-agent-{agent_id}-{uuid.uuid4().hex[:8]}")
    result = _normalize_result(_parse_json_block(llm.get("response", "")), llm.get("response", ""), evidence_pool=pool)

    doc = {
        "id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "query": query,
        "tenant_id": tenant_id,
        **result,
        "tool_trace": [{"tool": r.get("tool"), "summary": r.get("summary"), "count": r.get("count")} for r in tagged_results],
        "llm_provider": llm.get("provider"),
        "llm_model": llm.get("model"),
        "duration_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 1),
        "created_at": started.isoformat(),
    }
    await db.ops_agent_analyses.insert_one({**doc})
    doc.pop("_id", None)
    return doc
