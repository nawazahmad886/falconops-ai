"""
FalconOps AI - Multi-Agent Orchestration Engine
Supports: Emergent LLM Key (cloud) | OpenAI API Key (on-premise) | Heuristic fallback (offline)

Features:
  - RCA Agent, Alert Summarizer, Auto-Healing Agent
  - Agent Memory: learns from past incidents via similarity search
  - Auto-trigger pipeline: detection rules fire → agents analyze automatically
"""
import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from difflib import SequenceMatcher

from ..core.database import db

logger = logging.getLogger(__name__)


# ======================== LLM PROVIDER ABSTRACTION ========================

class LLMProvider:
    """Dual-mode LLM: Emergent key (cloud) or OpenAI key (on-premise) or fallback"""

    def __init__(self):
        self.mode = "fallback"
        self._emergent_chat = None
        self._openai_client = None
        self._detect_mode()

    def _detect_mode(self):
        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        openai_key = os.environ.get("OPENAI_API_KEY", "")

        if emergent_key:
            self.mode = "emergent"
            logger.info("AI Agents: Using Emergent LLM Key")
        elif openai_key:
            self.mode = "openai"
            logger.info("AI Agents: Using OpenAI API Key (on-premise)")
        else:
            self.mode = "fallback"
            logger.info("AI Agents: No LLM key found, using heuristic fallback")

    async def generate(self, system_prompt: str, user_prompt: str, session_id: str = None) -> str:
        # Security fix: this LLM path previously never went through
        # llm_provider_service.chat_completion() and so never got its pre-flight
        # prompt-injection screen — a real gap, since run_agent()/run_crew() (the
        # callers of generate()) are reachable from UNAUTHENTICATED SOC event
        # ingestion (POST /api/soc-engine/ingest -> correlation ->
        # trigger_from_rule() -> run_crew()). Reuses the exact same regex
        # ai_monitoring_service/llm_provider_service already screen with, rather
        # than maintaining a second denylist.
        if os.environ.get("LLM_PREFLIGHT_INJECTION_BLOCK", "true").lower() not in ("false", "0", "no"):
            try:
                from .ai_monitoring_service import INJECTION_REGEX
                if user_prompt and INJECTION_REGEX.search(user_prompt):
                    logger.warning(
                        "ai_agents_service.LLMProvider.generate: blocked a prompt-injection "
                        "pattern match (session=%s)", session_id,
                    )
                    return (
                        "I can't process that request — it matches a known prompt-injection "
                        "pattern. If this was unintentional, please rephrase without phrases "
                        "like 'ignore previous instructions' or attempts to reveal the system prompt."
                    )
            except Exception as e:
                logger.debug("ai_agents_service pre-flight guard skipped: %s", e)

        if self.mode == "emergent":
            return await self._call_emergent(system_prompt, user_prompt, session_id)
        elif self.mode == "openai":
            return await self._call_openai(system_prompt, user_prompt)
        else:
            return self._heuristic_fallback(user_prompt)

    async def _call_emergent(self, system_prompt: str, user_prompt: str, session_id: str = None) -> str:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            key = os.environ.get("EMERGENT_LLM_KEY", "")
            sid = session_id or str(uuid.uuid4())
            chat = LlmChat(api_key=key, session_id=sid, system_message=system_prompt)
            chat.with_model("openai", "gpt-4o-mini")
            msg = UserMessage(text=user_prompt)
            response = await chat.send_message(msg)
            return response
        except Exception as e:
            logger.error(f"Emergent LLM error: {e}")
            return self._heuristic_fallback(user_prompt)

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return self._heuristic_fallback(user_prompt)

    def _heuristic_fallback(self, prompt: str) -> str:
        """Deterministic fallback when no LLM is available"""
        lower = prompt.lower()
        if "root cause" in lower or "rca" in lower:
            return "Heuristic RCA: Check network connectivity, DNS resolution, upstream service health, and recent deployments. Monitor resource utilization (CPU/memory/disk) for anomalies."
        if "summar" in lower:
            return "Heuristic Summary: Multiple related alerts detected. Investigate the primary failing service and its dependencies for cascading failures."
        if "heal" in lower or "remedia" in lower:
            return "Heuristic Remediation: 1) Restart affected service 2) Scale up resources if under load 3) Rollback recent deployment if correlated 4) Enable circuit breaker for upstream dependencies."
        return "Analysis complete. Review the alert details and check related services for issues."

    def get_mode_info(self) -> Dict:
        return {
            "mode": self.mode,
            "description": {
                "emergent": "Emergent Universal Key (cloud-managed)",
                "openai": "OpenAI API Key (on-premise/self-hosted)",
                "fallback": "Heuristic analysis (no LLM key configured)",
            }.get(self.mode, "unknown"),
        }


