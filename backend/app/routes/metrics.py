"""
FalconOps AI - Metrics Routes
API endpoints for metrics ingestion and querying
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access, get_current_user
from ..services.metrics_service import metrics_service

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


# ======================== MODELS ========================

class MetricIngest(BaseModel):
    name: str
    value: float
    unit: str = ""
    tags: Optional[dict] = None
    service: Optional[str] = None
    host: Optional[str] = None
    timestamp: Optional[str] = None


class MetricBatchIngest(BaseModel):
    metrics: List[dict]


class MetricQuery(BaseModel):
    name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    service: Optional[str] = None
    host: Optional[str] = None
    tags: Optional[dict] = None
    aggregation: str = "avg"
    resolution: str = "5m"


# ======================== ENDPOINTS ========================

@router.post("")
async def ingest_metric(
    metric: MetricIngest,
    current_user: dict = Depends(require_write_access)
):
    """Ingest a single metric data point"""
    result = await metrics_service.ingest_metric(
        name=metric.name,
        value=metric.value,
        unit=metric.unit,
        tags=metric.tags,
        service=metric.service,
        host=metric.host,
        timestamp=metric.timestamp,
        tenant_id=current_user.get("tenant_id")
    )
    return result


@router.post("/batch")
async def ingest_batch(
    batch: MetricBatchIngest,
    current_user: dict = Depends(require_write_access)
):
    """Ingest multiple metrics at once"""
    result = await metrics_service.ingest_batch(
        metrics=batch.metrics,
        tenant_id=current_user.get("tenant_id")
    )
    return result


@router.post("/query")
async def query_metrics(
    query: MetricQuery,
    current_user: dict = Depends(require_auth)
):
    """Query metrics with aggregation"""
    result = await metrics_service.query_metrics(
        name=query.name,
        start_time=query.start_time,
        end_time=query.end_time,
        service=query.service,
        host=query.host,
        tags=query.tags,
        aggregation=query.aggregation,
        resolution=query.resolution,
        tenant_id=current_user.get("tenant_id")
    )
    return result


@router.get("/latest")
async def get_latest_metrics(
    service: Optional[str] = Query(None),
    host: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    current_user: dict = Depends(require_auth)
):
    """Get the latest metrics"""
    metrics = await metrics_service.get_latest_metrics(
        service=service,
        host=host,
        tenant_id=current_user.get("tenant_id"),
        limit=limit
    )
    return {"metrics": metrics}


@router.get("/names")
async def get_metric_names(
    service: Optional[str] = Query(None),
    current_user: dict = Depends(require_auth)
):
    """Get all unique metric names"""
    names = await metrics_service.get_metric_names(
        service=service,
        tenant_id=current_user.get("tenant_id")
    )
    return {"names": names}


@router.get("/stats")
async def get_metric_stats(current_user: dict = Depends(require_auth)):
    """Get metrics statistics"""
    stats = await metrics_service.get_metric_stats(
        tenant_id=current_user.get("tenant_id")
    )
    return stats


@router.delete("/cleanup")
async def cleanup_old_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(require_write_access)
):
    """Delete metrics older than specified days"""
    result = await metrics_service.delete_old_metrics(
        days=days,
        tenant_id=current_user.get("tenant_id")
    )
    return result
