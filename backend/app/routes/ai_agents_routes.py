"""
FalconOps AI - AI Agent Routes
Multi-agent orchestration: RCA, Alert Summarizer, Auto-Healing
Supports Emergent Key (cloud) | OpenAI Key (on-premise) | Heuristic fallback
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_admin
from ..services.ai_agents_service import (
    run_agent, run_crew, get_analysis_history, get_agent_stats, AGENTS, get_llm,
    recall_similar, get_memory_stats, clear_memory,
    get_pipeline_config, set_pipeline_enabled, trigger_from_rule,
    get_pipeline_events, get_pipeline_stats,
)

router = APIRouter(prefix="/api/ai", tags=["AI Agents"])


class AnalyzeRequest(BaseModel):
    data: dict
    agents: Optional[List[str]] = None
    parallel: bool = False


class SingleAgentRequest(BaseModel):
    data: dict


class MemorySearchRequest(BaseModel):
    data: dict
    agent_id: Optional[str] = None
    limit: int = 5


class PipelineToggleRequest(BaseModel):
    enabled: bool


class SimulateTriggerRequest(BaseModel):
    rule_id: str
    rule_name: str
    severity: str = "warning"
    metric: str = ""
    threshold: float = 0
    event_data: dict = {}


# ======================== AGENTS ========================

@router.get("/agents")
async def list_agents(current_user: dict = Depends(require_auth)):
    """List available AI agents and current LLM mode"""
    llm = get_llm()
    return {
        "agents": [{"id": k, "name": v["name"], "role": v["role"]} for k, v in AGENTS.items()],
        "llm_mode": llm.get_mode_info(),
    }


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, current_user: dict = Depends(require_auth)):
    """Run AI agent crew on data"""
    return await run_crew(req.data, req.agents, req.parallel)


@router.post("/agent/{agent_id}")
async def run_single(agent_id: str, req: SingleAgentRequest, current_user: dict = Depends(require_auth)):
    """Run a single AI agent"""
    return await run_agent(agent_id, req.data)


@router.get("/history")
async def history(
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth),
):
    """Get AI analysis history"""
    return await get_analysis_history(limit)


@router.get("/stats")
async def stats(current_user: dict = Depends(require_auth)):
    """Get AI agent statistics"""
    return await get_agent_stats()


# ======================== MEMORY ========================

@router.post("/memory/search")
async def search_memory(req: MemorySearchRequest, current_user: dict = Depends(require_auth)):
    """Search agent memory for similar past incidents"""
    return await recall_similar(req.data, req.agent_id, req.limit)


@router.get("/memory/stats")
async def memory_stats(current_user: dict = Depends(require_auth)):
    """Get memory statistics"""
    return await get_memory_stats()


@router.delete("/memory/clear")
async def memory_clear(
    agent_id: Optional[str] = Query(None),
    older_than_days: Optional[int] = Query(None),
    current_user: dict = Depends(require_admin),
):
    """Clear agent memory (admin only)"""
    return await clear_memory(agent_id, older_than_days)


# ======================== PIPELINE ========================

@router.get("/pipeline/config")
async def pipeline_config(current_user: dict = Depends(require_auth)):
    """Get pipeline configuration"""
    return await get_pipeline_config()


@router.post("/pipeline/toggle")
async def pipeline_toggle(req: PipelineToggleRequest, current_user: dict = Depends(require_admin)):
    """Enable/disable auto-trigger pipeline (admin only)"""
    await set_pipeline_enabled(req.enabled)
    return {"enabled": req.enabled}


@router.get("/pipeline/events")
async def pipeline_events(
    limit: int = Query(30, le=100),
    current_user: dict = Depends(require_auth),
):
    """Get pipeline trigger events"""
    return await get_pipeline_events(limit)


@router.get("/pipeline/stats")
async def pipeline_stats_endpoint(current_user: dict = Depends(require_auth)):
    """Get pipeline statistics"""
    return await get_pipeline_stats()


@router.post("/pipeline/simulate")
async def simulate_trigger(req: SimulateTriggerRequest, current_user: dict = Depends(require_admin)):
    """Simulate a rule trigger to test the pipeline (admin only)"""
    rule = {
        "rule_id": req.rule_id,
        "name": req.rule_name,
        "severity": req.severity,
        "metric": req.metric,
        "threshold": req.threshold,
        "cooldown_min": 0,
    }
    result = await trigger_from_rule(rule, req.event_data)
    if result is None:
        return {"status": "skipped", "reason": "Pipeline disabled or cooldown active"}
    return result
