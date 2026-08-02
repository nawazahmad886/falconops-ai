"""
RASED Phase 2 acceptance tests: business impact arithmetic and RCA hypothesis
revision. llm_provider_service.chat_completion is mocked throughout — these
tests verify the mechanism (evidence tiering drives what the model sees,
uncited hypotheses are rejected in code, confidence is computed not asked
for), not the literal wording a real model would produce. See rca.py's
module docstring for the operational note on which providers actually return
usable JSON.
"""
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.rased_schemas import Evidence, InvestigationState
from app.services.rased.agents.impact import ImpactAgent
from app.services.rased.agents.rca import RCAAgent
from app.services.rased.data import InMemorySink, generate_scenario

ANCHOR = datetime(2026, 8, 6, 14, 0, 0, tzinfo=timezone.utc)  # peak-hour, diurnal_multiplier(14) == 1.0


def _state(alerts, evidence=None, **overrides) -> InvestigationState:
    now = datetime.now(timezone.utc)
    defaults = dict(
        incident_id="test-incident-2",
        execution_mode="simulated",
        alerts=alerts,
        evidence=evidence or [],
        confidence=0.0,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return InvestigationState(**defaults)


async def _generate_s1():
    sink = InMemorySink()
    await generate_scenario("S1", sink, seed=42, anchor_time=ANCHOR)
    return sink.alerts["S1"], sink.evidence["S1"]


def _llm_patch(response_text: str):
    return patch(
        "app.services.llm_provider_service.chat_completion",
        AsyncMock(return_value={"provider": "test", "model": "test", "response": response_text}),
    )


class TestImpactAgent:
    def test_no_alerts_returns_empty_update(self):
        result = asyncio.run(ImpactAgent().run(_state([])))
        assert result == {}

    def test_computes_transactions_from_catalog_and_diurnal_curve(self):
        alerts, _ = asyncio.run(_generate_s1())
        state = _state(alerts)
        with _llm_patch("checkout-api is degraded, affecting 4200 transactions."):
            result = asyncio.run(ImpactAgent().run(state))

        impact = result["business_impact"]
        assert impact.affected_service == "checkout-api"
        assert impact.business_capability == "Checkout & Payments"
        # baseline_tpm=4200, diurnal_multiplier(14h)==1.0 (peak), 5-minute window,
        # allow for the alert's own jitter shifting the hour by less than a minute.
        assert 15000 <= impact.transactions_at_risk <= 25000
        assert impact.revenue_at_risk == pytest.approx(impact.transactions_at_risk * 42.50, rel=0.01)

    def test_llm_writes_the_sentence_python_computes_the_numbers(self):
        alerts, _ = asyncio.run(_generate_s1())
        state = _state(alerts)
        captured = {}

        async def capture(messages, session_id=None):
            captured["messages"] = messages
            return {"response": "checkout-api impact sentence"}

        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=capture)):
            result = asyncio.run(ImpactAgent().run(state))

        assert result["business_impact"].summary == "checkout-api impact sentence"
        user_content = captured["messages"][1]["content"]
        assert "Estimated transactions at risk" in user_content
        assert str(result["business_impact"].transactions_at_risk) in user_content

    def test_llm_failure_falls_back_to_deterministic_sentence(self):
        alerts, _ = asyncio.run(_generate_s1())
        state = _state(alerts)
        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=RuntimeError("provider down"))):
            result = asyncio.run(ImpactAgent().run(state))

        impact = result["business_impact"]
        assert "checkout-api" in impact.summary
        assert str(impact.transactions_at_risk) in impact.summary


def _hypothesis_json(statement: str, evidence_ids: list, root_cause_entity: str = None) -> str:
    return json.dumps([{"statement": statement, "root_cause_entity": root_cause_entity, "evidence_ids": evidence_ids}])


