"""
RCAAgent — two-pass root-cause hypothesis generation with genuine revision.

initial_hypothesis() only sees tier=="trigger" evidence. revise_hypotheses()
sees the full set. Both are persisted onto InvestigationState.hypotheses —
the revision never silently overwrites the initial pass: prior hypotheses
are marked superseded=True and kept, and each revised hypothesis records
changed_because (the evidence_ids that weren't visible to the initial pass)
plus a one-line revision_reason, so the UI can render "was X, now Y, because
Z" without extra bookkeeping downstream.

Confidence is computed in Python from a hypothesis's own citations, never
asked of the LLM: evidence_coverage x source_agreement x contradiction_factor.
A model can be asked to explain its reasoning; it cannot be asked for a
trustworthy self-assessed probability, so this agent never requests one.

A Hypothesis with no evidence_ids is rejected and regenerated once, then
dropped — enforced in code against the parsed JSON, not left to the prompt
instruction alone, so a model that ignores the citation requirement can
never reach the UI uncited.

Operational note: this agent's usefulness depends on a real LLM provider
(ollama/openai/anthropic/gemini) being configured behind
llm_provider_service.chat_completion(). Its documented rule_based fallback
is a generic templated responder, not tuned to return the JSON hypothesis
array this module parses — if that's the only provider active, expect
_parse_and_validate() to find no JSON and hypotheses to come back empty
after the one retry. That degrades safely (no hypotheses, not a crash) but
is worth knowing before wondering why RCA produced nothing.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from ....models.rased_schemas import Evidence, Hypothesis, InvestigationState
from ..prompts.rca import build_initial_hypothesis_prompt, build_revision_prompt
from ..redaction import sanitize_for_llm

logger = logging.getLogger(__name__)


class RCAAgent:
    async def run(self, state: InvestigationState) -> dict:
        trigger_evidence = [e for e in state.evidence if e.tier == "trigger"]
        deep_evidence = [e for e in state.evidence if e.tier == "deep"]

        if not trigger_evidence and not deep_evidence:
            return {}

        initial = await self._generate(
            state.incident_id, "initial",
            build_initial_hypothesis_prompt(trigger_evidence),
            considered_evidence=trigger_evidence,
        )

        hypotheses = list(initial)

        if deep_evidence:
            revised = await self._generate(
                state.incident_id, "revised",
                build_revision_prompt(state.evidence, [h.model_dump() for h in initial]),
                considered_evidence=state.evidence,
            )
            for h in initial:
                h.superseded = True
            hypotheses = initial + self._attach_revision_metadata(revised, initial)

        update: Dict[str, Any] = {"hypotheses": state.hypotheses + hypotheses}

        # Investigation-level confidence must reflect what RCA actually
        # concluded, not stay pinned at OrchestratorAgent's flat 0.5 baseline
        # — ActionAgent's confidence-floor gate (0.70) reads state.confidence,
        # and a baseline that never moves would make every investigation
        # escalate regardless of hypothesis quality.
        surviving = [h for h in hypotheses if not h.superseded]
        if surviving:
            update["confidence"] = max(h.confidence for h in surviving)

        return update

    @staticmethod
    def _attach_revision_metadata(revised: List[Hypothesis], initial: List[Hypothesis]) -> List[Hypothesis]:
        prior_evidence_ids = {eid for h in initial for eid in h.evidence_ids}
        for h in revised:
            new_ids = [eid for eid in h.evidence_ids if eid not in prior_evidence_ids]
            h.changed_because = new_ids or list(h.evidence_ids)
            h.revision_reason = (
                "New evidence outside the original trigger-tier set changed the most likely root cause."
                if new_ids else
                "Deeper evidence confirmed the original hypothesis rather than changing it."
            )
        return revised

    async def _generate(
        self, incident_id: str, stage: str, prompt_messages: List[dict], considered_evidence: List[Evidence],
    ) -> List[Hypothesis]:
        raw = await self._call_llm(prompt_messages)
        hypotheses = self._parse_and_validate(incident_id, stage, raw, considered_evidence)

        if not hypotheses:
            raw = await self._call_llm(prompt_messages)
            hypotheses = self._parse_and_validate(incident_id, stage, raw, considered_evidence)

        for h in hypotheses:
            h.confidence = self._compute_confidence(h, considered_evidence, len(hypotheses))

        return hypotheses

    async def _call_llm(self, messages: List[dict]) -> str:
        try:
            from ..llm import rased_chat_completion
            result = await rased_chat_completion(sanitize_for_llm(messages), session_id="rased-rca")
            return (result or {}).get("response", "") or ""
        except Exception as exc:
            logger.warning(f"rased RCA LLM call failed: {exc}")
            return ""

    def _parse_and_validate(
        self, incident_id: str, stage: str, raw: str, considered_evidence: List[Evidence],
    ) -> List[Hypothesis]:
        valid_ids = {e.evidence_id for e in considered_evidence}
        try:
            payload = json.loads(self._extract_json_array(raw))
        except Exception:
            return []

        hypotheses: List[Hypothesis] = []
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict):
                continue
            evidence_ids = [eid for eid in item.get("evidence_ids", []) if eid in valid_ids]
            if not evidence_ids:
                continue  # uncited — rejected in code, never reaches the UI
            hypotheses.append(Hypothesis(
                hypothesis_id=str(uuid.uuid4()),
                incident_id=incident_id,
                stage=stage,
                statement=str(item.get("statement") or "").strip() or "Unspecified hypothesis",
                root_cause_entity=item.get("root_cause_entity"),
                confidence=0.0,  # computed below, never trusted from the model
                evidence_ids=evidence_ids,
                generated_at=datetime.now(timezone.utc),
            ))
        return hypotheses

    @staticmethod
    def _extract_json_array(raw: str) -> str:
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1 or end < start:
            return "[]"
        return raw[start:end + 1]

    @staticmethod
    def _compute_confidence(hypothesis: Hypothesis, considered_evidence: List[Evidence], competing_count: int) -> float:
        total = max(1, len(considered_evidence))
        cited = len(set(hypothesis.evidence_ids))
        evidence_coverage = min(1.0, cited / total)

        all_sources = {e.source for e in considered_evidence}
        cited_sources = {e.source for e in considered_evidence if e.evidence_id in hypothesis.evidence_ids}
        source_agreement = len(cited_sources) / max(1, len(all_sources))

        contradiction_factor = max(0.1, 1.0 - 0.15 * max(0, competing_count - 1))

        return round(max(0.0, min(1.0, evidence_coverage * source_agreement * contradiction_factor)), 3)


__all__ = ["RCAAgent"]
