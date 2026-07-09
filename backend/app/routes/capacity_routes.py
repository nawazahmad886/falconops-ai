"""
FalconOps AI - Capacity Prediction Routes
AI-powered capacity forecasting and trend analysis
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from ..utils.auth import require_auth
from ..services.capacity_prediction_engine import capacity_prediction_engine

router = APIRouter(prefix="/api/capacity", tags=["Capacity Prediction"])


@router.get("/predict")
async def predict_capacity(
    metric_name: str = Query(..., description="Metric name to predict"),
    host: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    horizon: str = Query("24h", description="Prediction horizon: 1h, 6h, 24h, 7d, 30d"),
    threshold: float = Query(90, description="Threshold to check against"),
    current_user: dict = Depends(require_auth)
):
    """Predict when a metric will reach a threshold"""
    result = await capacity_prediction_engine.predict_capacity(
        metric_name=metric_name,
        host=host,
        service=service,
        horizon=horizon,
        threshold=threshold,
        tenant_id=current_user.get("tenant_id")
    )
    return result


@router.get("/predict/hosts")
async def predict_all_hosts(
    metric_name: str = Query(...),
    horizon: str = Query("24h"),
    threshold: float = Query(90),
    current_user: dict = Depends(require_auth)
):
    """Predict capacity for all hosts with a given metric"""
    predictions = await capacity_prediction_engine.predict_all_hosts(
        metric_name=metric_name,
        horizon=horizon,
        threshold=threshold,
        tenant_id=current_user.get("tenant_id")
    )
    return {"predictions": predictions, "total": len(predictions)}


@router.get("/alerts")
async def get_capacity_alerts(
    threshold: float = Query(90),
    horizon: str = Query("24h"),
    current_user: dict = Depends(require_auth)
):
    """Get capacity alerts for metrics approaching thresholds"""
    alerts = await capacity_prediction_engine.get_capacity_alerts(
        threshold=threshold,
        horizon=horizon,
        tenant_id=current_user.get("tenant_id")
    )
    return {"alerts": alerts, "total": len(alerts)}


@router.get("/trends")
async def get_trends_report(current_user: dict = Depends(require_auth)):
    """Get trends report for all monitored metrics"""
    report = await capacity_prediction_engine.get_trends_report(
        tenant_id=current_user.get("tenant_id")
    )
    return report



@router.get("/forecast-summary")
async def forecast_summary(
    current_user: dict = Depends(require_auth)
):
    """
    Get a summary forecast for key infrastructure metrics.
    Returns predictions for CPU, memory, disk across all monitored hosts.
    """
    from ..core.database import db as fdb
    from datetime import datetime, timezone, timedelta

    # Get distinct metrics+hosts from recent timeseries
    pipeline = [
        {"$match": {"timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}}},
        {"$group": {"_id": {"name": "$name", "host": "$tags.host"}}},
        {"$limit": 50}
    ]

    try:
        combos = await fdb.metrics_timeseries.aggregate(pipeline).to_list(50)
    except Exception:
        combos = []

    # Also build from server metrics
    servers = await fdb.servers.find({}, {"_id": 0, "id": 1, "hostname": 1}).to_list(50)

    key_metrics = ["cpu_percent", "memory_percent", "disk_percent"]
    predictions = []

    for server in servers[:10]:
        hostname = server.get("hostname", "")
        for metric in key_metrics:
            result = await capacity_prediction_engine.predict_capacity(
                metric_name=metric,
                host=hostname,
                horizon="24h",
                threshold=90,
                tenant_id=current_user.get("tenant_id"),
            )
            if result.get("status") == "success":
                predictions.append({
                    "metric": metric,
                    "host": hostname,
                    "current": result["current_value"],
                    "predicted_24h": result["prediction"]["predicted_value"],
                    "confidence": result["prediction"]["confidence"],
                    "will_breach": result["threshold_analysis"]["will_breach"],
                    "breach_time": result["threshold_analysis"]["estimated_breach_time"],
                    "trend": result["trend"]["direction"],
                    "risk_level": result["risk_assessment"]["level"],
                    "risk_message": result["risk_assessment"]["message"],
                    "forecast_series": result.get("forecast_series", [])[:24],
                })

    # If no predictions from servers, try from timeseries combos
    if not predictions and combos:
        for c in combos[:15]:
            name = c["_id"].get("name", "")
            host = c["_id"].get("host", "")
            if not name:
                continue
            result = await capacity_prediction_engine.predict_capacity(
                metric_name=name, host=host, horizon="24h", threshold=90,
                tenant_id=current_user.get("tenant_id"),
            )
            if result.get("status") == "success":
                predictions.append({
                    "metric": name, "host": host or "all",
                    "current": result["current_value"],
                    "predicted_24h": result["prediction"]["predicted_value"],
                    "confidence": result["prediction"]["confidence"],
                    "will_breach": result["threshold_analysis"]["will_breach"],
                    "breach_time": result["threshold_analysis"]["estimated_breach_time"],
                    "trend": result["trend"]["direction"],
                    "risk_level": result["risk_assessment"]["level"],
                    "risk_message": result["risk_assessment"]["message"],
                    "forecast_series": result.get("forecast_series", [])[:24],
                })

    # Summary
    at_risk = [p for p in predictions if p["will_breach"]]

    return {
        "predictions": predictions,
        "total": len(predictions),
        "at_risk": len(at_risk),
        "summary": f"{len(predictions)} metrics forecasted, {len(at_risk)} at risk of breaching threshold in 24h",
    }
