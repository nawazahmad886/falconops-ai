"""
FalconOps AI - Server Monitoring Routes
Server registration, metrics ingestion, and server management
"""
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ..core.database import db
from ..utils.auth import require_auth, require_write_access, get_current_user
from ..services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/servers", tags=["Server Monitoring"])


def _tid(user):
    return user.get("tenant_id") if user else None


# ======================== MODELS ========================

class ServerRegister(BaseModel):
    hostname: str
    ip_address: str
    os_type: str = "linux"
    os_version: Optional[str] = None
    agent_version: Optional[str] = "1.0.0"
    tags: Optional[dict] = None

class ServerResponse(BaseModel):
    id: str
    hostname: str
    ip_address: str
    os_type: str
    os_version: Optional[str]
    agent_token: str
    status: str
    last_seen: Optional[str]
    cpu_usage: Optional[float]
    memory_usage: Optional[float]
    disk_usage: Optional[float]
    created_at: str

class MetricsIngest(BaseModel):
    agent_token: str
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    memory_used_gb: Optional[float] = None
    memory_total_gb: Optional[float] = None
    disk_percent: float = Field(ge=0, le=100)
    disk_used_gb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    network_in_mbps: Optional[float] = None
    network_out_mbps: Optional[float] = None
    load_average_1m: Optional[float] = None
    load_average_5m: Optional[float] = None
    load_average_15m: Optional[float] = None
    process_count: Optional[int] = None
    uptime_seconds: Optional[int] = None
    timestamp: Optional[str] = None

class ServerAlertRule(BaseModel):
    name: str
    server_id: Optional[str] = None  # None = applies to all servers
    metric: str  # cpu, memory, disk, load
    operator: str  # gt, lt, eq
    threshold: float
    severity: str = "warning"  # warning, critical
    enabled: bool = True

class ServerDashboardResponse(BaseModel):
    total_servers: int
    online_servers: int
    offline_servers: int
    warning_servers: int
    critical_servers: int
    avg_cpu: float
    avg_memory: float
    avg_disk: float
    servers: List[dict]


# ======================== AGENT ENDPOINTS ========================