class TestRCAAgent:
    def test_no_evidence_returns_empty_update(self):
        result = asyncio.run(RCAAgent().run(_state([])))
        assert result == {}

    def test_initial_pass_only_sees_trigger_tier_evidence(self):
        alerts, evidence = asyncio.run(_generate_s1())
        state = _state(alerts, evidence)
        trigger_ids = [e.evidence_id for e in evidence if e.tier == "trigger"]

        seen_prompts = []

        async def capture(messages, session_id=None):
            seen_prompts.append(messages[1]["content"])
            return {"response": _hypothesis_json("database contention", trigger_ids, "invoice-db")}

        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=capture)):
            asyncio.run(RCAAgent().run(state))

        initial_prompt = seen_prompts[0]
        assert "payment-gateway" not in initial_prompt.lower()
        assert "invoice-db" in initial_prompt.lower() or "pool" in initial_prompt.lower()

    def test_revision_pass_sees_full_evidence_set(self):
        alerts, evidence = asyncio.run(_generate_s1())
        state = _state(alerts, evidence)
        trigger_ids = [e.evidence_id for e in evidence if e.tier == "trigger"]
        deep_ids = [e.evidence_id for e in evidence if e.tier == "deep"]

        seen_prompts = []
        call_count = {"n": 0}

        async def capture(messages, session_id=None):
            seen_prompts.append(messages[1]["content"])
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"response": _hypothesis_json("database contention", trigger_ids, "invoice-db")}
            return {"response": _hypothesis_json("payment gateway failure", deep_ids, "payment-gateway")}

        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=capture)):
            result = asyncio.run(RCAAgent().run(state))

        revision_prompt = seen_prompts[1]
        assert "payment-gateway" in revision_prompt.lower()

        hypotheses = result["hypotheses"]
        initial = [h for h in hypotheses if h.stage == "initial"]
        revised = [h for h in hypotheses if h.stage == "revised"]
        assert len(initial) == 1 and initial[0].superseded is True
        assert len(revised) == 1
        assert set(revised[0].changed_because) == set(deep_ids)
        assert revised[0].revision_reason

    def test_uncited_hypothesis_is_rejected_and_regenerated_once_then_dropped(self):
        alerts, evidence = asyncio.run(_generate_s1())
        trigger_evidence = [e for e in evidence if e.tier == "trigger"]
        state = _state(alerts, trigger_evidence)

        call_count = {"n": 0}

        async def always_uncited(messages, session_id=None):
            call_count["n"] += 1
            return {"response": _hypothesis_json("a claim with no citation", [])}

        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=always_uncited)):
            result = asyncio.run(RCAAgent().run(state))

        assert result.get("hypotheses", []) == []
        assert call_count["n"] == 2  # one regeneration attempt, then dropped

    def test_hypothesis_citing_an_unknown_evidence_id_is_rejected(self):
        alerts, evidence = asyncio.run(_generate_s1())
        trigger_evidence = [e for e in evidence if e.tier == "trigger"]
        state = _state(alerts, trigger_evidence)

        async def fabricated_id(messages, session_id=None):
            return {"response": _hypothesis_json("claim", ["not-a-real-evidence-id"])}

        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=fabricated_id)):
            result = asyncio.run(RCAAgent().run(state))

        assert result.get("hypotheses", []) == []

    def test_malformed_json_response_does_not_raise(self):
        alerts, evidence = asyncio.run(_generate_s1())
        trigger_evidence = [e for e in evidence if e.tier == "trigger"]
        state = _state(alerts, trigger_evidence)

        with _llm_patch("I cannot comply with JSON, sorry."):
            result = asyncio.run(RCAAgent().run(state))

        assert result.get("hypotheses", []) == []

    def test_confidence_is_computed_not_taken_from_llm(self):
        alerts, evidence = asyncio.run(_generate_s1())
        trigger_evidence = [e for e in evidence if e.tier == "trigger"]
        state = _state(alerts, trigger_evidence)
        trigger_ids = [e.evidence_id for e in trigger_evidence]

        async def llm_claims_high_confidence(messages, session_id=None):
            payload = [{
                "statement": "database contention",
                "root_cause_entity": "invoice-db",
                "evidence_ids": trigger_ids,
                "confidence": 0.99,  # RCAAgent must never read/trust this
            }]
            return {"response": json.dumps(payload)}

        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=llm_claims_high_confidence)):
            result = asyncio.run(RCAAgent().run(state))

        hypothesis = result["hypotheses"][0]
        assert hypothesis.confidence != 0.99
        assert 0.0 <= hypothesis.confidence <= 1.0


class TestConfidenceFormula:
    def _evidence(self, evidence_id: str, source: str) -> Evidence:
        return Evidence(
            evidence_id=evidence_id, tier="trigger", source=source, query="q", summary="s",
            data={}, observed_at=ANCHOR, retrieved_at=ANCHOR,
        )

    def test_full_coverage_single_hypothesis_single_source(self):
        from app.services.rased.agents.rca import RCAAgent
        from app.models.rased_schemas import Hypothesis

        evidence = [self._evidence("e1", "db"), self._evidence("e2", "db")]
        hyp = Hypothesis(
            hypothesis_id="h1", incident_id="i1", stage="initial", statement="s",
            confidence=0.0, evidence_ids=["e1", "e2"], generated_at=ANCHOR,
        )
        confidence = RCAAgent._compute_confidence(hyp, evidence, competing_count=1)
        # coverage=2/2=1.0, source_agreement=1/1=1.0, contradiction_factor=1.0 (only competitor)
        assert confidence == pytest.approx(1.0)

    def test_partial_coverage_lowers_confidence(self):
        from app.services.rased.agents.rca import RCAAgent
        from app.models.rased_schemas import Hypothesis

        evidence = [self._evidence("e1", "db"), self._evidence("e2", "appdynamics"), self._evidence("e3", "changes")]
        hyp = Hypothesis(
            hypothesis_id="h1", incident_id="i1", stage="initial", statement="s",
            confidence=0.0, evidence_ids=["e1"], generated_at=ANCHOR,
        )
        confidence = RCAAgent._compute_confidence(hyp, evidence, competing_count=1)
        # coverage=1/3, source_agreement=1/3
        assert confidence == pytest.approx((1 / 3) * (1 / 3), abs=0.01)

    def test_more_competing_hypotheses_lowers_confidence(self):
        from app.services.rased.agents.rca import RCAAgent
        from app.models.rased_schemas import Hypothesis

        evidence = [self._evidence("e1", "db")]
        hyp = Hypothesis(
            hypothesis_id="h1", incident_id="i1", stage="initial", statement="s",
            confidence=0.0, evidence_ids=["e1"], generated_at=ANCHOR,
        )
        one_competitor = RCAAgent._compute_confidence(hyp, evidence, competing_count=1)
        three_competitors = RCAAgent._compute_confidence(hyp, evidence, competing_count=3)
        assert three_competitors < one_competitor
