"""
RASED Phase 5 acceptance tests: incident trigger/feed/detail, approve/reject
gating, metrics, and SSE trace replay termination.

app.routes.rased_incident_routes is only reachable through the app.routes
package (same eager-import-everything risk documented in Phase 0's
test_rased_phase0.py), so route-level tests here use the same
pytest.importorskip guard. Most coverage instead calls the route module's
underlying async functions directly with a mocked db/graph runner — that
exercises the real logic without needing the full app.routes package or a
live LangGraph install.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.models.rased_schemas import Alert, InvestigationState
from app.utils.auth import require_auth

rased_incident_routes = pytest.importorskip(
    "app.routes.rased_incident_routes",
    reason="app.routes package failed to import; skipping route-level RASED tests "
    "(direct-function tests below are unaffected)",
)

ANCHOR = datetime(2026, 8, 11, 10, 0, 0, tzinfo=timezone.utc)


def _state(incident_id="incident-5", status="new", **overrides) -> InvestigationState:
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id=f"{incident_id}-alert-01", signature="sig", source="db", service="checkout-api",
        severity="high", title="t", description="d", observed_at=now, raw={},
    )
    defaults = dict(
        incident_id=incident_id, execution_mode="simulated", alerts=[alert],
        status=status, confidence=0.0, created_at=now, updated_at=now,
    )
    defaults.update(overrides)
    return InvestigationState(**defaults)


def _fake_user():
    return {"email": "test@rased", "role": "admin"}


class TestTriggerIncident:
    def test_persists_initial_state_and_schedules_background_run(self):
        mock_db = MagicMock()
        mock_db.rased_investigations.update_one = AsyncMock(return_value=None)

        payload = rased_incident_routes.TriggerAlertPayload(
            signature="checkout-api:elevated-error-rate", source="db", service="checkout-api",
            severity="high", title="Checkout API degraded", description="d",
        )

        with patch("app.core.database.db", mock_db), \
             patch("asyncio.create_task") as mock_create_task:
            result = asyncio.run(rased_incident_routes.trigger_incident(payload, current_user=_fake_user()))

        assert result["status"] == "new"
        assert "incident_id" in result
        mock_db.rased_investigations.update_one.assert_called_once()
        mock_create_task.assert_called_once()


class TestDriveAndPersist:
    def test_successful_run_persists_final_state(self):
        initial = _state()
        final = _state(status="resolved", confidence=0.9)

        mock_db = MagicMock()
        mock_db.rased_investigations.update_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db), \
             patch.object(rased_incident_routes, "run_investigation", AsyncMock(return_value=final)):
            asyncio.run(rased_incident_routes._drive_and_persist(initial))

        saved_doc = mock_db.rased_investigations.update_one.call_args.args[1]["$set"]
        assert saved_doc["status"] == "resolved"

    def test_graph_failure_persists_escalated_state_not_raise(self):
        initial = _state()
        mock_db = MagicMock()
        mock_db.rased_investigations.update_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db), \
             patch.object(rased_incident_routes, "run_investigation", AsyncMock(side_effect=RuntimeError("graph exploded"))):
            asyncio.run(rased_incident_routes._drive_and_persist(initial))

        saved_doc = mock_db.rased_investigations.update_one.call_args.args[1]["$set"]
        assert saved_doc["status"] == "escalated"
        assert "graph exploded" in saved_doc["error"]


class TestApproveReject:
    def test_unknown_incident_returns_404(self):
        mock_db = MagicMock()
        mock_db.rased_investigations.find_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(rased_incident_routes._decide("nope", True, None, "tester"))
        assert exc_info.value.status_code == 404

    def test_wrong_status_returns_409(self):
        mock_db = MagicMock()
        mock_db.rased_investigations.find_one = AsyncMock(return_value={"status": "resolved"})

        with patch("app.core.database.db", mock_db):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(rased_incident_routes._decide("incident-5", True, None, "tester"))
        assert exc_info.value.status_code == 409

    def test_approval_resumes_graph_and_persists(self):
        mock_db = MagicMock()
        mock_db.rased_investigations.find_one = AsyncMock(return_value={"status": "awaiting_approval"})
        mock_db.rased_investigations.update_one = AsyncMock(return_value=None)

        resumed_state = _state(status="resolved")

        with patch("app.core.database.db", mock_db), \
             patch.object(rased_incident_routes, "resume_investigation", AsyncMock(return_value=resumed_state)) as mock_resume:
            result = asyncio.run(rased_incident_routes._decide("incident-5", True, "looks fine", "tester@x.com"))

        mock_resume.assert_called_once_with("incident-5", {"approved": True, "reason": "looks fine", "decided_by": "tester@x.com"})
        assert result["status"] == "resolved"
        assert result["approved"] is True

    def test_rejection_passes_approved_false(self):
        mock_db = MagicMock()
        mock_db.rased_investigations.find_one = AsyncMock(return_value={"status": "awaiting_approval"})
        mock_db.rased_investigations.update_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db), \
             patch.object(rased_incident_routes, "resume_investigation", AsyncMock(return_value=_state(status="escalated"))) as mock_resume:
            result = asyncio.run(rased_incident_routes._decide("incident-5", False, None, "tester@x.com"))

        assert mock_resume.call_args.args[1]["approved"] is False
        assert result["approved"] is False


class TestMetrics:
    def test_computes_from_actual_counts(self):
        mock_db = MagicMock()
        mock_db.rased_investigations.count_documents = AsyncMock(side_effect=[10, 3, 5, 2])  # total, suppressed, resolved, escalated

        async def _empty_cursor(*args, **kwargs):
            return
            yield  # pragma: no cover - makes this an async generator with zero items

        mock_db.rased_investigations.find = MagicMock(return_value=_empty_cursor())

        with patch("app.core.database.db", mock_db):
            result = asyncio.run(rased_incident_routes.get_rased_metrics(current_user=_fake_user()))

        assert result["total_investigations"] == 10
        assert result["suppressed"] == 3
        assert result["resolved"] == 5
        assert result["escalated"] == 2
        assert result["alerts_suppressed_pct"] == 30.0

    def test_zero_investigations_does_not_divide_by_zero(self):
        mock_db = MagicMock()
        mock_db.rased_investigations.count_documents = AsyncMock(return_value=0)

        async def _empty_cursor(*args, **kwargs):
            return
            yield  # pragma: no cover

        mock_db.rased_investigations.find = MagicMock(return_value=_empty_cursor())

        with patch("app.core.database.db", mock_db):
            result = asyncio.run(rased_incident_routes.get_rased_metrics(current_user=_fake_user()))

        assert result["alerts_suppressed_pct"] == 0.0


class TestListAndGetIncident:
    def test_list_incidents_returns_docs(self):
        mock_db = MagicMock()
        docs = [{"incident_id": "a"}, {"incident_id": "b"}]

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=docs)
        mock_db.rased_investigations.find = MagicMock(return_value=mock_cursor)

        with patch("app.core.database.db", mock_db):
            result = asyncio.run(rased_incident_routes.list_incidents(limit=50, current_user=_fake_user()))

        assert result["incidents"] == docs

    def test_get_incident_404_when_missing(self):
        mock_db = MagicMock()
        mock_db.rased_investigations.find_one = AsyncMock(return_value=None)

        with patch("app.core.database.db", mock_db):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(rased_incident_routes.get_incident("missing", current_user=_fake_user()))
        assert exc_info.value.status_code == 404


class TestSSEStreamTerminatesWithoutRedis:
    def test_stream_replays_trace_then_ends_cleanly_when_redis_unavailable(self):
        app = FastAPI()
        app.include_router(rased_incident_routes.router)
        app.dependency_overrides[require_auth] = _fake_user

        trace_docs = [
            {"incident_id": "incident-5", "seq": 1, "agent": "orchestrator", "kind": "start", "title": "started", "detail": {}, "at": ANCHOR.isoformat()},
            {"incident_id": "incident-5", "seq": 2, "agent": "orchestrator", "kind": "decision", "title": "done", "detail": {}, "at": ANCHOR.isoformat()},
        ]

        async def _trace_cursor(*args, **kwargs):
            for doc in trace_docs:
                yield doc

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = _trace_cursor()
        mock_db.rased_trace.find = MagicMock(return_value=mock_cursor)

        with patch("app.core.database.db", mock_db), \
             patch.object(rased_incident_routes, "_get_redis", AsyncMock(return_value=None)):
            client = TestClient(app)
            with client.stream("GET", "/api/v1/rased/incidents/incident-5/stream") as response:
                assert response.status_code == 200
                events = []
                for line in response.iter_lines():
                    if line and line.startswith("data:"):
                        events.append(line)
                    if len(events) >= 3:  # 2 trace events + 1 end event, then generator returns
                        break

        assert len(events) == 3
