"""
FalconOps AI - Synthetic Monitoring Routes
Browser-based synthetic monitoring and login flow testing
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query

from ..core.database import db
from ..models.schemas import SyntheticMonitorCreate
from ..utils.auth import require_auth, require_write_access

router = APIRouter(prefix="/api/synthetic", tags=["Synthetic Monitoring"])


@router.get("/monitors")
async def get_synthetic_monitors(current_user: dict = Depends(require_auth)):
    """Get all synthetic monitors"""
    monitors = await db.synthetic_monitors.find({}, {"_id": 0}).to_list(100)
    return monitors


@router.post("/monitors")
async def create_synthetic_monitor(monitor: SyntheticMonitorCreate, current_user: dict = Depends(require_write_access)):
    """Create a synthetic login flow monitor"""
    monitor_id = str(uuid.uuid4())
    
    monitor_doc = {
        "id": monitor_id,
        "name": monitor.name,
        "target_url": monitor.target_url,
        "login_url": monitor.login_url,
        "test_username": monitor.test_username,
        "test_password": monitor.test_password,
        "username_selector": monitor.username_selector,
        "password_selector": monitor.password_selector,
        "submit_selector": monitor.submit_selector,
        "success_indicator": monitor.success_indicator,
        "check_interval_seconds": monitor.check_interval_seconds,
        "timeout_seconds": monitor.timeout_seconds,
        "enabled": monitor.enabled,
        "status": "pending",
        "last_check": None,
        "last_result": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"]
    }
    
    await db.synthetic_monitors.insert_one(monitor_doc)
    return {k: v for k, v in monitor_doc.items() if k != "_id"}


@router.get("/monitors/{monitor_id}")
async def get_synthetic_monitor(monitor_id: str, current_user: dict = Depends(require_auth)):
    """Get a specific synthetic monitor"""
    monitor = await db.synthetic_monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not monitor:
        raise HTTPException(status_code=404, detail="Synthetic monitor not found")
    return monitor


@router.delete("/monitors/{monitor_id}")
async def delete_synthetic_monitor(monitor_id: str, current_user: dict = Depends(require_write_access)):
    """Delete a synthetic monitor"""
    result = await db.synthetic_monitors.delete_one({"id": monitor_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return {"message": "Synthetic monitor deleted"}


@router.post("/monitors/{monitor_id}/test")
async def test_synthetic_monitor(monitor_id: str, current_user: dict = Depends(require_auth)):
    """Execute a synthetic monitor test (simulated)"""
    import random
    
    monitor = await db.synthetic_monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    
    # Simulate test execution
    success = random.random() > 0.1  # 90% success rate simulation
    duration_ms = random.uniform(500, 3000)
    
    result = {
        "id": str(uuid.uuid4()),
        "monitor_id": monitor_id,
        "success": success,
        "status": "passed" if success else "failed",
        "duration_ms": round(duration_ms, 2),
        "steps": [
            {"step": "navigate_to_login", "status": "passed", "duration_ms": round(duration_ms * 0.2, 2)},
            {"step": "enter_credentials", "status": "passed", "duration_ms": round(duration_ms * 0.1, 2)},
            {"step": "submit_form", "status": "passed", "duration_ms": round(duration_ms * 0.1, 2)},
            {"step": "verify_login", "status": "passed" if success else "failed", "duration_ms": round(duration_ms * 0.6, 2)}
        ],
        "error_message": None if success else "Login verification failed - success indicator not found",
        "screenshot_url": None,
        "executed_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Store result
    await db.synthetic_results.insert_one(result)
    
    # Update monitor status
    await db.synthetic_monitors.update_one(
        {"id": monitor_id},
        {"$set": {
            "status": "up" if success else "down",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "last_result": {k: v for k, v in result.items() if k != "_id"}
        }}
    )
    
    return {k: v for k, v in result.items() if k != "_id"}


@router.get("/monitors/{monitor_id}/results")
async def get_synthetic_results(
    monitor_id: str,
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_auth)
):
    """Get test results for a synthetic monitor"""
    results = await db.synthetic_results.find(
        {"monitor_id": monitor_id}, {"_id": 0}
    ).sort("executed_at", -1).limit(limit).to_list(limit)
    
    return results
