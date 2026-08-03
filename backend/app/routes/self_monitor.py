"""
FalconOps AI - Self-Monitoring Module
Platform health checks: API, MongoDB, services, system resources, background jobs
"""
import os
import time
import platform
import psutil
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends
from ..core.database import db
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/self-monitor", tags=["Self-Monitoring"])

# Track startup time
_STARTUP_TIME = datetime.now(timezone.utc)


@router.get("/env-check")
async def env_check(user: dict = Depends(require_auth)) -> dict:
    """On-prem installation diagnostics: reports which env vars are set/missing
    (booleans only — never echoes secret values). Use after install to verify
    the .env files are wired correctly before testing modules."""
    def is_set(key: str) -> bool:
        return bool(os.environ.get(key, "").strip())

    jwt = os.environ.get("JWT_SECRET_KEY", "")
    llm_keys = ["EMERGENT_LLM_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]
    llm_configured = any(is_set(k) for k in llm_keys) or (os.environ.get("LLM_PROVIDER", "").lower() in ("ollama", "rule_based"))
    required = {
        "MONGO_URL": is_set("MONGO_URL"),
        "DB_NAME": is_set("DB_NAME"),
        "JWT_SECRET_KEY": bool(jwt) and jwt != "fallback_secret"
                          and "change-this" not in jwt,
    }
    optional = {
        "CORS_ORIGINS": is_set("CORS_ORIGINS"),
        "LLM (any provider or ollama/rule_based)": llm_configured,
        "LLM_PROVIDER": os.environ.get("LLM_PROVIDER") or "(auto-detect)",
        "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL") or "(default http://localhost:11434)",
        "RESEND_API_KEY": is_set("RESEND_API_KEY"),
        "LICENSE_KEY": is_set("LICENSE_KEY"),
        "REDIS_URL": is_set("REDIS_URL"),
        "CHROMA_PATH": os.environ.get("CHROMA_PATH") or "(default backend/data/chroma)",
        "STRIPE_API_KEY": is_set("STRIPE_API_KEY"),
    }
    problems = [k for k, ok in required.items() if not ok]
    warnings = []
    if os.environ.get("CORS_ORIGINS", "*").strip() == "*":
        warnings.append("CORS_ORIGINS is '*' — restrict to your domain(s) in production")
    if not llm_configured:
        warnings.append("No LLM provider configured — AI features will run in rule_based mode")
    return {
        "status": "ok" if not problems else "misconfigured",
        "required": required,
        "optional": optional,
        "problems": problems,
        "warnings": warnings,
    }


async def _mongo_health() -> dict:
    """Check MongoDB connectivity and stats."""
    try:
        t0 = time.monotonic()
        await db.command("ping")
        latency_ms = round((time.monotonic() - t0) * 1000, 1)

        stats = await db.command("dbStats")
        collections = await db.list_collection_names()

        # Get doc counts for key collections
        key_cols = ["alerts", "incidents", "monitors", "servers", "health_rules",
                    "users", "runbooks", "metrics_timeseries"]
        col_counts = {}
        for c in key_cols:
            if c in collections:
                col_counts[c] = await db[c].estimated_document_count()

        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "total_collections": len(collections),
            "data_size_mb": round(stats.get("dataSize", 0) / (1024 * 1024), 2),
            "storage_size_mb": round(stats.get("storageSize", 0) / (1024 * 1024), 2),
            "index_size_mb": round(stats.get("indexSize", 0) / (1024 * 1024), 2),
            "total_documents": stats.get("objects", 0),
            "collection_counts": col_counts,
        }
    except Exception as e:
        return {"status": "critical", "error": str(e), "latency_ms": -1}


def _system_resources() -> dict:
    """Collect host-level resource metrics via psutil."""
    cpu_pct = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    boot = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    load1, load5, load15 = psutil.getloadavg()

    return {
        "cpu_percent": cpu_pct,
        "cpu_count": psutil.cpu_count(),
        "memory_total_gb": round(mem.total / (1024 ** 3), 2),
        "memory_used_gb": round(mem.used / (1024 ** 3), 2),
        "memory_percent": mem.percent,
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "load_avg_1m": round(load1, 2),
        "load_avg_5m": round(load5, 2),
        "load_avg_15m": round(load15, 2),
        "boot_time": boot.isoformat(),
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
    }


