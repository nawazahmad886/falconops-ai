"""
RASED's single LLM entry point. Every agent that needs an LLM call
(ImpactAgent, RCAAgent, PolicyAgent, ActionAgent) goes through this wrapper
instead of calling llm_provider_service.chat_completion() directly, so
demo-mode replay is one switch instead of four call sites kept in sync by
hand.

When config.DEMO_MODE is set (RASED_DEMO_MODE=1), calls never reach a real
provider — they return a cached response after a small fixed delay for
pacing, keyed by the "rased-<agent>" session_id prefix each agent already
passes. This exists so a slow or rate-limited model never ruins a live demo
run: the trace panel still paces visibly (Phase 5's "deliberate pacing"
requirement), it just paces against a constant instead of real network/
inference latency.

The RCA cache is not a single static string — a canned hypothesis with
scenario-specific evidence_ids baked in would be wrong for four of the five
scenarios. Instead it parses the actual prompt for every "[evidence_id]"
token the agent was shown and cites all of them, which is scenario-agnostic
by construction and always passes RCAAgent's own citation-validation gate.
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .config import DEMO_MODE

logger = logging.getLogger(__name__)

DEMO_MODE_DELAY_SECONDS = 0.4

_EVIDENCE_ID_RE = re.compile(r"\[([A-Za-z0-9\-]+)\]")


def _demo_rca_response(messages: List[Dict[str, Any]]) -> str:
    prompt_text = " ".join(str(m.get("content", "")) for m in messages)
    evidence_ids = _EVIDENCE_ID_RE.findall(prompt_text)
    if not evidence_ids:
        return json.dumps([])
    return json.dumps([{
        "statement": "Demo-mode cached hypothesis, citing every evidence item shown for this pass.",
        "root_cause_entity": None,
        "evidence_ids": evidence_ids,
    }])


_STATIC_CACHE: Dict[str, str] = {
    "rased-impact": "The affected service is degraded, putting a meaningful share of current transaction volume at risk.",
    "rased-policy": "Severity was classified per the cited SOP section.",
    "rased-action": "none",
}


def _cached_response(session_id: Optional[str], messages: List[Dict[str, Any]]) -> str:
    if session_id == "rased-rca":
        return _demo_rca_response(messages)
    return _STATIC_CACHE.get(session_id or "", "")


async def rased_chat_completion(messages: List[Dict[str, Any]], session_id: Optional[str] = None) -> Dict[str, Any]:
    if DEMO_MODE:
        await asyncio.sleep(DEMO_MODE_DELAY_SECONDS)
        return {
            "provider": "demo_mode_cache",
            "model": "cached",
            "response": _cached_response(session_id, messages),
            "fallback_used": True,
        }

    from ..llm_provider_service import chat_completion
    return await chat_completion(messages, session_id=session_id)


__all__ = ["rased_chat_completion", "DEMO_MODE_DELAY_SECONDS"]
