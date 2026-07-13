"""
FalconOps AI - Incident Engine Routes
Enterprise incident management with alert correlation
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access
from ..services.incident_engine import incident_engine
from ..services.rca_engine import rca_engine
from ..services import autonomous_ops_orchestrator

router = APIRouter(prefix="/api/incident-engine", tags=["Incident Engine"])


# ======================== MODELS ========================

class IncidentCreateRequest(BaseModel):
    title: str
    description: str
    severity: str = "sev3"
    affected_services: Optional[List[str]] = None
    affected_hosts: Optional[List[str]] = None
    initial_alert_ids: Optional[List[str]] = None
    source: str = "manual"


class CorrelateAlertsRequest(BaseModel):
    alert_ids: List[str]
    correlation_reason: str = "manual"


class StatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class RootCauseRequest(BaseModel):
    root_cause: str
    root_cause_analysis: dict = {}


class ResolutionStepRequest(BaseModel):
    step: str


class AddAlertRequest(BaseModel):
    alert_id: str


# ======================== ENDPOINTS ========================

@router.get("/stats")
async def get_incident_stats(current_user: dict = Depends(require_auth)):
    """Get incident statistics"""
    stats = await incident_engine.get_incident_stats(
        tenant_id=current_user.get("tenant_id")
    )
    return stats


@router.get("/active")
async def get_active_incidents(current_user: dict = Depends(require_auth)):
    """Get all active incidents"""
    incidents = await incident_engine.get_active_incidents(
        tenant_id=current_user.get("tenant_id")
    )
    return {"incidents": incidents, "total": len(incidents)}


@router.get("")
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


@router.post("")
async def create_incident(
    request: IncidentCreateRequest,
    current_user: dict = Depends(require_write_access)
):
    """Create a new incident"""
    incident = await incident_engine.create_incident(
        title=request.title,
        description=request.description,
        severity=request.severity,
        affected_services=request.affected_services,
        affected_hosts=request.affected_hosts,
        initial_alert_ids=request.initial_alert_ids,
        source=request.source,
        tenant_id=current_user.get("tenant_id"),
        created_by=current_user["email"]
    )
    return incident


@router.post("/from-alerts")
async def create_from_alerts(
    request: CorrelateAlertsRequest,
    current_user: dict = Depends(require_write_access)
):
    """Create an incident from correlated alerts"""
    incident = await incident_engine.create_incident_from_alerts(
        alert_ids=request.alert_ids,
        correlation_reason=request.correlation_reason,
        tenant_id=current_user.get("tenant_id"),
        created_by=current_user["email"]
    )
    return incident


@router.post("/auto-correlate")
async def auto_correlate(
    time_window_minutes: int = Query(5),
    min_alerts: int = Query(2),
    current_user: dict = Depends(require_write_access)
):
    """Automatically correlate alerts into incidents"""
    incidents = await incident_engine.auto_correlate_alerts(
        time_window_minutes=time_window_minutes,
        min_alerts=min_alerts,
        tenant_id=current_user.get("tenant_id")
    )
    return {
        "message": f"Created {len(incidents)} incidents from correlated alerts",
        "incidents": incidents,
        "count": len(incidents)
    }


@router.get("/{incident_id}")
async def get_incident(incident_id: str, current_user: dict = Depends(require_auth)):
    """Get a single incident with its alerts"""
    incident = await incident_engine.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/{incident_id}/status")
async def update_status(
    incident_id: str,
    request: StatusUpdateRequest,
    current_user: dict = Depends(require_write_access)
):
    """Update incident status"""
    valid = ["active", "investigating", "identified", "monitoring", "resolved", "closed"]
    if request.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be: {valid}")
    result = await incident_engine.update_status(
        incident_id=incident_id,
        new_status=request.status,
        user=current_user["email"],
        notes=request.notes
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.post("/{incident_id}/add-alert")
async def add_alert(
    incident_id: str,
    request: AddAlertRequest,
    current_user: dict = Depends(require_write_access)
):
    """Add an alert to an existing incident"""
    result = await incident_engine.add_alert_to_incident(
        incident_id=incident_id,
        alert_id=request.alert_id,
        user=current_user["email"]
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.post("/{incident_id}/root-cause")
async def set_root_cause(
    incident_id: str,
    request: RootCauseRequest,
    current_user: dict = Depends(require_write_access)
):
    """Set root cause for an incident"""
    result = await incident_engine.set_root_cause(
        incident_id=incident_id,
        root_cause=request.root_cause,
        root_cause_analysis=request.root_cause_analysis,
        user=current_user["email"]
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.post("/{incident_id}/resolution-step")
async def add_resolution_step(
    incident_id: str,
    request: ResolutionStepRequest,
    current_user: dict = Depends(require_write_access)
):
    """Add a resolution step"""
    result = await incident_engine.add_resolution_step(
        incident_id=incident_id,
        step=request.step,
        user=current_user["email"]
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.post("/{incident_id}/analyze-rca")
async def analyze_incident_rca(
    incident_id: str,
    current_user: dict = Depends(require_auth)
):
    """Trigger AI Root Cause Analysis for an incident"""
    result = await rca_engine.analyze_incident(
        incident_id=incident_id,
        tenant_id=current_user.get("tenant_id")
    )
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{incident_id}/recommendation")
async def get_recommendation(
    incident_id: str,
    current_user: dict = Depends(require_auth)
):
    """
    Get the autonomous investigate-and-recommend result for an incident (root cause,
    confidence, evidence, agent narratives, suggested actions). Real incidents created
    via correlation (ai_correlation.py / smart_correlation_engine.py) or a critical
    alert already trigger this automatically; this also supports manually re-running
    it on demand for any incident.
    """
    recommendation = await autonomous_ops_orchestrator.get_recommendation(incident_id)
    if not recommendation:
        incident = await incident_engine.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        recommendation = await autonomous_ops_orchestrator.investigate_and_recommend(
            incident_id, incident, tenant_id=current_user.get("tenant_id")
        )
        if not recommendation:
            raise HTTPException(status_code=502, detail="Recommendation generation failed")
    return recommendation