def _process_info() -> dict:
    """Info about the running backend process."""
    proc = psutil.Process(os.getpid())
    mem = proc.memory_info()
    create_time = datetime.fromtimestamp(proc.create_time(), tz=timezone.utc)
    uptime_sec = (datetime.now(timezone.utc) - create_time).total_seconds()

    return {
        "pid": proc.pid,
        "uptime_seconds": int(uptime_sec),
        "uptime_human": _fmt_duration(int(uptime_sec)),
        "memory_rss_mb": round(mem.rss / (1024 * 1024), 1),
        "memory_vms_mb": round(mem.vms / (1024 * 1024), 1),
        "cpu_percent": proc.cpu_percent(interval=0.1),
        "threads": proc.num_threads(),
        "started_at": create_time.isoformat(),
    }


# Hoisted from _service_status()'s former local variable, unchanged, so
# control_center/platform_overview.py can reuse the exact same list (with a
# richer status classification) instead of maintaining a second copy that
# could drift out of sync with this one.
SERVICE_HEALTH_TARGETS = [
    ("Monitoring Engine", "monitors", "Periodic URL/port checks"),
    ("Alert Engine", "alerts", "Alert processing pipeline"),
    ("Incident Engine", "incidents", "Incident correlation"),
    ("Health Rules", "health_rules", "Threshold-based alerting"),
    ("Synthetic Monitoring", "db.synthetic_monitors", "URL & login flow checks"),
    ("Database Monitoring", "db_instances", "DB agent metrics"),
    ("Server Monitoring", "servers", "Infrastructure agents"),
    ("Metrics Pipeline", "metrics_timeseries", "Time-series ingestion"),
    ("Anomaly Detection", "anomaly_results", "ML-based detection"),
    ("Capacity Prediction", "capacity_predictions", "Resource forecasting"),
    ("Report Scheduler", "report_schedules", "Scheduled PDF/Excel reports"),
    ("Licensing", "license_records", "License management"),
]


async def _service_status() -> list:
    """Check availability of each internal service/module."""
    results = []
    for name, collection, desc in SERVICE_HEALTH_TARGETS:
        try:
            count = await db[collection].estimated_document_count()
            results.append({
                "name": name,
                "status": "operational",
                "description": desc,
                "documents": count,
            })
        except Exception:
            results.append({
                "name": name,
                "status": "degraded",
                "description": desc,
                "documents": 0,
            })
    return results


# Every asyncio.create_task(...) background scheduler started in main.py's lifespan,
# keyed by the exact module-level global variable name main.py uses. Previously
# self_monitor.py never checked any of these — it appended a single hardcoded
# "monitor-check-cycle" entry with last_run=datetime.now() (computed at request
# time, not a real heartbeat) and said nothing about the other 9 real background
# tasks. A task that's still running (not done()) genuinely means its while-True
# loop is alive; a task that IS done() without being cancelled means its loop
# exited (crashed, or — like metrics_processor_task when Redis is down — returned
# early) and is never coming back without a restart.
_SCHEDULER_TASKS = [
    ("metrics_processor_task", "Metrics Stream Processor", "continuous (Redis stream consumer)"),
    ("kafka_consumer_task", "Event Bus Consumer", "continuous"),
    ("sla_breach_task", "SLA-Breach Escalation Scheduler", "periodic"),
    ("threat_intel_task", "Threat Intel Refresh Scheduler", "periodic"),
    ("vuln_sync_task", "Vulnerability Sync Scheduler", "periodic"),
    ("compliance_snapshot_task", "Compliance Snapshot Scheduler", "periodic"),
    ("generic_ingestion_task", "Generic Ingestion Scheduler", "periodic"),
    ("connector_poll_task", "Connector SDK Poll Scheduler", "every 60s"),
    ("resource_bridge_task", "Resource Explorer Bridge/Sync Scheduler", "every 60s"),
    ("runbook_schedule_task", "Runbook Schedule-Trigger Scheduler", "periodic"),
]


