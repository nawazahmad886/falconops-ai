"""
FalconOps AI - Network Flow Query Routes
Read API for netflow data ingested via POST /api/ingest/netflows (see
oneagent/pkg/plugins/netflow and backend/app/services/network_flow_service.py).

Mitigation of a detected netflow threat reuses the existing
PUT /api/security/threats/{threat_id} endpoint -- no separate endpoint here.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..core.database import db
from ..utils.auth import get_current_user
from ..services.network_flow_service import network_flow_service

router = APIRouter(prefix="/api/network", tags=["Network Flows"])


@router.get("/flows/summary")
async def flows_summary(
    hours: int = Query(1, ge=1, le=168),
    host: Optional[str] = Query(None),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Aggregate flow counts, top talkers, top services, threat-flagged count."""
    return await network_flow_service.get_flow_summary(hours=hours, host=host)


@router.get("/dependencies")
async def network_dependencies(
    hours: int = Query(24, ge=1, le=168),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Best-effort service-to-service network dependency graph derived from
    observed flows (see get_network_dependencies docstring for the caveat that
    not every remote IP resolves to a known service)."""
    return await network_flow_service.get_network_dependencies(hours=hours)


@router.get("/threats/active")
async def active_netflow_threats(
    limit: int = Query(50, le=200),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Threats detected from network flows specifically (detection_source=netflow),
    a subset of the same db.security_threats collection GET /api/security/threats
    reads from. To mitigate one, use PUT /api/security/threats/{threat_id}."""
    threats = await db.security_threats.find(
        {"detection_source": "netflow", "status": "active"}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"threats": threats, "count": len(threats)}