# Singleton
_llm = None


def get_llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = LLMProvider()
    return _llm


# ======================== AGENT DEFINITIONS ========================

AGENTS = {
    "rca": {
        "name": "RCA Agent",
        "role": "Site Reliability Engineer",
        "system_prompt": """You are an expert Site Reliability Engineer specialized in root cause analysis for distributed systems. When given alert/incident data:
1. Identify the most likely root cause
2. Assess severity (critical/high/medium/low)
3. List contributing factors
4. Provide a clear suggested fix
5. Estimate blast radius (affected services)
Keep responses concise and actionable. Use bullet points.""",
    },
    "summarizer": {
        "name": "Alert Summarizer",
        "role": "Incident Manager",
        "system_prompt": """You are an expert Incident Manager specialized in alert correlation and noise reduction. When given alert data:
1. Group related alerts by root cause
2. Provide a 2-3 sentence executive summary
3. Identify the primary affected service
4. Rate urgency (immediate/soon/monitor)
5. List recommended actions in priority order
Be concise and clear for NOC operators.""",
    },
    "healer": {
        "name": "Auto-Healing Agent",
        "role": "DevOps Automation Engineer",
        "system_prompt": """You are an expert DevOps Automation Engineer specialized in self-healing systems. When given incident data:
1. Suggest specific remediation steps (ordered)
2. Identify which steps can be automated safely
3. Flag any steps requiring human approval
4. Suggest preventive measures
5. Recommend monitoring changes to prevent recurrence
Be specific with commands/actions when possible.""",
    },
}


# ======================== AGENT EXECUTION ========================

