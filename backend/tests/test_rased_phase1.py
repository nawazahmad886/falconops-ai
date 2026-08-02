"""
RASED Phase 1 acceptance tests: orchestrator, telemetry retrieval, guarded
node contract.

Agent classes are exercised directly via their .run(state) coroutine — this
tests the real orchestration/retrieval logic without requiring a live
LangGraph install, Mongo, or Redis. TraceRecorder (which does touch Mongo and
Redis) only runs inside guarded_node, so it's mocked in the one test that
covers that wrapper.

The compiled StateGraph (build_graph()) is only exercised if langgraph
actually imports in this environment — see the module-level importorskip
below. No local Python interpreter was available while authoring Phase 1 to
confirm langgraph==1.2.10 imports cleanly (see Phase 0's dependency
resolution report and the risk notes in graph/checkpointer.py and
graph/workflow.py), so that path is guarded rather than assumed to work.
"""
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.rased_schemas import Alert, InvestigationState, ToolResult
from app.services.metrics_timeseries_service import metrics_timeseries_service as mts_singleton
from app.services.rased.agents.orchestrator import OrchestratorAgent
from app.services.rased.agents.telemetry import TelemetryRetrievalAgent
import app.services.rased.agents.telemetry as telemetry_module
from app.services.rased.data import InMemorySink, generate_scenario

ANCHOR = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


