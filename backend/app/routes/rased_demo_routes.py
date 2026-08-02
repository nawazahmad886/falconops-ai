"""
RASED Phase 6 demo routes: one-click scenario run and full reset.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services.rased.demo import reset_demo_data, run_demo_scenario
from ..utils.auth import require_admin

router = APIRouter(prefix="/api/v1/rased/demo", tags=["RASED Demo"])


class RunDemoRequest(BaseModel):
    seed: Optional[int] = None


@router.post("/run/{scenario_id}")
async def demo_run(
    scenario_id: str,
    payload: RunDemoRequest = RunDemoRequest(),
    current_user: dict = Depends(require_admin),
):
    try:
        return await run_demo_scenario(scenario_id, seed=payload.seed)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/reset")
async def demo_reset(current_user: dict = Depends(require_admin)):
    deleted = await reset_demo_data()
    return {"reset": True, "deleted_counts": deleted}


__all__ = ["router"]