async def run_agent(agent_id: str, data: Dict, session_id: str = None, use_memory: bool = True) -> Dict:
    """Run a single AI agent, optionally enriched with memory context"""
    agent = AGENTS.get(agent_id)
    if not agent:
        return {"error": f"Unknown agent: {agent_id}"}

    llm = get_llm()
    base_prompt = f"Analyze the following data and provide your expert assessment:\n\n{_format_data(data)}"

    # Inject memory context if available
    memory_context = ""
    similar_incidents = []
    if use_memory:
        similar_incidents = await recall_similar(data, agent_id, limit=3)
        if similar_incidents:
            memory_context = "\n\n--- RELEVANT PAST INCIDENTS (from memory) ---\n"
            for si in similar_incidents:
                memory_context += f"\n[Past incident - similarity {si['similarity']}%]\n"
                memory_context += f"Input: {si.get('input_summary', '')}\n"
                memory_context += f"Analysis: {si.get('analysis_summary', '')}\n"
            memory_context += "\n--- Use these past incidents to improve your analysis. Note patterns and recurring issues. ---\n"

        # Real outcome memory: not just what was said before, but whether the action
        # taken actually worked. This is what closes the "continuously learn from
        # previous incidents" loop — recall_similar() above only recalls past
        # narratives, this recalls verified effectiveness.
        similar_outcomes = await recall_similar_outcomes(data, limit=3)
        if similar_outcomes:
            memory_context += "\n\n--- PAST OUTCOMES (verified effectiveness) ---\n"
            for so in similar_outcomes:
                status = ("WORKED" if so["was_effective"] is True
                          else "DID NOT WORK" if so["was_effective"] is False
                          else "outcome unknown")
                mttr_note = f", resolved in {int(so['mttr_seconds'])}s" if so.get("mttr_seconds") else ""
                memory_context += f"\n[similarity {so['similarity']}%] Action: {so.get('action_taken') or 'n/a'} -> {status}{mttr_note}"
            memory_context += "\n--- Prefer actions that worked before for similar incidents; avoid ones that didn't. ---\n"

    prompt = base_prompt + memory_context
    sid = session_id or f"agent-{agent_id}-{uuid.uuid4().hex[:8]}"

    start = asyncio.get_event_loop().time()
    response = await llm.generate(agent["system_prompt"], prompt, sid)
    duration = round((asyncio.get_event_loop().time() - start) * 1000, 1)

    result = {
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "agent_role": agent["role"],
        "analysis": response,
        "llm_mode": llm.get_mode_info()["mode"],
        "duration_ms": duration,
        "memory_used": len(similar_incidents),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Store analysis + memory embedding
    doc = {
        **result,
        "input_data": str(data)[:2000],
        "input_fingerprint": _fingerprint(data),
        "session_id": sid,
    }
    await db.ai_analyses.insert_one(doc)

    return result


async def run_crew(data: Dict, agents: List[str] = None, parallel: bool = False) -> Dict:
    """Run multiple agents (crew) on the same data"""
    agent_ids = agents or ["rca", "summarizer", "healer"]
    session_id = f"crew-{uuid.uuid4().hex[:8]}"

    start = asyncio.get_event_loop().time()

    if parallel:
        tasks = [run_agent(aid, data, session_id) for aid in agent_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        results = [r if isinstance(r, dict) else {"error": str(r)} for r in results]
    else:
        results = []
        for aid in agent_ids:
            r = await run_agent(aid, data, session_id)
            results.append(r)

    duration = round((asyncio.get_event_loop().time() - start) * 1000, 1)

    llm = get_llm()
    crew_result = {
        "crew_id": session_id,
        "agents_run": agent_ids,
        "results": results,
        "total_duration_ms": duration,
        "llm_mode": llm.get_mode_info(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return crew_result


async def get_analysis_history(limit: int = 20) -> List[Dict]:
    return await db.ai_analyses.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


async def get_agent_stats() -> Dict:
    total = await db.ai_analyses.count_documents({})
    by_agent = []
    for aid in AGENTS:
        count = await db.ai_analyses.count_documents({"agent_id": aid})
        by_agent.append({"agent_id": aid, "name": AGENTS[aid]["name"], "count": count})

    llm = get_llm()
    return {
        "total_analyses": total,
        "by_agent": by_agent,
        "llm_mode": llm.get_mode_info(),
        "available_agents": [{"id": k, "name": v["name"], "role": v["role"]} for k, v in AGENTS.items()],
    }


def _format_data(data: Dict) -> str:
    """Format input data for LLM prompt"""
    lines = []
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v[:10]:
                lines.append(f"  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _fingerprint(data: Dict) -> str:
    """Create a text fingerprint of input data for similarity matching"""
    parts = []
    for k, v in sorted(data.items()):
        parts.append(f"{k}={v}")
    return " ".join(parts).lower()[:500]


# ======================== AGENT MEMORY ========================

async def recall_similar(data: Dict, agent_id: str = None, limit: int = 3, min_similarity: float = 0.3) -> List[Dict]:
    """Find similar past incidents from agent memory using text similarity"""
    fp = _fingerprint(data)
    query = {"input_fingerprint": {"$exists": True}}
    if agent_id:
        query["agent_id"] = agent_id

    past = await db.ai_analyses.find(query, {"_id": 0}).sort("timestamp", -1).limit(200).to_list(200)
    scored = []
    for p in past:
        past_fp = p.get("input_fingerprint", "")
        if not past_fp:
            continue
        sim = SequenceMatcher(None, fp, past_fp).ratio()
        if sim >= min_similarity:
            scored.append({
                "id": p.get("session_id", ""),
                "agent_id": p.get("agent_id", ""),
                "agent_name": p.get("agent_name", ""),
                "similarity": round(sim * 100, 1),
                "input_summary": p.get("input_data", "")[:200],
                "analysis_summary": (str(p.get("analysis", ""))[:200] if p.get("analysis") else ""),
                "timestamp": p.get("timestamp", ""),
            })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:limit]


async def recall_similar_outcomes(data: Dict, limit: int = 3, min_similarity: float = 0.3) -> List[Dict]:
    """Find past incident OUTCOMES (not just past analyses) similar to this one — i.e.
    'last time this happened, was the action taken actually effective'. Written by
    autonomous_ops_orchestrator.record_outcome() into db.incident_outcomes using the
    same fingerprint scheme as recall_similar() above, so they stay comparable."""
    fp = _fingerprint(data)
    past = await db.incident_outcomes.find(
        {"fingerprint": {"$exists": True, "$ne": ""}}, {"_id": 0}
    ).sort("recorded_at", -1).limit(200).to_list(200)

    scored = []
    for p in past:
        past_fp = p.get("fingerprint", "")
        if not past_fp:
            continue
        sim = SequenceMatcher(None, fp, past_fp).ratio()
        if sim >= min_similarity:
            scored.append({
                "incident_id": p.get("incident_id"),
                "similarity": round(sim * 100, 1),
                "action_taken": p.get("action_taken"),
                "was_effective": p.get("was_effective"),
                "mttr_seconds": p.get("mttr_seconds"),
                "recorded_at": p.get("recorded_at"),
            })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:limit]


async def get_memory_stats() -> Dict:
    """Get memory statistics"""
    total = await db.ai_analyses.count_documents({"input_fingerprint": {"$exists": True}})
    unique_fps = await db.ai_analyses.distinct("input_fingerprint")
    by_agent = {}
    for aid in AGENTS:
        c = await db.ai_analyses.count_documents({"agent_id": aid, "input_fingerprint": {"$exists": True}})
        by_agent[aid] = c
    return {
        "total_memories": total,
        "unique_patterns": len(unique_fps),
        "by_agent": by_agent,
    }


async def clear_memory(agent_id: str = None, older_than_days: int = None) -> Dict:
    """Clear agent memory (admin only)"""
    query = {}
    if agent_id:
        query["agent_id"] = agent_id
    if older_than_days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        query["timestamp"] = {"$lt": cutoff}
    r = await db.ai_analyses.delete_many(query)
    return {"deleted": r.deleted_count}


# ======================== AUTO-TRIGGER PIPELINE ========================

_pipeline_enabled = True
_pipeline_cooldowns = {}  # rule_id -> last_trigger_time


async def set_pipeline_enabled(enabled: bool):
    global _pipeline_enabled
    _pipeline_enabled = enabled
    await db.ai_pipeline_config.update_one(
        {"key": "enabled"}, {"$set": {"value": enabled}}, upsert=True
    )


async def get_pipeline_config() -> Dict:
    global _pipeline_enabled
    doc = await db.ai_pipeline_config.find_one({"key": "enabled"}, {"_id": 0})
    if doc:
        _pipeline_enabled = doc.get("value", True)
    return {
        "enabled": _pipeline_enabled,
        "cooldown_seconds": 60,
        "agents": ["rca", "summarizer"],
        "description": "Auto-triggers AI agents when detection rules fire",
    }


async def trigger_from_rule(rule: Dict, event_data: Dict) -> Optional[Dict]:
    """Called when a detection rule fires — triggers AI agents automatically"""
    global _pipeline_enabled, _pipeline_cooldowns

    if not _pipeline_enabled:
        return None

    rule_id = rule.get("rule_id", "")
    now = asyncio.get_event_loop().time()
    cooldown = rule.get("cooldown_min", 5) * 60
    last = _pipeline_cooldowns.get(rule_id, 0)

    if now - last < max(cooldown, 60):
        logger.debug(f"Pipeline cooldown active for rule {rule_id}")
        return None

    _pipeline_cooldowns[rule_id] = now

    trigger_data = {
        "trigger": "auto_detection",
        "rule_id": rule_id,
        "rule_name": rule.get("name", ""),
        "severity": rule.get("severity", "warning"),
        "metric": rule.get("metric", ""),
        "threshold": rule.get("threshold", ""),
        **event_data,
    }

    logger.info(f"AI Pipeline triggered by rule: {rule.get('name', rule_id)}")

    # Run RCA + Summarizer agents (healer is opt-in for safety)
    try:
        result = await run_crew(trigger_data, agents=["rca", "summarizer"], parallel=True)

        # Store pipeline event
        await db.ai_pipeline_events.insert_one({
            "id": str(uuid.uuid4()),
            "rule_id": rule_id,
            "rule_name": rule.get("name", ""),
            "severity": rule.get("severity", ""),
            "trigger_data": str(trigger_data)[:2000],
            "crew_result": {
                "crew_id": result.get("crew_id"),
                "agents_run": result.get("agents_run"),
                "total_duration_ms": result.get("total_duration_ms"),
                "results_summary": [
                    {"agent": r.get("agent_name", ""), "preview": str(r.get("analysis", ""))[:200]}
                    for r in result.get("results", [])
                ],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return result
    except Exception as e:
        logger.error(f"AI Pipeline error: {e}")
        return None


async def get_pipeline_events(limit: int = 30) -> List[Dict]:
    """Get auto-trigger pipeline event history"""
    return await db.ai_pipeline_events.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


async def get_pipeline_stats() -> Dict:
    total = await db.ai_pipeline_events.count_documents({})
    last_24h = await db.ai_pipeline_events.count_documents({
        "timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()}
    })
    by_rule = await db.ai_pipeline_events.aggregate([
        {"$group": {"_id": "$rule_id", "count": {"$sum": 1}, "rule_name": {"$first": "$rule_name"}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]).to_list(10)

    return {
        "total_triggers": total,
        "triggers_24h": last_24h,
        "by_rule": [{"rule_id": r["_id"], "rule_name": r.get("rule_name", ""), "count": r["count"]} for r in by_rule],
    }

