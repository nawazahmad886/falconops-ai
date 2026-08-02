"""
Prompt construction for RCAAgent. Two distinct prompts by design: the
initial pass only ever sees tier=="trigger" evidence (what's knowable from
the alert payload alone), the revision pass sees everything. The model is
never told what to conclude — the evidence set handed to it is what changes
between the two calls, and the JSON contract forces every hypothesis to cite
the specific evidence_ids it rests on.
"""
from typing import List

from ....models.rased_schemas import Evidence

_JSON_INSTRUCTIONS = (
    "Respond with a JSON array of hypothesis objects only, no prose outside "
    "the JSON, no markdown code fences. Each object: "
    '{"statement": str, "root_cause_entity": str or null, "evidence_ids": '
    '[str, ...]}. evidence_ids MUST be a subset of the evidence_id values '
    "given to you below and MUST be non-empty — every hypothesis must cite "
    "at least one piece of evidence it is based on. Do not invent an "
    "evidence_id that was not given to you."
)


def _format_evidence(evidence: List[Evidence]) -> str:
    return "\n".join(
        f"- [{item.evidence_id}] ({item.source}, {item.tier}-tier) {item.summary}"
        for item in evidence
    )


def build_initial_hypothesis_prompt(evidence: List[Evidence]) -> List[dict]:
    system = (
        "You are RASED's root-cause hypothesis generator, forming an initial "
        "hypothesis before any deep investigation has happened. You only have "
        "what is knowable from the alert itself. Propose 1-3 plausible root "
        "causes, ranked most-likely first, based only on the evidence given. "
        + _JSON_INSTRUCTIONS
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Evidence available so far:\n{_format_evidence(evidence)}"},
    ]


def build_revision_prompt(evidence: List[Evidence], prior_hypotheses: List[dict]) -> List[dict]:
    system = (
        "You are RASED's root-cause hypothesis generator. A deeper "
        "investigation has now retrieved more evidence. Re-evaluate your "
        "earlier hypotheses against the FULL evidence set below — if the new "
        "evidence changes the most likely root cause, say so and cite the "
        "evidence that changed your mind; if it confirms the earlier "
        "hypothesis instead, say that. Do not revise for the sake of "
        "revising. " + _JSON_INSTRUCTIONS
    )
    prior_text = "\n".join(f"- {h.get('statement')}" for h in prior_hypotheses) or "(none)"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": (
            f"Earlier hypotheses, based on limited evidence:\n{prior_text}\n\n"
            f"Full evidence now available:\n{_format_evidence(evidence)}"
        )},
    ]


__all__ = ["build_initial_hypothesis_prompt", "build_revision_prompt"]
