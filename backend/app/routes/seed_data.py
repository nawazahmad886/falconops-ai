"""
FalconOps AI - Seed Data Routes
Generate demo data for testing the observability platform
"""
import uuid
import random
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends

from ..utils.auth import require_write_access
from ..services.alert_engine import alert_engine
from ..services.incident_engine import incident_engine
from ..services.topology_service import topology_service
from ..core.database import db

router = APIRouter(prefix="/api/seed", tags=["Seed Data"])

HOSTS = ["prod-web-01", "prod-web-02", "prod-api-01", "prod-api-02", "prod-db-01", "prod-cache-01"]
SERVICES = ["api-gateway", "user-service", "payment-service", "order-service", "notification-service", "auth-service"]
SEVERITIES = ["critical", "high", "medium", "low"]
METRICS = [
    ("cpu_usage", "CPU usage exceeded threshold", 85, 90),
    ("memory_usage", "Memory usage exceeded threshold", 80, 90),
    ("disk_usage", "Disk usage exceeded threshold", 85, 95),
    ("response_time", "Response time exceeded SLA", 500, 1000),
    ("error_rate", "Error rate spike detected", 5, 15),
    ("request_rate", "Request rate anomaly detected", 1000, 5000),
]

# Topology definition
TOPOLOGY_NODES = [
    {"name": "web-frontend", "type": "frontend", "desc": "React web application"},
    {"name": "mobile-bff", "type": "api", "desc": "Mobile backend-for-frontend"},
    {"name": "api-gateway", "type": "api", "desc": "API Gateway / Load Balancer"},
    {"name": "auth-service", "type": "backend", "desc": "Authentication & JWT"},
    {"name": "user-service", "type": "backend", "desc": "User management"},
    {"name": "order-service", "type": "backend", "desc": "Order processing"},
    {"name": "payment-service", "type": "backend", "desc": "Payment processing"},
    {"name": "notification-service", "type": "backend", "desc": "Email/SMS/Push"},
    {"name": "inventory-service", "type": "backend", "desc": "Inventory management"},
    {"name": "postgres-primary", "type": "database", "desc": "PostgreSQL primary"},
    {"name": "postgres-replica", "type": "database", "desc": "PostgreSQL read replica"},
    {"name": "redis-cache", "type": "cache", "desc": "Redis cache cluster"},
    {"name": "rabbitmq", "type": "queue", "desc": "RabbitMQ message broker"},
    {"name": "s3-storage", "type": "storage", "desc": "Object storage"},
    {"name": "stripe-api", "type": "external", "desc": "Stripe payment API"},
    {"name": "sendgrid-api", "type": "external", "desc": "SendGrid email API"},
]

TOPOLOGY_EDGES = [
    ("web-frontend", "api-gateway", "http"),
    ("mobile-bff", "api-gateway", "http"),
    ("api-gateway", "auth-service", "http"),
    ("api-gateway", "user-service", "http"),
    ("api-gateway", "order-service", "http"),
    ("api-gateway", "payment-service", "http"),
    ("auth-service", "postgres-primary", "database"),
    ("auth-service", "redis-cache", "tcp"),
    ("user-service", "postgres-primary", "database"),
    ("user-service", "redis-cache", "tcp"),
    ("order-service", "postgres-primary", "database"),
    ("order-service", "inventory-service", "http"),
    ("order-service", "rabbitmq", "async"),
    ("payment-service", "stripe-api", "http"),
    ("payment-service", "postgres-primary", "database"),
    ("notification-service", "sendgrid-api", "http"),
    ("notification-service", "rabbitmq", "async"),
    ("inventory-service", "postgres-primary", "database"),
    ("inventory-service", "redis-cache", "tcp"),
    ("postgres-primary", "postgres-replica", "tcp"),
]


@router.post("/alerts")
async def seed_alerts(
    count: int = 20,
    current_user: dict = Depends(require_write_access)
):
    """Generate sample alerts for testing"""
    created = []
    for i in range(count):
        metric = random.choice(METRICS)
        host = random.choice(HOSTS)
        service = random.choice(SERVICES)
        severity = random.choice(SEVERITIES)

        alert = await alert_engine.create_alert(
            title=f"{metric[1]} on {host}",
            description=f"{metric[0]} is at {metric[2] + random.randint(0, 20)}% on {host} ({service})",
            severity=severity,
            source="health_rule",
            entity_type="service",
            entity_id=service,
            entity_name=service,
            metric_name=metric[0],
            metric_value=float(metric[2] + random.randint(0, 20)),
            threshold=float(metric[3]),
            tags={"host": host, "service": service, "environment": "production"},
            tenant_id=current_user.get("tenant_id"),
            auto_resolve_minutes=random.choice([None, 30, 60, 120])
        )
        created.append(alert)

    return {"message": f"Created {len(created)} sample alerts", "count": len(created)}


