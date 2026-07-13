"""
FalconOps AI - Compliance Monitoring Engine
Every control check queries a REAL, already-existing signal in the codebase (db.users
roles, db.audit_logs, db.runbooks, db.security_events, db.vulnerabilities). A control
whose backing signal doesn't exist in the schema (e.g. no MFA field on db.users) is
scored "unknown" — never a fabricated pass/fail. This mirrors the same honesty rule
already applied to remediation_service.py / k8s_healing_service.py.
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

COMPLIANCE_SNAPSHOT_INTERVAL_HOURS = 24


async def _check_mfa_enforced(tenant_id: Optional[str] = None) -> Dict:
    # No MFA field exists anywhere in the user schema (confirmed by repo-wide search) —
    # honestly reported as unknown rather than assumed pass or fail.
    return {"status": "unknown", "evidence": "No MFA field present in the user schema (db.users) to verify against."}


async def _check_encryption_at_rest(tenant_id: Optional[str] = None) -> Dict:
    # No encryption-at-rest config flag is stored anywhere in this deployment's data model.
    return {"status": "unknown", "evidence": "No encryption-at-rest configuration flag exists in any stored config."}


async def _check_rbac_enforced(tenant_id: Optional[str] = None) -> Dict:
    query = {"tenant_id": tenant_id} if tenant_id else {}
    roles = await db.users.distinct("role", query)
    distinct_roles = [r for r in roles if r]
    status = "pass" if len(distinct_roles) >= 2 else "fail"
    return {"status": status, "evidence": f"{len(distinct_roles)} distinct role(s) in use: {distinct_roles}"}


async def _check_access_review(tenant_id: Optional[str] = None) -> Dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    query = {"timestamp": {"$gte": cutoff}, "action": {"$regex": "role|permission", "$options": "i"}}
    if tenant_id:
        query["tenant_id"] = tenant_id
    count = await db.audit_logs.count_documents(query)
    status = "pass" if count > 0 else "fail"
    return {"status": status, "evidence": f"{count} role/permission-change audit event(s) in the last 90 days"}


async def _check_log_retention(tenant_id: Optional[str] = None, target_days: int = 90) -> Dict:
    query = {"tenant_id": tenant_id} if tenant_id else {}
    oldest = await db.security_events.find(query, {"_id": 0, "timestamp": 1}).sort("timestamp", 1).limit(1).to_list(1)
    if not oldest:
        return {"status": "unknown", "evidence": "No security events recorded yet to evaluate retention span."}
    try:
        oldest_ts = datetime.fromisoformat(oldest[0]["timestamp"].replace("Z", "+00:00"))
        span_days = (datetime.now(timezone.utc) - oldest_ts).days
    except Exception:
        return {"status": "unknown", "evidence": "Could not parse oldest event timestamp."}
    status = "pass" if span_days >= target_days else "fail"
    return {"status": status, "evidence": f"Security-event log history spans {span_days} day(s) (target: {target_days})"}


async def _check_incident_response_plan(tenant_id: Optional[str] = None) -> Dict:
    query = {"tenant_id": tenant_id} if tenant_id else {}
    runbook_count = await db.runbooks.count_documents(query)
    if runbook_count == 0:
        return {"status": "fail", "evidence": "No runbooks are defined for incident response."}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    recent = await db.runbook_executions.count_documents({**query, "started_at": {"$gte": cutoff}})
    status = "pass" if recent > 0 else "fail"
    return {"status": status, "evidence": f"{runbook_count} runbook(s) defined, {recent} execution(s) in the last 90 days"}


async def _check_vulnerability_management(tenant_id: Optional[str] = None) -> Dict:
    total = await db.vulnerabilities.count_documents({})
    if total == 0:
        return {"status": "unknown", "evidence": "No CVE sync has run yet — vulnerability_service.sync_recent_cves() has not been triggered."}
    latest = await db.vulnerabilities.find_one({}, {"_id": 0, "synced_at": 1}, sort=[("synced_at", -1)])
    try:
        latest_ts = datetime.fromisoformat(latest["synced_at"].replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - latest_ts).total_seconds() / 3600
    except Exception:
        age_hours = 9999
    status = "pass" if age_hours <= 48 else "fail"
    return {"status": status, "evidence": f"{total} tracked CVE(s), last synced {round(age_hours)}h ago"}


async def _check_security_monitoring(tenant_id: Optional[str] = None) -> Dict:
    query = {"tenant_id": tenant_id} if tenant_id else {}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent = await db.security_events.count_documents({**query, "timestamp": {"$gte": cutoff}})
    status = "pass" if recent > 0 else "fail"
    return {"status": status, "evidence": f"{recent} security event(s) ingested in the last 24h"}


# Each control lists which framework(s) it applies to. Real, queryable checks only.
COMPLIANCE_CONTROLS: List[Dict] = [
    {"id": "mfa_enforced", "name": "Multi-Factor Authentication Enforced",
     "frameworks": ["SOC2", "ISO27001"], "check": _check_mfa_enforced},
    {"id": "encryption_at_rest", "name": "Encryption at Rest",
     "frameworks": ["SOC2", "ISO27001"], "check": _check_encryption_at_rest},
    {"id": "rbac_enforced", "name": "Role-Based Access Control Enforced",
     "frameworks": ["SOC2", "ISO27001"], "check": _check_rbac_enforced},
    {"id": "access_review", "name": "Periodic Access Review",
     "frameworks": ["SOC2", "ISO27001"], "check": _check_access_review},
    {"id": "log_retention", "name": "Security Log Retention",
     "frameworks": ["SOC2", "ISO27001"], "check": _check_log_retention},
    {"id": "incident_response_plan", "name": "Incident Response Plan Exercised",
     "frameworks": ["SOC2", "ISO27001"], "check": _check_incident_response_plan},
    {"id": "vulnerability_management", "name": "Vulnerability Management Program",
     "frameworks": ["ISO27001"], "check": _check_vulnerability_management},
    {"id": "security_monitoring", "name": "Continuous Security Monitoring",
     "frameworks": ["SOC2"], "check": _check_security_monitoring},
]


def get_frameworks() -> List[str]:
    frameworks = set()
    for c in COMPLIANCE_CONTROLS:
        frameworks.update(c["frameworks"])
    return sorted(frameworks)


async def evaluate_compliance(framework: str, tenant_id: Optional[str] = None) -> Dict:
    controls = [c for c in COMPLIANCE_CONTROLS if framework in c["frameworks"]]
    results = []
    for c in controls:
        outcome = await c["check"](tenant_id)
        results.append({"control_id": c["id"], "name": c["name"], **outcome})

    scored = [r for r in results if r["status"] in ("pass", "fail")]
    passing = sum(1 for r in scored if r["status"] == "pass")
    compliance_score = round(100 * passing / len(scored), 1) if scored else None

    return {
        "framework": framework,
        "compliance_score": compliance_score,
        "controls": results,
        "pass_count": passing,
        "fail_count": sum(1 for r in results if r["status"] == "fail"),
        "unknown_count": sum(1 for r in results if r["status"] == "unknown"),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_compliance_dashboard(tenant_id: Optional[str] = None) -> Dict:
    frameworks = get_frameworks()
    results = [await evaluate_compliance(f, tenant_id) for f in frameworks]
    return {"frameworks": results}


async def snapshot_compliance() -> Dict:
    """Daily snapshot of compliance scores, for trend display on the executive dashboard."""
    dashboard = await get_compliance_dashboard()
    doc = {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "frameworks": [{"framework": f["framework"], "compliance_score": f["compliance_score"]} for f in dashboard["frameworks"]],
    }
    await db.compliance_snapshots.insert_one(doc)
    return doc


async def get_compliance_trend(days: int = 30) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return await db.compliance_snapshots.find(
        {"snapshot_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("snapshot_at", 1).to_list(days)


async def compliance_snapshot_scheduler():
    """Background loop mirroring the shape of autonomous_ops_orchestrator.sla_breach_scheduler."""
    while True:
        try:
            await snapshot_compliance()
        except Exception as e:
            logger.error(f"Compliance snapshot scheduler error: {e}")
        await asyncio.sleep(COMPLIANCE_SNAPSHOT_INTERVAL_HOURS * 3600)
