"""
FalconOps AI - Enterprise Metrics Observability API
High-performance metrics ingestion, query, and analysis endpoints
"""
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel, Field

from ..utils.auth import require_auth, require_write_access
from ..services.metrics_timeseries_service import (
    metrics_timeseries_service,
    METRIC_CATEGORIES,
    AGGREGATIONS,
    TIME_BUCKETS
)
from ..services.ai_anomaly_analyzer import ai_anomaly_analyzer

router = APIRouter(prefix="/api/metrics/v2", tags=["Metrics Observability"])


# ==================== MODELS ====================

class MetricIngestRequest(BaseModel):
    """Single metric ingestion request"""
    name: str = Field(..., description="Metric name (e.g., cpu_usage, response_time)")
    value: float = Field(..., description="Metric value")
    timestamp: Optional[str] = Field(None, description="ISO timestamp (defaults to now)")
    tags: Optional[Dict[str, str]] = Field(default_factory=dict, description="Metric tags/dimensions")
    unit: str = Field("", description="Unit of measurement (%, ms, bytes, etc.)")
    type: str = Field("gauge", description="Metric type: gauge, counter, histogram")


class MetricBatchIngestRequest(BaseModel):
    """Batch metric ingestion request"""
    metrics: List[Dict[str, Any]] = Field(..., description="List of metrics to ingest")


class MetricQueryRequest(BaseModel):
    """Metric query request"""
    metric_name: str = Field(..., description="Metric name to query")
    start_time: Optional[str] = Field(None, description="Start time (ISO format)")
    end_time: Optional[str] = Field(None, description="End time (ISO format)")
    tags: Optional[Dict[str, str]] = Field(None, description="Filter by tags")
    aggregation: str = Field("avg", description="Aggregation function")
    bucket: str = Field("5m", description="Time bucket size")


class AnomalyAnalysisRequest(BaseModel):
    """Request for AI anomaly analysis"""
    anomaly_id: str = Field(..., description="Anomaly/metric ID to analyze")
    include_correlated_metrics: bool = Field(True)
    include_logs: bool = Field(True)
    include_topology: bool = Field(True)


# ==================== INGESTION ENDPOINTS ====================

@router.post("/ingest")
async def ingest_metric(
    request: MetricIngestRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_write_access)
):
    """
    Ingest a single metric data point.
    
    Metrics are queued in Redis Streams for async processing with anomaly detection.
    """
    result = await metrics_timeseries_service.ingest_metric(
        metric_name=request.name,
        value=request.value,
        timestamp=request.timestamp,
        tags=request.tags,
        unit=request.unit,
        metric_type=request.type,
        tenant_id=current_user.get("tenant_id")
    )
    return result


@router.post("/ingest/batch")
async def ingest_batch(
    request: MetricBatchIngestRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_write_access)
):
    """
    Ingest multiple metrics at once.
    
    Supports high-throughput ingestion for agents and integrations.
    Maximum 1000 metrics per batch.
    """
    if len(request.metrics) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 metrics per batch")
    
    result = await metrics_timeseries_service.ingest_batch(
        metrics=request.metrics,
        tenant_id=current_user.get("tenant_id")
    )
    return result


# ==================== QUERY ENDPOINTS ====================

@router.get("/query")
async def query_metrics(
    metric_name: str = Query(..., description="Metric name to query"),
    start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format)"),
    aggregation: str = Query("avg", description="Aggregation: avg, sum, min, max, p50, p90, p95, p99"),
    bucket: str = Query("5m", description="Time bucket: 1m, 5m, 15m, 1h, 6h, 1d"),
    host: Optional[str] = Query(None, description="Filter by host tag"),
    service: Optional[str] = Query(None, description="Filter by service tag"),
    current_user: dict = Depends(require_auth)
):
    """
    Query metrics with aggregation and time bucketing.
    
    Returns time-series data aggregated by the specified bucket size.
    """
    if aggregation not in AGGREGATIONS:
        raise HTTPException(status_code=400, detail=f"Invalid aggregation. Must be one of: {AGGREGATIONS}")
    
    if bucket not in TIME_BUCKETS:
        raise HTTPException(status_code=400, detail=f"Invalid bucket. Must be one of: {list(TIME_BUCKETS.keys())}")
    
    tags = {}
    if host:
        tags["host"] = host
    if service:
        tags["service"] = service
    
    result = await metrics_timeseries_service.query_metrics(
        metric_name=metric_name,
        start_time=start_time,
        end_time=end_time,
        tags=tags if tags else None,
        aggregation=aggregation,
        bucket=bucket,
        tenant_id=current_user.get("tenant_id")
    )
    return result


@router.post("/query")
async def query_metrics_post(
    request: MetricQueryRequest,
    current_user: dict = Depends(require_auth)
):
    """
    Query metrics (POST version for complex queries).
    """
    result = await metrics_timeseries_service.query_metrics(
        metric_name=request.metric_name,
        start_time=request.start_time,
        end_time=request.end_time,
        tags=request.tags,
        aggregation=request.aggregation,
        bucket=request.bucket,
        tenant_id=current_user.get("tenant_id")
    )
    return result


# ==================== CATALOG & DISCOVERY ====================

