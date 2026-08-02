"""
RASED Phase 6 acceptance tests: one-click demo run/reset, all five scenarios
running end-to-end through the full agent chain with no unhandled exception,
the failure-mode scenario (forced adapter timeout -> confidence below floor
-> no action proposed -> human still paged via a case record), and
--demo-mode LLM response caching.

"End to end" means the full agent chain (orchestrator -> telemetry ->
impact+rca -> policy -> action -> case_mgmt) driven directly, not through
the compiled LangGraph — see graph/workflow.py's risk note for why the graph
wiring itself is only exercised in the pytest.importorskip-guarded tests
elsewhere. Driving the same agents directly still faithfully tests "no
unhandled exception path": every graph node IS one of these agents: only the
LangGraph plumbing between them is unverified, not the agent logic itself.
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.rased_schemas import InvestigationState
from app.services.rased.actions.registry import CONFIDENCE_FLOOR
from app.services.rased.agents.action import ActionAgent
from app.services.rased.agents.case_mgmt import CaseManagementAgent
from app.services.rased.agents.impact import ImpactAgent
from app.services.rased.agents.orchestrator import OrchestratorAgent
from app.services.rased.agents.policy import PolicyAgent
from app.services.rased.agents.rca import RCAAgent
from app.services.rased.agents.telemetry import TelemetryRetrievalAgent
import app.services.rased.agents.telemetry as telemetry_module
from app.services.rased.data import InMemorySink, SCENARIOS, generate_scenario
from app.services.rased.demo import RASED_COLLECTIONS, reset_demo_data, run_demo_scenario
from app.services.rased.llm import DEMO_MODE_DELAY_SECONDS, rased_chat_completion

ANCHOR = datetime(2026, 8, 12, 14, 0, 0, tzinfo=timezone.utc)


def _no_llm():
    return patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=RuntimeError("no provider")))


def _no_redis():
    from app.services.metrics_timeseries_service import metrics_timeseries_service as mts
    return patch.object(mts, "get_redis", AsyncMock(return_value=None))


def _empty_evidence_db_mock() -> MagicMock:
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find.return_value.to_list = AsyncMock(return_value=[])
    return mock_db


async def _generate_alerts(scenario_id: str, seed: int = 42):
    sink = InMemorySink()
    await generate_scenario(scenario_id, sink, seed=seed, anchor_time=ANCHOR)
    return sink.alerts[scenario_id]


async def _run_full_chain(scenario_id: str) -> InvestigationState:
    alerts = await _generate_alerts(scenario_id)
    now = datetime.now(timezone.utc)
    state = InvestigationState(
        incident_id=f"{scenario_id}-e2e", execution_mode="simulated",
        alerts=alerts, confidence=0.0, created_at=now, updated_at=now,
    )

    with _no_redis():
        state = state.model_copy(update=await OrchestratorAgent().run(state))
    if state.status == "suppressed":
        return state

    with patch("app.core.database.db", _empty_evidence_db_mock()):
        state = state.model_copy(update=await TelemetryRetrievalAgent().run(state))

    with _no_llm():
        impact_update, rca_update = await asyncio.gather(ImpactAgent().run(state), RCAAgent().run(state))
    state = state.model_copy(update={**impact_update, **rca_update})

    with _no_llm():
        state = state.model_copy(update=await PolicyAgent().run(state))

    with _no_llm(), patch.object(ActionAgent, "_await_approval", AsyncMock(return_value=True)):
        state = state.model_copy(update=await ActionAgent().run(state))

    mock_jira = MagicMock()
    mock_jira.create_or_update_case = AsyncMock(return_value={"mode": "mock"})
    mock_teams = MagicMock()
    mock_teams.notify = AsyncMock(return_value={"mode": "mock"})
    mock_case_db = MagicMock()
    mock_case_db.rased_cases.update_one = AsyncMock(return_value=None)
    with patch("app.core.database.db", mock_case_db):
        await CaseManagementAgent(jira=mock_jira, teams=mock_teams).run(state)

    return state


class TestAllScenariosEndToEndNoUnhandledException:
    @pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
    def test_full_agent_chain_completes_without_raising(self, scenario_id):
        final_state = asyncio.run(_run_full_chain(scenario_id))
        assert final_state.status in ("suppressed", "resolved", "escalated", "awaiting_approval", "investigating")

    def test_s5_storm_never_reaches_action_agent(self):
        final_state = asyncio.run(_run_full_chain("S5"))
        assert final_state.status == "suppressed"
        assert final_state.actions == []
        assert final_state.action_results == []


class TestFailureModeScenario:
    def test_adapter_timeout_drops_confidence_no_action_but_case_still_paged(self):
        """Forced adapter timeout -> confidence below floor -> ActionAgent
        declines -> CaseManagementAgent still builds and dispatches a case
        with everything already assembled, i.e. the human is paged."""
        alerts = asyncio.run(_generate_alerts("S1"))
        now = datetime.now(timezone.utc)
        state = InvestigationState(
            incident_id="failure-mode-1", execution_mode="simulated",
            alerts=alerts, confidence=0.5, created_at=now, updated_at=now,
        )

        async def hangs(params):
            await asyncio.sleep(10)

        all_timeout_adapters = {
            name: MagicMock(source=name, query=AsyncMock(side_effect=hangs))
            for name in telemetry_module.ADAPTERS
        }

        with patch.object(telemetry_module, "ADAPTER_TIMEOUT_SECONDS", 0.02), \
             patch.dict(telemetry_module.ADAPTERS, all_timeout_adapters, clear=False), \
             patch("app.core.database.db", _empty_evidence_db_mock()):
            state = state.model_copy(update=asyncio.run(TelemetryRetrievalAgent().run(state)))

        assert state.confidence < CONFIDENCE_FLOOR

        with _no_llm():
            action_update = asyncio.run(ActionAgent().run(state))
        assert action_update == {"status": "escalated"}
        state = state.model_copy(update=action_update)

        mock_jira = MagicMock()
        mock_jira.create_or_update_case = AsyncMock(return_value={"mode": "mock"})
        mock_teams = MagicMock()
        mock_teams.notify = AsyncMock(return_value={"mode": "mock"})
        mock_db = MagicMock()
        mock_db.rased_cases.update_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db):
            asyncio.run(CaseManagementAgent(jira=mock_jira, teams=mock_teams).run(state))

        mock_jira.create_or_update_case.assert_called_once()
        mock_teams.notify.assert_called_once()
        brief = mock_jira.create_or_update_case.call_args.args[1]
        needs = brief["en"]["needs_from_human"].lower()
        assert "escalated" in needs or "review" in needs


class TestDemoMode:
    def test_demo_mode_off_by_default(self):
        from app.services.rased.config import DEMO_MODE
        assert DEMO_MODE is False

    def test_demo_mode_returns_cached_response_with_delay_never_calls_real_provider(self):
        with patch("app.services.rased.llm.DEMO_MODE", True), \
             patch("app.services.llm_provider_service.chat_completion", AsyncMock(side_effect=RuntimeError("must not be called"))):
            started = time.perf_counter()
            result = asyncio.run(rased_chat_completion([{"role": "user", "content": "hi"}], session_id="rased-impact"))
            elapsed = time.perf_counter() - started

        assert result["provider"] == "demo_mode_cache"
        assert elapsed >= DEMO_MODE_DELAY_SECONDS

    def test_demo_mode_rca_cites_every_evidence_id_shown_in_prompt(self):
        messages = [
            {"role": "system", "content": "..."},
            {"role": "user", "content": (
                "Evidence:\n- [S1-ev-01] (db, trigger-tier) pool saturation\n"
                "- [S1-ev-02] (db, trigger-tier) slow queries"
            )},
        ]
        with patch("app.services.rased.llm.DEMO_MODE", True):
            result = asyncio.run(rased_chat_completion(messages, session_id="rased-rca"))

        parsed = json.loads(result["response"])
        assert set(parsed[0]["evidence_ids"]) == {"S1-ev-01", "S1-ev-02"}

    def test_demo_mode_rca_with_no_evidence_in_prompt_returns_empty_array(self):
        with patch("app.services.rased.llm.DEMO_MODE", True):
            result = asyncio.run(rased_chat_completion([{"role": "user", "content": "no brackets here"}], session_id="rased-rca"))
        assert json.loads(result["response"]) == []

    def test_demo_mode_action_pick_defers_to_entity_hints(self):
        with patch("app.services.rased.llm.DEMO_MODE", True):
            result = asyncio.run(rased_chat_completion([{"role": "user", "content": "x"}], session_id="rased-action"))
        assert result["response"] == "none"


class TestDemoServiceLayer:
    def test_run_demo_scenario_unknown_id_raises_value_error(self):
        with pytest.raises(ValueError):
            asyncio.run(run_demo_scenario("S999"))

    def test_run_demo_scenario_generates_persists_and_schedules_run(self):
        alert_doc = {
            "alert_id": "S1-alert-01", "signature": "checkout-api:elevated-error-rate", "source": "db",
            "service": "checkout-api", "severity": "critical", "title": "t", "description": "d",
            "observed_at": ANCHOR, "raw": {},
        }
        mock_db = MagicMock()
        mock_db.__getitem__.return_value.find.return_value.to_list = AsyncMock(return_value=[alert_doc])
        mock_db.rased_investigations.update_one = AsyncMock(return_value=None)

        # generate_scenario writes through MongoSink, which touches many
        # collections via db[...]; the shared mock_db above returns a
        # MagicMock for every collection, and insert_many on a plain
        # MagicMock attribute needs to be awaitable too.
        for collection_mock in [mock_db.__getitem__.return_value]:
            collection_mock.insert_many = AsyncMock(return_value=None)
            collection_mock.delete_many = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db), patch("asyncio.create_task") as mock_create_task:
            result = asyncio.run(run_demo_scenario("S1", seed=42))

        assert result["scenario_id"] == "S1"
        assert result["alert_count"] == 1
        mock_create_task.assert_called_once()

    def test_reset_demo_data_deletes_from_every_owned_collection(self):
        mock_db = MagicMock()
        delete_result = MagicMock(deleted_count=3)
        mock_db.__getitem__.return_value.delete_many = AsyncMock(return_value=delete_result)

        with patch("app.core.database.db", mock_db):
            deleted = asyncio.run(reset_demo_data())

        assert set(deleted.keys()) == set(RASED_COLLECTIONS)
        assert all(count == 3 for count in deleted.values())


class TestDemoRoutes:
    def test_run_and_reset_route_wiring(self):
        rased_demo_routes = pytest.importorskip(
            "app.routes.rased_demo_routes",
            reason="app.routes package failed to import; skipping route-level RASED demo tests",
        )

        with patch.object(rased_demo_routes, "run_demo_scenario", AsyncMock(return_value={"incident_id": "x", "scenario_id": "S1"})):
            result = asyncio.run(rased_demo_routes.demo_run(
                "S1", rased_demo_routes.RunDemoRequest(), current_user={"email": "t", "role": "admin"},
            ))
        assert result["scenario_id"] == "S1"

        with patch.object(rased_demo_routes, "reset_demo_data", AsyncMock(return_value={"rased_synthetic_alerts": 5})):
            result = asyncio.run(rased_demo_routes.demo_reset(current_user={"email": "t", "role": "admin"}))
        assert result["reset"] is True
        assert result["deleted_counts"]["rased_synthetic_alerts"] == 5

    def test_run_unknown_scenario_returns_404(self):
        rased_demo_routes = pytest.importorskip(
            "app.routes.rased_demo_routes",
            reason="app.routes package failed to import; skipping route-level RASED demo tests",
        )
        from fastapi import HTTPException

        with patch.object(rased_demo_routes, "run_demo_scenario", AsyncMock(side_effect=ValueError("Unknown scenario_id: 'S999'"))):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(rased_demo_routes.demo_run(
                    "S999", rased_demo_routes.RunDemoRequest(), current_user={"email": "t", "role": "admin"},
                ))
        assert exc_info.value.status_code == 404
