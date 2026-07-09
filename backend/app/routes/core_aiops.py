"""
FalconOps AI - Core AIOps Hub API
Aggregates data from all AI subsystems for the central intelligence page
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from ..core.database import db
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/core-aiops", tags=["Core AIOps"])


@router.get("/overview")
async def get_core_overview(user: dict = Depends(require_auth)):
    """Get aggregated overview from all AIOps subsystems"""

    now = datetime.now(timezone.utc)
    last_24h = (now - timedelta(hours=24)).isoformat()

    # Parallel data gathering
    total_alerts = await db.alerts.count_documents({})
    active_alerts = await db.alerts.count_documents({"status": {"$in": ["open", "firing"]}})
    critical_alerts = await db.alerts.count_documents({"severity": "critical", "status": {"$in": ["open", "firing"]}})

    total_incidents = await db.incidents.count_documents({})
    active_incidents = await db.incidents.count_documents({"status": {"$in": ["open", "investigating"]}})

    total_servers = await db.servers.count_documents({})
    healthy_servers = await db.servers.count_documents({"status": "healthy"})

    monitors_total = await db.monitors.count_documents({})
    monitors_up = await db.monitors.count_documents({"status": "up"})

    total_runbooks = await db.runbooks.count_documents({})
    total_executions = await db.runbook_executions.count_documents({})

    event_uploads = await db.event_uploads.count_documents({})
    event_analyses = await db.event_analyses.count_documents({})

    ingested_alerts = await db.ingested_alerts.count_documents({})
    unanalyzed_alerts = await db.ingested_alerts.count_documents({"analyzed": False})

    webhooks_count = await db.webhooks.count_documents({"enabled": True})

    knowledge_patterns = await db.incident_knowledge.count_documents({})

    # Calculate system health score
    health_factors = []
    if total_servers > 0:
        health_factors.append(healthy_servers / total_servers * 100)
    if monitors_total > 0:
        health_factors.append(monitors_up / monitors_total * 100)
    if total_alerts > 0:
        non_critical_pct = max(0, 100 - (critical_alerts / max(total_alerts, 1) * 200))
        health_factors.append(non_critical_pct)
    else:
        health_factors.append(100)

    system_health = round(sum(health_factors) / len(health_factors), 1) if health_factors else 100

    # Get recent alert severity distribution
    severity_pipeline = [
        {"$match": {"status": {"$in": ["open", "firing"]}}},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
    ]
    severity_data = await db.alerts.aggregate(severity_pipeline).to_list(length=10)
    severity_dist = {s["_id"]: s["count"] for s in severity_data if s["_id"]}

    # Capabilities status
    capabilities = [
        {
            "id": "anomaly_detection",
            "name": "Anomaly Detection",
            "description": "Multi-algorithm anomaly detection: Z-score, EWMA, Isolation Forest, Dynamic Thresholds, Seasonal Decomposition",
            "category": "detection",
            "status": "active",
            "path": "/aiops-brain",
            "stats": {"algorithms": 5, "active_alerts": active_alerts},
            "icon": "zap"
        },
        {
            "id": "event_correlation",
            "name": "Smart Correlation",
            "description": "Topology-aware event correlation using dependency graphs, host patterns, and metric signals",
            "category": "correlation",
            "status": "active",
            "path": "/aiops-brain",
            "stats": {"methods": 4, "correlated_events": total_incidents},
            "icon": "git-merge"
        },
        {
            "id": "root_cause",
            "name": "Root Cause Analysis",
            "description": "LLM-powered root cause analysis with rule-based fallback and knowledge base learning",
            "category": "analysis",
            "status": "active",
            "path": "/incident-engine",
            "stats": {"incidents_analyzed": total_incidents, "active_incidents": active_incidents},
            "icon": "target"
        },
        {
            "id": "impact_analysis",
            "name": "Impact Analysis",
            "description": "Blast radius calculation, business impact scoring, and service dependency cascade analysis",
            "category": "analysis",
            "status": "active",
            "path": "/aiops-brain",
            "stats": {"services_monitored": monitors_total},
            "icon": "radio"
        },
        {
            "id": "event_analyzer",
            "name": "AI Event Analyzer",
            "description": "Upload event files or receive webhook alerts for AI-powered pattern detection and root cause analysis",
            "category": "intelligence",
            "status": "active",
            "path": "/event-analyzer",
            "stats": {"uploads": event_uploads, "analyses": event_analyses, "ingested": ingested_alerts},
            "icon": "brain"
        },
        {
            "id": "capacity_prediction",
            "name": "Capacity Prediction",
            "description": "Linear regression forecasting for CPU, memory, disk usage with exhaustion date prediction",
            "category": "prediction",
            "status": "active",
            "path": "/capacity-prediction",
            "stats": {"servers_tracked": total_servers},
            "icon": "trending-up"
        },
        {
            "id": "alert_engine",
            "name": "Alert Engine",
            "description": "Centralized alert management with auto-escalation, deduplication, and severity-based routing",
            "category": "operations",
            "status": "active",
            "path": "/alert-engine",
            "stats": {"total": total_alerts, "active": active_alerts, "critical": critical_alerts},
            "icon": "bell"
        },
        {
            "id": "incident_management",
            "name": "Incident Management",
            "description": "Full incident lifecycle with auto-correlation, war room, and MTTR tracking",
            "category": "operations",
            "status": "active",
            "path": "/incident-engine",
            "stats": {"total": total_incidents, "active": active_incidents},
            "icon": "alert-triangle"
        },
        {
            "id": "noc_dashboard",
            "name": "NOC Dashboard",
            "description": "Enterprise NOC overview with infrastructure fleet grid, application health, and live alert feed",
            "category": "monitoring",
            "status": "active",
            "path": "/noc-dashboard",
            "stats": {"servers": total_servers, "monitors": monitors_total},
            "icon": "monitor"
        },
        {
            "id": "runbook_automation",
            "name": "Runbook Automation",
            "description": "Automated remediation playbooks with step-by-step execution, templates, and scheduling",
            "category": "automation",
            "status": "active",
            "path": "/runbooks",
            "stats": {"runbooks": total_runbooks, "executions": total_executions},
            "icon": "book-open"
        },
        {
            "id": "topology_map",
            "name": "Topology & Dependencies",
            "description": "Service dependency graph visualization with real-time health overlays and trace correlation",
            "category": "observability",
            "status": "active",
            "path": "/topology",
            "stats": {},
            "icon": "network"
        },
        {
            "id": "knowledge_base",
            "name": "AI Knowledge Base",
            "description": "Self-learning knowledge base that improves suggestions from resolved incidents and patterns",
            "category": "intelligence",
            "status": "active",
            "path": "/event-analyzer",
            "stats": {"patterns": knowledge_patterns, "webhooks": webhooks_count},
            "icon": "graduation-cap"
        },
    ]

    return {
        "system_health": system_health,
        "severity_distribution": severity_dist,
        "summary": {
            "total_alerts": total_alerts,
            "active_alerts": active_alerts,
            "critical_alerts": critical_alerts,
            "total_incidents": total_incidents,
            "active_incidents": active_incidents,
            "total_servers": total_servers,
            "healthy_servers": healthy_servers,
            "monitors_total": monitors_total,
            "monitors_up": monitors_up,
            "event_analyses": event_analyses,
            "knowledge_patterns": knowledge_patterns,
            "ingested_alerts": ingested_alerts,
            "unanalyzed_alerts": unanalyzed_alerts,
        },
        "capabilities": capabilities,
        "last_updated": now.isoformat()
    }