@router.post("/register")
async def register_server(server: ServerRegister):
    """Register a new server agent (public endpoint for agents)"""
    # Check if server already registered by hostname + IP
    existing = await db.servers.find_one({
        "hostname": server.hostname,
        "ip_address": server.ip_address
    })
    
    if existing:
        # Return existing token
        return {
            "message": "Server already registered",
            "server_id": existing["id"],
            "agent_token": existing["agent_token"]
        }
    
    server_id = str(uuid.uuid4())
    agent_token = f"fop_srv_{secrets.token_hex(32)}"
    
    server_doc = {
        "id": server_id,
        "hostname": server.hostname,
        "ip_address": server.ip_address,
        "os_type": server.os_type,
        "os_version": server.os_version,
        "agent_version": server.agent_version,
        "agent_token": agent_token,
        "tags": server.tags or {},
        "status": "online",
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "cpu_usage": None,
        "memory_usage": None,
        "disk_usage": None,
        "network_in": None,
        "network_out": None,
        "load_average": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.servers.insert_one(server_doc)
    
    return {
        "message": "Server registered successfully",
        "server_id": server_id,
        "agent_token": agent_token
    }


@router.post("/metrics/ingest")
async def ingest_metrics(metrics: MetricsIngest):
    """Ingest metrics from server agent (authenticated by agent token)"""
    # Validate agent token
    server = await db.servers.find_one({"agent_token": metrics.agent_token})
    if not server:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    
    timestamp = metrics.timestamp or datetime.now(timezone.utc).isoformat()
    
    # Store metrics
    metric_doc = {
        "id": str(uuid.uuid4()),
        "server_id": server["id"],
        "cpu_percent": metrics.cpu_percent,
        "memory_percent": metrics.memory_percent,
        "memory_used_gb": metrics.memory_used_gb,
        "memory_total_gb": metrics.memory_total_gb,
        "disk_percent": metrics.disk_percent,
        "disk_used_gb": metrics.disk_used_gb,
        "disk_total_gb": metrics.disk_total_gb,
        "network_in_mbps": metrics.network_in_mbps,
        "network_out_mbps": metrics.network_out_mbps,
        "load_average_1m": metrics.load_average_1m,
        "load_average_5m": metrics.load_average_5m,
        "load_average_15m": metrics.load_average_15m,
        "process_count": metrics.process_count,
        "uptime_seconds": metrics.uptime_seconds,
        "timestamp": timestamp,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.server_metrics.insert_one(metric_doc)
    
    # Determine server health status
    status = "online"
    if metrics.cpu_percent > 90 or metrics.memory_percent > 90 or metrics.disk_percent > 95:
        status = "critical"
    elif metrics.cpu_percent > 75 or metrics.memory_percent > 80 or metrics.disk_percent > 85:
        status = "warning"
    
    # Update server with latest metrics
    await db.servers.update_one(
        {"id": server["id"]},
        {"$set": {
            "status": status,
            "last_seen": timestamp,
            "cpu_usage": metrics.cpu_percent,
            "memory_usage": metrics.memory_percent,
            "disk_usage": metrics.disk_percent,
            "network_in": metrics.network_in_mbps,
            "network_out": metrics.network_out_mbps,
            "load_average": metrics.load_average_1m,
            "process_count": metrics.process_count,
            "uptime_seconds": metrics.uptime_seconds
        }}
    )
    
    # Check alert rules and create alerts if needed
    await check_server_alert_rules(server["id"], metrics)
    
    # Evaluate health rules against incoming metrics
    try:
        from ..services.health_rule_evaluator import evaluate_rules_for_server
        server_metrics_dict = {
            "cpu_percent": metrics.cpu_percent, "cpu_usage": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent, "memory_usage": metrics.memory_percent,
            "disk_percent": metrics.disk_percent, "disk_usage": metrics.disk_percent,
            "network_in_mbps": metrics.network_in_mbps, "network_in": metrics.network_in_mbps,
            "network_out_mbps": metrics.network_out_mbps, "network_out": metrics.network_out_mbps,
            "load_average_1m": metrics.load_average_1m, "load_average": metrics.load_average_1m,
        }
        await evaluate_rules_for_server(server["id"], server.get("name", ""), server_metrics_dict)
    except Exception as e:
        import logging
        logging.getLogger("health-eval").warning(f"Health rule evaluation failed: {e}")
    
    # Broadcast update via WebSocket
    await ws_manager.broadcast({
        "type": "server_metrics",
        "data": {
            "server_id": server["id"],
            "hostname": server["hostname"],
            "status": status,
            "cpu": metrics.cpu_percent,
            "memory": metrics.memory_percent,
            "disk": metrics.disk_percent
        }
    })
    
    return {"message": "Metrics ingested successfully", "status": status}


async def check_server_alert_rules(server_id: str, metrics: MetricsIngest):
    """Check alert rules and create alerts if thresholds exceeded"""
    rules = await db.server_alert_rules.find({
        "$or": [{"server_id": server_id}, {"server_id": None}],
        "enabled": True
    }, {"_id": 0}).to_list(100)
    
    metric_values = {
        "cpu": metrics.cpu_percent,
        "memory": metrics.memory_percent,
        "disk": metrics.disk_percent,
        "load": metrics.load_average_1m or 0
    }
    
    for rule in rules:
        metric_value = metric_values.get(rule["metric"], 0)
        threshold = rule["threshold"]
        triggered = False
        
        if rule["operator"] == "gt" and metric_value > threshold:
            triggered = True
        elif rule["operator"] == "lt" and metric_value < threshold:
            triggered = True
        elif rule["operator"] == "eq" and metric_value == threshold:
            triggered = True
        
        if triggered:
            # Check if similar alert already open
            existing_alert = await db.alerts.find_one({
                "source": "FalconOps-Server",
                "service": f"server:{server_id}",
                "status": "open",
                "title": {"$regex": f".*{rule['metric'].upper()}.*"}
            })
            
            if not existing_alert:
                server = await db.servers.find_one({"id": server_id}, {"_id": 0})
                alert_doc = {
                    "id": str(uuid.uuid4()),
                    "source": "FalconOps-Server",
                    "severity": rule["severity"],
                    "title": f"Server {rule['metric'].upper()} Alert: {server.get('hostname', server_id)}",
                    "description": f"{rule['metric'].upper()} is {metric_value:.1f}% (threshold: {threshold}%)",
                    "service": f"server:{server_id}",
                    "host": server.get("ip_address"),
                    "status": "open",
                    "incident_id": None,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.alerts.insert_one(alert_doc)
                await ws_manager.broadcast({"type": "new_alert", "data": {k: v for k, v in alert_doc.items() if k != "_id"}})


# ======================== DASHBOARD ENDPOINTS ========================

@router.get("/dashboard", response_model=ServerDashboardResponse)
async def get_server_dashboard(current_user: Optional[dict] = Depends(get_current_user)):
    """Get server monitoring dashboard overview"""
    tid = _tid(current_user)
    q = {}
    if tid:
        q["tenant_id"] = tid
    servers = await db.servers.find(q, {"_id": 0}).to_list(500)
    
    # Check for offline servers (no heartbeat in 5 minutes)
    five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    
    online = 0
    offline = 0
    warning = 0
    critical = 0
    total_cpu = 0
    total_memory = 0
    total_disk = 0
    active_servers = 0
    
    for server in servers:
        last_seen = server.get("last_seen", "")
        
        if last_seen < five_min_ago:
            server["status"] = "offline"
            await db.servers.update_one({"id": server["id"]}, {"$set": {"status": "offline"}})
            offline += 1
        elif server.get("status") == "critical":
            critical += 1
        elif server.get("status") == "warning":
            warning += 1
        else:
            online += 1
        
        if server.get("cpu_usage") is not None:
            total_cpu += server["cpu_usage"]
            total_memory += server.get("memory_usage", 0)
            total_disk += server.get("disk_usage", 0)
            active_servers += 1
    
    return ServerDashboardResponse(
        total_servers=len(servers),
        online_servers=online,
        offline_servers=offline,
        warning_servers=warning,
        critical_servers=critical,
        avg_cpu=round(total_cpu / active_servers, 1) if active_servers > 0 else 0,
        avg_memory=round(total_memory / active_servers, 1) if active_servers > 0 else 0,
        avg_disk=round(total_disk / active_servers, 1) if active_servers > 0 else 0,
        servers=servers
    )


@router.get("")
async def get_servers(
    status: Optional[str] = Query(None),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get all registered servers"""
    query = {}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    if status:
        query["status"] = status
    
    servers = await db.servers.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return servers


@router.get("/{server_id}")
async def get_server(server_id: str, current_user: Optional[dict] = Depends(get_current_user)):
    """Get single server details"""
    query = {"id": server_id}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    server = await db.servers.find_one(query, {"_id": 0})
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.get("/{server_id}/metrics")
async def get_server_metrics(
    server_id: str,
    hours: int = Query(24, ge=1, le=168),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get server metrics history"""
    query = {"id": server_id}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    server = await db.servers.find_one(query)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    
    metrics = await db.server_metrics.find(
        {"server_id": server_id, "timestamp": {"$gte": since}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(1000).to_list(1000)
    
    return metrics


@router.delete("/{server_id}")
async def delete_server(server_id: str, current_user: dict = Depends(require_write_access)):
    """Delete a server and its metrics"""
    query = {"id": server_id}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    result = await db.servers.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Clean up metrics
    await db.server_metrics.delete_many({"server_id": server_id})
    
    return {"message": "Server deleted successfully"}


# ======================== ALERT RULES ========================

@router.get("/rules/alerts")
async def get_server_alert_rules(current_user: dict = Depends(require_auth)):
    """Get all server alert rules"""
    rules = await db.server_alert_rules.find({**({"tenant_id": current_user.get("tenant_id")} if current_user.get("tenant_id") else {})}, {"_id": 0}).to_list(100)
    return rules


@router.post("/rules/alerts")
async def create_server_alert_rule(rule: ServerAlertRule, current_user: dict = Depends(require_write_access)):
    """Create a server alert rule"""
    rule_id = str(uuid.uuid4())
    rule_doc = {
        "id": rule_id,
        "name": rule.name,
        "server_id": rule.server_id,
        "metric": rule.metric,
        "operator": rule.operator,
        "threshold": rule.threshold,
        "severity": rule.severity,
        "enabled": rule.enabled,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"]
    }
    
    await db.server_alert_rules.insert_one(rule_doc)
    return {k: v for k, v in rule_doc.items() if k != "_id"}


@router.delete("/rules/alerts/{rule_id}")
async def delete_server_alert_rule(rule_id: str, current_user: dict = Depends(require_write_access)):
    """Delete a server alert rule"""
    result = await db.server_alert_rules.delete_one({"id": rule_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Alert rule deleted"}


# ======================== SIMULATE METRICS (FOR DEMO) ========================

@router.post("/simulate")
async def simulate_server_metrics(current_user: dict = Depends(require_write_access)):
    """Simulate server metrics for demo purposes"""
    import random
    
    # Get or create demo servers
    demo_servers = [
        {"hostname": "prod-web-01", "ip_address": "10.0.1.10", "os_type": "linux", "os_version": "Ubuntu 22.04"},
        {"hostname": "prod-web-02", "ip_address": "10.0.1.11", "os_type": "linux", "os_version": "Ubuntu 22.04"},
        {"hostname": "prod-db-01", "ip_address": "10.0.1.20", "os_type": "linux", "os_version": "CentOS 8"},
        {"hostname": "prod-cache-01", "ip_address": "10.0.1.30", "os_type": "linux", "os_version": "Debian 11"},
        {"hostname": "prod-api-01", "ip_address": "10.0.1.40", "os_type": "linux", "os_version": "Ubuntu 22.04"},
    ]
    
    created = 0
    updated = 0
    
    for server_data in demo_servers:
        existing = await db.servers.find_one({"hostname": server_data["hostname"]})
        
        if not existing:
            # Register new server
            server_id = str(uuid.uuid4())
            agent_token = f"fop_srv_{secrets.token_hex(32)}"
            
            server_doc = {
                "id": server_id,
                "hostname": server_data["hostname"],
                "ip_address": server_data["ip_address"],
                "os_type": server_data["os_type"],
                "os_version": server_data["os_version"],
                "agent_version": "1.0.0",
                "agent_token": agent_token,
                "tags": {"env": "production"},
                "status": "online",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.servers.insert_one(server_doc)
            existing = server_doc
            created += 1
        
        # Generate random metrics
        cpu = random.uniform(15, 85)
        memory = random.uniform(40, 75)
        disk = random.uniform(30, 70)
        
        # Occasionally spike one metric
        if random.random() < 0.1:
            cpu = random.uniform(85, 98)
        if random.random() < 0.05:
            memory = random.uniform(85, 95)
        
        metrics = MetricsIngest(
            agent_token=existing["agent_token"],
            cpu_percent=round(cpu, 1),
            memory_percent=round(memory, 1),
            memory_used_gb=round(memory * 0.32, 2),
            memory_total_gb=32.0,
            disk_percent=round(disk, 1),
            disk_used_gb=round(disk * 5, 2),
            disk_total_gb=500.0,
            network_in_mbps=round(random.uniform(10, 500), 2),
            network_out_mbps=round(random.uniform(5, 200), 2),
            load_average_1m=round(random.uniform(0.5, 4.0), 2),
            load_average_5m=round(random.uniform(0.5, 3.5), 2),
            load_average_15m=round(random.uniform(0.5, 3.0), 2),
            process_count=random.randint(100, 300),
            uptime_seconds=random.randint(86400, 8640000)
        )
        
        await ingest_metrics(metrics)
        updated += 1
    
    return {"message": f"Simulation complete. Created: {created}, Updated: {updated}"}
