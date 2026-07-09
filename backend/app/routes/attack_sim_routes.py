"""
FalconOps AI - Attack Simulation Routes
Red team simulation API endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access
from ..services.attack_simulator_service import (
    run_simulation,
    get_available_scenarios,
    get_simulation_history,
)

router = APIRouter(prefix="/api/security/attack-sim", tags=["Attack Simulation"])


class SimulationRequest(BaseModel):
    scenario_id: str
    config: Optional[dict] = None


@router.get("/scenarios")
async def list_scenarios(current_user: dict = Depends(require_auth)):
    """Get available attack simulation scenarios"""
    return get_available_scenarios()


@router.post("/run")
async def execute_simulation(
    req: SimulationRequest,
    current_user: dict = Depends(require_write_access),
):
    """Run an attack simulation"""
    return await run_simulation(req.scenario_id, req.config)


@router.get("/history")
async def simulation_history(
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth),
):
    """Get simulation run history"""
    return await get_simulation_history(limit)
