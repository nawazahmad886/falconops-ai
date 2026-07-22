"""
FalconOps AI - Runbook Routes
Enterprise Runbook management and execution with automation engine
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from pydantic import BaseModel

from ..core.database import db
from ..models.schemas import RunbookCreate, RunbookResponse
from ..utils.auth import require_auth, require_write_access, get_current_user, build_tenant_query
from ..services.runbook_engine import runbook_engine, get_runbook_templates, get_action_types

router = APIRouter(prefix="/api/runbooks", tags=["Runbooks"])


# ======================== MODELS ========================

class RunbookStepCreate(BaseModel):
    name: str
    action_type: str
    config: dict = {}
    continue_on_failure: bool = False
    description: Optional[str] = None


class RunbookCreateEnhanced(BaseModel):
    name: str
    description: str
    service: str
    category: str = "general"
    trigger_conditions: Optional[dict] = None
    steps: List[dict]
    auto_execute: bool = False
    schedule: Optional[dict] = None  # Cron schedule support
    tags: List[str] = []
    # Structured trigger: {type: on_demand|problem|event|schedule|ai_anomaly, ...filter}.
    # Additive — trigger_conditions/schedule/auto_execute above are kept for back-compat
    # reads of runbooks created before this field existed.
    trigger: Optional[dict] = None


class RunbookExecuteRequest(BaseModel):
    variables: dict = {}
    trigger_source: str = "manual"


class ScheduleConfig(BaseModel):
    enabled: bool = False
    cron_expression: str = "0 * * * *"  # Default: every hour
    timezone: str = "UTC"
    next_run: Optional[str] = None


# ======================== CRUD OPERATIONS ========================

@router.get("", response_model=List[RunbookResponse])
async def get_runbooks(
    service: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get all runbooks with optional filters"""
    query = {}
    if service:
        query["service"] = service
    if category:
        query["category"] = category
    
    # Apply tenant filter if user has tenant_id
    if current_user and current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    runbooks = await db.runbooks.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [RunbookResponse(**r) for r in runbooks]


@router.post("", response_model=RunbookResponse)
async def create_runbook(runbook: RunbookCreateEnhanced, current_user: dict = Depends(require_write_access)):
    """Create a new runbook"""
    from ..services.workflow_trigger_service import derive_legacy_schedule

    runbook_id = str(uuid.uuid4())
    # A structured 'schedule' trigger drives its due-check through the same legacy
    # schedule.{enabled,cron_expression,next_run} fields the scheduler already knows
    # how to evaluate — derive it here unless the caller explicitly set one.
    schedule = runbook.schedule or derive_legacy_schedule(runbook.trigger)
    runbook_doc = {
        "id": runbook_id,
        "name": runbook.name,
        "description": runbook.description,
        "service": runbook.service,
        "category": runbook.category,
        "trigger_conditions": runbook.trigger_conditions,
        "steps": runbook.steps,
        "auto_execute": runbook.auto_execute,
        "schedule": schedule,
        "tags": runbook.tags,
        "trigger": runbook.trigger or {"type": "on_demand"},
        "execution_count": 0,
        "last_executed": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"],
        "tenant_id": current_user.get("tenant_id")
    }

    await db.runbooks.insert_one(runbook_doc)
    return RunbookResponse(**runbook_doc)


@router.get("/templates")
async def get_templates(current_user: Optional[dict] = Depends(get_current_user)):
    """Get predefined runbook templates"""
    templates = await get_runbook_templates()
    return {"templates": templates}


