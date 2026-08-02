"""
RASED scenario generation — decoupled from HTTP.

generate_scenario() is the one callable both the API route and pytest call.
It never imports FastAPI, never touches a request/response object, and (with
an InMemorySink) never touches Mongo either — generation works with no
FalconOps stack running.

Determinism: the same seed AND the same anchor_time produce identical output.
anchor_time is a separate deterministic input from seed on purpose — callers
that want a live-looking "just happened" scenario pass anchor_time=None (or
omit it) and get datetime.now(); callers that need reproducibility (tests)
pass both explicitly.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random
from typing import Dict, Optional

from .scenarios import SCENARIOS, GenerationContext, ScenarioSpec
from .sinks import Sink
from ..config import DEFAULT_SEED


@dataclass
class GenerationResult:
    scenario_id: str
    name: str
    seed: int
    anchor_time: datetime
    alert_count: int
    evidence_count: int
    source_record_counts: Dict[str, int]


def list_scenarios() -> Dict[str, ScenarioSpec]:
    return dict(SCENARIOS)


async def generate_scenario(
    scenario_id: str,
    sink: Sink,
    seed: int = DEFAULT_SEED,
    anchor_time: Optional[datetime] = None,
) -> GenerationResult:
    spec = SCENARIOS.get(scenario_id)
    if spec is None:
        raise ValueError(f"Unknown scenario_id: {scenario_id!r}. Known: {sorted(SCENARIOS)}")

    anchor = anchor_time if anchor_time is not None else datetime.now(timezone.utc)
    rng = Random(seed)
    ctx = GenerationContext(scenario_id=scenario_id, rng=rng, anchor_time=anchor)

    data = spec.builder(ctx)

    await sink.clear_scenario(scenario_id)
    await sink.write_alerts(scenario_id, data.alerts)
    await sink.write_evidence(scenario_id, data.evidence)
    for source, records in data.source_records.items():
        await sink.write_source_records(scenario_id, source, records)

    return GenerationResult(
        scenario_id=scenario_id,
        name=spec.name,
        seed=seed,
        anchor_time=anchor,
        alert_count=len(data.alerts),
        evidence_count=len(data.evidence),
        source_record_counts={source: len(records) for source, records in data.source_records.items()},
    )


__all__ = ["GenerationResult", "list_scenarios", "generate_scenario"]
