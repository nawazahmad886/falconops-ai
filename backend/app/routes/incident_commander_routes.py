"""
FalconOps AI — Incident Commander API.

New endpoints that sit alongside RASED's own (/api/v1/rased/..., unchanged)
rather than replacing them — these compose RASED data with other existing
FalconOps services (topology, reports) or add the genuinely-new capabilities
identified in the Incident Commander plan (verification is automatic inside
the RASED graph; this file adds blast-radius, SRE score, report export, and
incident-scoped chat on top of an incident RASED already investigated).
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..utils.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/incidents", tags=["Incident Commander"])

# Separate prefix — GET /api/ai/audit is platform-wide, not scoped to one
# incident, so it doesn't belong under /api/ai/incidents/{id}/...
audit_router = APIRouter(prefix="/api/ai", tags=["Incident Commander"])


@audit_router.get("/audit")
async def unified_ai_audit(limit: int = 100, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Same query-time UNION pattern as control_center/activity_timeline.py
    (which this calls directly) — now including RASED investigation events
    as an eleventh source, added alongside this feature rather than as a
    separate write path."""
    from ..services.control_center.activity_timeline import get_activity_timeline
    events = await get_activity_timeline(limit=min(limit, 500))
    return {"events": events, "count": len(events)}


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@router.post("/{incident_id}/ask")
async def ask_about_incident(incident_id: str, req: AskRequest, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    from ..services.rased.chat import ask_about_incident as _ask
    return await _ask(incident_id, req.question)


@router.get("/{incident_id}/sre-score")
async def incident_sre_score(incident_id: str, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """The platform's current SRE score, surfaced in incident context — this
    is the live score, not a reconstructed historical snapshot from when the
    incident started (that would need score history tracking this doesn't
    build); disclosed via `as_of` rather than implied."""
    from ..services.sre_score_service import get_sre_score
    score = await get_sre_score(current_user.get("tenant_id"))
    return {"incident_id": incident_id, "note": "current platform score, not a historical snapshot", **score}


@router.get("/{incident_id}/blast-radius")
async def incident_blast_radius(incident_id: str, current_user: dict = Depends(require_auth)) -> Dict[str, Any]:
    from ..core.database import db
    from ..services.topology_service import topology_service

    investigation = await db.rased_investigations.find_one({"incident_id": incident_id}, {"_id": 0})
    if investigation is None:
        raise HTTPException(404, f"Unknown incident_id: {incident_id}")

    services = sorted({a.get("service") for a in (investigation.get("alerts") or []) if a.get("service")})
    if not services:
        return {"incident_id": incident_id, "services": [], "impacted": []}

    impacted = []
    for service in services:
        try:
            node = await topology_service.get_service_by_name(service)
            if node is None:
                impacted.append({"service": service, "available": False,
                                  "reason": "no topology node for this service — not discovered yet"})
                continue
            downstream = await topology_service.get_impacted_services(node["id"])
            impacted.append({
                "service": service, "available": True,
                "impacted_count": len(downstream),
                "impacted_services": [
                    {"name": d["service"].get("name"), "impact_depth": d["impact_depth"]} for d in downstream
                ],
            })
        except Exception as e:
            impacted.append({"service": service, "available": False, "reason": str(e)[:200]})
    return {"incident_id": incident_id, "services": services, "impacted": impacted}


@router.post("/{incident_id}/report")
async def generate_incident_report(incident_id: str, format: str = "markdown", current_user: dict = Depends(require_auth)):
    from ..services import incident_report_service
    if format == "pdf":
        content = await incident_report_service.generate_pdf_report(incident_id)
        if content is None:
            raise HTTPException(404, f"Unknown incident_id: {incident_id}")
        from fastapi.responses import Response
        return Response(content=content, media_type="application/pdf",
                         headers={"Content-Disposition": f'attachment; filename="incident_{incident_id}.pdf"'})

    content = await incident_report_service.generate_markdown_report(incident_id)
    if content is None:
        raise HTTPException(404, f"Unknown incident_id: {incident_id}")
    return {"incident_id": incident_id, "format": "markdown", "content": content}


__all__ = ["router", "audit_router"]
