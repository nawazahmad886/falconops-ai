"""
PolicyAgent — severity/escalation/approval-requirement decisioning against
the SOP corpus.

Severity tier, approval requirement, and maintenance-window status are
DECIDED IN CODE from business_impact and a maintenance-window lookup — the
same "compute it, don't ask an LLM to invent it" stance Phase 2's RCA
confidence formula takes, for the same reason: a severity misclassification
is something a human will ask "why" about, and a citable rule answers that;
an LLM's freeform severity guess does not. The retriever finds the SOP
section that rule maps to, and the LLM only writes the one-line plain-
language justification — the same division of labor ImpactAgent uses for
its executive sentence.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ....models.rased_schemas import InvestigationState, PolicyCitation, PolicyDecision
from ..policy import SOPSection, get_retriever
from ..redaction import sanitize_for_llm

logger = logging.getLogger(__name__)

# Synthetic weekly maintenance windows: service -> (weekday, start_hour, end_hour), UTC.
# weekday: 0=Monday .. 6=Sunday. A real deployment would source this from a
# change-calendar system; this is a fixed table for demo determinism.
MAINTENANCE_WINDOWS: Dict[str, Tuple[int, int, int]] = {
    "reporting-svc": (6, 2, 4),  # Sunday 02:00-04:00 UTC
}

SEVERITY_QUERY_MAP = {
    "P1": "critical severity major business impact escalation immediate incident commander",
    "P2": "significant impact escalation shift lead guarded action",
    "P3": "moderate impact standard response ticketing service owner",
    "P4": "low priority monitoring log only maintenance window suppression",
}

ESCALATION_TARGETS = {
    "P1": "on-call-incident-commander",
    "P2": "noc-shift-lead",
    "P3": "service-owner-oncall",
    "P4": "automated-ticket-only",
}

NOTIFICATION_TEMPLATES = {
    "P1": "P1_MAJOR_INCIDENT",
    "P2": "P2_SIGNIFICANT_IMPACT",
    "P3": "P3_STANDARD_NOTICE",
    "P4": "P4_LOW_PRIORITY_LOG",
}


def is_in_maintenance_window(service: str, at: datetime) -> bool:
    window = MAINTENANCE_WINDOWS.get(service)
    if not window:
        return False
    weekday, start_hour, end_hour = window
    return at.weekday() == weekday and start_hour <= at.hour < end_hour


class PolicyAgent:
    def __init__(self, retriever=None):
        self._retriever = retriever

    async def run(self, state: InvestigationState) -> dict:
        if not state.alerts:
            return {}

        service = state.alerts[0].service
        observed_at = state.alerts[0].observed_at
        maintenance_active = is_in_maintenance_window(service, observed_at)

        severity_tier = self._decide_severity(state, maintenance_active)
        approval_required = severity_tier in ("P1", "P2") and not maintenance_active

        retriever = self._retriever or get_retriever()
        matches: List[SOPSection] = retriever.search(SEVERITY_QUERY_MAP[severity_tier], top_k=1)
        citations = [PolicyCitation(document_id=m.document_id, section=m.section_id) for m in matches]

        justification = await self._write_justification(severity_tier, maintenance_active, matches)

        decision = PolicyDecision(
            incident_id=state.incident_id,
            severity_tier=severity_tier,
            escalation_target=ESCALATION_TARGETS[severity_tier],
            notification_template=NOTIFICATION_TEMPLATES[severity_tier],
            approval_required=approval_required,
            maintenance_window_active=maintenance_active,
            citations=citations,
            justification=justification,
            decided_at=datetime.now(timezone.utc),
        )
        return {"policy_decision": decision}

    @staticmethod
    def _decide_severity(state: InvestigationState, maintenance_active: bool) -> str:
        if maintenance_active:
            return "P4"
        impact = state.business_impact
        if impact is None:
            return "P3"
        if impact.transactions_at_risk >= 10000 or (impact.revenue_at_risk or 0) >= 100000:
            return "P1"
        if impact.transactions_at_risk >= 2000:
            return "P2"
        if impact.transactions_at_risk >= 200:
            return "P3"
        return "P4"

    async def _write_justification(self, severity_tier: str, maintenance_active: bool, matches: List[SOPSection]) -> str:
        citation_text = ", ".join(f"{m.document_id} {m.section_id} ({m.title})" for m in matches) or "no matching SOP section found"
        fallback = f"Classified as {severity_tier} per {citation_text}."

        facts = (
            f"Severity tier decided: {severity_tier}\n"
            f"Maintenance window active: {maintenance_active}\n"
            f"Cited SOP section(s): {citation_text}\n"
        )
        messages = sanitize_for_llm([
            {"role": "system", "content": (
                "You are RASED's policy writer. Given an already-decided severity "
                "tier and the SOP section it maps to, write exactly one plain-"
                "language sentence justifying the escalation decision, referencing "
                "the citation. Do not change the severity tier or invent a "
                "different one."
            )},
            {"role": "user", "content": facts},
        ])
        try:
            from ..llm import rased_chat_completion
            result = await rased_chat_completion(messages, session_id="rased-policy")
            text = (result or {}).get("response", "").strip()
            if text:
                return text
        except Exception as exc:
            logger.warning(f"rased policy justification LLM call failed, using fallback: {exc}")

        return fallback


__all__ = ["PolicyAgent", "is_in_maintenance_window", "MAINTENANCE_WINDOWS"]
