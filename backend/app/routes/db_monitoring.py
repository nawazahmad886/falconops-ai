"""
FalconOps AI - Database Monitoring Routes
API endpoints for DB metrics ingestion, instance management, query monitoring, and AI analysis
"""
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel

from ..core.database import db
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/db-monitoring", tags=["Database Monitoring"])


def _tid(user: dict) -> Optional[str]:
    return (user or {}).get("tenant_id")


# ── Pydantic Models ──

class DBInstanceCreate(BaseModel):
    name: str
    db_type: str  # postgres, oracle, mysql, sqlserver
    host: str
    port: int = 5432
    database: str = ""
    environment: str = "production"
    tags: dict = {}


class DBInstanceUpdate(BaseModel):
    name: Optional[str] = None
    environment: Optional[str] = None
    tags: Optional[dict] = None
    status: Optional[str] = None


class DBMetricsIngest(BaseModel):
    instance_id: str
    timestamp: Optional[str] = None
    metrics: dict  # active_sessions, cpu_usage, memory_usage, tps, io_read, io_write, etc.
    slow_queries: List[dict] = []
    locks: List[dict] = []
    custom_query_results: List[dict] = []


class DBAlertRule(BaseModel):
    instance_id: Optional[str] = None
    name: str
    metric: str
    operator: str  # gt, lt, gte, lte, eq
    threshold: float
    severity: str = "warning"
    enabled: bool = True


class CustomQueryCreate(BaseModel):
    instance_id: str
    name: str
    query: str
    interval: int = 60
    enabled: bool = True
    chart_type: str = "line"  # line, area, bar, gauge
    description: str = ""
    unit: str = ""
    color: str = "#00E0FF"


