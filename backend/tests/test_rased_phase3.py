"""
RASED Phase 3 acceptance tests: SOP corpus loading, BM25 retrieval (fully
offline, no mocking needed — it reads the real markdown files this phase
shipped), and PolicyAgent's severity/citation/maintenance-window behavior.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.rased_schemas import BusinessImpact, InvestigationState
from app.services.rased.agents.policy import PolicyAgent, is_in_maintenance_window
from app.services.rased.data import InMemorySink, generate_scenario
from app.services.rased.policy import BM25Retriever, get_retriever, load_corpus

ANCHOR = datetime(2026, 8, 7, 15, 0, 0, tzinfo=timezone.utc)  # a Friday


def _state(alerts, business_impact=None, **overrides) -> InvestigationState:
    now = datetime.now(timezone.utc)
    defaults = dict(
        incident_id="test-incident-3",
        execution_mode="simulated",
        alerts=alerts,
        business_impact=business_impact,
        confidence=0.0,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return InvestigationState(**defaults)


async def _generate_s1():
    sink = InMemorySink()
    await generate_scenario("S1", sink, seed=42, anchor_time=ANCHOR)
    return sink.alerts["S1"]


async def _generate_s4():
    sink = InMemorySink()
    await generate_scenario("S4", sink, seed=42, anchor_time=ANCHOR)
    return sink.alerts["S4"]


def _no_llm():
    """Force the deterministic fallback justification path — these tests
    verify the rule-based decision and citation, not LLM wording."""
    return patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=RuntimeError("no provider")))


class TestCorpusLoader:
    def test_loads_both_sop_documents(self):
        sections = load_corpus(force_reload=True)
        document_ids = {s.document_id for s in sections}
        assert document_ids == {"SOP-NOC-SW-001", "SOP-NOC-AD-001"}

    def test_sections_have_stable_bracketed_ids(self):
        sections = load_corpus(force_reload=True)
        section_ids = {s.section_id for s in sections}
        assert "SW-001-2" in section_ids
        assert "AD-001-4" in section_ids
        assert "AD-001-5" in section_ids

    def test_section_text_does_not_bleed_into_next_heading(self):
        sections = load_corpus(force_reload=True)
        sw_2 = next(s for s in sections if s.section_id == "SW-001-2")
        assert "[SW-001-3]" not in sw_2.text
        assert "P1" in sw_2.text


class TestBM25Retrieval:
    def test_works_fully_offline_with_no_mocking(self):
        retriever = BM25Retriever(sections=load_corpus())
        results = retriever.search("critical severity major business impact escalation", top_k=1)
        assert results
        assert results[0].section_id in ("SW-001-2", "SW-001-3")

    def test_maintenance_query_finds_suppression_section(self):
        retriever = BM25Retriever(sections=load_corpus())
        results = retriever.search("maintenance window suppression", top_k=1)
        assert results
        assert results[0].section_id == "AD-001-5"

    def test_default_retriever_is_bm25(self):
        assert isinstance(get_retriever(), BM25Retriever)


class TestPolicyAgent:
    def test_no_alerts_returns_empty_update(self):
        result = asyncio.run(PolicyAgent().run(_state([])))
        assert result == {}

    def test_s1_resolves_to_p1_with_citation(self):
        alerts = asyncio.run(_generate_s1())
        impact = BusinessImpact(
            incident_id="test-incident-3", affected_service="checkout-api",
            business_capability="Checkout & Payments", transactions_at_risk=21000,
            revenue_at_risk=892500.0, summary="checkout-api degraded",
            computed_at=ANCHOR,
        )
        state = _state(alerts, business_impact=impact)

        with _no_llm():
            result = asyncio.run(PolicyAgent().run(state))

        decision = result["policy_decision"]
        assert decision.severity_tier == "P1"
        assert decision.escalation_target == "on-call-incident-commander"
        assert decision.approval_required is True
        assert decision.citations
        assert decision.citations[0].document_id in ("SOP-NOC-SW-001", "SOP-NOC-AD-001")
        assert decision.justification

    def test_low_impact_resolves_to_lower_tier_without_approval(self):
        alerts = asyncio.run(_generate_s1())
        impact = BusinessImpact(
            incident_id="test-incident-3", affected_service="checkout-api",
            business_capability="Checkout & Payments", transactions_at_risk=50,
            revenue_at_risk=None, summary="minor blip", computed_at=ANCHOR,
        )
        state = _state(alerts, business_impact=impact)

        with _no_llm():
            result = asyncio.run(PolicyAgent().run(state))

        decision = result["policy_decision"]
        assert decision.severity_tier == "P4"
        assert decision.approval_required is False

    def test_maintenance_window_suppresses_regardless_of_impact(self):
        alerts = asyncio.run(_generate_s1())
        for alert in alerts:
            alert.service = "reporting-svc"
        maintenance_time = datetime(2026, 8, 9, 3, 0, 0, tzinfo=timezone.utc)  # Sunday 03:00 UTC
        for alert in alerts:
            alert.observed_at = maintenance_time

        impact = BusinessImpact(
            incident_id="test-incident-3", affected_service="reporting-svc",
            business_capability="Merchant Analytics", transactions_at_risk=50000,  # would otherwise be P1
            revenue_at_risk=1_000_000.0, summary="would be critical outside the window",
            computed_at=maintenance_time,
        )
        state = _state(alerts, business_impact=impact)

        with _no_llm():
            result = asyncio.run(PolicyAgent().run(state))

        decision = result["policy_decision"]
        assert decision.maintenance_window_active is True
        assert decision.severity_tier == "P4"
        assert decision.approval_required is False

    def test_s4_produces_policy_decision_with_citation(self):
        alerts = asyncio.run(_generate_s4())
        impact = BusinessImpact(
            incident_id="test-incident-3", affected_service="notification-svc",
            business_capability="Customer Communications", transactions_at_risk=3000,
            revenue_at_risk=None, summary="notification-svc memory leak",
            computed_at=ANCHOR,
        )
        state = _state(alerts, business_impact=impact)

        with _no_llm():
            result = asyncio.run(PolicyAgent().run(state))

        decision = result["policy_decision"]
        assert decision.severity_tier == "P2"
        assert decision.citations

    def test_llm_failure_falls_back_to_deterministic_justification(self):
        alerts = asyncio.run(_generate_s1())
        impact = BusinessImpact(
            incident_id="test-incident-3", affected_service="checkout-api",
            business_capability="Checkout & Payments", transactions_at_risk=21000,
            revenue_at_risk=892500.0, summary="checkout-api degraded", computed_at=ANCHOR,
        )
        state = _state(alerts, business_impact=impact)

        with _no_llm():
            result = asyncio.run(PolicyAgent().run(state))

        assert "P1" in result["policy_decision"].justification


class TestMaintenanceWindowHelper:
    def test_service_with_no_window_is_never_in_maintenance(self):
        assert is_in_maintenance_window("checkout-api", ANCHOR) is False

    def test_reporting_svc_window_boundaries(self):
        inside = datetime(2026, 8, 9, 3, 0, 0, tzinfo=timezone.utc)  # Sunday 03:00
        before = datetime(2026, 8, 9, 1, 0, 0, tzinfo=timezone.utc)  # Sunday 01:00
        wrong_day = datetime(2026, 8, 8, 3, 0, 0, tzinfo=timezone.utc)  # Saturday 03:00
        assert is_in_maintenance_window("reporting-svc", inside) is True
        assert is_in_maintenance_window("reporting-svc", before) is False
        assert is_in_maintenance_window("reporting-svc", wrong_day) is False
