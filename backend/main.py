"""
FalconOps AI - Main Application Entry Point
Saudi Enterprise AI NOC Copilot
"""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import routers
from app.routes import all_routers
from app.services.websocket_manager import ws_manager
from app.services.soc_live_feed import soc_manager, get_recent_feed
from app.services.monitoring_service import start_monitoring_scheduler, stop_monitoring_scheduler
from app.services.uptime_monitor_service import start_uptime_scheduler, stop_uptime_scheduler
from app.services.reports_service import start_report_scheduler, stop_report_scheduler
from app.services import report_scheduler_service
from app.core.database import db, close_database

# Import metrics processor
from app.services.metrics_timeseries_service import metrics_timeseries_service

# Import event bus (Kafka if reachable, MongoDB fallback otherwise)
from app.services import kafka_pipeline
from app.services import kafka_consumers

# Import autonomous ops orchestrator (SLA-breach escalation scheduler)
from app.services import autonomous_ops_orchestrator

# Import AI-SOC background schedulers (threat intel, vulnerability sync, compliance
# snapshots, generic ingestion polling)
from app.services import threat_intel_service
from app.services import vulnerability_service
from app.services import compliance_service
from app.services import soc_ingestion_service

# Import the workflow trigger service (closes the previously-dead cron-schedule gap —
# runbook.schedule.next_run was computed and stored but nothing polled for due
# runbooks automatically until now)
from app.services import workflow_trigger_service

# Background task for metrics processor
metrics_processor_task = None

# Background task for the Kafka/event-bus consumer
kafka_consumer_task = None

# Background task for the SLA-breach escalation scheduler
sla_breach_task = None

# Background tasks for the AI-SOC schedulers
threat_intel_task = None
vuln_sync_task = None
compliance_snapshot_task = None
generic_ingestion_task = None

