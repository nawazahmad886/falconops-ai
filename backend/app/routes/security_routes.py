"""
FalconOps AI - Security Monitoring Routes
API endpoints for security event ingestion, threat detection, and user activity analysis
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access, get_current_user
from ..services.security_service import (
    ingest_security_event,
    get_security_dashboard,
    get_threats,
    get_user_activity,
    get_security_events,
    update_threat_status,
    correlate_security_ops,
    generate_security_demo_data,
)

router = APIRouter(prefix="/api/security", tags=["Security Monitoring"])


# ======================== MODELS ========================

class SecurityEvent(BaseModel):
    action: str
    user: Optional[str] = "unknown"
    source_ip: Optional[str] = "unknown"
    target: Optional[str] = ""
    status: Optional[str] = "unknown"
    severity: Optional[str] = "info"
    message: Optional[str] = ""
    host: Optional[str] = ""
    service: Optional[str] = ""
    category: Optional[str] = "authentication"
    geo_location: Optional[str] = ""
    user_agent: Optional[str] = ""
    source: Optional[str] = "api"
    timestamp: Optional[str] = None
    raw: Optional[str] = ""


class SecurityEventBatch(BaseModel):
    events: List[SecurityEvent]
    source: Optional[str] = "api"


class ThreatStatusUpdate(BaseModel):
    status: str  # resolved, dismissed, investigating


# ======================== EVENT INGESTION ========================

@router.post("/events")
async def ingest_event(event: SecurityEvent, current_user: Optional[dict] = Depends(get_current_user)):
    """Ingest a single security event"""
    tenant_id = current_user.get("tenant_id") if current_user else None
    result = await ingest_security_event(event.dict(), tenant_id)
    return result


@router.post("/events/batch")
async def ingest_events_batch(batch: SecurityEventBatch, current_user: Optional[dict] = Depends(get_current_user)):
    """Ingest multiple security events"""
    tenant_id = current_user.get("tenant_id") if current_user else None
    results = []
    total_threats = 0

    for event in batch.events:
        ev = event.dict()
        ev["source"] = batch.source
        r = await ingest_security_event(ev, tenant_id)
        results.append(r)
        total_threats += r.get("threats_detected", 0)

    return {
        "ingested": len(results),
        "total_threats_detected": total_threats,
    }


# ======================== DASHBOARD ========================

@router.get("/dashboard")
async def security_dashboard(
    hours: int = Query(24, description="Time range in hours"),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Get security monitoring dashboard overview"""
    return await get_security_dashboard(hours)


# ======================== THREATS ========================

@router.get("/threats")
async def list_threats(
    status: Optional[str] = Query("active", description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, le=200),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Get detected threats"""
    return await get_threats(status, severity, limit)


@router.put("/threats/{threat_id}")
async def update_threat(
    threat_id: str,
    update: ThreatStatusUpdate,
    current_user: dict = Depends(require_auth),
):
    """Update threat status"""
    return await update_threat_status(threat_id, update.status, current_user.get("email"))


# ======================== USER ACTIVITY ========================

@router.get("/user-activity")
async def user_activity(
    hours: int = Query(24, description="Time range in hours"),
    limit: int = Query(50, le=200),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Get user activity analysis"""
    return await get_user_activity(hours, limit)


# ======================== EVENTS ========================

@router.get("/events")
async def list_security_events(
    hours: int = Query(24, description="Time range in hours"),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Get security events with filters"""
    return await get_security_events(hours, category, severity, action, search, limit, offset)


# ======================== CORRELATION ========================

@router.get("/correlations")
async def get_correlations(current_user: Optional[dict] = Depends(get_current_user)):
    """Get security-ops correlations"""
    return await correlate_security_ops()


# ======================== DEMO DATA ========================

@router.post("/simulate")
async def simulate_security_events(
    count: int = Query(200, le=1000, description="Number of events to generate"),
    current_user: dict = Depends(require_write_access),
):
    """Generate sample security events for demo"""
    return await generate_security_demo_data(count)
