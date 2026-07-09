"""
FalconOps AI - AI Correlation Engine
Smart rule-based and AI-powered alert correlation for incident creation
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

from ..core.database import db
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)


# ======================== CORRELATION RULES ========================

CORRELATION_RULES = [
    {
        "id": "resource_saturation",
        "name": "Resource Saturation",
        "description": "High CPU + High Memory + Database connection issues indicate resource saturation",
        "conditions": [
            {"type": "metric", "source": "server", "metric": "cpu", "operator": "gt", "value": 85},
            {"type": "metric", "source": "server", "metric": "memory", "operator": "gt", "value": 85},
        ],
        "root_cause": "Resource Saturation - Server under heavy load",
        "suggested_actions": [
            "Scale up server resources (CPU/Memory)",
            "Identify and optimize resource-intensive processes",
            "Consider horizontal scaling if persistent",
            "Review recent deployments for memory leaks"
        ],
        "severity": "critical"
    },
    {
        "id": "database_connection_pool",
        "name": "Database Connection Pool Exhaustion",
        "description": "APM latency spike + Database errors indicate connection pool issues",
        "conditions": [
            {"type": "alert_pattern", "title_contains": ["database", "connection", "pool", "timeout"]},
            {"type": "metric", "source": "apm", "metric": "latency", "operator": "gt", "value": 2000},
        ],
        "root_cause": "Database Connection Pool Exhaustion",
        "suggested_actions": [
            "Increase database connection pool size",
            "Review slow queries causing connection holding",
            "Implement connection pooling if not present",
            "Check for connection leaks in application code"
        ],
        "severity": "critical"
    },
    {
        "id": "network_connectivity",
        "name": "Network Connectivity Issues",
        "description": "Multiple services down + Network errors indicate network issues",
        "conditions": [
            {"type": "alert_pattern", "title_contains": ["network", "timeout", "unreachable", "connection refused"]},
            {"type": "service_count", "status": "down", "operator": "gt", "value": 2},
        ],
        "root_cause": "Network Connectivity Issues",
        "suggested_actions": [
            "Check network infrastructure (routers, switches, firewalls)",
            "Verify DNS resolution",
            "Review recent network configuration changes",
            "Check for ISP or cloud provider issues"
        ],
        "severity": "critical"
    },
    {
        "id": "disk_space_critical",
        "name": "Disk Space Critical",
        "description": "Disk usage above 95% causing application failures",
        "conditions": [
            {"type": "metric", "source": "server", "metric": "disk", "operator": "gt", "value": 95},
        ],
        "root_cause": "Disk Space Critical",
        "suggested_actions": [
            "Clear old logs and temporary files",
            "Expand disk volume",
            "Set up log rotation",
            "Identify and remove unused data"
        ],
        "severity": "critical"
    },
    {
        "id": "ssl_certificate_expiry",
        "name": "SSL Certificate Expiry",
        "description": "SSL certificate warnings indicate upcoming expiry",
        "conditions": [
            {"type": "alert_pattern", "title_contains": ["ssl", "certificate", "expir", "tls"]},
        ],
        "root_cause": "SSL Certificate Expiring/Expired",
        "suggested_actions": [
            "Renew SSL certificate immediately",
            "Set up automatic certificate renewal (Let's Encrypt)",
            "Update certificate in load balancer/CDN",
            "Notify affected service owners"
        ],
        "severity": "warning"
    },
    {
        "id": "application_error_spike",
        "name": "Application Error Spike",
        "description": "High error rate indicates application issues",
        "conditions": [
            {"type": "alert_count", "severity": "critical", "time_window_minutes": 5, "operator": "gt", "value": 5},
        ],
        "root_cause": "Application Error Spike",
        "suggested_actions": [
            "Review recent code deployments",
            "Check application logs for stack traces",
            "Rollback if recently deployed",
            "Identify error patterns and fix root cause"
        ],
        "severity": "critical"
    },
    {
        "id": "cascading_failure",
        "name": "Cascading Failure",
        "description": "Multiple dependent services failing indicates cascade",
        "conditions": [
            {"type": "service_count", "status": "down", "operator": "gt", "value": 3},
            {"type": "time_proximity", "minutes": 5},
        ],
        "root_cause": "Cascading Failure - Multiple services affected",
        "suggested_actions": [
            "Identify the root service causing cascade",
            "Implement circuit breakers",
            "Check shared dependencies (database, cache, message queue)",
            "Failover to backup services if available"
        ],
        "severity": "critical"
    },
]


# ======================== DEDUPLICATION ENGINE ========================

async def deduplicate_alert(alert: Dict[str, Any]) -> Optional[str]:
    """
    Check if a similar alert already exists and return its ID for deduplication.
    
    Deduplication criteria:
    1. Same monitor_id or service
    2. Same severity
    3. Similar title (fuzzy match)
    4. Within time window (default 10 minutes)
    """
    time_window = datetime.now(timezone.utc) - timedelta(minutes=10)
    
    # Build query for similar alerts
    query = {
        "status": {"$in": ["open", "acknowledged"]},
        "created_at": {"$gte": time_window.isoformat()},
    }
    
    # Match by service if available
    if alert.get("service"):
        query["service"] = alert["service"]
    
    # Match by severity
    if alert.get("severity"):
        query["severity"] = alert["severity"]
    
    existing_alerts = await db.alerts.find(query, {"_id": 0}).to_list(100)
    
    for existing in existing_alerts:
        # Check title similarity
        if is_similar_title(alert.get("title", ""), existing.get("title", "")):
            logger.info(f"Deduplicated alert: {alert.get('title')} matches existing {existing.get('id')}")
            
            # Update existing alert's occurrence count
            await db.alerts.update_one(
                {"id": existing["id"]},
                {
                    "$inc": {"occurrence_count": 1},
                    "$set": {"last_occurrence": datetime.now(timezone.utc).isoformat()}
                }
            )
            return existing["id"]
    
    return None


def is_similar_title(title1: str, title2: str, threshold: float = 0.7) -> bool:
    """Check if two alert titles are similar using simple word overlap."""
    if not title1 or not title2:
        return False
    
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())
    
    # Remove common words
    stopwords = {"the", "a", "an", "is", "on", "for", "alert", "warning", "error", "critical"}
    words1 = words1 - stopwords
    words2 = words2 - stopwords
    
    if not words1 or not words2:
        return title1.lower() == title2.lower()
    
    intersection = words1 & words2
    union = words1 | words2
    
    similarity = len(intersection) / len(union)
    return similarity >= threshold


# ======================== CORRELATION ENGINE ========================

async def correlate_alerts(time_window_minutes: int = 15, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Correlate alerts into incidents using rule-based correlation.
    Returns list of newly created incidents.
    Supports multi-tenancy via tenant_id parameter.
    """
    logger.info("Running alert correlation engine...")
    
    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)
    
    # Build query with tenant support
    query = {
        "incident_id": None,
        "status": {"$in": ["open", "acknowledged"]},
        "created_at": {"$gte": time_threshold.isoformat()}
    }
    if tenant_id:
        query["tenant_id"] = tenant_id
    
    # Get uncorrelated alerts within time window
    uncorrelated_alerts = await db.alerts.find(query, {"_id": 0}).to_list(500)
    
    if not uncorrelated_alerts:
        logger.info("No uncorrelated alerts to process")
        return []
    
    logger.info(f"Processing {len(uncorrelated_alerts)} uncorrelated alerts")
    
    # Get current server metrics for context
    server_metrics = await get_current_server_metrics()
    apm_metrics = await get_current_apm_metrics()
    
    # Get service status counts
    service_status = await get_service_status_counts()
    
    # Try to match against correlation rules
    created_incidents = []
    
    for rule in CORRELATION_RULES:
        if await evaluate_rule(rule, uncorrelated_alerts, server_metrics, apm_metrics, service_status):
            # Find matching alerts for this rule
            matching_alerts = await find_matching_alerts_for_rule(rule, uncorrelated_alerts)
            
            if matching_alerts:
                # Create incident
                incident = await create_incident_from_rule(rule, matching_alerts)
                if incident:
                    created_incidents.append(incident)
                    
                    # Remove matched alerts from uncorrelated list
                    matched_ids = {a["id"] for a in matching_alerts}
                    uncorrelated_alerts = [a for a in uncorrelated_alerts if a["id"] not in matched_ids]
    
    # Group remaining alerts by service/time proximity
    if uncorrelated_alerts:
        service_grouped = await group_alerts_by_service(uncorrelated_alerts)
        for service, alerts in service_grouped.items():
            if len(alerts) >= 2:
                incident = await create_generic_incident(service, alerts)
                if incident:
                    created_incidents.append(incident)
    
    logger.info(f"Created {len(created_incidents)} new incidents from correlation")
    return created_incidents


