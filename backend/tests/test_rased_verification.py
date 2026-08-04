"""
Tests for RASED's VerificationAgent / data/recovery.py.

Unit-style, no real Mongo — compute_recovery() is a pure function of
(scenario_id, InvestigationState), and VerificationAgent's persist/trace calls
are mocked out so the agent's status-transition logic is what's actually
under test.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.rased_schemas import (
    Action, ActionResult, ActionSpec, Alert, Evidence, InvestigationState,
)
from app.services.rased.data.recovery import compute_recovery, RECOVERY_PROFILES
from app.services.rased.agents.verification import VerificationAgent

NOW = datetime(2026, 8, 3, 15, 0, 0, tzinfo=timezone.utc)


def _s1_state(status: str = "resolved", action_success: bool = True) -> InvestigationState:
    alert = Alert(
        alert_id="S1-alert-01", signature="checkout-api:elevated-error-rate", source="db",
        service="checkout-api", severity="critical", title="t", description="d",
        observed_at=NOW, raw={},
    )
    evidence = [
        Evidence(
            evidence_id="S1-ev-01", tier="trigger", source="db", query="q",
            summary="s", data={"service": "invoice-db", "pool_usage_pct": 92.0},
            observed_at=NOW, retrieved_at=NOW,
        ),
        Evidence(
            evidence_id="S1-ev-03", tier="deep", source="appdynamics", query="q",
            summary="s", data={"dependency": "payment-gateway", "exit_span_failure_rate_pct": 34.0},
            observed_at=NOW, retrieved_at=NOW,
        ),
    ]
    spec = ActionSpec(tier="GUARDED", adapter="k8s_mock", description="d")
    action = Action(
        action_id="a1", incident_id="S1-run-150000", name="restart_pod", spec=spec,
        status="executed", proposed_at=NOW,
    )
    result = ActionResult(
        action_id="a1", incident_id="S1-run-150000", success=action_success,
        execution_mode="simulated", executed_at=NOW,
    )
    return InvestigationState(
        incident_id="S1-run-150000", execution_mode="simulated", status=status,
        alerts=[alert], evidence=evidence, actions=[action], action_results=[result],
        confidence=0.91, created_at=NOW, updated_at=NOW,
    )


def test_recovery_profiles_cover_scenarios_with_actions():
    # S1-S4 have real ActionAgent remediation paths; S5 (alert storm) never
    # proposes an action at all, so it must not have a recovery profile.
    assert set(RECOVERY_PROFILES) == {"S1", "S2", "S3", "S4"}


def test_compute_recovery_s1_always_crosses_threshold():
    state = _s1_state()
    for _ in range(50):
        # Different incident_id each time -> different rng stream -> exercises
        # the full width of the recovered-value distribution, not one draw.
        state.incident_id = f"S1-run-{_:04d}"
        result = asyncio.run(compute_recovery("S1", state))
        assert result is not None
        assert result.available is True
        assert result.recovered is True, f"metrics didn't clear the recovery threshold: {result.metrics}"
        for m in result.metrics:
            assert m.after < m.before
            assert m.improved_pct >= 60.0


def test_compute_recovery_unknown_scenario_returns_none():
    state = _s1_state()
    result = asyncio.run(compute_recovery("S5", state))
    assert result is None


def test_compute_recovery_missing_evidence_returns_none():
    state = _s1_state()
    state.evidence = []  # no pool/gateway evidence to compute a "before" from
    result = asyncio.run(compute_recovery("S1", state))
    assert result is None


def test_verification_agent_noop_when_not_resolved():
    state = _s1_state(status="escalated")
    update = asyncio.run(VerificationAgent().run(state))
    assert update == {}


def test_verification_agent_noop_when_action_failed():
    state = _s1_state(status="resolved", action_success=False)
    update = asyncio.run(VerificationAgent().run(state))
    assert update == {}


@patch("app.services.rased.agents.verification.VerificationAgent._persist", new_callable=AsyncMock)
@patch("app.services.rased.agents.verification.VerificationAgent._emit_trace", new_callable=AsyncMock)
def test_verification_agent_marks_resolved_on_real_recovery(mock_trace, mock_persist):
    state = _s1_state(status="resolved")
    update = asyncio.run(VerificationAgent().run(state))
    assert update["status"] == "resolved"
    assert update["verification"].available is True
    assert update["verification"].recovered is True
    mock_persist.assert_awaited_once()


@patch("app.services.rased.agents.verification.VerificationAgent._persist", new_callable=AsyncMock)
@patch("app.services.rased.agents.verification.VerificationAgent._emit_trace", new_callable=AsyncMock)
def test_verification_agent_reopens_when_recovery_fails(mock_trace, mock_persist):
    state = _s1_state(status="resolved")
    with patch(
        "app.services.rased.agents.verification.compute_recovery",
        new_callable=AsyncMock,
    ) as mock_compute:
        from app.models.rased_schemas import MetricSnapshot, Verification
        mock_compute.return_value = Verification(
            incident_id=state.incident_id, available=True, recovered=False,
            metrics=[MetricSnapshot(
                metric="db_connection_pool_pct", service="invoice-db", before=92.0, after=88.0,
                unit="%", healthy_direction="down", improved_pct=4.3, recovered=False,
            )],
            verified_at=NOW,
        )
        update = asyncio.run(VerificationAgent().run(state))
    assert update["status"] == "escalated"
    assert update["verification"].recovered is False


def test_verification_agent_never_fabricates_when_unavailable():
    state = _s1_state(status="resolved")
    state.alerts = []  # no alert -> no inferable scenario_id -> can't run at all
    update = asyncio.run(VerificationAgent().run(state))
    assert update == {}
