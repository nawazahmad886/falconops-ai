"""
FalconOps AI - Enterprise Alert & Incident Management API
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ..utils.auth import require_auth, require_write_access
from ..services.alert_engine import alert_engine, AlertStatus, AlertSeverity
from ..services.incident_engine import incident_engine, IncidentStatus
from ..services.rca_engine import rca_engine
from ..services.capacity_prediction_engine import capacity_prediction_engine

router = APIRouter(prefix="/api/enterprise", tags=["Enterprise Operations"])


# ==================== MODELS ====================

class CreateAlertRequest(BaseModel):
    title: str
    description: str
    severity: str = Field(..., description="critical, high, medium, low, info")
    source: str = "manual"
    entity_type: str
    entity_id: str
    entity_name: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    rule_id: Optional[str] = None
    tags: Optional[dict] = None


class AcknowledgeRequest(BaseModel):
    notes: Optional[str] = None


class ResolveRequest(BaseModel):
    resolution_notes: Optional[str] = None


class CreateIncidentRequest(BaseModel):
    title: str
    description: str
    severity: str = Field(..., description="sev1, sev2, sev3, sev4, sev5")
    affected_services: Optional[List[str]] = None
    affected_hosts: Optional[List[str]] = None
    alert_ids: Optional[List[str]] = None


class CorrelateAlertsRequest(BaseModel):
    alert_ids: List[str]
    correlation_reason: str = "manual"


class UpdateStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class SetRootCauseRequest(BaseModel):
    root_cause: str
    root_cause_analysis: dict


class AddResolutionStepRequest(BaseModel):
    step: str


# ==================== ALERT ENDPOINTS ====================

@router.post("/alerts")
async def create_alert(
    request: CreateAlertRequest,
    current_user: dict = Depends(require_write_access)
):
    """Create a new alert"""
    alert = await alert_engine.create_alert(
        title=request.title,
        description=request.description,
        severity=request.severity,
        source=request.source,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        entity_name=request.entity_name,
        metric_name=request.metric_name,
        metric_value=request.metric_value,
        threshold=request.threshold,
        rule_id=request.rule_id,
        tags=request.tags,
        tenant_id=current_user.get("tenant_id")
    )
    return alert


@router.get("/alerts")
async def get_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    current_user: dict = Depends(require_auth)
):
    """Get alerts with filtering"""
    result = await alert_engine.get_alerts(
        status=status,
        severity=severity,
        entity_type=entity_type,
        source=source,
        tenant_id=current_user.get("tenant_id"),
        limit=limit,
        offset=offset
    )
    return result


@router.get("/alerts/active")
async def get_active_alerts(current_user: dict = Depends(require_auth)):
    """Get all active alerts"""
    alerts = await alert_engine.get_active_alerts(
        tenant_id=current_user.get("tenant_id")
    )
    return {"alerts": alerts, "count": len(alerts)}


@router.get("/alerts/stats")
async def get_alert_stats(current_user: dict = Depends(require_auth)):
    """Get alert statistics"""
    stats = await alert_engine.get_alert_stats(
        tenant_id=current_user.get("tenant_id")
    )
    return stats


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str, current_user: dict = Depends(require_auth)):
    """Get a single alert"""
    alert = await alert_engine.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: AcknowledgeRequest,
    current_user: dict = Depends(require_write_access)
):
    """Acknowledge an alert"""
    result = await alert_engine.acknowledge_alert(
        alert_id=alert_id,
        user_id=current_user.get("user_id", ""),
        user_email=current_user.get("email", "unknown"),
        notes=request.notes
    )
    if not result:
        raise HTTPException(status_code=400, detail="Alert cannot be acknowledged")
    return result


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    request: ResolveRequest,
    current_user: dict = Depends(require_write_access)
):
    """Resolve an alert"""
    result = await alert_engine.resolve_alert(
        alert_id=alert_id,
        user_id=current_user.get("user_id", ""),
        user_email=current_user.get("email", "unknown"),
        resolution_notes=request.resolution_notes
    )
    if not result:
        raise HTTPException(status_code=400, detail="Alert cannot be resolved")
    return result


@router.post("/alerts/{alert_id}/close")
async def close_alert(
    alert_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Close a resolved alert"""
    result = await alert_engine.close_alert(
        alert_id=alert_id,
        user_id=current_user.get("user_id", ""),
        user_email=current_user.get("email", "unknown")
    )
    if not result:
        raise HTTPException(status_code=400, detail="Alert cannot be closed")
    return result