def _state(alerts, **overrides) -> InvestigationState:
    now = datetime.now(timezone.utc)
    defaults = dict(
        incident_id="test-incident-1",
        execution_mode="simulated",
        alerts=alerts,
        confidence=0.0,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return InvestigationState(**defaults)


async def _scenario_alerts(scenario_id: str, seed: int = 42):
    sink = InMemorySink()
    await generate_scenario(scenario_id, sink, seed=seed, anchor_time=ANCHOR)
    return sink.alerts[scenario_id]


def _no_redis():
    return patch.object(mts_singleton, "get_redis", AsyncMock(return_value=None))


def _empty_evidence_db_mock() -> MagicMock:
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find.return_value.to_list = AsyncMock(return_value=[])
    return mock_db


class TestOrchestratorAgent:
    def test_no_alerts_resolves(self):
        state = _state([])
        result = asyncio.run(OrchestratorAgent().run(state))
        assert result["status"] == "resolved"

    def test_root_signature_is_majority_signature(self):
        alerts = [
            Alert(alert_id="a1", signature="sig-a", source="db", service="svc", severity="high",
                  title="t", description="d", observed_at=ANCHOR, raw={}),
            Alert(alert_id="a2", signature="sig-a", source="db", service="svc", severity="high",
                  title="t", description="d", observed_at=ANCHOR, raw={}),
            Alert(alert_id="a3", signature="sig-b", source="db", service="svc", severity="high",
                  title="t", description="d", observed_at=ANCHOR, raw={}),
        ]
        assert OrchestratorAgent._pick_root_signature(alerts) == "sig-a"

    def test_s1_routes_to_investigating_with_correct_signature(self):
        alerts = asyncio.run(_scenario_alerts("S1"))
        state = _state(alerts)
        with _no_redis():
            result = asyncio.run(OrchestratorAgent().run(state))
        assert result["status"] == "investigating"
        assert result["root_signature"] == "checkout-api:elevated-error-rate"

    def test_s5_storm_of_40plus_alerts_suppresses(self):
        alerts = asyncio.run(_scenario_alerts("S5"))
        assert len(alerts) >= 40
        state = _state(alerts)
        with _no_redis():
            result = asyncio.run(OrchestratorAgent().run(state))
        assert result["status"] == "suppressed"
        assert result["root_signature"] == "edge-router-cluster:network-flap"

    def test_dedup_window_suppresses_second_call(self):
        alerts = asyncio.run(_scenario_alerts("S1"))
        state = _state(alerts)

        fake_redis = MagicMock()
        # first call: key not present -> SET NX succeeds -> not a duplicate
        # second call: key present -> SET NX returns None -> is a duplicate
        fake_redis.set = AsyncMock(side_effect=[True, None])

        with patch.object(mts_singleton, "get_redis", AsyncMock(return_value=fake_redis)):
            first = asyncio.run(OrchestratorAgent().run(state))
            second = asyncio.run(OrchestratorAgent().run(state))

        assert first["status"] == "investigating"
        assert second["status"] == "suppressed"

    def test_correlation_wrapper_failure_does_not_crash_orchestrate(self):
        alerts = asyncio.run(_scenario_alerts("S1"))
        state = _state(alerts)
        with _no_redis(), patch(
            "app.services.rased.correlation.correlate_alerts",
            side_effect=RuntimeError("shape mismatch"),
        ):
            result = asyncio.run(OrchestratorAgent().run(state))
        assert result["status"] == "investigating"


class TestTelemetryRetrievalAgent:
    def test_concurrent_retrieval_bounded_by_slowest_adapter(self):
        alerts = asyncio.run(_scenario_alerts("S1"))
        state = _state(alerts)

        async def slow_stub(params):
            await asyncio.sleep(0.05)
            return ToolResult(source="elk", query="x", success=True, data=[], latency_ms=50, retrieved_at=datetime.now(timezone.utc))

        with patch.dict(
            telemetry_module.ADAPTERS,
            {name: MagicMock(source=name, query=AsyncMock(side_effect=slow_stub)) for name in telemetry_module.ADAPTERS},
            clear=False,
        ), patch("app.core.database.db", _empty_evidence_db_mock()):
            started = time.perf_counter()
            asyncio.run(TelemetryRetrievalAgent().run(state))
            elapsed = time.perf_counter() - started

        # 7 adapters at 0.05s each: sequential would be ~0.35s+, concurrent
        # should stay close to a single adapter's delay.
        assert elapsed < 0.25, f"retrieval took {elapsed:.3f}s — adapters do not appear to run concurrently"

    def test_timed_out_adapter_degrades_confidence_without_raising(self):
        alerts = asyncio.run(_scenario_alerts("S1"))
        state = _state(alerts, confidence=0.8)

        async def hangs(params):
            await asyncio.sleep(10)

        adapters = dict(telemetry_module.ADAPTERS)
        adapters["elk"] = MagicMock(source="elk", query=AsyncMock(side_effect=hangs))

        with patch.object(telemetry_module, "ADAPTER_TIMEOUT_SECONDS", 0.02), \
             patch.dict(telemetry_module.ADAPTERS, adapters, clear=False), \
             patch("app.core.database.db", _empty_evidence_db_mock()):
            result = asyncio.run(TelemetryRetrievalAgent().run(state))

        assert result["confidence"] < 0.8

    def test_scenario_id_inferred_from_alert_id_convention(self):
        alerts = asyncio.run(_scenario_alerts("S4"))
        assert TelemetryRetrievalAgent._infer_scenario_id(_state(alerts)) == "S4"

    def test_no_alerts_infers_no_scenario(self):
        assert TelemetryRetrievalAgent._infer_scenario_id(_state([])) is None

    def test_loads_pre_tiered_evidence_and_merges_into_state(self):
        alerts = asyncio.run(_scenario_alerts("S1"))
        state = _state(alerts)

        evidence_doc = {
            "evidence_id": "S1-ev-01", "tier": "trigger", "source": "db",
            "query": "alert.raw.db_connection_pool_pct", "summary": "pool saturation",
            "data": {"pool_usage_pct": 92.0}, "observed_at": ANCHOR, "retrieved_at": ANCHOR,
        }
        mock_db = MagicMock()
        mock_db.__getitem__.return_value.find.return_value.to_list = AsyncMock(return_value=[evidence_doc])

        async def instant_ok(params):
            return ToolResult(source="db", query="x", success=True, data=[], latency_ms=1, retrieved_at=datetime.now(timezone.utc))

        with patch.dict(
            telemetry_module.ADAPTERS,
            {name: MagicMock(source=name, query=AsyncMock(side_effect=instant_ok)) for name in telemetry_module.ADAPTERS},
            clear=False,
        ), patch("app.core.database.db", mock_db):
            result = asyncio.run(TelemetryRetrievalAgent().run(state))

        assert len(result["evidence"]) == 1
        assert result["evidence"][0].evidence_id == "S1-ev-01"


class TestGuardedNode:
    def test_node_never_raises_records_error_and_lowers_confidence(self):
        from app.services.rased.agents.base import guarded_node

        @guarded_node("broken_agent")
        async def broken(state: InvestigationState) -> dict:
            raise RuntimeError("boom")

        state = _state([], confidence=0.6)
        with patch("app.services.rased.graph.trace.TraceRecorder.emit", AsyncMock(return_value=None)):
            result = asyncio.run(broken(state))

        assert "error" in result
        assert "broken_agent" in result["error"]
        assert result["confidence"] == pytest.approx(0.35)

    def test_node_success_passes_update_through(self):
        from app.services.rased.agents.base import guarded_node

        @guarded_node("ok_agent")
        async def ok(state: InvestigationState) -> dict:
            return {"status": "investigating"}

        state = _state([])
        with patch("app.services.rased.graph.trace.TraceRecorder.emit", AsyncMock(return_value=None)):
            result = asyncio.run(ok(state))

        assert result == {"status": "investigating"}


class TestTraceRecorder:
    def test_seq_increments_atomically_via_mongo_counter(self):
        from app.services.rased.graph.trace import TraceRecorder

        counter = {"seq": 0}

        async def fake_find_one_and_update(filter_, update, upsert, return_document):
            counter["seq"] += 1
            return {"seq": counter["seq"]}

        mock_db = MagicMock()
        mock_db.rased_trace_counters.find_one_and_update = AsyncMock(side_effect=fake_find_one_and_update)
        mock_db.rased_trace.insert_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db), _no_redis():
            recorder = TraceRecorder("incident-x")
            first = asyncio.run(recorder.emit("agent", "start", "first"))
            second = asyncio.run(recorder.emit("agent", "decision", "second"))

        assert first.seq == 1
        assert second.seq == 2

    def test_publish_and_persist_failures_do_not_raise(self):
        from app.services.rased.graph.trace import TraceRecorder

        mock_db = MagicMock()
        mock_db.rased_trace_counters.find_one_and_update = AsyncMock(side_effect=RuntimeError("mongo down"))
        mock_db.rased_trace.insert_one = AsyncMock(side_effect=RuntimeError("mongo down"))

        with patch("app.core.database.db", mock_db), patch.object(
            mts_singleton, "get_redis", AsyncMock(side_effect=RuntimeError("redis down"))
        ):
            recorder = TraceRecorder("incident-y")
            event = asyncio.run(recorder.emit("agent", "start", "title"))

        assert event.incident_id == "incident-y"


class TestBuildGraph:
    def test_graph_compiles_if_langgraph_is_importable(self):
        langgraph_graph = pytest.importorskip(
            "langgraph.graph",
            reason="langgraph not importable in this environment — graph-level "
            "wiring is unverified here, see graph/workflow.py's risk note",
        )
        from app.services.rased.graph.workflow import build_graph

        fake_checkpointer = MagicMock()
        compiled = build_graph(checkpointer=fake_checkpointer)
        assert compiled is not None