async def evaluate_rule(
    rule: Dict[str, Any],
    alerts: List[Dict[str, Any]],
    server_metrics: Dict[str, Any],
    apm_metrics: Dict[str, Any],
    service_status: Dict[str, int]
) -> bool:
    """Evaluate if a correlation rule matches current conditions."""
    conditions_met = 0
    total_conditions = len(rule.get("conditions", []))
    
    for condition in rule.get("conditions", []):
        cond_type = condition.get("type")
        
        if cond_type == "metric":
            source = condition.get("source")
            metric = condition.get("metric")
            operator = condition.get("operator")
            value = condition.get("value")
            
            if source == "server":
                current_value = server_metrics.get(f"avg_{metric}", 0)
            elif source == "apm":
                current_value = apm_metrics.get(f"avg_{metric}", 0)
            else:
                continue
            
            if evaluate_operator(current_value, operator, value):
                conditions_met += 1
        
        elif cond_type == "alert_pattern":
            title_contains = condition.get("title_contains", [])
            for alert in alerts:
                title_lower = alert.get("title", "").lower()
                if any(pattern.lower() in title_lower for pattern in title_contains):
                    conditions_met += 1
                    break
        
        elif cond_type == "service_count":
            status = condition.get("status")
            operator = condition.get("operator")
            value = condition.get("value")
            
            count = service_status.get(status, 0)
            if evaluate_operator(count, operator, value):
                conditions_met += 1
        
        elif cond_type == "alert_count":
            severity = condition.get("severity")
            time_window = condition.get("time_window_minutes", 5)
            operator = condition.get("operator")
            value = condition.get("value")
            
            threshold = datetime.now(timezone.utc) - timedelta(minutes=time_window)
            count = sum(
                1 for a in alerts 
                if a.get("severity") == severity 
                and a.get("created_at", "") >= threshold.isoformat()
            )
            
            if evaluate_operator(count, operator, value):
                conditions_met += 1
        
        elif cond_type == "time_proximity":
            # Check if multiple alerts occurred within specified minutes
            minutes = condition.get("minutes", 5)
            if len(alerts) >= 2:
                timestamps = sorted([a.get("created_at", "") for a in alerts])
                if timestamps:
                    first = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
                    last = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
                    if (last - first).total_seconds() <= minutes * 60:
                        conditions_met += 1
    
    # Rule matches if all conditions are met (AND logic)
    return conditions_met >= total_conditions and total_conditions > 0


