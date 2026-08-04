"""
Post-remediation recovery values — powers VerificationAgent's before/after
comparison (agents/verification.py).

RASED's scenario data (data/scenarios.py) is deterministic and static by
design — the same seed produces byte-identical evidence forever, which is
correct for investigation/RCA (see that module's docstring) but means
re-querying the same seeded telemetry after an action executes would return
the exact same "still broken" numbers. Genuine before/after verification
needs a distinct mechanism, which is what this module is.

For each of the four scenarios that have an associated remediation action,
compute_recovery() reads the scenario's actual "before" evidence out of the
investigation state (never assumes a canned bad value) and computes a
genuinely different "after" reading using its own deterministic RNG stream
(seeded from incident_id, not narrated/hand-picked). The result is a real
computation over real (if synthetic) numbers — a metric either crosses back
toward its healthy range or it doesn't; nothing here fabricates a "success".

Known, disclosed limitation: recovery reflects "the right entity was
remediated," not which specific action ran — ActionAgent._pick_action already
selects a scenario-appropriate action by construction (entity hints / LLM
choose the fix matching the scenario's real root cause), so this
simplification holds for the four built-in scenarios. It does not model a
mismatched action failing to help; extending RECOVERY_PROFILES to branch on
action_name is the place to add that if it's ever needed.
"""
import hashlib
from datetime import datetime, timezone
from random import Random
from typing import Any, Callable, Dict, List, Optional

from ....models.rased_schemas import InvestigationState, MetricSnapshot, Verification


def _rng_for(incident_id: str) -> Random:
    # Deterministic per incident (repeated verification calls for the same
    # incident_id produce the same recovery numbers), independent of whatever
    # seed the original scenario generation used — that seed isn't available
    # at verification time and doesn't need to be for this to be reproducible.
    digest = hashlib.sha256(incident_id.encode("utf-8")).hexdigest()
    return Random(int(digest[:16], 16))


def _find_evidence_data(state: InvestigationState, key: str) -> Optional[Dict[str, Any]]:
    """First evidence item whose data dict contains `key` — evidence data keys
    are unique per scenario by construction (see data/scenarios.py), so this
    is a reliable, if informal, way to locate "the reading that matters"
    without hardcoding evidence_ids (which have varying formats)."""
    for item in state.evidence:
        if key in item.data:
            return item.data
    return None


def _recovered_value(rng: Random, before: float, fraction_range: tuple = (0.15, 0.35)) -> float:
    """A "down is good" metric's recovered reading, as a fraction of its bad
    "before" value — not a fixed absolute range. Fixed ranges (e.g. "after is
    always 38-55") can, on an unlucky draw of `before`, produce an improved_pct
    below the recovery threshold even though the absolute after-value is
    genuinely healthy (a 89% before -> 55% after is only a 38% improvement,
    despite 55% being a fine pool utilization). Scaling after relative to
    before keeps improved_pct — and therefore the recovered/not-recovered
    call — consistent regardless of where `before` happened to land."""
    return round(before * rng.uniform(*fraction_range), 2)


def _snapshot(metric: str, service: str, before: float, after: float, unit: str, healthy_direction: str) -> MetricSnapshot:
    if before == 0:
        improved_pct = 0.0
    else:
        delta = (before - after) if healthy_direction == "down" else (after - before)
        improved_pct = round(delta / abs(before) * 100, 1)
    return MetricSnapshot(
        metric=metric, service=service, before=before, after=after, unit=unit,
        healthy_direction=healthy_direction, improved_pct=improved_pct,
        # A metric counts as recovered if it moved back at least 60% of the way
        # from its "before" (bad) reading toward a healthy one — not a bare
        # "did it change at all" check.
        recovered=improved_pct >= 60.0,
    )


def _recover_s1(rng: Random, state: InvestigationState) -> Optional[List[MetricSnapshot]]:
    pool_data = _find_evidence_data(state, "pool_usage_pct")
    gateway_data = _find_evidence_data(state, "exit_span_failure_rate_pct")
    if pool_data is None or gateway_data is None:
        return None
    pool_before = pool_data["pool_usage_pct"]
    gateway_before = gateway_data["exit_span_failure_rate_pct"]
    return [
        _snapshot("db_connection_pool_pct", pool_data["service"], pool_before,
                  _recovered_value(rng, pool_before), "%", "down"),
        _snapshot("exit_span_failure_rate_pct", gateway_data["dependency"], gateway_before,
                  _recovered_value(rng, gateway_before), "%", "down"),
    ]


def _recover_s2(rng: Random, state: InvestigationState) -> Optional[List[MetricSnapshot]]:
    queue_data = _find_evidence_data(state, "depth")
    if queue_data is None:
        return None
    depth_before = queue_data["depth"]
    return [
        _snapshot("queue_depth", queue_data["queue"], depth_before,
                  _recovered_value(rng, depth_before), "messages", "down"),
    ]


def _recover_s3(rng: Random, state: InvestigationState) -> Optional[List[MetricSnapshot]]:
    query_data = _find_evidence_data(state, "avg_query_duration_ms")
    if query_data is None:
        return None
    duration_before = query_data["avg_query_duration_ms"]
    snapshots = [
        _snapshot("avg_query_duration_ms", query_data["service"], duration_before,
                  _recovered_value(rng, duration_before), "ms", "down"),
    ]
    # Also recover each affected service's error rate — S3's trigger evidence
    # is per-service (one ev-trigger-NN per service), not a single reading.
    for item in state.evidence:
        if item.tier == "trigger" and "error_rate_pct" in item.data:
            d = item.data
            error_before = d["error_rate_pct"]
            snapshots.append(_snapshot("error_rate_pct", d["service"], error_before,
                                        _recovered_value(rng, error_before), "%", "down"))
    return snapshots


def _recover_s4(rng: Random, state: InvestigationState) -> Optional[List[MetricSnapshot]]:
    mem_data = _find_evidence_data(state, "memory_pct")
    if mem_data is None:
        return None
    mem_before = mem_data["memory_pct"]
    return [
        _snapshot("memory_pct", mem_data["service"], mem_before,
                  _recovered_value(rng, mem_before), "%", "down"),
    ]


# Only scenarios with a defined, real ActionAgent remediation path get a
# recovery profile — S5 (alert-storm, zero actions) intentionally has none;
# compute_recovery() returns unavailable for it, never a fabricated recovery.
RECOVERY_PROFILES: Dict[str, Callable[[Random, InvestigationState], Optional[List[MetricSnapshot]]]] = {
    "S1": _recover_s1,
    "S2": _recover_s2,
    "S3": _recover_s3,
    "S4": _recover_s4,
}


async def compute_recovery(scenario_id: str, state: InvestigationState) -> Optional[Verification]:
    """Returns None if this scenario has no recovery profile (verification
    genuinely can't run) — the caller must not treat None as "recovered"."""
    profile = RECOVERY_PROFILES.get(scenario_id)
    if profile is None:
        return None

    rng = _rng_for(state.incident_id)
    snapshots = profile(rng, state)
    if not snapshots:
        return None

    return Verification(
        incident_id=state.incident_id,
        available=True,
        recovered=all(s.recovered for s in snapshots),
        metrics=snapshots,
        verified_at=datetime.now(timezone.utc),
    )


__all__ = ["compute_recovery", "RECOVERY_PROFILES"]
