"""
FalconOps AI - Synthetic URL Monitoring Routes
CRUD for URL monitors, check execution, results, and availability.
"""
import uuid
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.database import db
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/synthetic", tags=["synthetic-monitoring"])


class SyntheticMonitorCreate(BaseModel):
    name: str
    url: Optional[str] = None  # optional for check_type='multi_step' which uses steps[]
    check_type: str = "http"  # http, login, login_otp, multi_step
    interval: int = 300  # seconds
    timeout: int = 30
    expected_status: int = 200
    expected_text: str = ""
    auth_config: dict = {}  # {login_url, username, password, otp_secret, etc.}
    # Multi-step + assertion engine
    steps: Optional[List[dict]] = None  # list of step dicts (see synthetic_service._check_multi_step)
    assertions: Optional[List[dict]] = None  # legacy single-step assertions (for http check_type)
    max_response_time_ms: Optional[int] = None
    ssl_expiry_warn_days: Optional[int] = 14
    apply_safe_defaults: Optional[bool] = True
    variables: Optional[dict] = None  # initial variables available to step 1
    enabled: bool = True
    tags: List[str] = []


class SyntheticMonitorUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    check_type: Optional[str] = None
    interval: Optional[int] = None
    timeout: Optional[int] = None
    expected_status: Optional[int] = None
    expected_text: Optional[str] = None
    auth_config: Optional[dict] = None
    steps: Optional[List[dict]] = None
    assertions: Optional[List[dict]] = None
    max_response_time_ms: Optional[int] = None
    ssl_expiry_warn_days: Optional[int] = None
    apply_safe_defaults: Optional[bool] = None
    variables: Optional[dict] = None
    enabled: Optional[bool] = None
    tags: Optional[List[str]] = None


# ── CRUD ──

@router.get("/monitors")
async def list_monitors(user: dict = Depends(require_auth)):
    monitors = await db.db.synthetic_monitors.find({}, {"_id": 0}).to_list(length=100)
    # Enrich with availability
    for m in monitors:
        from ..services.synthetic_service import calculate_availability
        avail = await calculate_availability(m["id"], 24)
        m["availability_24h"] = avail["availability_pct"]
        m["total_checks_24h"] = avail["total_checks"]
    return {"monitors": monitors}


