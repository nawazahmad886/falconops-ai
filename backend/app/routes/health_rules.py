"""
FalconOps AI - Health Rules Routes
API endpoints for health rule management
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access, get_current_user, build_tenant_query
from ..services.health_rule_engine import health_rule_engine

router = APIRouter(prefix="/api/health-rules", tags=["Health Rules"])


# ======================== MODELS ========================

class HealthRuleCreate(BaseModel):
    name: str
    description: str = ""
    metric: str
    operator: str
    threshold: float
    threshold_max: Optional[float] = None  # For BETWEEN operator
    duration: int = 300
    severity: str = "warning"
    category: str = "custom"
    component_type: str = "infrastructure"  # infrastructure, application, database, network
    service_filter: Optional[str] = None
    host_filter: Optional[str] = None
    enabled: bool = True
    conditions: Optional[List[dict]] = None  # For compound rules [{metric, operator, threshold, logic: AND/OR}]
    action: str = "alert"  # alert, email, webhook


class HealthRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    threshold_max: Optional[float] = None
    duration: Optional[int] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    component_type: Optional[str] = None
    service_filter: Optional[str] = None
    host_filter: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[List[dict]] = None
    action: Optional[str] = None


class MetricsEvaluationRequest(BaseModel):
    metrics: dict
    service: Optional[str] = None
    host: Optional[str] = None


# ======================== ENDPOINTS ========================

@router.get("")
async def get_health_rules(
    category: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
    current_user: dict = Depends(require_auth)
):
    """Get all health rules"""
    rules = await health_rule_engine.get_rules(
        category=category,
        enabled_only=enabled_only,
        tenant_id=current_user.get("tenant_id")
    )
    return {"rules": rules, "total": len(rules)}


@router.post("")
async def create_health_rule(
    rule: HealthRuleCreate,
    current_user: dict = Depends(require_write_access)
):
    """Create a new health rule"""
    result = await health_rule_engine.create_rule(
        name=rule.name,
        description=rule.description,
        metric=rule.metric,
        operator=rule.operator,
        threshold=rule.threshold,
        threshold_max=rule.threshold_max,
        duration=rule.duration,
        severity=rule.severity,
        category=rule.category,
        component_type=rule.component_type,
        service_filter=rule.service_filter,
        host_filter=rule.host_filter,
        enabled=rule.enabled,
        conditions=rule.conditions,
        action=rule.action,
        tenant_id=current_user.get("tenant_id"),
        created_by=current_user["email"]
    )
    return result


@router.get("/templates")
async def get_rule_templates(current_user: dict = Depends(require_auth)):
    """Get predefined health rule templates"""
    templates = await health_rule_engine.get_rule_templates()
    return {"templates": templates}


@router.get("/categories")
async def get_rule_categories(current_user: dict = Depends(require_auth)):
    """Get available rule categories"""
    categories = await health_rule_engine.get_rule_categories()
    return {"categories": categories}


@router.get("/metrics")
async def get_metric_types(current_user: dict = Depends(require_auth)):
    """Get available metric types"""
    metrics = await health_rule_engine.get_metric_types()
    return {"metrics": metrics}


@router.get("/operators")
async def get_operators(current_user: dict = Depends(require_auth)):
    """Get available operators"""
    operators = await health_rule_engine.get_operators()
    return {"operators": operators}


@router.get("/stats")
async def get_rule_stats(current_user: dict = Depends(require_auth)):
    """Get health rule statistics"""
    stats = await health_rule_engine.get_rule_stats(
        tenant_id=current_user.get("tenant_id")
    )
    return stats


@router.get("/{rule_id}")
async def get_health_rule(rule_id: str, current_user: dict = Depends(require_auth)):
    """Get a single health rule"""
    rule = await health_rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/{rule_id}")
async def update_health_rule(
    rule_id: str,
    updates: HealthRuleUpdate,
    current_user: dict = Depends(require_write_access)
):
    """Update a health rule"""
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    result = await health_rule_engine.update_rule(rule_id, update_data)
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.delete("/{rule_id}")
async def delete_health_rule(
    rule_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Delete a health rule"""
    success = await health_rule_engine.delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule deleted"}


@router.post("/evaluate")
async def evaluate_metrics(
    request: MetricsEvaluationRequest,
    current_user: dict = Depends(require_auth)
):
    """Evaluate metrics against all enabled health rules"""
    results = await health_rule_engine.evaluate_metrics(
        metrics=request.metrics,
        service=request.service,
        host=request.host,
        tenant_id=current_user.get("tenant_id")
    )
    
    # Trigger alerts for violations that exceed duration
    alerts_created = []
    for alert_data in results.get("alerts_to_trigger", []):
        alert = await health_rule_engine.trigger_alert_from_violation(
            violation=alert_data,
            service=request.service,
            host=request.host,
            tenant_id=current_user.get("tenant_id")
        )
        alerts_created.append(alert)
    
    results["alerts_created"] = alerts_created
    return results


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Toggle a rule's enabled status"""
    rule = await health_rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    result = await health_rule_engine.update_rule(
        rule_id,
        {"enabled": not rule["enabled"]}
    )
    return result


@router.post("/from-template/{template_id}")
async def create_from_template(
    template_id: str,
    service_filter: Optional[str] = Query(None),
    current_user: dict = Depends(require_write_access)
):
    """Create a health rule from a template"""
    templates = await health_rule_engine.get_rule_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    result = await health_rule_engine.create_rule(
        name=template["name"],
        description=template["description"],
        metric=template["metric"],
        operator=template["operator"],
        threshold=template["threshold"],
        duration=template["duration"],
        severity=template["severity"],
        category=template["category"],
        service_filter=service_filter,
        enabled=True,
        tenant_id=current_user.get("tenant_id"),
        created_by=current_user["email"]
    )
    return result
