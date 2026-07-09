"""
FalconOps AI - Anomaly Detection Routes
Multi-algorithm anomaly detection API
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..utils.auth import require_auth
from ..services.anomaly_detection_engine import anomaly_detection_engine

router = APIRouter(prefix="/api/anomaly-detection", tags=["Anomaly Detection"])


@router.get("/analyze")
async def analyze_metric(
    metric_name: str = Query(...),
    host: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    lookback_hours: int = Query(6, ge=1, le=168),
    current_user: dict = Depends(require_auth),
):
    return await anomaly_detection_engine.analyze_metric(
        metric_name=metric_name,
        host=host,
        service=service,
        lookback_hours=lookback_hours,
        tenant_id=current_user.get("tenant_id"),
    )


@router.get("/scan")
async def scan_all(
    lookback_hours: int = Query(6, ge=1, le=168),
    current_user: dict = Depends(require_auth),
):
    """Scan all metrics for anomalies"""
    return await anomaly_detection_engine.scan_all_metrics(
        lookback_hours=lookback_hours,
        tenant_id=current_user.get("tenant_id"),
    )


@router.get("/baseline")
async def get_baseline(
    metric_name: str = Query(...),
    host: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    current_user: dict = Depends(require_auth),
):
    return await anomaly_detection_engine.get_metric_baseline(
        metric_name=metric_name,
        host=host,
        hours=hours,
        tenant_id=current_user.get("tenant_id"),
    )
