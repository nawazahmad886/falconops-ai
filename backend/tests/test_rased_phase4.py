"""
RASED Phase 4 acceptance tests: action gate hard gates, DESTRUCTIVE approval
pause, executors, Jira/Teams mock-by-default integrations, bilingual brief,
case management persistence.

ActionAgent._await_approval (the one call site that touches
langgraph.types.interrupt) is mocked directly for every test except
TestInterruptImportPath, which is guarded by pytest.importorskip — see
Phase 1's TestBuildGraph for the same pattern and agents/action.py's module
docstring for why: no local interpreter was available to confirm
langgraph.types.interrupt's exact behavior while authoring this.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.rased_schemas import Action, Alert, Hypothesis, InvestigationState, PolicyDecision
from app.services.rased.actions.executors import EXECUTORS, execute_action
from app.services.rased.actions.registry import ACTIONS, BLAST_RADIUS_THRESHOLD, CONFIDENCE_FLOOR
from app.services.rased.agents.action import ActionAgent
from app.services.rased.agents.case_mgmt import CaseManagementAgent
from app.services.rased.brief.bilingual import build_bilingual_brief
from app.services.rased.data import InMemorySink, generate_scenario
from app.services.rased.integrations.jira import JiraAdapter
from app.services.rased.integrations.teams import TeamsAdapter

ANCHOR = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def _alert(service: str = "checkout-api") -> Alert:
    return Alert(
        alert_id="a1", signature="sig", source="db", service=service, severity="high",
        title="t", description="d", observed_at=ANCHOR, raw={},
    )


def _hypothesis(root_cause_entity: str, confidence: float = 0.9, superseded: bool = False) -> Hypothesis:
    return Hypothesis(
        hypothesis_id="h1", incident_id="i1", stage="revised",
        statement=f"caused by {root_cause_entity}", root_cause_entity=root_cause_entity,
        confidence=confidence, evidence_ids=["e1"], superseded=superseded, generated_at=ANCHOR,
    )


def _state(alerts, hypotheses=None, confidence=0.9, policy_decision=None, **overrides) -> InvestigationState:
    now = datetime.now(timezone.utc)
    defaults = dict(
        incident_id="test-incident-4", execution_mode="simulated",
        alerts=alerts, hypotheses=hypotheses or [], confidence=confidence,
        policy_decision=policy_decision, created_at=now, updated_at=now,
    )
    defaults.update(overrides)
    return InvestigationState(**defaults)


def _no_llm_action_pick():
    return patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=RuntimeError("no provider")))


class TestActionAgentHardGates:
    def test_suppressed_investigation_proposes_nothing(self):
        state = _state([_alert()], status="suppressed")
        result = asyncio.run(ActionAgent().run(state))
        assert result == {}

    def test_blast_radius_over_threshold_escalates_without_proposing(self):
        alerts = [_alert(f"svc-{i}") for i in range(BLAST_RADIUS_THRESHOLD + 1)]
        state = _state(alerts, confidence=0.9)
        result = asyncio.run(ActionAgent().run(state))
        assert result == {"status": "escalated"}

    def test_low_confidence_escalates_without_proposing(self):
        state = _state([_alert()], confidence=CONFIDENCE_FLOOR - 0.01)
        result = asyncio.run(ActionAgent().run(state))
        assert result == {"status": "escalated"}

    def test_maintenance_window_active_suppresses(self):
        decision = PolicyDecision(
            incident_id="i1", severity_tier="P4", escalation_target="x", notification_template="x",
            approval_required=False, maintenance_window_active=True, citations=[], justification="j",
            decided_at=ANCHOR,
        )
        state = _state([_alert()], confidence=0.9, policy_decision=decision)
        result = asyncio.run(ActionAgent().run(state))
        assert result == {"status": "suppressed"}


class TestActionAgentProposal:
    def test_guarded_action_executes_immediately_no_approval(self):
        hyp = _hypothesis("order-queue-consumer")
        state = _state([_alert("order-queue-consumer")], hypotheses=[hyp], confidence=0.9)

        with _no_llm_action_pick(), patch.object(ActionAgent, "_await_approval", AsyncMock(return_value=True)) as mock_approval:
            result = asyncio.run(ActionAgent().run(state))

        mock_approval.assert_not_called()
        assert result["actions"][0].name == "clear_queue_backlog"
        assert result["actions"][0].spec.tier == "GUARDED"
        assert result["actions"][0].status == "executed"
        assert result["status"] == "resolved"
        assert result["action_results"][0].success is True

    def test_destructive_action_pauses_for_approval_then_executes_if_approved(self):
        hyp = _hypothesis("payment-gateway")
        state = _state([_alert("checkout-api")], hypotheses=[hyp], confidence=0.9)

        with _no_llm_action_pick(), patch.object(ActionAgent, "_await_approval", AsyncMock(return_value=True)) as mock_approval:
            result = asyncio.run(ActionAgent().run(state))

        mock_approval.assert_called_once()
        assert result["actions"][0].name == "failover_dependency"
        assert result["actions"][0].spec.tier == "DESTRUCTIVE"
        assert result["actions"][0].status == "executed"
        assert result["status"] == "resolved"

    def test_destructive_action_rejected_does_not_execute(self):
        hyp = _hypothesis("payment-gateway")
        state = _state([_alert("checkout-api")], hypotheses=[hyp], confidence=0.9)

        with _no_llm_action_pick(), patch.object(ActionAgent, "_await_approval", AsyncMock(return_value=False)):
            result = asyncio.run(ActionAgent().run(state))

        assert result["actions"][0].status == "rejected"
        assert result["status"] == "escalated"
        assert "action_results" not in result

    def test_no_matching_hypothesis_escalates(self):
        state = _state([_alert("some-unmapped-service")], hypotheses=[], confidence=0.9)
        with _no_llm_action_pick():
            result = asyncio.run(ActionAgent().run(state))
        assert result == {"status": "escalated"}

    def test_superseded_hypothesis_is_ignored_for_action_pick(self):
        superseded_hyp = _hypothesis("invoice-db", confidence=0.99, superseded=True)
        state = _state([_alert("checkout-api")], hypotheses=[superseded_hyp], confidence=0.9)
        with _no_llm_action_pick():
            result = asyncio.run(ActionAgent().run(state))
        assert result == {"status": "escalated"}

    def test_llm_pick_outside_registry_falls_back_to_entity_hint(self):
        hyp = _hypothesis("order-queue-consumer")
        state = _state([_alert("order-queue-consumer")], hypotheses=[hyp], confidence=0.9)

        async def bogus_pick(messages, session_id=None):
            return {"response": "delete_the_entire_database"}

        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=bogus_pick)):
            result = asyncio.run(ActionAgent().run(state))

        assert result["actions"][0].name == "clear_queue_backlog"

    def test_llm_pick_within_registry_is_used_directly(self):
        hyp = _hypothesis("payment-gateway")  # entity-hint fallback would pick failover_dependency
        state = _state([_alert("checkout-api")], hypotheses=[hyp], confidence=0.9)

        async def valid_pick(messages, session_id=None):
            return {"response": "collect_diagnostics"}

        with patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=valid_pick)):
            result = asyncio.run(ActionAgent().run(state))

        assert result["actions"][0].name == "collect_diagnostics"
        assert result["actions"][0].spec.tier == "SAFE"


class TestS5ProposesZeroActions:
    def test_s5_suppressed_status_yields_no_actions(self):
        async def _s5_alerts():
            sink = InMemorySink()
            await generate_scenario("S5", sink, seed=42, anchor_time=ANCHOR)
            return sink.alerts["S5"]

        alerts = asyncio.run(_s5_alerts())
        state = _state(alerts, status="suppressed", confidence=1.0)
        result = asyncio.run(ActionAgent().run(state))
        assert result == {}
        assert "actions" not in result


class TestExecutors:
    def test_unknown_adapter_returns_failure_not_exception(self):
        result = asyncio.run(execute_action("x", "no-such-adapter", {}, "incident-1"))
        assert result.success is False
        assert "no executor" in result.error

    def test_known_adapter_succeeds_and_carries_execution_mode(self):
        result = asyncio.run(execute_action("restart_pod", "k8s_mock", {"service": "checkout-api"}, "incident-1"))
        assert result.success is True
        assert result.execution_mode == "simulated"
        assert result.incident_id == "incident-1"

    def test_all_registry_actions_have_a_registered_executor(self):
        for spec in ACTIONS.values():
            assert spec.adapter in EXECUTORS


class TestIntegrationsMockByDefault:
    def test_jira_defaults_to_mock(self):
        state = _state([_alert()])
        brief = {"en": {"what_is_happening": "checkout-api degraded"}, "ar": {}}
        adapter = JiraAdapter()
        assert asyncio.run(adapter.is_live()) is False
        ticket = asyncio.run(adapter.create_or_update_case(state, brief))
        assert ticket["mode"] == "mock"
        assert "RASED-" in ticket["ticket_key"]

    def test_teams_defaults_to_mock(self):
        state = _state([_alert()])
        brief = {"en": {"what_is_happening": "checkout-api degraded"}, "ar": {}}
        adapter = TeamsAdapter()
        assert asyncio.run(adapter.is_live()) is False
        result = asyncio.run(adapter.notify(state, brief))
        assert result["mode"] == "mock"

    def test_jira_without_base_url_or_token_never_reports_live(self):
        adapter = JiraAdapter()
        adapter.base_url = None
        adapter.token = None
        assert asyncio.run(adapter.is_live()) is False


class TestBilingualBrief:
    def test_all_five_fields_present_in_both_languages(self):
        state = _state([_alert()], status="resolved")
        brief = build_bilingual_brief(state)
        expected_keys = {
            "what_is_happening", "who_and_how_many", "probable_cause_and_confidence",
            "what_rased_did", "needs_from_human",
        }
        assert set(brief["en"].keys()) == expected_keys
        assert set(brief["ar"].keys()) == expected_keys
        for value in brief["ar"].values():
            assert value.strip()

    def test_awaiting_approval_status_reflected_in_needs_from_human(self):
        state = _state([_alert()], status="awaiting_approval")
        brief = build_bilingual_brief(state)
        assert "approval" in brief["en"]["needs_from_human"].lower()
        assert "موافقة" in brief["ar"]["needs_from_human"]

    def test_no_hypothesis_yet_produces_placeholder_not_crash(self):
        state = _state([_alert()], hypotheses=[])
        brief = build_bilingual_brief(state)
        assert brief["en"]["probable_cause_and_confidence"]
        assert brief["ar"]["probable_cause_and_confidence"]


class TestCaseManagementAgent:
    def test_persists_case_and_dispatches_both_integrations(self):
        state = _state([_alert()], status="resolved")

        mock_jira = MagicMock()
        mock_jira.create_or_update_case = AsyncMock(return_value={"mode": "mock", "ticket_key": "RASED-TEST"})
        mock_teams = MagicMock()
        mock_teams.notify = AsyncMock(return_value={"mode": "mock", "delivered": True})

        mock_db = MagicMock()
        mock_db.rased_cases.update_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db):
            result = asyncio.run(CaseManagementAgent(jira=mock_jira, teams=mock_teams).run(state))

        assert result == {}
        mock_jira.create_or_update_case.assert_called_once()
        mock_teams.notify.assert_called_once()
        mock_db.rased_cases.update_one.assert_called_once()

    def test_jira_failure_does_not_block_teams_or_persistence(self):
        state = _state([_alert()], status="resolved")

        mock_jira = MagicMock()
        mock_jira.create_or_update_case = AsyncMock(side_effect=RuntimeError("jira down"))
        mock_teams = MagicMock()
        mock_teams.notify = AsyncMock(return_value={"mode": "mock", "delivered": True})

        mock_db = MagicMock()
        mock_db.rased_cases.update_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db):
            result = asyncio.run(CaseManagementAgent(jira=mock_jira, teams=mock_teams).run(state))

        assert result == {}
        mock_teams.notify.assert_called_once()
        mock_db.rased_cases.update_one.assert_called_once()


class TestInterruptImportPath:
    def test_await_approval_calls_real_langgraph_interrupt_if_importable(self):
        pytest.importorskip(
            "langgraph.types",
            reason="langgraph not importable in this environment — see agents/action.py's risk note",
        )
        with patch("langgraph.types.interrupt", MagicMock(return_value={"approved": True})):
            action = Action(
                action_id="a1", incident_id="i1", name="failover_dependency",
                spec=ACTIONS["failover_dependency"], status="proposed", proposed_at=ANCHOR,
            )
            approved = asyncio.run(ActionAgent._await_approval(_state([_alert()]), action))
        assert approved is True