class CustomQueryUpdate(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    interval: Optional[int] = None
    enabled: Optional[bool] = None
    chart_type: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    color: Optional[str] = None


# ── Instance Management ──

@router.get("/instances")
async def list_instances(user: dict = Depends(require_auth)):
    """List all registered database instances"""
    q: dict = {}
    tid = _tid(user)
    if tid:
        q["tenant_id"] = tid
    instances = await db.db_instances.find(q, {"_id": 0, "api_key": 0}).to_list(length=100)
    return {"instances": instances}


@router.post("/instances")
async def register_instance(body: DBInstanceCreate, user: dict = Depends(require_auth)):
    """Register a new database instance for monitoring. Generates an api_key the DB
    agent must send back (via the X-API-Key header) on every /metrics/ingest call —
    that endpoint has no user auth (the agent doesn't hold a JWT), so this key is the
    only thing preventing an unauthenticated caller from injecting fake metrics into
    any instance_id it can guess."""
    api_key = secrets.token_urlsafe(32)
    instance = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "db_type": body.db_type,
        "host": body.host,
        "port": body.port,
        "database": body.database,
        "environment": body.environment,
        "tags": body.tags,
        "status": "registered",
        "last_seen": None,
        "api_key": api_key,
        "tenant_id": user.get("tenant_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("email", ""),
    }
    await db.db_instances.insert_one({**instance})
    instance.pop("_id", None)
    return instance


@router.put("/instances/{instance_id}")
async def update_instance(instance_id: str, body: DBInstanceUpdate, user: dict = Depends(require_auth)):
    """Update a database instance"""
    update = {k: v for k, v in body.dict().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    q = {"id": instance_id}
    tid = _tid(user)
    if tid:
        q["tenant_id"] = tid
    result = await db.db_instances.update_one(q, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Instance not found")
    inst = await db.db_instances.find_one({"id": instance_id}, {"_id": 0, "api_key": 0})
    return inst


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str, user: dict = Depends(require_auth)):
    """Delete a database instance"""
    q = {"id": instance_id}
    tid = _tid(user)
    if tid:
        q["tenant_id"] = tid
    result = await db.db_instances.delete_one(q)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Instance not found")
    return {"deleted": True}


# ── Metrics Ingestion ──

@router.post("/metrics/ingest")
async def ingest_metrics(body: DBMetricsIngest, x_api_key: Optional[str] = Header(None)):
    """Ingest database metrics from the DB agent. Previously had no authentication at
    all — any caller who could guess/enumerate an instance_id could inject fake
    metrics/slow-queries/locks into that instance's dashboard and trigger fake
    alert-rule firings. Now requires the api_key generated at instance registration
    (sent back as X-API-Key), the same key the install script already embeds in the
    agent's config."""
    instance = await db.db_instances.find_one({"id": body.instance_id}, {"_id": 0})
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    if not x_api_key or x_api_key != instance.get("api_key"):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")

    ts = body.timestamp or datetime.now(timezone.utc).isoformat()

    # Update instance last_seen
    await db.db_instances.update_one(
        {"id": body.instance_id},
        {"$set": {
            "last_seen": ts,
            "status": "active",
            "agent_heartbeat": ts,
            "agent_version": body.metrics.get("agent_version", ""),
        }}
    )

    # Store metrics
    metric_doc = {
        "instance_id": body.instance_id,
        "timestamp": ts,
        "metrics": body.metrics,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.db_metrics.insert_one(metric_doc)

    # Store slow queries
    for sq in body.slow_queries:
        sq["instance_id"] = body.instance_id
        sq["detected_at"] = ts
        sq.setdefault("id", str(uuid.uuid4()))
        await db.db_slow_queries.insert_one(sq)

    # Store locks
    for lock in body.locks:
        lock["instance_id"] = body.instance_id
        lock["detected_at"] = ts
        await db.db_locks.insert_one(lock)

    # Store custom query results
    for cqr in body.custom_query_results:
        cqr["instance_id"] = body.instance_id
        cqr["executed_at"] = cqr.get("executed_at", ts)
        cqr.setdefault("id", str(uuid.uuid4()))
        await db.db_custom_results.insert_one(cqr)

    # Check alert rules
    alerts_fired = await _check_alert_rules(body.instance_id, body.metrics, body.slow_queries, body.locks)

    # Evaluate health rules against DB metrics
    try:
        from ..services.health_rule_evaluator import evaluate_rules_for_db
        inst_name = instance.get("name", "")
        db_metrics = {**body.metrics, "slow_query_count": len(body.slow_queries)}
        await evaluate_rules_for_db(body.instance_id, inst_name, db_metrics)
    except Exception as e:
        import logging
        logging.getLogger("health-eval").warning(f"DB health rule evaluation failed: {e}")

    return {
        "status": "ok",
        "metrics_stored": True,
        "slow_queries_count": len(body.slow_queries),
        "locks_count": len(body.locks),
        "alerts_fired": len(alerts_fired),
    }


# ── Dashboard Data ──

@router.get("/dashboard/{instance_id}")
async def get_dashboard(
    instance_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    user: dict = Depends(require_auth),
):
    """Get dashboard data for a specific database instance"""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    inst_q = {"id": instance_id}
    tid = _tid(user)
    if tid:
        inst_q["tenant_id"] = tid
    instance = await db.db_instances.find_one(inst_q, {"_id": 0, "api_key": 0})
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    # Get recent metrics
    metrics_cursor = db.db_metrics.find(
        {"instance_id": instance_id, "timestamp": {"$gte": since}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(200)
    metrics = await metrics_cursor.to_list(length=200)

    # Get slow queries
    slow_queries = await db.db_slow_queries.find(
        {"instance_id": instance_id, "detected_at": {"$gte": since}},
        {"_id": 0}
    ).sort("detected_at", -1).to_list(length=50)

    # Get locks
    locks = await db.db_locks.find(
        {"instance_id": instance_id, "detected_at": {"$gte": since}},
        {"_id": 0}
    ).sort("detected_at", -1).to_list(length=50)

    # Get alerts
    alerts = await db.db_alerts.find(
        {"instance_id": instance_id, "created_at": {"$gte": since}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(length=50)

    # Calculate current stats from latest metrics
    latest = metrics[0]["metrics"] if metrics else {}
    avg_metrics = _calculate_avg_metrics(metrics)

    return {
        "instance": instance,
        "current": latest,
        "averages": avg_metrics,
        "metrics_history": metrics[:100],  # last 100 data points
        "slow_queries": slow_queries,
        "locks": locks,
        "alerts": alerts,
        "period_hours": hours,
    }


@router.get("/dashboard-overview")
async def get_overview(user: dict = Depends(require_auth)):
    """Get overview of all monitored databases"""
    q: dict = {}
    tid = _tid(user)
    if tid:
        q["tenant_id"] = tid
    instances = await db.db_instances.find(q, {"_id": 0, "api_key": 0}).to_list(length=100)

    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    overview = []
    for inst in instances:
        # Latest metrics
        latest_metric = await db.db_metrics.find_one(
            {"instance_id": inst["id"]},
            {"_id": 0},
            sort=[("timestamp", -1)]
        )
        # Recent slow query count
        sq_count = await db.db_slow_queries.count_documents(
            {"instance_id": inst["id"], "detected_at": {"$gte": since}}
        )
        # Recent lock count
        lock_count = await db.db_locks.count_documents(
            {"instance_id": inst["id"], "detected_at": {"$gte": since}}
        )
        # Recent alert count
        alert_count = await db.db_alerts.count_documents(
            {"instance_id": inst["id"], "created_at": {"$gte": since}}
        )

        current = latest_metric.get("metrics", {}) if latest_metric else {}
        health = _calc_db_health(current, sq_count, lock_count)

        # Agent status
        heartbeat = inst.get("agent_heartbeat", "")
        agent_status = "offline"
        if heartbeat:
            try:
                hb_time = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
                age_min = (datetime.now(timezone.utc) - hb_time).total_seconds() / 60
                agent_status = "online" if age_min < 5 else "stale" if age_min < 30 else "offline"
            except Exception:
                pass

        # Custom query count
        cq_count = await db.db_custom_queries.count_documents({"instance_id": inst["id"]})

        overview.append({
            **inst,
            "current_metrics": current,
            "health_score": health,
            "slow_queries_1h": sq_count,
            "locks_1h": lock_count,
            "alerts_1h": alert_count,
            "agent_status": agent_status,
            "agent_version": inst.get("agent_version", ""),
            "custom_queries_count": cq_count,
        })

    # Totals
    total_instances = len(instances)
    active = sum(1 for o in overview if o.get("status") == "active")
    total_sq = sum(o.get("slow_queries_1h", 0) for o in overview)
    total_locks = sum(o.get("locks_1h", 0) for o in overview)
    avg_health = round(sum(o.get("health_score", 0) for o in overview) / max(total_instances, 1), 1)

    return {
        "instances": overview,
        "summary": {
            "total_instances": total_instances,
            "active_instances": active,
            "avg_health_score": avg_health,
            "total_slow_queries_1h": total_sq,
            "total_locks_1h": total_locks,
        }
    }


# ── Slow Queries ──

@router.get("/slow-queries/{instance_id}")
async def get_slow_queries(
    instance_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(require_auth),
):
    """Get slow queries for an instance"""
    queries = await db.db_slow_queries.find(
        {"instance_id": instance_id}, {"_id": 0}
    ).sort("detected_at", -1).to_list(length=limit)
    return {"slow_queries": queries, "total": len(queries)}


@router.get("/top-queries/{instance_id}")
async def get_top_queries(
    instance_id: str,
    user: dict = Depends(require_auth),
):
    """Get top queries by execution count and time"""
    pipeline = [
        {"$match": {"instance_id": instance_id}},
        {"$group": {
            "_id": "$fingerprint",
            "query_sample": {"$first": "$query"},
            "total_executions": {"$sum": 1},
            "avg_duration_ms": {"$avg": "$duration_ms"},
            "max_duration_ms": {"$max": "$duration_ms"},
            "total_time_ms": {"$sum": "$duration_ms"},
            "last_seen": {"$max": "$detected_at"},
        }},
        {"$sort": {"total_time_ms": -1}},
        {"$limit": 20},
    ]
    results = await db.db_slow_queries.aggregate(pipeline).to_list(length=20)
    # Clean ObjectId
    for r in results:
        r["fingerprint"] = r.pop("_id", "")
    return {"top_queries": results}


# ── Locks ──

@router.get("/locks/{instance_id}")
async def get_locks(
    instance_id: str,
    limit: int = Query(default=50),
    user: dict = Depends(require_auth),
):
    """Get lock/blocking data for an instance"""
    locks = await db.db_locks.find(
        {"instance_id": instance_id}, {"_id": 0}
    ).sort("detected_at", -1).to_list(length=limit)
    return {"locks": locks, "total": len(locks)}


# ── Alert Rules ──

@router.get("/alert-rules")
async def list_alert_rules(user: dict = Depends(require_auth)):
    """List all DB alert rules"""
    rules = await db.db_alert_rules.find({}, {"_id": 0}).to_list(length=100)
    return {"rules": rules}


@router.post("/alert-rules")
async def create_alert_rule(body: DBAlertRule, user: dict = Depends(require_auth)):
    """Create a new DB alert rule"""
    rule = {
        "id": str(uuid.uuid4()),
        **body.dict(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.db_alert_rules.insert_one({**rule})
    rule.pop("_id", None)
    return rule


@router.delete("/alert-rules/{rule_id}")
async def delete_alert_rule(rule_id: str, user: dict = Depends(require_auth)):
    """Delete a DB alert rule"""
    result = await db.db_alert_rules.delete_one({"id": rule_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": True}


# ── Custom Queries ──

@router.get("/custom-queries/{instance_id}")
async def list_custom_queries(instance_id: str, user: dict = Depends(require_auth)):
    """List custom monitoring queries for an instance"""
    queries = await db.db_custom_queries.find(
        {"instance_id": instance_id}, {"_id": 0}
    ).to_list(length=50)
    return {"queries": queries}


@router.post("/custom-queries")
async def create_custom_query(body: CustomQueryCreate, user: dict = Depends(require_auth)):
    """Create a custom monitoring query"""
    cq = {
        "id": str(uuid.uuid4()),
        **body.dict(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.db_custom_queries.insert_one({**cq})
    cq.pop("_id", None)
    return cq


@router.put("/custom-queries/{query_id}")
async def update_custom_query(query_id: str, body: CustomQueryUpdate, user: dict = Depends(require_auth)):
    """Update a custom monitoring query"""
    update = {k: v for k, v in body.dict().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.db_custom_queries.update_one({"id": query_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Query not found")
    doc = await db.db_custom_queries.find_one({"id": query_id}, {"_id": 0})
    return doc


@router.post("/custom-queries/{query_id}/toggle")
async def toggle_custom_query(query_id: str, user: dict = Depends(require_auth)):
    """Toggle enable/disable for a custom query"""
    doc = await db.db_custom_queries.find_one({"id": query_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Query not found")
    new_state = not doc.get("enabled", True)
    await db.db_custom_queries.update_one({"id": query_id}, {"$set": {"enabled": new_state}})
    return {"id": query_id, "enabled": new_state}


@router.delete("/custom-queries/{query_id}")
async def delete_custom_query(query_id: str, user: dict = Depends(require_auth)):
    """Delete a custom query and its results"""
    result = await db.db_custom_queries.delete_one({"id": query_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Query not found")
    # Also clean up results
    await db.db_custom_results.delete_many({"query_id": query_id})
    return {"deleted": True}


@router.post("/custom-queries/{query_id}/execute")
async def execute_custom_query(query_id: str, user: dict = Depends(require_auth)):
    """Execute a custom query (simulated) and store results"""
    from ..services.custom_query_service import execute_query_simulation
    doc = await db.db_custom_queries.find_one({"id": query_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Query not found")
    result = await execute_query_simulation(doc)
    return result


@router.get("/custom-queries/{instance_id}/dashboard")
async def get_custom_query_dashboard(
    instance_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    user: dict = Depends(require_auth),
):
    """Get all custom query widgets with chart data for the dashboard"""
    from ..services.custom_query_service import get_dashboard_widgets
    widgets = await get_dashboard_widgets(instance_id, hours)
    return {"widgets": widgets, "instance_id": instance_id, "period_hours": hours}


@router.get("/custom-results/{instance_id}")
async def get_custom_results(
    instance_id: str,
    query_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50),
    user: dict = Depends(require_auth),
):
    """Get custom query results, optionally filtered by query_id"""
    query_filter = {"instance_id": instance_id}
    if query_id:
        query_filter["query_id"] = query_id
    results = await db.db_custom_results.find(
        query_filter, {"_id": 0}
    ).sort("executed_at", -1).to_list(length=limit)
    return {"results": results}


@router.get("/custom-results/{instance_id}/timeseries/{query_id}")
async def get_custom_query_timeseries(
    instance_id: str,
    query_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    user: dict = Depends(require_auth),
):
    """Get time-series results for a specific custom query"""
    from ..services.custom_query_service import get_query_timeseries
    results = await get_query_timeseries(query_id, hours)
    return {"query_id": query_id, "timeseries": results, "period_hours": hours}


@router.post("/custom-queries/seed/{instance_id}")
async def seed_custom_queries_endpoint(instance_id: str, user: dict = Depends(require_auth)):
    """Seed demo custom queries and historical results for an instance"""
    from ..services.custom_query_service import seed_custom_queries
    # Verify instance exists
    inst = await db.db_instances.find_one({"id": instance_id}, {"_id": 0})
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    # Clear existing custom queries for this instance
    existing = await db.db_custom_queries.find({"instance_id": instance_id}, {"_id": 0}).to_list(length=100)
    for q in existing:
        await db.db_custom_results.delete_many({"query_id": q["id"]})
    await db.db_custom_queries.delete_many({"instance_id": instance_id})
    result = await seed_custom_queries(instance_id)
    return result


# ── Agent Endpoints (no auth - agent uses instance_id) ──

@router.get("/agent/queries/{instance_id}")
async def get_agent_queries(instance_id: str):
    """Fetch enabled custom queries for the agent (no auth required - agent polling)."""
    inst = await db.db_instances.find_one({"id": instance_id}, {"_id": 0})
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    queries = await db.db_custom_queries.find(
        {"instance_id": instance_id, "enabled": True}, {"_id": 0}
    ).to_list(length=100)
    return {"queries": queries, "instance_id": instance_id, "instance_name": inst.get("name", "")}


@router.get("/agent/download")
async def download_db_agent():
    """Download the FalconOps DB Monitoring Agent"""
    import os
    agent_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "agents", "falcon_db_agent.py")
    if not os.path.exists(agent_path):
        raise HTTPException(status_code=404, detail="Agent file not found")
    from fastapi.responses import FileResponse
    return FileResponse(agent_path, filename="falcon_db_agent.py", media_type="text/x-python")


@router.get("/agent/install-script")
async def get_install_script(
    api_url: str = Query(default=""),
    api_key: str = Query(default=""),
    instance_id: str = Query(default=""),
    db_type: str = Query(default="postgres"),
):
    """Generate a Linux install script for the DB monitoring agent."""
    from fastapi.responses import PlainTextResponse
    script = f'''#!/bin/bash
# ═══════════════════════════════════════════════════════════
# FalconOps AI - DB Monitoring Agent Installer
# Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
# ═══════════════════════════════════════════════════════════
set -e

AGENT_DIR="/opt/falconops/db-agent"
CONFIG_DIR="/etc/falconops"
LOG_DIR="/var/log/falconops"
SERVICE_NAME="falconops-db-agent"

echo "========================================"
echo " FalconOps DB Monitoring Agent Installer"
echo "========================================"
echo ""

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo)"
    exit 1
fi

# Create directories
mkdir -p "$AGENT_DIR" "$CONFIG_DIR" "$LOG_DIR"

# Install Python dependencies
echo "[1/5] Installing Python dependencies..."
pip3 install --quiet requests pyyaml 2>/dev/null || pip install --quiet requests pyyaml
if [ "{db_type}" = "postgres" ] || [ "{db_type}" = "postgresql" ]; then
    pip3 install --quiet psycopg2-binary 2>/dev/null || pip install --quiet psycopg2-binary
elif [ "{db_type}" = "oracle" ]; then
    # python-oracledb runs in "thin" mode by default — talks the Oracle wire
    # protocol directly, no Oracle Instant Client install needed.
    pip3 install --quiet oracledb 2>/dev/null || pip install --quiet oracledb
elif [ "{db_type}" = "mysql" ]; then
    pip3 install --quiet pymysql 2>/dev/null || pip install --quiet pymysql
elif [ "{db_type}" = "sqlserver" ] || [ "{db_type}" = "mssql" ]; then
    # pyodbc needs a real native ODBC driver on this host, unlike the other
    # three engines — install Microsoft's msodbcsql18 package first.
    if command -v apt-get >/dev/null 2>&1; then
        curl -sSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add - 2>/dev/null || true
        curl -sSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list -o /etc/apt/sources.list.d/mssql-release.list 2>/dev/null || true
        apt-get update -qq && ACCEPT_EULA=Y apt-get install -y -qq msodbcsql18 unixodbc-dev
    elif command -v yum >/dev/null 2>&1; then
        curl -sSL https://packages.microsoft.com/config/rhel/9/prod.repo -o /etc/yum.repos.d/mssql-release.repo 2>/dev/null || true
        ACCEPT_EULA=Y yum install -y -q msodbcsql18 unixODBC-devel
    else
        echo "  WARNING: unrecognized package manager — install the 'msodbcsql18' ODBC driver manually: https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server"
    fi
    pip3 install --quiet pyodbc 2>/dev/null || pip install --quiet pyodbc
fi
echo "  Done."

# Download agent
echo "[2/5] Downloading agent..."
API_URL="{api_url or "https://your-falconops-server.com"}"
curl -sSf "$API_URL/api/db-monitoring/agent/download" -o "$AGENT_DIR/falcon_db_agent.py"
chmod +x "$AGENT_DIR/falcon_db_agent.py"
echo "  Agent saved to $AGENT_DIR/falcon_db_agent.py"

# Generate config
echo "[3/5] Generating configuration..."
cat > "$CONFIG_DIR/db_agent.yaml" << 'YAMLEOF'
# FalconOps DB Monitoring Agent Configuration
# Edit these values for your environment

database:
  type: {db_type}            # postgres | oracle | mysql
  host: localhost             # Database host
  port: {5432 if db_type in ("postgres","postgresql") else 1521 if db_type == "oracle" else 3306}
  username: monitor           # Database user (read-only recommended)
  password: CHANGE_ME         # Database password
  database: prod_db           # Database name or service name

api:
  endpoint: {api_url or "https://your-falconops-server.com"}
  key: {api_key or "YOUR_API_TOKEN"}
  {"instance_id: " + instance_id if instance_id else "# instance_id: auto-registered"}

collection_interval: 60       # Seconds between metric collections
query_sync_interval: 300      # Seconds between custom query sync from server

alerts:
  slow_query_threshold: 20    # Seconds
  connection_limit: 500
  deadlock_limit: 3

# Optional: local custom queries (in addition to server-synced ones)
# custom_queries:
#   - name: "Row Count"
#     query: "SELECT count(*) FROM my_table"
#     interval: 300
#     enabled: true
YAMLEOF
echo "  Config saved to $CONFIG_DIR/db_agent.yaml"
echo "  >>> IMPORTANT: Edit $CONFIG_DIR/db_agent.yaml with your database credentials <<<"

# Create systemd service
echo "[4/5] Creating systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=FalconOps DB Monitoring Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 $AGENT_DIR/falcon_db_agent.py --config $CONFIG_DIR/db_agent.yaml
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/db-agent.log
StandardError=append:$LOG_DIR/db-agent-error.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "  Systemd service created: $SERVICE_NAME"

# Summary
echo "[5/5] Installation complete!"
echo ""
echo "========================================"
echo " Next Steps:"
echo "========================================"
echo ""
echo " 1. Edit configuration:"
echo "    sudo nano $CONFIG_DIR/db_agent.yaml"
echo ""
echo " 2. Start the agent:"
echo "    sudo systemctl start $SERVICE_NAME"
echo "    sudo systemctl enable $SERVICE_NAME"
echo ""
echo " 3. Check status:"
echo "    sudo systemctl status $SERVICE_NAME"
echo ""
echo " 4. View logs:"
echo "    tail -f $LOG_DIR/db-agent.log"
echo ""
echo " 5. Test (dry run):"
echo "    python3 $AGENT_DIR/falcon_db_agent.py --config $CONFIG_DIR/db_agent.yaml --dry-run --once"
echo ""
echo "========================================"
'''
    return PlainTextResponse(content=script, media_type="text/x-shellscript",
                            headers={"Content-Disposition": "attachment; filename=install_db_agent.sh"})


@router.get("/agent/config-template")
async def get_config_template(
    db_type: str = Query(default="postgres"),
    api_url: str = Query(default=""),
    instance_id: str = Query(default=""),
):
    """Generate a YAML config template for the DB agent."""
    from fastapi.responses import PlainTextResponse
    port_map = {"postgres": 5432, "oracle": 1521, "mysql": 3306, "sqlserver": 1433}
    template = f"""# FalconOps DB Monitoring Agent Configuration
# Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

database:
  type: {db_type}
  host: localhost
  port: {port_map.get(db_type, 5432)}
  username: monitor
  password: CHANGE_ME
  database: prod_db

api:
  endpoint: {api_url or "https://your-falconops-server.com"}
  key: ""
  {"instance_id: " + instance_id if instance_id else "# instance_id: will be auto-assigned on first connection"}

collection_interval: 60
query_sync_interval: 300

alerts:
  slow_query_threshold: 20
  connection_limit: 500
  deadlock_limit: 3
"""
    return PlainTextResponse(content=template, media_type="text/yaml",
                            headers={"Content-Disposition": f"attachment; filename=db_agent_{db_type}.yaml"})


# ── AI Analysis ──

@router.post("/ai-analyze/{instance_id}")
async def ai_analyze_db(instance_id: str, user: dict = Depends(require_auth)):
    """Run AI-powered root cause analysis on database issues"""
    import os
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except ImportError:
        raise HTTPException(status_code=500, detail="AI not available")

    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="AI key not configured")

    inst_q = {"id": instance_id}
    tid = _tid(user)
    if tid:
        inst_q["tenant_id"] = tid
    instance = await db.db_instances.find_one(inst_q, {"_id": 0, "api_key": 0})
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    since = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()

    # Gather recent data
    metrics = await db.db_metrics.find(
        {"instance_id": instance_id, "timestamp": {"$gte": since}}, {"_id": 0}
    ).sort("timestamp", -1).to_list(length=20)

    slow_queries = await db.db_slow_queries.find(
        {"instance_id": instance_id, "detected_at": {"$gte": since}}, {"_id": 0}
    ).sort("detected_at", -1).to_list(length=20)

    locks = await db.db_locks.find(
        {"instance_id": instance_id, "detected_at": {"$gte": since}}, {"_id": 0}
    ).sort("detected_at", -1).to_list(length=10)

    alerts = await db.db_alerts.find(
        {"instance_id": instance_id, "created_at": {"$gte": since}}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=10)

    import json
    context = f"""Database: {instance.get('name')} ({instance.get('db_type')})
Host: {instance.get('host')}:{instance.get('port')}
Environment: {instance.get('environment')}

Recent Metrics (last 6h, newest first):
{json.dumps([m.get('metrics',{}) for m in metrics[:5]], indent=2)}

Slow Queries ({len(slow_queries)} detected):
{json.dumps([{'query': sq.get('query','')[:200], 'duration_ms': sq.get('duration_ms'), 'user': sq.get('user')} for sq in slow_queries[:10]], indent=2)}

Locks/Blocking ({len(locks)} detected):
{json.dumps([{'type': l.get('lock_type'), 'blocked_pid': l.get('blocked_pid'), 'blocking_pid': l.get('blocking_pid'), 'wait_time': l.get('wait_time')} for l in locks[:5]], indent=2)}

Recent Alerts ({len(alerts)}):
{json.dumps([{'metric': a.get('metric'), 'severity': a.get('severity'), 'value': a.get('value')} for a in alerts[:5]], indent=2)}
"""

    prompt = f"""You are a Senior DBA and Database Performance expert. Analyze this database monitoring data and provide:

{context}

Provide:
### 1. DATABASE HEALTH ASSESSMENT
Overall health status and key concerns.

### 2. ROOT CAUSE ANALYSIS
If there are performance issues, identify the most likely root causes with evidence.

### 3. SLOW QUERY ANALYSIS
For each slow query, explain why it might be slow and suggest optimizations (indexes, query rewrites).

### 4. LOCK ANALYSIS
If locks/deadlocks exist, explain the cause and resolution.

### 5. RECOMMENDATIONS
Prioritized list of actions:
| Priority | Action | Expected Impact |
|----------|--------|-----------------|

### 6. INDEX RECOMMENDATIONS
If applicable, suggest specific indexes to create.

Be specific, actionable, and reference the actual data provided."""

    chat = LlmChat(api_key=key, session_id=f"db-analyze-{instance_id[:8]}")
    response = await chat.send_message_async(UserMessage(message=prompt))
    ai_text = response.text if hasattr(response, 'text') else str(response)

    # Store analysis
    analysis_doc = {
        "id": str(uuid.uuid4()),
        "instance_id": instance_id,
        "analysis": ai_text,
        "metrics_analyzed": len(metrics),
        "slow_queries_analyzed": len(slow_queries),
        "locks_analyzed": len(locks),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.db_ai_analyses.insert_one({**analysis_doc})
    analysis_doc.pop("_id", None)

    return analysis_doc


# ── Helper Functions ──

def _calculate_avg_metrics(metrics: list) -> dict:
    if not metrics:
        return {}
    keys_to_avg = ["active_sessions", "cpu_usage", "memory_usage", "tps", "io_read_ms", "io_write_ms"]
    avgs = {}
    for key in keys_to_avg:
        vals = [m["metrics"].get(key) for m in metrics if m.get("metrics", {}).get(key) is not None]
        if vals:
            avgs[key] = round(sum(vals) / len(vals), 2)
    return avgs


def _calc_db_health(metrics: dict, sq_count: int, lock_count: int) -> float:
    # cpu_usage/memory_usage are genuinely None (not 0) for engines/permission
    # levels where the agent can't obtain them (e.g. Postgres/MySQL have no
    # SQL-only path to host CPU) — skip that component of the score rather
    # than silently treating "unknown" as "0%, perfectly healthy".
    score = 100.0
    cpu = metrics.get("cpu_usage")
    mem = metrics.get("memory_usage")
    sessions = metrics.get("active_sessions") or 0
    if cpu is not None:
        if cpu > 90: score -= 30
        elif cpu > 70: score -= 15
        elif cpu > 50: score -= 5
    if mem is not None:
        if mem > 90: score -= 25
        elif mem > 70: score -= 10
    if sessions > 500: score -= 20
    elif sessions > 200: score -= 10
    if sq_count > 10: score -= 15
    elif sq_count > 3: score -= 5
    if lock_count > 5: score -= 20
    elif lock_count > 0: score -= 10
    return max(0, min(100, round(score, 1)))


async def _check_alert_rules(instance_id: str, metrics: dict, slow_queries: list, locks: list) -> list:
    """Check alert rules and fire alerts"""
    rules = await db.db_alert_rules.find(
        {"$or": [{"instance_id": instance_id}, {"instance_id": None}], "enabled": True},
        {"_id": 0}
    ).to_list(length=50)

    ops = {"gt": lambda a, b: a > b, "lt": lambda a, b: a < b, "gte": lambda a, b: a >= b, "lte": lambda a, b: a <= b, "eq": lambda a, b: a == b}
    fired = []

    for rule in rules:
        metric_name = rule.get("metric", "")
        threshold = rule.get("threshold", 0)
        op = ops.get(rule.get("operator", "gt"), lambda a, b: a > b)

        # Check standard metrics
        val = metrics.get(metric_name)
        if val is not None and op(float(val), threshold):
            alert = {
                "id": str(uuid.uuid4()),
                "instance_id": instance_id,
                "rule_id": rule["id"],
                "rule_name": rule.get("name", ""),
                "metric": metric_name,
                "value": val,
                "threshold": threshold,
                "severity": rule.get("severity", "warning"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.db_alerts.insert_one({**alert})
            alert.pop("_id", None)
            fired.append(alert)

        # Special: slow_query_count
        if metric_name == "slow_query_count" and op(len(slow_queries), threshold):
            alert = {
                "id": str(uuid.uuid4()),
                "instance_id": instance_id,
                "rule_id": rule["id"],
                "rule_name": rule.get("name", ""),
                "metric": "slow_query_count",
                "value": len(slow_queries),
                "threshold": threshold,
                "severity": rule.get("severity", "warning"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.db_alerts.insert_one({**alert})
            alert.pop("_id", None)
            fired.append(alert)

        # Special: deadlock_count / lock_count
        if metric_name in ("deadlock_count", "lock_count") and op(len(locks), threshold):
            alert = {
                "id": str(uuid.uuid4()),
                "instance_id": instance_id,
                "rule_id": rule["id"],
                "rule_name": rule.get("name", ""),
                "metric": metric_name,
                "value": len(locks),
                "threshold": threshold,
                "severity": rule.get("severity", "warning"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.db_alerts.insert_one({**alert})
            alert.pop("_id", None)
            fired.append(alert)

    return fired