@router.get("/catalog")
async def get_metrics_catalog(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search metric names"),
    current_user: dict = Depends(require_auth)
):
    """
    Get catalog of all available metrics.
    
    Returns metrics organized by category with metadata.
    """
    if category and category not in METRIC_CATEGORIES:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid category. Must be one of: {list(METRIC_CATEGORIES.keys())}"
        )
    
    result = await metrics_timeseries_service.get_metrics_catalog(
        category=category,
        search=search,
        tenant_id=current_user.get("tenant_id")
    )
    return result


@router.get("/categories")
async def get_metric_categories(current_user: dict = Depends(require_auth)):
    """Get available metric categories and their metric types."""
    return {
        "categories": METRIC_CATEGORIES,
        "aggregations": AGGREGATIONS,
        "time_buckets": list(TIME_BUCKETS.keys())
    }


@router.get("/top")
async def get_top_metrics(
    metric_name: str = Query(..., description="Metric name"),
    group_by: str = Query("host", description="Tag to group by (host, service, etc.)"),
    aggregation: str = Query("avg", description="Aggregation for ranking"),
    limit: int = Query(10, ge=1, le=100, description="Number of results"),
    start_time: Optional[str] = Query(None, description="Start time"),
    current_user: dict = Depends(require_auth)
):
    """
    Get top N metrics grouped by a dimension.
    
    Useful for finding highest CPU usage by host, slowest services, etc.
    """
    result = await metrics_timeseries_service.get_top_metrics(
        metric_name=metric_name,
        group_by=group_by,
        aggregation=aggregation,
        limit=limit,
        start_time=start_time,
        tenant_id=current_user.get("tenant_id")
    )
    return {"metric_name": metric_name, "group_by": group_by, "results": result}


# ==================== ANOMALY DETECTION ====================

@router.get("/anomalies")
async def get_anomalies(
    start_time: Optional[str] = Query(None, description="Start time"),
    end_time: Optional[str] = Query(None, description="End time"),
    metric_name: Optional[str] = Query(None, description="Filter by metric name"),
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high, critical"),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(require_auth)
):
    """
    Get detected anomalies.
    
    Returns metrics that have been flagged as anomalous by the statistical detection engine.
    """
    anomalies = await metrics_timeseries_service.get_anomalies(
        start_time=start_time,
        end_time=end_time,
        metric_name=metric_name,
        severity=severity,
        tenant_id=current_user.get("tenant_id"),
        limit=limit
    )
    return {"anomalies": anomalies, "count": len(anomalies)}


@router.post("/anomalies/analyze")
async def analyze_anomaly(
    request: AnomalyAnalysisRequest,
    current_user: dict = Depends(require_auth)
):
    """
    AI-powered anomaly analysis.
    
    Uses LLM to analyze the anomaly with correlated metrics, logs, and topology
    to determine root cause and recommendations.
    """
    from ..core.database import db
    
    # Get the anomaly data
    anomaly = await db.metrics_timeseries.find_one(
        {"id": request.anomaly_id},
        {"_id": 0}
    )
    
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    
    analysis = await ai_anomaly_analyzer.analyze_anomaly(
        anomaly_data=anomaly,
        include_correlated_metrics=request.include_correlated_metrics,
        include_logs=request.include_logs,
        include_topology=request.include_topology,
        tenant_id=current_user.get("tenant_id")
    )
    
    return analysis


@router.get("/anomalies/correlations")
async def get_anomaly_correlations(
    start_time: Optional[str] = Query(None),
    time_window_minutes: int = Query(5, ge=1, le=60),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_auth)
):
    """
    Find correlations between anomalies.
    
    Identifies anomalies that occurred together on the same host or service.
    """
    anomalies = await metrics_timeseries_service.get_anomalies(
        start_time=start_time,
        tenant_id=current_user.get("tenant_id"),
        limit=limit
    )
    
    correlations = await ai_anomaly_analyzer.correlate_anomalies(
        anomalies=anomalies,
        time_window_minutes=time_window_minutes,
        tenant_id=current_user.get("tenant_id")
    )
    
    return {
        "anomalies_analyzed": len(anomalies),
        "correlations": correlations,
        "correlation_count": len(correlations)
    }


# ==================== STATISTICS ====================

@router.get("/stats")
async def get_metrics_stats(current_user: dict = Depends(require_auth)):
    """
    Get metrics service statistics.
    
    Returns total data points, ingestion rate, anomaly rate, and stream info.
    """
    stats = await metrics_timeseries_service.get_stats(
        tenant_id=current_user.get("tenant_id")
    )
    return stats


# ==================== STREAM MANAGEMENT ====================

@router.post("/stream/initialize")
async def initialize_stream(current_user: dict = Depends(require_write_access)):
    """Initialize the Redis metrics stream (admin operation)."""
    await metrics_timeseries_service.initialize_stream()
    return {"status": "initialized", "stream": "falcon:metrics:stream"}


# Background worker starter (called from main.py)
async def start_metrics_processor():
    """Start the background metrics processor worker"""
    await metrics_timeseries_service.initialize_stream()
    # Start processor in background
    asyncio.create_task(metrics_timeseries_service.process_stream())
