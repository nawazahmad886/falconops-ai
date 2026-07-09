"""
FalconOps AI - AI Analysis Routes
CrewAI and AI-powered incident analysis
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import json

from ..utils.auth import require_auth, require_write_access
from ..core.config import get_db
from ..services.ai_crew_service import get_aiops_service

router = APIRouter(prefix="/ai", tags=["AI Analysis"])
db = get_db()


@router.post("/analyze-alert")
async def analyze_alert(
    alert_data: dict,
    user: dict = Depends(require_auth)
):
    """Analyze an alert using AI"""
    aiops = get_aiops_service()
    result = await aiops.analyze_alert(alert_data)
    return result


@router.post("/rca/{incident_id}")
async def perform_rca(
    incident_id: str,
    user: dict = Depends(require_auth)
):
    """Perform root cause analysis on an incident"""
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get related alerts
    alerts = await db.alerts.find(
        {"incident_id": incident_id}, {"_id": 0}
    ).to_list(100)
    
    incident["alerts_summary"] = "\n".join([
        f"- {a.get('severity', 'info').upper()}: {a.get('message', 'No message')}"
        for a in alerts
    ])
    
    aiops = get_aiops_service()
    result = await aiops.perform_rca(incident)
    
    # Store result
    if result.get("success"):
        await db.incidents.update_one(
            {"id": incident_id},
            {"$set": {
                "ai_analysis": result,
                "root_cause": result.get("rca_report", {}).get("root_cause")
            }}
        )
    
    return result


@router.post("/summarize/{incident_id}")
async def summarize_incident(
    incident_id: str,
    user: dict = Depends(require_auth)
):
    """Generate AI summary for an incident"""
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Check for existing RCA
    rca_data = incident.get("ai_analysis")
    
    aiops = get_aiops_service()
    result = await aiops.generate_summary(incident, rca_data)
    
    return result


@router.post("/full-investigation/{incident_id}")
async def full_investigation(
    incident_id: str,
    user: dict = Depends(require_auth)
):
    """Perform complete AI investigation on an incident"""
    incident = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get related alerts
    alerts = await db.alerts.find(
        {"incident_id": incident_id}, {"_id": 0}
    ).to_list(100)
    
    incident["alerts_summary"] = "\n".join([
        f"- [{a.get('severity', 'info').upper()}] {a.get('service', 'Unknown')}: {a.get('message', 'No message')}"
        for a in alerts
    ])
    incident["affected_services"] = list(set([a.get("service", "Unknown") for a in alerts]))
    incident["alert_count"] = len(alerts)
    
    aiops = get_aiops_service()
    result = await aiops.full_investigation(incident)
    
    # Store result
    if result.get("success"):
        await db.incidents.update_one(
            {"id": incident_id},
            {"$set": {
                "ai_analysis": result,
                "root_cause": result.get("investigation", {}).get("root_cause_analysis", {}).get("primary_cause")
            }}
        )
    
    return result
