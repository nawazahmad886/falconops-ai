"""
RASED (راصد) Phase 0 routes — synthetic scenario generation and inspection.

Generation itself lives in app.services.rased.data.generate_scenario(), which
this route calls with a MongoSink. Nothing here is scenario-generation logic;
this file only turns HTTP requests into calls against that decoupled
function, so pytest can exercise the exact same generation path through an
InMemorySink with no server running.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ..services.rased.config import DEFAULT_SEED, EXECUTION_MODE
from ..services.rased.data import MongoSink, generate_scenario, list_scenarios
from ..utils.auth import require_admin

router = APIRouter(prefix="/api/rased", tags=["RASED"])


@router.get("/scenarios")
async def get_scenarios(current_user: dict = Depends(require_admin)):
    return {
        "execution_mode": EXECUTION_MODE,
        "scenarios": [
            {"scenario_id": spec.scenario_id, "name": spec.name, "description": spec.description}
            for spec in list_scenarios().values()
        ],
    }


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str, current_user: dict = Depends(require_admin)):
    spec = list_scenarios().get(scenario_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario_id: {scenario_id}")
    return {"scenario_id": spec.scenario_id, "name": spec.name, "description": spec.description}


@router.post("/scenarios/{scenario_id}/generate")
async def generate(
    scenario_id: str,
    seed: Optional[int] = None,
    current_user: dict = Depends(require_admin),
):
    try:
        result = await generate_scenario(scenario_id, MongoSink(), seed=seed if seed is not None else DEFAULT_SEED)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "scenario_id": result.scenario_id,
        "name": result.name,
        "seed": result.seed,
        "anchor_time": result.anchor_time,
        "alert_count": result.alert_count,
        "evidence_count": result.evidence_count,
        "source_record_counts": result.source_record_counts,
        "execution_mode": EXECUTION_MODE,
    }