def evaluate_operator(value: float, operator: str, threshold: float) -> bool:
    """Evaluate comparison operator."""
    if operator == "gt":
        return value > threshold
    elif operator == "lt":
        return value < threshold
    elif operator == "gte":
        return value >= threshold
    elif operator == "lte":
        return value <= threshold
    elif operator == "eq":
        return value == threshold
    return False


async def find_matching_alerts_for_rule(
    rule: Dict[str, Any],
    alerts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Find alerts that match a specific correlation rule."""
    matching = []
    
    for condition in rule.get("conditions", []):
        if condition.get("type") == "alert_pattern":
            title_contains = condition.get("title_contains", [])
            for alert in alerts:
                title_lower = alert.get("title", "").lower()
                if any(pattern.lower() in title_lower for pattern in title_contains):
                    if alert not in matching:
                        matching.append(alert)
    
    # If no pattern matching, get alerts by severity
    if not matching and rule.get("severity"):
        matching = [a for a in alerts if a.get("severity") == rule["severity"]][:10]
    
    return matching


async def create_incident_from_rule(
    rule: Dict[str, Any],
    alerts: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Create an incident based on a matched correlation rule."""
    if not alerts:
        return None
    
    incident_id = str(uuid.uuid4())
    alert_ids = [a["id"] for a in alerts]
    
    # Determine service from alerts
    services = list(set(a.get("service", "unknown") for a in alerts))
    primary_service = services[0] if services else "unknown"
    
    incident = {
        "id": incident_id,
        "title": f"{rule['name']} - {primary_service}",
        "description": rule.get("description", ""),
        "severity": rule.get("severity", "warning"),
        "status": "open",
        "service": primary_service,
        "affected_services": services,
        "alert_count": len(alerts),
        "alert_ids": alert_ids,
        "correlation_rule_id": rule["id"],
        "root_cause": rule.get("root_cause"),
        "suggested_actions": rule.get("suggested_actions", []),
        "ai_analysis": {
            "correlation_type": "rule_based",
            "rule_name": rule["name"],
            "confidence": 0.85
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "mttr_seconds": None
    }
    
    await db.incidents.insert_one(incident)
    
    # Update alerts with incident ID
    await db.alerts.update_many(
        {"id": {"$in": alert_ids}},
        {"$set": {"incident_id": incident_id}}
    )
    
    # Broadcast new incident
    await ws_manager.broadcast({
        "type": "new_incident",
        "data": {k: v for k, v in incident.items() if k != "_id"}
    })
    
    logger.info(f"Created incident {incident_id} from rule '{rule['name']}' with {len(alerts)} alerts")
    return {k: v for k, v in incident.items() if k != "_id"}


async def create_generic_incident(
    service: str,
    alerts: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Create a generic incident from grouped alerts."""
    if len(alerts) < 2:
        return None
    
    incident_id = str(uuid.uuid4())
    alert_ids = [a["id"] for a in alerts]
    
    # Determine severity from highest alert severity
    severity_order = {"critical": 3, "warning": 2, "info": 1}
    max_severity = max(alerts, key=lambda a: severity_order.get(a.get("severity", "info"), 0))
    
    incident = {
        "id": incident_id,
        "title": f"Multiple Alerts - {service}",
        "description": f"{len(alerts)} related alerts detected for {service}",
        "severity": max_severity.get("severity", "warning"),
        "status": "open",
        "service": service,
        "affected_services": [service],
        "alert_count": len(alerts),
        "alert_ids": alert_ids,
        "correlation_rule_id": None,
        "root_cause": None,
        "suggested_actions": [
            "Review alert details",
            "Check service logs",
            "Investigate recent changes"
        ],
        "ai_analysis": {
            "correlation_type": "proximity_grouping",
            "confidence": 0.6
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "mttr_seconds": None
    }
    
    await db.incidents.insert_one(incident)
    
    # Update alerts with incident ID
    await db.alerts.update_many(
        {"id": {"$in": alert_ids}},
        {"$set": {"incident_id": incident_id}}
    )
    
    # Broadcast new incident
    await ws_manager.broadcast({
        "type": "new_incident",
        "data": {k: v for k, v in incident.items() if k != "_id"}
    })
    
    logger.info(f"Created generic incident {incident_id} for service '{service}' with {len(alerts)} alerts")
    return {k: v for k, v in incident.items() if k != "_id"}


async def group_alerts_by_service(alerts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group alerts by service."""
    grouped = defaultdict(list)
    for alert in alerts:
        service = alert.get("service", "unknown")
        grouped[service].append(alert)
    return dict(grouped)


# ======================== HELPER FUNCTIONS ========================

async def get_current_server_metrics() -> Dict[str, Any]:
    """Get aggregated server metrics."""
    servers = await db.servers.find({"status": {"$ne": "offline"}}, {"_id": 0}).to_list(100)
    
    if not servers:
        return {}
    
    total_cpu = sum(s.get("cpu_usage", 0) or 0 for s in servers)
    total_memory = sum(s.get("memory_usage", 0) or 0 for s in servers)
    total_disk = sum(s.get("disk_usage", 0) or 0 for s in servers)
    count = len(servers)
    
    return {
        "avg_cpu": total_cpu / count if count > 0 else 0,
        "avg_memory": total_memory / count if count > 0 else 0,
        "avg_disk": total_disk / count if count > 0 else 0,
        "server_count": count
    }


async def get_current_apm_metrics() -> Dict[str, Any]:
    """Get aggregated APM metrics."""
    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
    
    transactions = await db.apm_transactions.find({
        "start_time": {"$gte": time_threshold.isoformat()}
    }, {"_id": 0, "duration_ms": 1}).to_list(1000)
    
    if not transactions:
        return {"avg_latency": 0}
    
    durations = [t.get("duration_ms", 0) for t in transactions]
    return {
        "avg_latency": sum(durations) / len(durations) if durations else 0,
        "transaction_count": len(transactions)
    }


async def get_service_status_counts() -> Dict[str, int]:
    """Get count of services by status."""
    monitors = await db.monitors.find({}, {"_id": 0, "status": 1}).to_list(500)
    
    counts = defaultdict(int)
    for m in monitors:
        status = m.get("status", "unknown")
        if status in ["up", "healthy"]:
            counts["up"] += 1
        elif status in ["down", "unhealthy"]:
            counts["down"] += 1
        elif status == "degraded":
            counts["degraded"] += 1
        else:
            counts["unknown"] += 1
    
    return dict(counts)


# ======================== API FUNCTIONS ========================

async def run_correlation_cycle(tenant_id: Optional[str] = None):
    """Run a single correlation cycle - called by scheduler or API."""
    try:
        incidents = await correlate_alerts(tenant_id=tenant_id)
        return {
            "success": True,
            "incidents_created": len(incidents),
            "incidents": incidents
        }
    except Exception as e:
        logger.error(f"Correlation cycle failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def get_correlation_rules() -> List[Dict[str, Any]]:
    """Get all correlation rules."""
    return CORRELATION_RULES


async def get_correlation_stats(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get correlation engine statistics (tenant-aware)."""
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
        
    total_incidents = await db.incidents.count_documents(query)
    rule_based = await db.incidents.count_documents({**query, "correlation_rule_id": {"$ne": None}})
    auto_grouped = await db.incidents.count_documents({**query, "correlation_rule_id": None})
    
    return {
        "total_incidents": total_incidents,
        "rule_based_incidents": rule_based,
        "auto_grouped_incidents": auto_grouped,
        "correlation_rules_count": len(CORRELATION_RULES),
        "rules": [{"id": r["id"], "name": r["name"]} for r in CORRELATION_RULES]
    }
