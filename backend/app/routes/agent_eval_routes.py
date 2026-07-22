"""
FalconOps AI - Agent Evaluation Routes
Run YAML test sets against real FalconOps agents and track trajectory/score history —
see agent_eval_service.py for the full design.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from ..utils.auth import require_auth
from ..services import agent_eval_service

router = APIRouter(prefix="/api/agent-eval", tags=["Agent Evaluation"])


@router.get("/test-sets")
async def get_test_sets(current_user: dict = Depends(require_auth)):
    """List available YAML test sets (backend/eval/agent_test_sets/*.yaml)."""
    return {"test_sets": agent_eval_service.list_test_sets()}


@router.post("/run/{test_set_name}")
async def run_test_set(test_set_name: str, current_user: dict = Depends(require_auth)):
    """Run every question in a test set through its target agent, scoring each
    resulting trajectory (deterministic checks + an LLM-as-judge quality score)."""
    try:
        return await agent_eval_service.run_test_set(test_set_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/history")
async def get_history(
    test_set: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth),
):
    """Run history (score trend) for one or all test sets."""
    runs = await agent_eval_service.get_run_history(test_set=test_set, limit=limit)
    return {"runs": runs}


@router.get("/compare")
async def compare_runs(
    run: str = Query(..., description="Current run_id"),
    baseline: str = Query(..., description="Baseline run_id to compare against"),
    current_user: dict = Depends(require_auth),
):
    """Real per-question score diff between two runs — flags regressions."""
    return await agent_eval_service.compare_to_baseline(run, baseline)
