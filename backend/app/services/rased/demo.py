"""
One-click demo runner.

run_demo_scenario() regenerates a scenario's synthetic data via the exact
same generate_scenario() the pytest suite and the admin scenario route use,
reads the alerts back out of MongoSink's target collection, and drives them
through run_investigation() — the same driver the live /incidents/trigger
webhook uses. This isn't a special demo-only code path; it's the Phase 0
generator and the Phase 5 investigation driver wired together, so what a
judge watches is the real system, not a scripted replay.

reset_demo_data() clears every RASED-owned collection so a demo can be
re-run without a prior run's data biasing the metrics strip or leaving a
stale incident in the feed.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ...models.rased_schemas import Alert, InvestigationState
from .config import ALERTS_COLLECTION, DEFAULT_SEED, EVIDENCE_COLLECTION, EXECUTION_MODE, SOURCE_COLLECTIONS
from .data import MongoSink, SCENARIOS, generate_scenario
from .graph.runner import run_investigation

logger = logging.getLogger(__name__)

RASED_COLLECTIONS = [
    ALERTS_COLLECTION,
    EVIDENCE_COLLECTION,
    *SOURCE_COLLECTIONS.values(),
    "rased_investigations",
    "rased_trace",
    "rased_trace_counters",
    "rased_cases",
    "rased_checkpoints",
]


async def run_demo_scenario(scenario_id: str, seed: Optional[int] = None) -> Dict[str, Any]:
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario_id: {scenario_id!r}. Known: {sorted(SCENARIOS)}")

    from ...core.database import db

    generation = await generate_scenario(scenario_id, MongoSink(), seed=seed if seed is not None else DEFAULT_SEED)

    docs = await db[ALERTS_COLLECTION].find(
        {"scenario_id": scenario_id}, {"_id": 0, "scenario_id": 0},
    ).to_list(200)
    alerts = [Alert(**doc) for doc in docs]

    now = datetime.now(timezone.utc)
    incident_id = f"{scenario_id}-run-{now.strftime('%H%M%S')}"
    initial_state = InvestigationState(
        incident_id=incident_id, execution_mode=EXECUTION_MODE, alerts=alerts,
        created_at=now, updated_at=now,
    )

    doc = initial_state.model_dump()
    doc["updated_at"] = now
    await db.rased_investigations.update_one({"incident_id": incident_id}, {"$set": doc}, upsert=True)

    asyncio.create_task(_drive_demo(initial_state))

    return {
        "incident_id": incident_id,
        "scenario_id": scenario_id,
        "scenario_name": generation.name,
        "seed": generation.seed,
        "alert_count": generation.alert_count,
        "execution_mode": EXECUTION_MODE,
    }


async def _drive_demo(initial_state: InvestigationState) -> None:
    from ...core.database import db
    try:
        final_state = await run_investigation(initial_state)
    except Exception as exc:
        logger.exception(f"rased demo run {initial_state.incident_id} failed")
        final_state = initial_state.model_copy(update={"status": "escalated", "error": str(exc)})
    doc = final_state.model_dump()
    doc["updated_at"] = datetime.now(timezone.utc)
    await db.rased_investigations.update_one({"incident_id": initial_state.incident_id}, {"$set": doc}, upsert=True)


async def reset_demo_data() -> Dict[str, int]:
    from ...core.database import db
    deleted_counts: Dict[str, int] = {}
    for collection_name in RASED_COLLECTIONS:
        result = await db[collection_name].delete_many({})
        deleted_counts[collection_name] = result.deleted_count
    return deleted_counts


__all__ = ["run_demo_scenario", "reset_demo_data", "RASED_COLLECTIONS"]
