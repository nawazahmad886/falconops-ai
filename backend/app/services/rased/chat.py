"""
Incident-scoped operational AI chat — "Ask about this incident."

Distinct from ai_copilot_chat_service.py on purpose: that service is scoped
to uptime-monitor CRUD proposals and has no data grounding or anti-
hallucination instruction in its system prompt (confirmed by reading it while
planning this feature) — retrofitting a general-purpose chat service used
elsewhere for unrelated things was judged riskier than a small, new,
correctly-scoped endpoint. This module answers questions about EXACTLY one
incident, grounded ONLY in that incident's own RASED investigation record
(evidence, hypotheses, actions, verification, trace) — the same honesty
convention intelligence_agents_service.py already applies to its evidence-
grounded prompts ("never invent data not present in the tool result(s), if
the tools returned nothing, say so plainly").

Every prompt sent to the LLM passes through RASED's sanitize_for_llm()
redaction boundary first, same as every other RASED LLM call — the incident
context assembled here is built from the same evidence/trace data that
boundary already exists to protect.
"""
import logging
from typing import Any, Dict, List, Optional

from .redaction import sanitize_for_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the FalconOps AI Incident Commander's operational assistant for ONE
specific incident. Answer the operator's question using ONLY the incident context provided below
(alerts, evidence, hypotheses, actions taken, verification results, trace log).

Rules:
- Never invent monitoring data, metrics, or evidence not present in the context below.
- If the context does not contain enough information to answer, say exactly: "Insufficient evidence."
  Do not guess or extrapolate beyond what's shown.
- When you do answer, cite which part of the context supports it (e.g. "per the RCA hypothesis" or
  "per the verification result").
- Be concise — operators are reading this during an active incident, not after."""


def _format_incident_context(investigation: Dict[str, Any]) -> str:
    lines: List[str] = [f"Incident ID: {investigation.get('incident_id')}",
                         f"Status: {investigation.get('status')}",
                         f"Confidence: {investigation.get('confidence')}"]

    alerts = investigation.get("alerts") or []
    if alerts:
        lines.append("\nAlerts:")
        for a in alerts[:10]:
            lines.append(f"- [{a.get('severity')}] {a.get('service')}: {a.get('title')} — {a.get('description')}")

    evidence = investigation.get("evidence") or []
    if evidence:
        lines.append("\nEvidence:")
        for e in evidence[:20]:
            lines.append(f"- ({e.get('tier')}, {e.get('source')}) {e.get('summary')}")

    hypotheses = investigation.get("hypotheses") or []
    if hypotheses:
        lines.append("\nHypotheses:")
        for h in hypotheses:
            status = "SUPERSEDED" if h.get("superseded") else "CURRENT"
            lines.append(f"- [{status}, confidence={h.get('confidence')}] {h.get('statement')}"
                         + (f" (revised: {h.get('revision_reason')})" if h.get("revision_reason") else ""))

    actions = investigation.get("actions") or []
    if actions:
        lines.append("\nActions:")
        for a in actions:
            lines.append(f"- {a.get('name')} ({a.get('spec', {}).get('tier')}) — status: {a.get('status')}")

    verification = investigation.get("verification")
    if verification:
        if verification.get("available"):
            lines.append(f"\nVerification: recovered={verification.get('recovered')}")
            for m in verification.get("metrics") or []:
                lines.append(f"  - {m.get('metric')} ({m.get('service')}): {m.get('before')}{m.get('unit')} -> "
                             f"{m.get('after')}{m.get('unit')} ({m.get('improved_pct')}%)")
        else:
            lines.append(f"\nVerification: not available ({verification.get('reason')})")

    policy = investigation.get("policy_decision")
    if policy:
        lines.append(f"\nPolicy: severity_tier={policy.get('severity_tier')}, "
                     f"escalation_target={policy.get('escalation_target')}, "
                     f"justification={policy.get('justification')}")

    return "\n".join(lines)


async def ask_about_incident(incident_id: str, question: str) -> Dict[str, Any]:
    """Returns {answer, insufficient_evidence, incident_id}. Never raises for
    a missing incident — returns insufficient_evidence=True with a clear
    reason instead, consistent with this module's core rule."""
    from ...core.database import db

    investigation = await db.rased_investigations.find_one({"incident_id": incident_id}, {"_id": 0})
    if investigation is None:
        return {
            "incident_id": incident_id, "answer": "Insufficient evidence.",
            "insufficient_evidence": True, "reason": "unknown incident_id",
        }

    context = _format_incident_context(investigation)
    messages = sanitize_for_llm([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Incident context:\n{context}\n\nQuestion: {question}"},
    ])

    try:
        from ..llm_provider_service import chat_completion
        result = await chat_completion(messages, session_id=f"incident-commander-{incident_id}")
        answer = (result.get("response") or "").strip() or "Insufficient evidence."
    except Exception as exc:
        logger.warning(f"incident chat LLM call failed for {incident_id}: {exc}")
        answer = "Insufficient evidence — the AI assistant is temporarily unavailable."

    return {
        "incident_id": incident_id, "answer": answer,
        "insufficient_evidence": answer.strip().lower().startswith("insufficient evidence"),
    }


__all__ = ["ask_about_incident"]