@router.post("/monitors")
async def create_monitor(body: SyntheticMonitorCreate, user: dict = Depends(require_auth)):
    payload = body.dict()
    # Validate: either url (single check) or steps[] (multi-step) must be provided
    if not payload.get("url") and not payload.get("steps"):
        raise HTTPException(status_code=400, detail="Either 'url' or non-empty 'steps[]' must be provided")
    if payload.get("check_type") == "multi_step" and not payload.get("steps"):
        raise HTTPException(status_code=400, detail="check_type='multi_step' requires non-empty steps[]")

    # Hydrate per-step assertions with safe defaults at create time so the persisted
    # document reflects what will be evaluated at check time (matches URL monitor behaviour).
    if payload.get("check_type") == "multi_step" and payload.get("steps"):
        from ..services.assertion_engine import merge_safe_defaults
        from ..services.feature_flags_service import get_deny_patterns
        try:
            live_patterns = await get_deny_patterns()
            live_defaults = [
                {"type": "not_contains", "value": p, "case_sensitive": False}
                for p in live_patterns
            ]
        except Exception:
            live_defaults = None

        for step in payload["steps"]:
            if step.get("apply_safe_defaults", True):
                if live_defaults is not None:
                    user_assertions = list(step.get("assertions") or [])
                    existing = {(a.get("type"), str(a.get("value", "")).lower()) for a in user_assertions}
                    for d in live_defaults:
                        key = (d["type"], str(d["value"]).lower())
                        if key not in existing:
                            user_assertions.append(d)
                    step["assertions"] = user_assertions
                else:
                    step["assertions"] = merge_safe_defaults(step.get("assertions"), enable=True)

    doc = {
        "id": str(uuid.uuid4()),
        **payload,
        "created_by": user["email"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_check": None,
        "last_status": "pending",
        "last_response_time": None,
        "is_up": None,
    }
    await db.db.synthetic_monitors.insert_one({**doc})
    doc.pop("_id", None)
    return doc


@router.get("/monitors/{monitor_id}")
async def get_monitor(monitor_id: str, user: dict = Depends(require_auth)):
    doc = await db.db.synthetic_monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Monitor not found")
    from ..services.synthetic_service import calculate_availability
    avail = await calculate_availability(monitor_id, 24)
    doc["availability_24h"] = avail["availability_pct"]
    doc["total_checks_24h"] = avail["total_checks"]
    return doc


@router.put("/monitors/{monitor_id}")
async def update_monitor(monitor_id: str, body: SyntheticMonitorUpdate, user: dict = Depends(require_auth)):
    update = {k: v for k, v in body.dict().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.db.synthetic_monitors.update_one({"id": monitor_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Monitor not found")
    doc = await db.db.synthetic_monitors.find_one({"id": monitor_id}, {"_id": 0})
    return doc


@router.delete("/monitors/{monitor_id}")
async def delete_monitor(monitor_id: str, user: dict = Depends(require_auth)):
    result = await db.db.synthetic_monitors.delete_one({"id": monitor_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Monitor not found")
    await db.db.synthetic_results.delete_many({"monitor_id": monitor_id})
    return {"deleted": True}


@router.post("/monitors/{monitor_id}/toggle")
async def toggle_monitor(monitor_id: str, user: dict = Depends(require_auth)):
    doc = await db.db.synthetic_monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Monitor not found")
    new_state = not doc.get("enabled", True)
    await db.db.synthetic_monitors.update_one({"id": monitor_id}, {"$set": {"enabled": new_state}})
    return {"id": monitor_id, "enabled": new_state}


# ── Check Execution ──

@router.post("/monitors/{monitor_id}/check")
async def run_check(monitor_id: str, user: dict = Depends(require_auth)):
    doc = await db.db.synthetic_monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Monitor not found")
    from ..services.synthetic_service import execute_check
    result = await execute_check(doc)
    return result


# ── Results ──

@router.get("/monitors/{monitor_id}/results")
async def get_results(
    monitor_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(require_auth),
):
    results = await db.db.synthetic_results.find(
        {"monitor_id": monitor_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(length=limit)
    return {"results": results}


@router.get("/monitors/{monitor_id}/availability")
async def get_availability(
    monitor_id: str,
    hours: int = Query(default=24, ge=1, le=720),
    user: dict = Depends(require_auth),
):
    from ..services.synthetic_service import calculate_availability
    avail = await calculate_availability(monitor_id, hours)
    return avail


@router.get("/monitors/{monitor_id}/timeseries")
async def get_timeseries(
    monitor_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    user: dict = Depends(require_auth),
):
    from ..services.synthetic_service import get_response_time_series
    data = await get_response_time_series(monitor_id, hours)
    return {"timeseries": data}


# ── Dashboard Overview ──

@router.get("/dashboard")
async def get_dashboard(user: dict = Depends(require_auth)):
    monitors = await db.db.synthetic_monitors.find({}, {"_id": 0}).to_list(length=100)
    total = len(monitors)
    up = sum(1 for m in monitors if m.get("is_up") is True)
    down = sum(1 for m in monitors if m.get("is_up") is False)
    pending = total - up - down

    return {
        "monitors": monitors,
        "summary": {
            "total": total,
            "up": up,
            "down": down,
            "pending": pending,
            "availability_avg": round(up / max(total, 1) * 100, 1),
        }
    }


# ── Seed Demo Data ──

@router.post("/seed")
async def seed_demo_data(user: dict = Depends(require_auth)):
    """Seed demo synthetic monitors with historical results."""
    # Clear existing
    await db.db.synthetic_monitors.delete_many({})
    await db.db.synthetic_results.delete_many({})

    demo_monitors = [
        {"name": "Production API", "url": "https://api.example.com/health", "check_type": "http", "interval": 60,
         "expected_status": 200, "tags": ["production", "api"]},
        {"name": "Customer Portal", "url": "https://portal.example.com/login", "check_type": "login", "interval": 300,
         "auth_config": {"login_url": "https://portal.example.com/login", "username": "monitor@example.com",
                        "password": "MonitorPass123", "success_text": "Dashboard"},
         "tags": ["production", "web"]},
        {"name": "Admin Panel (OTP)", "url": "https://admin.example.com", "check_type": "login_otp", "interval": 600,
         "auth_config": {"login_url": "https://admin.example.com/auth", "username": "admin",
                        "password": "AdminPass", "otp_secret": "JBSWY3DPEHPK3PXP",
                        "otp_field": "totp_code", "success_text": "Admin Dashboard"},
         "tags": ["production", "admin"]},
        {"name": "Staging API", "url": "https://staging-api.example.com/health", "check_type": "http", "interval": 120,
         "expected_status": 200, "tags": ["staging", "api"]},
        {"name": "Payment Gateway", "url": "https://pay.example.com/status", "check_type": "http", "interval": 60,
         "expected_text": "operational", "tags": ["production", "payment"]},
    ]

    now = datetime.now(timezone.utc)
    created_monitors = []

    for dm in demo_monitors:
        monitor_id = str(uuid.uuid4())
        is_up = random.random() > 0.1  # 90% chance up

        monitor_doc = {
            "id": monitor_id,
            "name": dm["name"],
            "url": dm["url"],
            "check_type": dm["check_type"],
            "interval": dm["interval"],
            "timeout": 30,
            "expected_status": dm.get("expected_status", 200),
            "expected_text": dm.get("expected_text", ""),
            "auth_config": dm.get("auth_config", {}),
            "enabled": True,
            "tags": dm.get("tags", []),
            "created_by": user["email"],
            "created_at": now.isoformat(),
            "last_check": now.isoformat(),
            "last_status": "success" if is_up else "failed",
            "last_response_time": round(random.uniform(50, 800), 1),
            "is_up": is_up,
        }
        await db.db.synthetic_monitors.insert_one({**monitor_doc})
        monitor_doc.pop("_id", None)
        created_monitors.append(monitor_doc)

        # Generate 96 historical check results (24h at 15-min intervals)
        results = []
        for i in range(96):
            ts = now - timedelta(minutes=15 * (96 - i))
            hour = ts.hour
            # Simulate realistic patterns
            base_rt = 150 + 50 * math.sin(math.pi * (hour - 8) / 12)  # Peak during business hours
            resp_time = max(20, round(base_rt + random.gauss(0, 30), 1))
            check_up = random.random() > 0.02  # 98% uptime

            steps = [{"step": "HTTP GET", "url": dm["url"], "status_code": 200 if check_up else 503,
                      "status": "pass" if check_up else "fail", "response_time_ms": resp_time}]
            if dm["check_type"] == "login":
                steps.append({"step": "Load Login Page", "status": "pass", "status_code": 200, "response_time_ms": resp_time * 0.4})
                steps.append({"step": "Submit Login", "status": "pass" if check_up else "fail", "status_code": 200 if check_up else 401, "response_time_ms": resp_time * 0.6})
            elif dm["check_type"] == "login_otp":
                steps.append({"step": "Load Login Page", "status": "pass", "status_code": 200, "response_time_ms": resp_time * 0.3})
                steps.append({"step": "Submit Credentials", "status": "pass", "status_code": 200, "response_time_ms": resp_time * 0.3})
                steps.append({"step": "Submit OTP", "status": "pass" if check_up else "fail", "status_code": 200 if check_up else 401,
                              "response_time_ms": resp_time * 0.4, "otp_generated": True})

            results.append({
                "id": str(uuid.uuid4()),
                "monitor_id": monitor_id,
                "monitor_name": dm["name"],
                "url": dm["url"],
                "check_type": dm["check_type"],
                "timestamp": ts.isoformat(),
                "status": "success" if check_up else "failed",
                "status_code": 200 if check_up else 503,
                "response_time_ms": resp_time,
                "is_up": check_up,
                "steps": steps,
            })

        if results:
            await db.db.synthetic_results.insert_many(results)

    return {
        "monitors_created": len(created_monitors),
        "results_seeded": 96 * len(created_monitors),
        "monitors": created_monitors,
    }
