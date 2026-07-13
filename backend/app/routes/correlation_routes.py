"""
FalconOps AI - NLP Alert Correlation Routes

Mounted at /api/correlation/nlp (not /api/correlation) because that prefix is already
used by app.routes.correlation for the topology/rule-based correlation engine — sharing
it previously caused GET /api/correlation/stats to silently shadow this router's real
NLP-similarity stats with the other engine's response.
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional

from ..utils.auth import require_auth, require_admin
from ..services.alert_correlation_service import (
    correlate_alerts, get_correlation_stats,
    get_correlation_config, update_correlation_config,
)

router = APIRouter(prefix="/api/correlation/nlp", tags=["Alert Correlation (NLP)"])


class UpdateConfigRequest(BaseModel):
    correlation_window_min: Optional[int] = None
    similarity_threshold: Optional[float] = None
    max_group_size: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/analyze")
async def analyze_correlations(hours: int = Query(24), current_user: dict = Depends(require_auth)):
    return await correlate_alerts(hours)


@router.get("/stats")
async def stats(hours: int = Query(24), current_user: dict = Depends(require_auth)):
    return await get_correlation_stats(hours)


@router.get("/config")
async def config(current_user: dict = Depends(require_auth)):
    return await get_correlation_config()


@router.put("/config")
async def update_config(req: UpdateConfigRequest, current_user: dict = Depends(require_admin)):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    return await update_correlation_config(updates)