@router.post("/incidents")
async def seed_incidents(
    count: int = 5,
    current_user: dict = Depends(require_write_access)
):
    """Generate sample incidents from existing alerts"""
    # Get active alerts
    active = await alert_engine.get_active_alerts(
        tenant_id=current_user.get("tenant_id")
    )

    if len(active) < 2:
        return {"message": "Not enough active alerts. Seed alerts first.", "count": 0}

    created = []
    # Group alerts by host for correlation
    host_groups = {}
    for a in active:
        host = a.get("tags", {}).get("host", "unknown")
        host_groups.setdefault(host, []).append(a)

    for host, alerts in list(host_groups.items())[:count]:
        if len(alerts) >= 2:
            alert_ids = [a["id"] for a in alerts[:4]]
            try:
                incident = await incident_engine.create_incident_from_alerts(
                    alert_ids=alert_ids,
                    correlation_reason=f"same_host:{host}",
                    tenant_id=current_user.get("tenant_id"),
                    created_by=current_user["email"]
                )
                created.append(incident)
            except Exception as e:
                print(f"Seed incident error: {e}")

    return {"message": f"Created {len(created)} sample incidents", "count": len(created)}


@router.post("/metrics")
async def seed_metrics(
    hours: int = 24,
    current_user: dict = Depends(require_write_access)
):
    """Generate sample time-series metrics"""
    now = datetime.now(timezone.utc)
    docs = []

    for host in HOSTS[:3]:
        for minute_offset in range(0, hours * 60, 5):
            ts = now - timedelta(minutes=minute_offset)
            base_cpu = 40 + random.gauss(0, 10)
            base_mem = 55 + random.gauss(0, 8)
            base_disk = 60 + (minute_offset / (hours * 60)) * 10 + random.gauss(0, 3)

            for metric_name, value in [
                ("cpu_usage", max(0, min(100, base_cpu + random.gauss(0, 5)))),
                ("memory_usage", max(0, min(100, base_mem + random.gauss(0, 3)))),
                ("disk_usage", max(0, min(100, base_disk))),
            ]:
                docs.append({
                    "name": metric_name,
                    "value": round(value, 2),
                    "timestamp": ts.isoformat(),
                    "tags": {"host": host, "service": "system", "environment": "production"},
                    "tenant_id": current_user.get("tenant_id")
                })

    if docs:
        await db.metrics_timeseries.insert_many(docs)

    return {"message": f"Inserted {len(docs)} metric data points", "count": len(docs)}


@router.post("/topology")
async def seed_topology(current_user: dict = Depends(require_write_access)):
    """Generate sample topology graph"""
    tenant_id = current_user.get("tenant_id")
    # Clear existing topology for this tenant
    if tenant_id:
        await db.topology_nodes.delete_many({"tenant_id": tenant_id})
        await db.topology_edges.delete_many({"tenant_id": tenant_id})
    else:
        await db.topology_nodes.delete_many({})
        await db.topology_edges.delete_many({})

    created_nodes = {}
    for n in TOPOLOGY_NODES:
        statuses = ["healthy"] * 8 + ["degraded", "critical"]
        node = await topology_service.create_service_node(
            name=n["name"],
            service_type=n["type"],
            description=n["desc"],
            environment="production",
            tags=[n["type"]],
            tenant_id=tenant_id,
        )
        # Randomize health for realism
        status = random.choice(statuses)
        health = 100 if status == "healthy" else 70 if status == "degraded" else 30
        await topology_service.update_service_health(node["id"], status, health)
        created_nodes[n["name"]] = node

    created_edges = 0
    for source_name, target_name, conn_type in TOPOLOGY_EDGES:
        source = created_nodes.get(source_name)
        target = created_nodes.get(target_name)
        if source and target:
            await topology_service.create_connection(
                source_id=source["id"],
                target_id=target["id"],
                connection_type=conn_type,
                latency_p50=round(random.uniform(1, 50), 1),
                latency_p99=round(random.uniform(20, 200), 1),
                request_rate=round(random.uniform(10, 5000), 0),
                error_rate=round(random.uniform(0, 3), 2),
                tenant_id=tenant_id,
            )
            created_edges += 1

    return {
        "message": f"Created {len(created_nodes)} nodes, {created_edges} edges",
        "nodes": len(created_nodes),
        "edges": created_edges,
    }


@router.post("/full")
async def seed_full_demo(current_user: dict = Depends(require_write_access)):
    """Seed complete demo dataset (topology + metrics + alerts + incidents)"""
    topology_result = await seed_topology(current_user=current_user)
    metrics_result = await seed_metrics(hours=24, current_user=current_user)
    alerts_result = await seed_alerts(count=25, current_user=current_user)
    incidents_result = await seed_incidents(count=5, current_user=current_user)

    return {
        "message": "Full demo data seeded",
        "topology": topology_result,
        "metrics": metrics_result,
        "alerts": alerts_result,
        "incidents": incidents_result
    }
