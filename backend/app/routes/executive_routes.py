"""
FalconOps AI - Executive Security Dashboard Routes
Thin aggregator combining existing real dashboards (security, UEBA, vulnerability,
compliance) into one composite security score — no new detection logic here, just
composition of already-real signals.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..utils.auth import get_current_user
from ..services.security_service import get_security_dashboard
from ..services.ueba_service import get_ueba_summary
from ..services.vulnerability_service import get_vulnerability_dashboard
from ..services.compliance_service import get_compliance_dashboard
from ..services.mitre_mapping_service import get_mitre_matrix

router = APIRouter(prefix="/api/executive", tags=["Executive Dashboard"])


def _compute_security_score(security: dict, ueba: dict, vuln: dict, compliance: dict) -> dict:
    # Compliance component: average compliance_score across frameworks that have a real score.
    scored_frameworks = [f["compliance_score"] for f in compliance.get("frameworks", []) if f.get("compliance_score") is not None]
    compliance_component = sum(scored_frameworks) / len(scored_frameworks) if scored_frameworks else 50.0

    # UEBA component: inverse of average behavioral risk (0 risk -> 100 component).
    ueba_component = 100 - min(100, ueba.get("avg_risk_score", 0))

    # Vulnerability component: penalize by count of high-priority (>=70) open vulns.
    high_priority_vulns = sum(1 for v in vuln.get("top_priority", []) if v.get("priority_score", 0) >= 70)
    vuln_component = max(0, 100 - high_priority_vulns * 10)

    # Threat component: penalize by active critical/high threats.
    threat_pressure = security.get("critical_threats", 0) * 8 + security.get("high_threats", 0) * 4
    threat_component = max(0, 100 - threat_pressure)

    composite = round(
        compliance_component * 0.25 + ueba_component * 0.25 + vuln_component * 0.25 + threat_component * 0.25, 1
    )
    return {
        "composite_score": composite,
        "components": {
            "compliance": round(compliance_component, 1),
            "behavioral_risk": round(ueba_component, 1),
            "vulnerability_exposure": round(vuln_component, 1),
            "active_threats": round(threat_component, 1),
        },
    }


@router.get("/security-overview")
async def security_overview(
    hours: int = Query(24, description="Lookback window in hours"),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Composite executive security overview: security score, MITRE matrix, top threats,
    vulnerability priorities, compliance status, and the attack timeline."""
    tenant_id = current_user.get("tenant_id") if current_user else None

    security = await get_security_dashboard(hours)
    ueba = await get_ueba_summary(hours=168)
    vuln = await get_vulnerability_dashboard(tenant_id)
    compliance = await get_compliance_dashboard(tenant_id)
    mitre = await get_mitre_matrix(hours=hours, tenant_id=tenant_id)

    score = _compute_security_score(security, ueba, vuln, compliance)

    return {
        "security_score": score,
        "security_dashboard": security,
        "ueba_summary": ueba,
        "vulnerability_dashboard": vuln,
        "compliance_dashboard": compliance,
        "mitre_matrix": mitre,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
