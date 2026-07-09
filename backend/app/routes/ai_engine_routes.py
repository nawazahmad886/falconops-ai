"""
FalconOps AI — Autonomous AI Engine Routes
Public surface for the unified pipeline + cost optimizer + prevention + insights.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_admin
from ..services import ai_pipeline, prevention_engine, cost_optimizer, context_engine, noise_reducer

router = APIRouter(prefix="/api/ai-engine", tags=["AI Engine"])


class ProcessEventRequest(BaseModel):
    event: dict


class TopologyUpsert(BaseModel):
    service: str
    upstream: Optional[List[str]] = None
    downstream: Optional[List[str]] = None
    tier: Optional[str] = None
    owner: Optional[str] = None


class RunbookUpsert(BaseModel):
    alert_name: str
    steps: List[str]
    links: Optional[List[dict]] = None
    owner: Optional[str] = None
    matches: Optional[List[str]] = None


# ──────────────── Pipeline ────────────────

@router.post("/process")
async def process_event(body: ProcessEventRequest, user: dict = Depends(require_auth)):
    if not body.event:
        raise HTTPException(400, "event payload required")
    return await ai_pipeline.process_event(body.event)


@router.get("/insights")
async def list_insights(hours: int = Query(24, ge=1, le=720), limit: int = Query(100, ge=1, le=500),
                        user: dict = Depends(require_auth)):
    return {"insights": await ai_pipeline.list_recent_insights(hours, limit)}


@router.get("/summary")
async def insights_summary(hours: int = Query(24, ge=1, le=720), user: dict = Depends(require_auth)):
    return await ai_pipeline.get_insight_summary(hours)


# ──────────────── Prevention ────────────────

@router.post("/prevention/scan")
async def prevention_scan(admin_user: dict = Depends(require_admin)):
    """Run the prevention scan across all monitors right now (admin-triggered)."""
    return {"warnings": await prevention_engine.scan_all_monitors()}


@router.get("/prevention/warnings")
async def prevention_list(hours: int = Query(24, ge=1, le=168), user: dict = Depends(require_auth)):
    return {"warnings": await prevention_engine.list_recent_warnings(hours)}


# ──────────────── Cost optimizer ────────────────

@router.get("/cost/scan")
async def cost_scan(user: dict = Depends(require_auth)):
    return await cost_optimizer.run_cost_scan()


# ──────────────── Noise reducer ────────────────

@router.get("/noise/top-buckets")
async def noise_top(limit: int = Query(20, ge=1, le=100), user: dict = Depends(require_auth)):
    return {"buckets": await noise_reducer.get_top_noisy_buckets(limit)}


# ──────────────── Context: Topology + Runbooks ────────────────

@router.get("/context/topology/{service}")
async def topology_get(service: str, user: dict = Depends(require_auth)):
    return await context_engine.get_topology(service)


@router.put("/context/topology")
async def topology_upsert(body: TopologyUpsert, admin_user: dict = Depends(require_admin)):
    return await context_engine.upsert_topology(
        body.service, body.upstream or [], body.downstream or [], body.tier, body.owner
    )


@router.get("/context/runbook")
async def runbook_get(alert: str = Query(...), user: dict = Depends(require_auth)):
    rb = await context_engine.get_runbook(alert)
    if not rb:
        raise HTTPException(404, "Runbook not found")
    return rb


@router.put("/context/runbook")
async def runbook_upsert(body: RunbookUpsert, admin_user: dict = Depends(require_admin)):
    return await context_engine.upsert_runbook(
        body.alert_name, body.steps, body.links, body.owner, body.matches
    )


@router.post("/context/enrich")
async def context_enrich(body: ProcessEventRequest, user: dict = Depends(require_auth)):
    return await context_engine.enrich(body.event)
