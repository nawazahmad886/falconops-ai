"""
Prompt construction for ImpactAgent's one-sentence executive impact summary.
The LLM only writes this sentence — every number in it was computed in
Python (catalogue walk + diurnal curve) and handed to the prompt as already-
final facts, not something the model is asked to calculate.
"""
from typing import List, Optional


def build_impact_prompt(
    affected_service: str,
    business_capability: str,
    transactions_at_risk: int,
    revenue_at_risk: Optional[float],
) -> List[dict]:
    facts = (
        f"Affected service: {affected_service}\n"
        f"Business capability: {business_capability}\n"
        f"Estimated transactions at risk in the current window: {transactions_at_risk}\n"
    )
    if revenue_at_risk is not None:
        facts += f"Estimated revenue at risk: ${revenue_at_risk:,.2f}\n"

    system = (
        "You are RASED's business-impact writer. You are given already-computed "
        "facts — do not invent or recompute any number, and do not add facts "
        "that were not given to you. Write exactly one plain sentence an "
        "executive can read in three seconds, stating what is affected and "
        "the scale of impact. No hedging, no bullet points, no markdown."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": facts},
    ]


__all__ = ["build_impact_prompt"]