@router.post("/from-template/{template_id}")
async def create_from_template(
    template_id: str,
    service: str = Query(...),
    current_user: dict = Depends(require_write_access)
):
    """Create a runbook from a template"""
    from ..services.workflow_trigger_service import derive_legacy_schedule

    templates = await get_runbook_templates()
    template = next((t for t in templates if t["id"] == template_id), None)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    runbook_id = str(uuid.uuid4())
    template_trigger = template.get("trigger") or {"type": "on_demand"}
    runbook_doc = {
        "id": runbook_id,
        "name": template["name"],
        "description": template["description"],
        "service": service,
        "category": template.get("category", "general"),
        "trigger_conditions": None,
        "steps": template["steps"],
        "auto_execute": False,
        "schedule": derive_legacy_schedule(template_trigger),
        "tags": [template.get("category", "general")],
        "trigger": template_trigger,
        "execution_count": 0,
        "last_executed": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"],
        "tenant_id": current_user.get("tenant_id"),
        "from_template": template_id
    }
    
    await db.runbooks.insert_one(runbook_doc)
    return {"id": runbook_id, "message": "Runbook created from template", "runbook": {k: v for k, v in runbook_doc.items() if k != "_id"}}


@router.get("/categories")
async def get_categories(current_user: Optional[dict] = Depends(get_current_user)):
    """Get available runbook categories"""
    return {
        "categories": [
            {"id": "infrastructure", "name": "Infrastructure", "icon": "server", "description": "Server and resource management"},
            {"id": "monitoring", "name": "Monitoring", "icon": "activity", "description": "Health checks and monitoring tasks"},
            {"id": "incident", "name": "Incident Response", "icon": "alert-triangle", "description": "Incident handling workflows"},
            {"id": "deployment", "name": "Deployment", "icon": "rocket", "description": "Deployment and release automation"},
            {"id": "security", "name": "Security", "icon": "shield", "description": "Security and compliance tasks"},
            {"id": "database", "name": "Database", "icon": "database", "description": "Database maintenance and operations"},
            {"id": "network", "name": "Network", "icon": "network", "description": "Network troubleshooting"},
            {"id": "agent", "name": "AI Agent", "icon": "bot", "description": "Trigger-driven workflows that call a specialized AI agent"},
            {"id": "general", "name": "General", "icon": "folder", "description": "General purpose runbooks"}
        ]
    }


@router.get("/action-types")
async def get_action_types_endpoint(current_user: Optional[dict] = Depends(get_current_user)):
    """Get available action types for runbook steps"""
    action_types = await get_action_types()
    return {"action_types": action_types}


@router.get("/agent-catalog")
async def get_agent_catalog_endpoint(current_user: Optional[dict] = Depends(get_current_user)):
    """List every AI agent a 'call_agent' workflow step can invoke — the 5 specialized
    security agents plus the 3 core (rca/summarizer/healer) agents. Powers the
    workflow builder's agent-picker dropdown."""
    from ..services.security_agents_service import get_agent_catalog as get_security_catalog
    from ..services.ops_agents_service import get_agent_catalog as get_ops_catalog
    from ..services.ai_agents_service import AGENTS

    security = [{**a, "agent_source": "security"} for a in get_security_catalog()]
    ops = [{**a, "agent_source": "ops"} for a in get_ops_catalog()]
    core = [
        {"id": aid, "name": a["name"], "specialty": a["role"], "tools": [], "agent_source": "core"}
        for aid, a in AGENTS.items()
    ]
    return {"agents": security + ops + core}


@router.get("/trigger-types")
async def get_trigger_types_endpoint(current_user: Optional[dict] = Depends(get_current_user)):
    """List the trigger types a workflow can start from, with their filter schema —
    keeps the frontend's trigger-config panel data-driven instead of hardcoded twice."""
    return {
        "trigger_types": [
            {"id": "on_demand", "name": "On-Demand", "description": "Only runs when manually executed",
             "filter_fields": []},
            {"id": "problem", "name": "Problem Trigger", "description": "Runs when a matching alert/problem is created",
             "filter_fields": [
                 {"name": "severity", "label": "Severity", "type": "multiselect",
                  "options": ["critical", "high", "medium", "low", "info"]},
                 {"name": "service", "label": "Service (optional)", "type": "text"},
             ]},
            {"id": "event", "name": "Event Trigger", "description": "Runs when a matching ingested SOC event occurs",
             "filter_fields": [
                 {"name": "source", "label": "Event source (optional)", "type": "text"},
                 {"name": "keyword", "label": "Message keyword (optional)", "type": "text"},
             ]},
            {"id": "ai_anomaly", "name": "AI Anomaly Trigger", "description": "Runs when the real threat/anomaly engine flags a new finding",
             "filter_fields": [
                 {"name": "min_severity", "label": "Minimum severity", "type": "select",
                  "options": ["low", "medium", "high", "critical"]},
             ]},
            {"id": "schedule", "name": "Schedule Trigger", "description": "Runs on a fixed time, interval, or cron schedule",
             "filter_fields": [
                 {"name": "mode", "label": "Mode", "type": "select", "options": ["cron", "interval", "fixed_time"]},
                 {"name": "cron_expression", "label": "Cron expression", "type": "text"},
                 {"name": "interval_minutes", "label": "Interval (minutes)", "type": "number"},
                 {"name": "fixed_time", "label": "Fixed time (HH:MM UTC)", "type": "text"},
             ]},
        ]
    }


