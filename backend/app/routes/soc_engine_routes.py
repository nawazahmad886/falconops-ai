"""
FalconOps AI - SOC Ingestion Routes + Admin Agent Configuration
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_admin
from ..services.soc_ingestion_service import (
    ingest_event, ingest_batch, get_recent_events,
    get_incidents, get_ingestion_stats, get_ingestion_config, update_ingestion_config,
)
from ..services.ai_agents_service import (
    AGENTS, get_llm, get_agent_stats, get_pipeline_config,
    set_pipeline_enabled, get_memory_stats, clear_memory,
)

router = APIRouter(prefix="/api/soc-engine", tags=["SOC Engine"])


# ======================== INGESTION ========================

class IngestRequest(BaseModel):
    source: Optional[str] = "api"
    service: Optional[str] = "unknown"
    severity: Optional[str] = "info"
    message: str
    host: Optional[str] = ""
    ip: Optional[str] = ""
    user: Optional[str] = ""
    category: Optional[str] = "generic"
    action: Optional[str] = ""


class BatchIngestRequest(BaseModel):
    events: List[dict]


@router.post("/ingest")
async def ingest(req: IngestRequest):
    """Universal event ingestion (no auth for external sources)"""
    return await ingest_event(req.dict())


@router.post("/ingest/batch")
async def batch_ingest(req: BatchIngestRequest):
    """Batch ingest multiple events"""
    return await ingest_batch(req.events)


@router.get("/events")
async def events(
    limit: int = Query(50, le=200),
    source: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    current_user: dict = Depends(require_auth),
):
    return await get_recent_events(limit, source, severity)


@router.get("/incidents")
async def incidents(
    status: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth),
):
    return await get_incidents(status, limit)


@router.get("/stats")
async def stats(current_user: dict = Depends(require_auth)):
    return await get_ingestion_stats()


# ======================== INGESTION CONFIG ========================

class IngestionConfigRequest(BaseModel):
    auto_correlate: Optional[bool] = None
    auto_ai_trigger: Optional[bool] = None
    correlation_window_min: Optional[int] = None
    incident_threshold: Optional[int] = None


@router.get("/config")
async def config(current_user: dict = Depends(require_auth)):
    return await get_ingestion_config()


@router.put("/config")
async def update_config(req: IngestionConfigRequest, current_user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    return await update_ingestion_config(updates)


# ======================== ADMIN AGENT CONFIGURATION ========================

class AgentConfigUpdate(BaseModel):
    agent_id: str
    name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    enabled: Optional[bool] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@router.get("/admin/agents")
async def admin_agents(current_user: dict = Depends(require_admin)):
    """Get full agent configuration for admin"""
    from ..core.database import db as database
    configs = await database.agent_configs.find({}, {"_id": 0}).to_list(20)
    config_map = {c["agent_id"]: c for c in configs}

    result = []
    for aid, agent in AGENTS.items():
        override = config_map.get(aid, {})
        result.append({
            "agent_id": aid,
            "name": override.get("name", agent["name"]),
            "role": override.get("role", agent["role"]),
            "system_prompt": override.get("system_prompt", agent["system_prompt"]),
            "enabled": override.get("enabled", True),
            "temperature": override.get("temperature", 0.3),
            "max_tokens": override.get("max_tokens", 1000),
            "is_custom": bool(override),
        })
    return result


@router.put("/admin/agents")
async def update_agent_config(req: AgentConfigUpdate, current_user: dict = Depends(require_admin)):
    """Update agent configuration (admin only)"""
    from ..core.database import db as database
    updates = {k: v for k, v in req.dict().items() if v is not None and k != "agent_id"}
    if not updates:
        return {"error": "No updates provided"}
    await database.agent_configs.update_one(
        {"agent_id": req.agent_id}, {"$set": {**updates, "agent_id": req.agent_id}}, upsert=True
    )
    return {"agent_id": req.agent_id, "updated": list(updates.keys())}


@router.get("/admin/overview")
async def admin_overview(current_user: dict = Depends(require_admin)):
    """Complete admin overview: agents, pipeline, memory, LLM status"""
    llm = get_llm()
    agent_stats = await get_agent_stats()
    pipeline_cfg = await get_pipeline_config()
    mem_stats = await get_memory_stats()
    ingestion_cfg = await get_ingestion_config()
    ingestion_stats = await get_ingestion_stats()

    return {
        "llm": llm.get_mode_info(),
        "agents": agent_stats,
        "pipeline": pipeline_cfg,
        "memory": mem_stats,
        "ingestion": {**ingestion_cfg, **ingestion_stats},
    }
