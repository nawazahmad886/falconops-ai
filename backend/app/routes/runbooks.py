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
    runbook_id = str(uuid.uuid4())
    runbook_doc = {
        "id": runbook_id,
        "name": runbook.name,
        "description": runbook.description,
        "service": runbook.service,
        "category": runbook.category,
        "trigger_conditions": runbook.trigger_conditions,
        "steps": runbook.steps,
        "auto_execute": runbook.auto_execute,
        "schedule": runbook.schedule,
        "tags": runbook.tags,
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
    templates = await get_runbook_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    runbook_id = str(uuid.uuid4())
    runbook_doc = {
        "id": runbook_id,
        "name": template["name"],
        "description": template["description"],
        "service": service,
        "category": template.get("category", "general"),
        "trigger_conditions": None,
        "steps": template["steps"],
        "auto_execute": False,
        "schedule": None,
        "tags": [template.get("category", "general")],
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
            {"id": "general", "name": "General", "icon": "folder", "description": "General purpose runbooks"}
        ]
    }


@router.get("/action-types")
async def get_action_types_endpoint(current_user: Optional[dict] = Depends(get_current_user)):
    """Get available action types for runbook steps"""
    action_types = await get_action_types()
    return {"action_types": action_types}


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
    existing = await db.runbooks.find_one({"id": runbook_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    update_data = {
        "name": runbook.name,
        "description": runbook.description,
        "service": runbook.service,
        "category": runbook.category,
        "trigger_conditions": runbook.trigger_conditions,
        "steps": runbook.steps,
        "auto_execute": runbook.auto_execute,
        "schedule": runbook.schedule,
        "tags": runbook.tags,
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
    """Execute all due scheduled runbooks (typically called by a cron job)"""
    now = datetime.now(timezone.utc).isoformat()
    
    query = {
        "schedule.enabled": True,
        "schedule.next_run": {"$lte": now}
    }
    if current_user.get("tenant_id"):
        query = build_tenant_query(current_user.get("tenant_id"), query)
    
    due_runbooks = await db.runbooks.find(query, {"_id": 0}).to_list(50)
    
    results = []
    for runbook in due_runbooks:
        # Execute in background
        result = await runbook_engine.execute_runbook(
            runbook_id=runbook["id"],
            trigger_source="scheduled",
            trigger_context={"scheduled_at": now},
            user_email="scheduler",
            tenant_id=runbook.get("tenant_id")
        )
        
        # Update next run time
        try:
            from croniter import croniter
            cron = croniter(runbook["schedule"]["cron_expression"], datetime.now(timezone.utc))
            next_run = cron.get_next(datetime).isoformat()
            await db.runbooks.update_one(
                {"id": runbook["id"]},
                {"$set": {"schedule.next_run": next_run}}
            )
        except:
            pass
        
        results.append({
            "runbook_id": runbook["id"],
            "runbook_name": runbook["name"],
            "success": result.get("success", False)
        })
    
    return {
        "executed": len(results),
        "results": results
    }
