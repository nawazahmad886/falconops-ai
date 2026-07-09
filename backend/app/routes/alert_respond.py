"""
FalconOps AI - Alert & Respond Routes
Policies, Violations, and Action Configuration
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.database import db
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/alert-respond", tags=["alert-respond"])


# ── Models ──

class PolicyCreate(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "health_rule"  # health_rule, anomaly, event
    trigger_rules: List[str] = []  # list of health rule IDs
    action_type: str = "alert"  # alert, email, webhook, runbook
    action_config: dict = {}
    enabled: bool = True


# ── Policies ──

@router.get("/policies")
async def list_policies(user: dict = Depends(require_auth)):
    policies = await db.db.alert_policies.find({}, {"_id": 0}).to_list(length=100)
    return {"policies": policies}


@router.post("/policies")
async def create_policy(body: PolicyCreate, user: dict = Depends(require_auth)):
    doc = {
        "id": str(uuid.uuid4()),
        **body.dict(),
        "created_by": user["email"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "executions": 0,
    }
    await db.db.alert_policies.insert_one({**doc})
    doc.pop("_id", None)
    return doc


@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str, user: dict = Depends(require_auth)):
    result = await db.db.alert_policies.delete_one({"id": policy_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"deleted": True}


# ── Violations ──

@router.get("/violations")
async def list_violations(
    limit: int = Query(default=50, ge=1, le=200),
    severity: Optional[str] = Query(default=None),
    user: dict = Depends(require_auth),
):
    query = {}
    if severity:
        query["severity"] = severity
    violations = await db.db.health_violations.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).to_list(length=limit)
    return {"violations": violations, "total": len(violations)}


@router.get("/violations/{violation_id}")
async def get_violation(violation_id: str, user: dict = Depends(require_auth)):
    doc = await db.db.health_violations.find_one({"id": violation_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Violation not found")
    return doc


@router.post("/violations")
async def create_violation(user: dict = Depends(require_auth)):
    """Create a test violation (for demo purposes)"""
    doc = {
        "id": str(uuid.uuid4()),
        "rule_id": "demo",
        "rule_name": "Demo Health Rule Violation",
        "metric": "cpu_usage",
        "operator": "greater_than",
        "threshold": 90,
        "actual_value": 95.2,
        "severity": "critical",
        "state": "active",
        "description": "CPU Usage exceeded threshold of 90%",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "events": [
            {
                "type": "Started - Warning",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "warning",
            }
        ],
        "actions_executed": [],
    }
    await db.db.health_violations.insert_one({**doc})
    doc.pop("_id", None)
    return doc