# Background task for the workflow builder's schedule-trigger executor
runbook_schedule_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global metrics_processor_task, kafka_consumer_task, sla_breach_task
    global threat_intel_task, vuln_sync_task, compliance_snapshot_task, generic_ingestion_task
    global runbook_schedule_task

    logger.info("Starting FalconOps AI...")

    # ─── ENV PREFLIGHT — surface misconfiguration clearly instead of cryptic
    # crashes later (critical for on-prem installs where .env is hand-edited).
    _missing = [k for k in ("MONGO_URL", "DB_NAME") if not os.environ.get(k, "").strip()]
    if _missing:
        logger.critical("ENV PREFLIGHT FAILED — missing required env vars: %s. "
                        "Check backend/.env (see .env.example).", ", ".join(_missing))
    _jwt = os.environ.get("JWT_SECRET_KEY", "")
    if not _jwt or _jwt == "fallback_secret" or "change-this" in _jwt:
        logger.warning("ENV PREFLIGHT: JWT_SECRET_KEY is unset or default — set a strong secret "
                       "in backend/.env (the on-prem install.sh generates one automatically).")
    if not any(os.environ.get(k, "").strip() for k in
               ("EMERGENT_LLM_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")) \
            and os.environ.get("LLM_PROVIDER", "").lower() not in ("ollama", "rule_based"):
        logger.warning("ENV PREFLIGHT: no LLM provider configured — AI features fall back to "
                       "rule_based mode. Set a key or LLM_PROVIDER=ollama in backend/.env.")
    logger.info("Env preflight done. Verify anytime via GET /api/self-monitor/env-check")

    # Start background schedulers
    start_monitoring_scheduler()
    start_report_scheduler()
    report_scheduler_service.init_scheduler(db)

    # Enterprise weekly report scheduler (Resend email)
    try:
        from app.services.weekly_report_scheduler_service import init_scheduler as init_weekly_scheduler
        await init_weekly_scheduler()
    except Exception as e:
        logger.warning(f"Weekly enterprise report scheduler init failed: {e}")
    
    # Initialize and start metrics stream processor
    try:
        await metrics_timeseries_service.initialize_stream()
        metrics_processor_task = asyncio.create_task(
            metrics_timeseries_service.process_stream()
        )
        logger.info("Metrics stream processor started")
    except Exception as e:
        logger.warning(f"Metrics processor init warning: {e}")

    # Connect the real event bus (Kafka if KAFKA_BOOTSTRAP_SERVERS is reachable —
    # kafka_pipeline.py degrades to its MongoDB fallback automatically otherwise, so
    # this is always safe to call even with no broker deployed).
    try:
        kafka_consumers.register_handlers()
        kafka_bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        await kafka_pipeline.producer.connect(kafka_bootstrap)
        await kafka_pipeline.consumer.connect(kafka_bootstrap)
        kafka_consumer_task = asyncio.create_task(kafka_pipeline.consumer.start_consuming())
        logger.info(f"Event bus started (mode={'kafka' if kafka_pipeline.producer.is_kafka else 'mongodb_fallback'})")
    except Exception as e:
        logger.warning(f"Event bus init warning: {e}")

    # Autonomous ops: SLA-breach escalation scheduler. incidents_engine already computes
    # sla_breach_at/is_sla_breached at creation time but nothing previously read or acted
    # on them — this is what makes that real.
    try:
        sla_breach_task = asyncio.create_task(autonomous_ops_orchestrator.sla_breach_scheduler())
        logger.info("SLA-breach escalation scheduler started")
    except Exception as e:
        logger.warning(f"SLA-breach scheduler init warning: {e}")

    # AI-SOC schedulers: threat intel IOC feed refresh, CVE sync, compliance snapshots,
    # and generic pull-source ingestion polling. Each degrades honestly (network failures
    # are logged, not fatal) and follows the same while/sleep pattern as sla_breach_scheduler.
    try:
        threat_intel_task = asyncio.create_task(threat_intel_service.threat_intel_refresh_scheduler())
        vuln_sync_task = asyncio.create_task(vulnerability_service.vulnerability_sync_scheduler())
        compliance_snapshot_task = asyncio.create_task(compliance_service.compliance_snapshot_scheduler())
        generic_ingestion_task = asyncio.create_task(soc_ingestion_service.generic_ingestion_scheduler())
        logger.info("AI-SOC schedulers started (threat intel, vulnerability sync, compliance snapshots, generic ingestion)")
    except Exception as e:
        logger.warning(f"AI-SOC scheduler init warning: {e}")

    # Workflow builder: schedule-trigger executor. Fixes a real pre-existing gap —
    # runbook.schedule.next_run was computed and stored by the manual
    # POST /runbooks/scheduled/execute endpoint, but nothing called it on a timer.
    try:
        runbook_schedule_task = asyncio.create_task(workflow_trigger_service.runbook_schedule_scheduler())
        logger.info("Runbook schedule-trigger scheduler started")
    except Exception as e:
        logger.warning(f"Runbook schedule scheduler init warning: {e}")

    logger.info("FalconOps AI started successfully")
    
    # Start uptime monitor scheduler
    start_uptime_scheduler()

    # Start trace-driven alert evaluator
    try:
        from app.services import trace_alert_engine
        trace_alert_engine.start_scheduler()
    except Exception as e:
        logger.warning(f"Trace alert evaluator failed to start: {e}")

    yield
    
    # Cleanup
    logger.info("Shutting down FalconOps AI...")
    
    # Stop metrics processor
    if metrics_processor_task:
        metrics_processor_task.cancel()
        try:
            await metrics_processor_task
        except asyncio.CancelledError:
            pass

    # Stop event bus consumer + close connections
    if kafka_consumer_task:
        kafka_consumer_task.cancel()
        try:
            await kafka_consumer_task
        except asyncio.CancelledError:
            pass
    try:
        await kafka_pipeline.consumer.close()
        await kafka_pipeline.producer.close()
    except Exception:
        pass

    # Stop SLA-breach escalation scheduler
    if sla_breach_task:
        sla_breach_task.cancel()
        try:
            await sla_breach_task
        except asyncio.CancelledError:
            pass

    # Stop AI-SOC schedulers
    for task in (threat_intel_task, vuln_sync_task, compliance_snapshot_task, generic_ingestion_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # Stop the runbook schedule-trigger scheduler
    if runbook_schedule_task:
        runbook_schedule_task.cancel()
        try:
            await runbook_schedule_task
        except asyncio.CancelledError:
            pass

    stop_monitoring_scheduler()
    stop_uptime_scheduler()
    stop_report_scheduler()
    try:
        from app.services import trace_alert_engine
        trace_alert_engine.stop_scheduler()
    except Exception:
        pass
    close_database()
    logger.info("FalconOps AI shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="FalconOps AI",
    description="Saudi Enterprise AI NOC Copilot - AI-Powered Incident Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS — read from env, support comma-separated list. Production-safe.
_cors_raw = os.environ.get("CORS_ORIGINS", "*").strip()
if _cors_raw == "*":
    # Browsers reject "*" + credentials, so we drop credentials in wildcard mode.
    _cors_origins = ["*"]
    _cors_credentials = False
else:
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    _cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
#  Security Headers Middleware
#  Applied at the FastAPI app level so these are real regardless of what (if anything)
#  sits in front of it — an on-prem nginx gateway or a cloud ALB/CloudFront may add its
#  own copies, but the app no longer depends on that being present.
# ──────────────────────────────────────────────
@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Swagger/Redoc load their assets from a CDN — skip CSP there so /docs stays usable.
    if request.url.path not in ("/docs", "/redoc"):
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response


# ──────────────────────────────────────────────
#  Tenant Routing Middleware
#  Resolves the inbound request → tenant via Host header / path-prefix /t/{slug}.
#  Stamps tenant context onto request.state for downstream handlers.
# ──────────────────────────────────────────────
@app.middleware("http")
async def tenant_resolution_middleware(request, call_next):
    try:
        from app.services.tenant_routing_service import resolve_tenant_from_request, PATH_TENANT_RE
        host = request.headers.get("host")
        path = request.url.path
        # Skip resolution for static / docs / WS — they don't need tenant context
        if not (path.startswith("/api/") or path.startswith("/t/")):
            return await call_next(request)
        tenant = await resolve_tenant_from_request(host=host, path=path)
        if tenant:
            request.state.tenant_id = tenant.get("id")
            request.state.tenant_slug = tenant.get("slug") or tenant.get("subdomain")
            request.state.tenant_routing_method = tenant.get("_routing_method")
            # URL rewrite: strip /t/{slug} prefix so the underlying /api/* routes match
            if tenant.get("_routing_method") == "path_prefix":
                m = PATH_TENANT_RE.match(path)
                if m:
                    new_path = path[m.end() - 1:] or "/"
                    if not new_path.startswith("/"):
                        new_path = "/" + new_path
                    # Mutate ASGI scope so downstream routing sees the rewritten path
                    request.scope["path"] = new_path
                    request.scope["raw_path"] = new_path.encode()
        else:
            request.state.tenant_id = None
            request.state.tenant_slug = None
            request.state.tenant_routing_method = None
    except Exception as e:
        # Never block a request because of routing resolution
        request.state.tenant_id = None
        request.state.tenant_slug = None
        request.state.tenant_routing_method = None
        logger.debug(f"Tenant resolution error: {e}")
    response = await call_next(request)
    if getattr(request.state, "tenant_slug", None):
        response.headers["X-Tenant-Slug"] = request.state.tenant_slug
        if request.state.tenant_routing_method:
            response.headers["X-Tenant-Routing"] = request.state.tenant_routing_method
    return response


# Include all routers
for router in all_routers:
    app.include_router(router)


# WebSocket endpoint for real-time alerts
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alert streaming"""
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
            # Echo back or handle client messages if needed
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# SOC Live Feed WebSocket endpoint
@app.websocket("/ws/soc-feed")
async def websocket_soc_feed(websocket: WebSocket):
    """WebSocket endpoint for real-time SOC threat feed"""
    await soc_manager.connect(websocket)
    try:
        # Send initial feed on connect
        import json
        recent = await get_recent_feed(30)
        await websocket.send_text(json.dumps({"type": "initial", "data": recent}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        soc_manager.disconnect(websocket)


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    from app.services.storage_service import storage_info
    return {
        "status": "healthy",
        "service": "FalconOps AI",
        "version": "1.0.0",
        "storage": storage_info(),
    }


# Stripe webhook endpoint
@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    from app.routes.billing_routes import handle_stripe_webhook
    return await handle_stripe_webhook(request)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "FalconOps AI",
        "description": "Saudi Enterprise AI NOC Copilot",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
