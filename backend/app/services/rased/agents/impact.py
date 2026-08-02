"""
ImpactAgent — walks the service catalogue from the affected service to its
business capability, computes transactions-at-risk off the diurnal traffic
curve, and asks the LLM to write exactly one sentence describing that
impact. All arithmetic happens here in Python; the prompt hands the model
already-final numbers rather than asking it to compute or invent any of
them. If the LLM call fails or returns nothing usable, a deterministic
template sentence built from the same numbers is used instead — impact
reporting never silently disappears because a provider was unreachable.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from ....models.rased_schemas import BusinessImpact, InvestigationState
from ..data.scenarios import SERVICE_CATALOG, diurnal_multiplier
from ..prompts.impact import build_impact_prompt
from ..redaction import sanitize_for_llm

logger = logging.getLogger(__name__)

# Synthetic, generic average-order-value stand-in — not a real business figure.
SYNTHETIC_REVENUE_PER_TX = 42.50
IMPACT_WINDOW_MINUTES = 5


class ImpactAgent:
    async def run(self, state: InvestigationState) -> dict:
        if not state.alerts:
            return {}

        affected_service = state.alerts[0].service
        catalog_entry = SERVICE_CATALOG.get(affected_service, {})
        business_capability = catalog_entry.get("business_capability", "Unclassified")
        baseline_tpm = catalog_entry.get("baseline_tpm", 0)

        observed_at = state.alerts[0].observed_at
        transactions_at_risk = round(baseline_tpm * diurnal_multiplier(observed_at.hour) * IMPACT_WINDOW_MINUTES)
        revenue_at_risk = round(transactions_at_risk * SYNTHETIC_REVENUE_PER_TX, 2) if transactions_at_risk else None

        summary = await self._write_summary(affected_service, business_capability, transactions_at_risk, revenue_at_risk)

        impact = BusinessImpact(
            incident_id=state.incident_id,
            affected_service=affected_service,
            business_capability=business_capability,
            transactions_at_risk=transactions_at_risk,
            revenue_at_risk=revenue_at_risk,
            summary=summary,
            computed_at=datetime.now(timezone.utc),
        )
        return {"business_impact": impact}

    async def _write_summary(
        self,
        affected_service: str,
        business_capability: str,
        transactions_at_risk: int,
        revenue_at_risk: Optional[float],
    ) -> str:
        messages = sanitize_for_llm(
            build_impact_prompt(affected_service, business_capability, transactions_at_risk, revenue_at_risk)
        )
        try:
            from ..llm import rased_chat_completion
            result = await rased_chat_completion(messages, session_id="rased-impact")
            text = (result or {}).get("response", "").strip()
            if text:
                return text
        except Exception as exc:
            logger.warning(f"rased impact summary LLM call failed, using fallback sentence: {exc}")

        return self._fallback_sentence(affected_service, business_capability, transactions_at_risk, revenue_at_risk)

    @staticmethod
    def _fallback_sentence(
        affected_service: str, business_capability: str, transactions_at_risk: int, revenue_at_risk: Optional[float],
    ) -> str:
        revenue_clause = f", an estimated ${revenue_at_risk:,.0f} in revenue," if revenue_at_risk else ""
        return (
            f"{affected_service} is degraded, putting an estimated {transactions_at_risk} "
            f"{business_capability} transactions{revenue_clause} at risk in the current window."
        )


__all__ = ["ImpactAgent", "SYNTHETIC_REVENUE_PER_TX", "IMPACT_WINDOW_MINUTES"]