@router.get("/scheduled")
async def get_scheduled_runbooks(current_user: dict = Depends(require_auth)):
    """Get all scheduled runbooks"""
    query = {"schedule.enabled": True}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    runbooks = await db.runbooks.find(query, {"_id": 0}).sort("schedule.next_run", 1).to_list(100)
    
    return {
        "scheduled_runbooks": runbooks,
        "total": len(runbooks)
    }


@router.get("/schedules/presets")
async def get_schedule_presets(current_user: Optional[dict] = Depends(get_current_user)):
    """Get common cron schedule presets"""
    return {
        "presets": [
            {"name": "Every minute", "cron": "* * * * *", "description": "Run every minute"},
            {"name": "Every 5 minutes", "cron": "*/5 * * * *", "description": "Run every 5 minutes"},
            {"name": "Every 15 minutes", "cron": "*/15 * * * *", "description": "Run every 15 minutes"},
            {"name": "Every 30 minutes", "cron": "*/30 * * * *", "description": "Run every 30 minutes"},
            {"name": "Every hour", "cron": "0 * * * *", "description": "Run at the start of every hour"},
            {"name": "Every 6 hours", "cron": "0 */6 * * *", "description": "Run every 6 hours"},
            {"name": "Daily at midnight", "cron": "0 0 * * *", "description": "Run once daily at 00:00"},
            {"name": "Daily at 6 AM", "cron": "0 6 * * *", "description": "Run once daily at 06:00"},
            {"name": "Daily at noon", "cron": "0 12 * * *", "description": "Run once daily at 12:00"},
            {"name": "Weekly (Monday)", "cron": "0 0 * * 1", "description": "Run every Monday at 00:00"},
            {"name": "Weekly (Sunday)", "cron": "0 0 * * 0", "description": "Run every Sunday at 00:00"},
            {"name": "Monthly (1st)", "cron": "0 0 1 * *", "description": "Run on the 1st of every month"},
            {"name": "Quarterly", "cron": "0 0 1 */3 *", "description": "Run every 3 months"}
        ]
    }


@router.get("/{runbook_id}", response_model=RunbookResponse)
async def get_runbook(runbook_id: str, current_user: Optional[dict] = Depends(get_current_user)):
    """Get single runbook by ID"""
    runbook = await db.runbooks.find_one({"id": runbook_id}, {"_id": 0})
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return RunbookResponse(**runbook)


