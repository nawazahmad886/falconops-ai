"""
FalconOps AI - Specialized Security Agents
Threat Hunting, Compliance, Cloud Security, Network, and Identity agents — built on the
same real tool-calling pattern as intelligence_agents_service.incident_analysis() (parallel
tool gathering -> evidence block -> one structured LLM call -> evidence-capped confidence),
not the simpler no-tools ai_agents_service.AGENTS dict. Reuses _tag_tool_result/
_normalize_result/_parse_json_block directly from intelligence_agents_service rather than
duplicating that logic.
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
from . import rag_service
from .llm_provider_service import chat_completion
from .intelligence_agents_service import _tag_tool_result, _normalize_result, _parse_json_block

logger = logging.getLogger(__name__)

SECURITY_AGENT_SYSTEM_PROMPT_TEMPLATE = """You are the FalconOpsAI {role} — a security specialist.
{specialty}

You are given evidence gathered via tools. Respond with ONLY a JSON object (no prose outside JSON):
{{
  "summary": "clear finding in 2-4 sentences",
  "evidence": ["specific supporting evidence item", "..."],
  "confidence": 0.0-1.0,
  "recommended_actions": ["concrete action 1", "concrete action 2"]
}}
Rules:
- Base evidence ONLY on the data provided. Never invent events, users, or CVEs.
- If evidence is weak/absent, say so in summary and set confidence <= 0.4.
- Evidence rows are tagged with a citable handle (e.g. "handle": "L3"). When a bullet is backed by a
  specific row, prefix it with that handle, e.g. "[L3] failed login for admin at 14:32:10"."""

SECURITY_AGENTS: Dict[str, Dict] = {
    "threat_hunting": {
        "name": "Threat Hunting Agent",
        "role": "Threat Hunting Agent",
        "specialty": "You proactively hunt for signs of compromise across threats, security events, "
                     "UEBA risk profiles, and MITRE ATT&CK technique patterns, correlating with similar past incidents.",
        "tools": ["get_threats", "get_security_events", "get_mitre_matrix", "get_ueba_profiles"],
        "use_rag": True,
    },
    "compliance": {
        "name": "Compliance Agent",
        "role": "Compliance Agent",
        "specialty": "You assess compliance posture (SOC2/ISO27001 controls) and flag gaps, "
                     "correlating control failures with recent security events.",
        "tools": ["get_compliance_status", "get_security_events"],
        "use_rag": False,
    },
    "cloud_security": {
        "name": "Cloud Security Agent",
        "role": "Cloud Security Agent",
        "specialty": "You assess vulnerability exposure against the real service topology, "
                     "prioritizing by CVSS and blast radius, and MITRE technique coverage.",
        "tools": ["get_vulnerabilities", "get_topology_summary", "get_mitre_matrix"],
        "use_rag": False,
    },
    "network": {
        "name": "Network Security Agent",
        "role": "Network Security Agent",
        "specialty": "You analyze traces, security events, and threats for network-level attack "
                     "patterns (scanning, lateral movement, anomalous traffic).",
        "tools": ["get_traces", "get_security_events", "get_threats"],
        "use_rag": False,
    },
    "identity": {
        "name": "Identity Security Agent",
        "role": "Identity Security Agent",
        "specialty": "You analyze UEBA behavioral risk profiles and security events for identity-based "
                     "threats: credential compromise, privilege escalation, insider threat, impossible travel.",
        "tools": ["get_ueba_profiles", "get_security_events"],
        "use_rag": False,
    },
}


def get_agent_catalog() -> List[Dict]:
    return [{"id": aid, "name": a["name"], "specialty": a["specialty"], "tools": a["tools"]}
            for aid, a in SECURITY_AGENTS.items()]


async def run_security_agent(agent_id: str, query: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    agent = SECURITY_AGENTS.get(agent_id)
    if not agent:
        return None
    started = datetime.now(timezone.utc)

    tool_results = await asyncio.gather(
        *[tools.execute_tool(name, {}) for name in agent["tools"]]
    )

    pool: Dict[str, Dict[str, Any]] = {}
    counters: Dict[str, int] = {}
    tagged_results = [_tag_tool_result(r, pool, counters) for r in tool_results]

    similar: List[Dict] = []
    if agent.get("use_rag"):
        try:
            similar = await rag_service.find_similar_incidents(query, top_k=3)
        except Exception as e:
            logger.debug(f"RAG lookup skipped for {agent_id}: {e}")

    evidence_block = json.dumps({
        "query": query,
        "tool_results": [
            {"tool": r.get("tool"), "summary": r.get("summary"), "count": r.get("count"), "data": r.get("data")}
            for r in tagged_results
        ],
        "similar_past_incidents": [{"text": s["text"], "similarity": s["similarity"]} for s in similar],
    }, default=str)[:14000]

    system_prompt = SECURITY_AGENT_SYSTEM_PROMPT_TEMPLATE.format(role=agent["role"], specialty=agent["specialty"])
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question: {query}\n\nEvidence gathered by tools:\n{evidence_block}"},
    ]
    llm = await chat_completion(messages, session_id=f"security-agent-{agent_id}-{uuid.uuid4().hex[:8]}")
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
    await db.security_agent_analyses.insert_one({**doc})
    doc.pop("_id", None)
    return doc