def _scheduler_task_statuses() -> list:
    """Real liveness check via asyncio.Task.done()/cancelled()/exception() — no
    fabricated timestamps. Lazily imports main.py (deferred past module-load time)
    to avoid the circular import that would occur if this ran at import time:
    main.py imports app.routes (which imports this module) before its own
    scheduler-task globals are assigned."""
    results = []
    try:
        import main as _main_module
    except Exception as e:
        return [{"id": "scheduler-check-error", "name": "Scheduler liveness check",
                 "status": "unknown", "error": f"could not import main: {str(e)[:200]}"}]

    for attr_name, label, cadence in _SCHEDULER_TASKS:
        task = getattr(_main_module, attr_name, None)
        if task is None:
            results.append({"id": attr_name, "name": label, "frequency": cadence,
                            "status": "not_started", "error": None})
            continue
        if not task.done():
            results.append({"id": attr_name, "name": label, "frequency": cadence,
                            "status": "active", "error": None})
            continue
        if task.cancelled():
            results.append({"id": attr_name, "name": label, "frequency": cadence,
                            "status": "stopped", "error": "cancelled (expected during shutdown)"})
            continue
        exc = task.exception()
        if exc is not None:
            results.append({"id": attr_name, "name": label, "frequency": cadence,
                            "status": "crashed", "error": str(exc)[:300]})
        else:
            # Returned normally without being cancelled — every one of these
            # scheduler coroutines is a `while True` loop, so this only happens
            # when the loop exited early (e.g. process_stream() with no Redis).
            results.append({"id": attr_name, "name": label, "frequency": cadence,
                            "status": "stopped_unexpectedly",
                            "error": "task completed without being cancelled — its loop exited early"})
    return results


async def _background_jobs() -> list:
    """Report schedules (real, DB-backed) + real liveness for every asyncio
    scheduler task started at boot."""
    jobs = []
    try:
        schedules = await db.report_schedules.find(
            {"active": True}, {"_id": 0, "id": 1, "name": 1, "frequency": 1, "last_run_at": 1, "next_run_at": 1}
        ).to_list(50)
        for s in schedules:
            jobs.append({
                "id": s.get("id"),
                "name": s.get("name", "Unknown"),
                "frequency": s.get("frequency", "unknown"),
                "last_run": s.get("last_run_at"),
                "next_run": s.get("next_run_at"),
                "status": "active",
            })
    except Exception:
        pass

    jobs.extend(_scheduler_task_statuses())
    return jobs


async def _recent_api_errors() -> list:
    """Fetch recent error-level log entries if available."""
    try:
        errors = await db.system_logs.find(
            {"level": {"$in": ["error", "critical"]}},
            {"_id": 0}
        ).sort("timestamp", -1).limit(10).to_list(10)
        return errors
    except Exception:
        return []


def _overall_status(mongo: dict, system: dict, services: list, jobs: Optional[list] = None) -> str:
    """Determine overall platform health."""
    if mongo["status"] != "healthy":
        return "critical"
    if system["cpu_percent"] > 90 or system["memory_percent"] > 90 or system["disk_percent"] > 90:
        return "warning"
    degraded = sum(1 for s in services if s["status"] != "operational")
    if degraded > len(services) // 2:
        return "critical"
    if degraded > 0:
        return "warning"
    if jobs is not None:
        crashed = sum(1 for j in jobs if j.get("status") in ("crashed", "stopped_unexpectedly"))
        if crashed > 0:
            return "critical"
    return "healthy"


def _fmt_duration(seconds: int) -> str:
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


# ======================== ENDPOINTS ========================

@router.get("/health")
async def get_platform_health(user: dict = Depends(require_auth)):
    """Comprehensive platform health check."""
    mongo = await _mongo_health()
    system = _system_resources()
    process = _process_info()
    services = await _service_status()
    jobs = await _background_jobs()
    errors = await _recent_api_errors()
    status = _overall_status(mongo, system, services, jobs)

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "platform": "FalconOps AI",
        "startup_time": _STARTUP_TIME.isoformat(),
        "mongodb": mongo,
        "system": system,
        "process": process,
        "services": services,
        "background_jobs": jobs,
        "recent_errors": errors,
    }


@router.get("/ping")
async def ping():
    """Lightweight health ping (no auth)."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