@router.put("/{runbook_id}", response_model=RunbookResponse)
async def update_runbook(runbook_id: str, runbook: RunbookCreateEnhanced, current_user: dict = Depends(require_write_access)):
    """Update a runbook"""
    from ..services.workflow_trigger_service import derive_legacy_schedule

    existing = await db.runbooks.find_one({"id": runbook_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Runbook not found")

    schedule = runbook.schedule or derive_legacy_schedule(runbook.trigger)
    update_data = {
        "name": runbook.name,
        "description": runbook.description,
        "service": runbook.service,
        "category": runbook.category,
        "trigger_conditions": runbook.trigger_conditions,
        "steps": runbook.steps,
        "auto_execute": runbook.auto_execute,
        "schedule": schedule,
        "tags": runbook.tags,
        "trigger": runbook.trigger or {"type": "on_demand"},
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.runbooks.update_one({"id": runbook_id}, {"$set": update_data})
    updated = await db.runbooks.find_one({"id": runbook_id}, {"_id": 0})
    return RunbookResponse(**updated)


@router.delete("/{runbook_id}")
async def delete_runbook(runbook_id: str, current_user: dict = Depends(require_write_access)):
    """Delete a runbook"""
    result = await db.runbooks.delete_one({"id": runbook_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return {"message": "Runbook deleted"}


# ======================== EXECUTION ========================

@router.post("/{runbook_id}/execute")
async def execute_runbook(
    runbook_id: str,
    request: RunbookExecuteRequest = None,
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(require_auth)
):
    """Execute a runbook with the automation engine"""
    runbook = await db.runbooks.find_one({"id": runbook_id}, {"_id": 0})
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    variables = request.variables if request else {}
    trigger_source = request.trigger_source if request else "manual"
    
    # Execute the runbook
    result = await runbook_engine.execute_runbook(
        runbook_id=runbook_id,
        trigger_source=trigger_source,
        trigger_context=variables,
        user_email=current_user["email"],
        tenant_id=current_user.get("tenant_id")
    )
    
    return result


@router.post("/{runbook_id}/dry-run")
async def dry_run_runbook(
    runbook_id: str,
    request: RunbookExecuteRequest = None,
    current_user: dict = Depends(require_auth)
):
    """Dry run a runbook (validate without executing)"""
    runbook = await db.runbooks.find_one({"id": runbook_id}, {"_id": 0})
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    # Validate steps
    validation_results = []
    for idx, step in enumerate(runbook.get("steps", [])):
        step_validation = {
            "step_number": idx + 1,
            "name": step.get("name", f"Step {idx + 1}"),
            "action_type": step.get("action_type", "unknown"),
            "valid": True,
            "warnings": []
        }
        
        # Check for common issues
        action_type = step.get("action_type", "")
        config = step.get("config", {})
        
        if action_type == "http_request":
            if not config.get("url"):
                step_validation["valid"] = False
                step_validation["warnings"].append("URL is required for HTTP requests")
        elif action_type == "notification":
            if not config.get("message"):
                step_validation["warnings"].append("No message specified for notification")
        elif action_type == "delay":
            seconds = config.get("seconds", 0)
            if seconds > 60:
                step_validation["warnings"].append("Delay exceeds maximum (60 seconds)")
        
        validation_results.append(step_validation)
    
    all_valid = all(r["valid"] for r in validation_results)
    
    return {
        "runbook_id": runbook_id,
        "runbook_name": runbook["name"],
        "valid": all_valid,
        "steps_count": len(validation_results),
        "step_validations": validation_results
    }


@router.get("/{runbook_id}/executions")
async def get_runbook_executions(
    runbook_id: str,
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth)
):
    """Get execution history for a runbook"""
    runbook = await db.runbooks.find_one({"id": runbook_id})
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    executions = await db.runbook_executions.find(
        {"runbook_id": runbook_id}, {"_id": 0}
    ).sort("started_at", -1).limit(limit).to_list(limit)
    
    return {"executions": executions}


@router.get("/executions/{execution_id}")
async def get_execution_details(
    execution_id: str,
    current_user: dict = Depends(require_auth)
):
    """Get detailed execution results"""
    execution = await db.runbook_executions.find_one({"id": execution_id}, {"_id": 0})
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution


# ======================== STATISTICS ========================

@router.get("/stats/summary")
async def get_runbook_stats(current_user: dict = Depends(require_auth)):
    """Get runbook statistics"""
    query = build_tenant_query(current_user.get("tenant_id"))
    
    total_runbooks = await db.runbooks.count_documents(query)
    total_executions = await db.runbook_executions.count_documents(query)
    
    # Get success/failure counts
    successful = await db.runbook_executions.count_documents({**query, "status": "completed"})
    failed = await db.runbook_executions.count_documents({**query, "status": "failed"})
    
    # Get auto-execute enabled count
    auto_enabled = await db.runbooks.count_documents({**query, "auto_execute": True})
    
    # Get recent executions
    recent = await db.runbook_executions.find(
        query, {"_id": 0}
    ).sort("started_at", -1).limit(5).to_list(5)
    
    # Get runbooks by category
    pipeline = [
        {"$match": query} if query else {"$match": {}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$project": {"category": "$_id", "count": 1, "_id": 0}}
    ]
    by_category = await db.runbooks.aggregate(pipeline).to_list(20)
    
    return {
        "total_runbooks": total_runbooks,
        "total_executions": total_executions,
        "successful_executions": successful,
        "failed_executions": failed,
        "success_rate": (successful / total_executions * 100) if total_executions > 0 else 0,
        "auto_execute_enabled": auto_enabled,
        "by_category": by_category,
        "recent_executions": recent
    }


# ======================== TRIGGERS ========================

@router.post("/trigger/alert")
async def trigger_from_alert(
    alert_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Trigger auto-execute runbooks based on alert"""
    # Get the alert
    alert = await db.alerts.find_one({"id": alert_id}, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Find matching runbooks with auto_execute enabled
    matching_runbooks = await db.runbooks.find({
        "auto_execute": True,
        "$or": [
            {"service": alert.get("service")},
            {"trigger_conditions.severity": alert.get("severity")},
            {"trigger_conditions.alert_type": alert.get("title")}
        ]
    }, {"_id": 0}).to_list(10)
    
    results = []
    for runbook in matching_runbooks:
        result = await runbook_engine.execute_runbook(
            runbook_id=runbook["id"],
            trigger_source="alert",
            trigger_context={
                "alert_id": alert_id,
                "alert_title": alert.get("title"),
                "alert_severity": alert.get("severity"),
                "alert_service": alert.get("service"),
                "alert_host": alert.get("host")
            },
            user_email="system",
            tenant_id=alert.get("tenant_id")
        )
        results.append({
            "runbook_id": runbook["id"],
            "runbook_name": runbook["name"],
            "execution_result": result
        })
    
    return {
        "alert_id": alert_id,
        "triggered_runbooks": len(results),
        "results": results
    }


# ======================== SCHEDULING ========================

@router.post("/{runbook_id}/schedule")
async def set_runbook_schedule(
    runbook_id: str,
    schedule: ScheduleConfig,
    current_user: dict = Depends(require_write_access)
):
    """Set or update schedule for a runbook"""
    query = {"id": runbook_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    runbook = await db.runbooks.find_one(query)
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    # Calculate next run based on cron expression
    next_run = None
    if schedule.enabled:
        try:
            from croniter import croniter
            cron = croniter(schedule.cron_expression, datetime.now(timezone.utc))
            next_run = cron.get_next(datetime).isoformat()
        except:
            # If croniter not available, estimate next run
            next_run = datetime.now(timezone.utc).isoformat()
    
    schedule_doc = {
        "enabled": schedule.enabled,
        "cron_expression": schedule.cron_expression,
        "timezone": schedule.timezone,
        "next_run": next_run,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    await db.runbooks.update_one(
        {"id": runbook_id},
        {"$set": {"schedule": schedule_doc}}
    )
    
    return {
        "message": "Schedule updated",
        "runbook_id": runbook_id,
        "schedule": schedule_doc
    }


@router.delete("/{runbook_id}/schedule")
async def remove_runbook_schedule(
    runbook_id: str,
    current_user: dict = Depends(require_write_access)
):
    """Remove schedule from a runbook"""
    query = {"id": runbook_id}
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    runbook = await db.runbooks.find_one(query)
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    await db.runbooks.update_one(
        {"id": runbook_id},
        {"$set": {"schedule": None}}
    )
    
    return {"message": "Schedule removed", "runbook_id": runbook_id}


@router.post("/scheduled/execute")
async def execute_scheduled_runbooks(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_write_access)
):
    """Execute all due scheduled runbooks (typically called by a cron job — the same
    logic also runs automatically every 60s via workflow_trigger_service.
    runbook_schedule_scheduler, registered in main.py's lifespan)."""
    from ..services.workflow_trigger_service import execute_due_runbooks
    return await execute_due_runbooks(tenant_id=current_user.get("tenant_id"))