@router.post("/alerts/{alert_id}/escalate")
async def escalate_alert(
    alert_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Escalate an alert"""
    result = await alert_engine.escalate_alert(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


# ==================== INCIDENT ENDPOINTS ====================

@router.post("/incidents")
async def create_incident(
    request: CreateIncidentRequest,
    current_user: dict = Depends(require_write_access)
):
    """Create a new incident"""
    incident = await incident_engine.create_incident(
        title=request.title,
        description=request.description,
        severity=request.severity,
        affected_services=request.affected_services,
        affected_hosts=request.affected_hosts,
        initial_alert_ids=request.alert_ids,
        tenant_id=current_user.get("tenant_id"),
        created_by=current_user.get("email", "unknown")
    )
    return incident


@router.post("/incidents/from-alerts")
async def create_incident_from_alerts(
    request: CorrelateAlertsRequest,
    current_user: dict = Depends(require_write_access)
):
    """Create an incident from correlated alerts"""
    incident = await incident_engine.create_incident_from_alerts(
        alert_ids=request.alert_ids,
        correlation_reason=request.correlation_reason,
        tenant_id=current_user.get("tenant_id"),
        created_by=current_user.get("email", "unknown")
    )
    return incident


@router.post("/incidents/auto-correlate")
async def auto_correlate_alerts(
    time_window_minutes: int = Query(5, ge=1, le=60),
    min_alerts: int = Query(2, ge=2, le=10),
    current_user: dict = Depends(require_write_access)
):
    """Automatically correlate alerts into incidents"""
    incidents = await incident_engine.auto_correlate_alerts(
        time_window_minutes=time_window_minutes,
        min_alerts=min_alerts,
        tenant_id=current_user.get("tenant_id")
    )
    return {"incidents_created": len(incidents), "incidents": incidents}


@router.get("/incidents")
async def get_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: dict = Depends(require_auth)
):
    """Get incidents with filtering"""
    result = await incident_engine.get_incidents(
        status=status,
        severity=severity,
        tenant_id=current_user.get("tenant_id"),
        limit=limit,
        offset=offset
    )
    return result


@router.get("/incidents/active")
async def get_active_incidents(current_user: dict = Depends(require_auth)):
    """Get all active incidents"""
    incidents = await incident_engine.get_active_incidents(
        tenant_id=current_user.get("tenant_id")
    )
    return {"incidents": incidents, "count": len(incidents)}


@router.get("/incidents/stats")
async def get_incident_stats(current_user: dict = Depends(require_auth)):
    """Get incident statistics"""
    stats = await incident_engine.get_incident_stats(
        tenant_id=current_user.get("tenant_id")
    )
    return stats


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, current_user: dict = Depends(require_auth)):
    """Get a single incident with alerts"""
    incident = await incident_engine.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    request: UpdateStatusRequest,
    current_user: dict = Depends(require_write_access)
):
    """Update incident status"""
    result = await incident_engine.update_status(
        incident_id=incident_id,
        new_status=request.status,
        user=current_user.get("email", "unknown"),
        notes=request.notes
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.post("/incidents/{incident_id}/alerts/{alert_id}")
async def add_alert_to_incident(
    incident_id: str,
    alert_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Add an alert to an incident"""
    result = await incident_engine.add_alert_to_incident(
        incident_id=incident_id,
        alert_id=alert_id,
        user=current_user.get("email", "unknown")
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.post("/incidents/{incident_id}/root-cause")
async def set_root_cause(
    incident_id: str,
    request: SetRootCauseRequest,
    current_user: dict = Depends(require_write_access)
):
    """Set root cause for an incident"""
    result = await incident_engine.set_root_cause(
        incident_id=incident_id,
        root_cause=request.root_cause,
        root_cause_analysis=request.root_cause_analysis,
        user=current_user.get("email", "unknown")
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.post("/incidents/{incident_id}/resolution-steps")
async def add_resolution_step(
    incident_id: str,
    request: AddResolutionStepRequest,
    current_user: dict = Depends(require_write_access)
):
    """Add a resolution step to an incident"""
    result = await incident_engine.add_resolution_step(
        incident_id=incident_id,
        step=request.step,
        user=current_user.get("email", "unknown")
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


# ==================== RCA ENDPOINTS ====================

@router.post("/incidents/{incident_id}/analyze")
async def analyze_incident(
    incident_id: str,
    current_user: dict = Depends(require_auth)
):
    """Perform AI-powered root cause analysis on an incident"""
    result = await rca_engine.analyze_incident(
        incident_id=incident_id,
        tenant_id=current_user.get("tenant_id")
    )
    return result


# ==================== CAPACITY PREDICTION ENDPOINTS ====================

@router.get("/capacity/predict")
async def predict_capacity(
    metric_name: str = Query(..., description="Metric to predict"),
    host: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    horizon: str = Query("24h", description="Prediction horizon: 1h, 6h, 24h, 7d, 30d"),
    threshold: float = Query(90, description="Alert threshold"),
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


@router.get("/capacity/alerts")
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
    return {"alerts": alerts, "count": len(alerts)}


@router.get("/capacity/trends")
async def get_trends_report(current_user: dict = Depends(require_auth)):
    """Get trends report for all monitored metrics"""
    report = await capacity_prediction_engine.get_trends_report(
        tenant_id=current_user.get("tenant_id")
    )
    return report


@router.get("/capacity/hosts/{metric_name}")
async def predict_all_hosts(
    metric_name: str,
    horizon: str = Query("24h"),
    threshold: float = Query(90),
    current_user: dict = Depends(require_auth)
):
    """Predict capacity for all hosts with a specific metric"""
    predictions = await capacity_prediction_engine.predict_all_hosts(
        metric_name=metric_name,
        horizon=horizon,
        threshold=threshold,
        tenant_id=current_user.get("tenant_id")
    )
    return {"predictions": predictions, "count": len(predictions)}
