"""
FalconOps AI - Query Analyzer Routes
SQL query analysis and optimization suggestions
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services.query_analyzer_service import (
    analyze_query,
    analyze_and_store,
    get_slow_queries,
    get_query_stats,
)

router = APIRouter(prefix="/api/query-analyzer", tags=["Query Analyzer"])


class AnalyzeRequest(BaseModel):
    query: str
    db_id: Optional[str] = ""
    duration_ms: Optional[float] = 0


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, current_user: dict = Depends(require_auth)):
    """Analyze a SQL query and return optimization findings"""
    result = await analyze_and_store(req.query, req.db_id, req.duration_ms)
    return result


@router.post("/analyze/quick")
async def analyze_quick(req: AnalyzeRequest, current_user: dict = Depends(require_auth)):
    """Quick analyze without storing to DB"""
    return analyze_query(req.query)


@router.get("/slow-queries")
async def slow_queries(
    db_id: Optional[str] = Query(None),
    hours: int = Query(24),
    limit: int = Query(50, le=200),
    current_user: dict = Depends(require_auth),
):
    """Get analyzed slow queries"""
    return await get_slow_queries(db_id, hours, limit)


@router.get("/stats")
async def stats(
    hours: int = Query(24),
    current_user: dict = Depends(require_auth),
):
    """Get query analysis statistics"""
    return await get_query_stats(hours)
