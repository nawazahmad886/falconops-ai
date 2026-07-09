"""
FalconOps AI - Detection Rules & Incident Intelligence Service
Admin-configurable error detection rules and AI-powered incident correlation
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

# ======================== DETECTION RULES ========================

DEFAULT_RULES = [
    {"rule_id": "high_error_rate", "name": "High Error Rate", "description": "Triggers when error rate exceeds threshold", "metric": "error_rate", "operator": "gt", "threshold": 5.0, "severity": "critical", "cooldown_min": 5, "enabled": True, "category": "performance"},
    {"rule_id": "slow_response", "name": "Slow Response Time", "description": "Triggers when avg response > threshold ms", "metric": "response_time_ms", "operator": "gt", "threshold": 2000, "severity": "warning", "cooldown_min": 10, "enabled": True, "category": "performance"},
    {"rule_id": "service_down", "name": "Service Down", "description": "Triggers when a service becomes unreachable", "metric": "status", "operator": "eq", "threshold": "down", "severity": "critical", "cooldown_min": 1, "enabled": True, "category": "availability"},
    {"rule_id": "memory_high", "name": "High Memory Usage", "description": "Triggers when memory usage exceeds threshold", "metric": "memory_usage", "operator": "gt", "threshold": 90, "severity": "warning", "cooldown_min": 15, "enabled": True, "category": "resource"},
    {"rule_id": "cpu_high", "name": "High CPU Usage", "description": "Triggers when CPU usage exceeds threshold", "metric": "cpu_usage", "operator": "gt", "threshold": 85, "severity": "warning", "cooldown_min": 15, "enabled": True, "category": "resource"},
    {"rule_id": "disk_full", "name": "Disk Nearly Full", "description": "Triggers when disk usage exceeds threshold", "metric": "disk_usage", "operator": "gt", "threshold": 90, "severity": "critical", "cooldown_min": 30, "enabled": True, "category": "resource"},
    {"rule_id": "ssl_expiry", "name": "SSL Certificate Expiring", "description": "Triggers when SSL cert expires within days", "metric": "ssl_days_remaining", "operator": "lt", "threshold": 14, "severity": "warning", "cooldown_min": 1440, "enabled": True, "category": "security"},
    {"rule_id": "anomaly_detected", "name": "Anomaly Detected", "description": "Triggers when AI detects unusual pattern", "metric": "anomaly_score", "operator": "gt", "threshold": 0.8, "severity": "warning", "cooldown_min": 30, "enabled": True, "category": "ai"},
]


async def init_default_rules():
    for rule in DEFAULT_RULES:
        existing = await db.detection_rules.find_one({"rule_id": rule["rule_id"]})
        if not existing:
            rule["created_at"] = datetime.now(timezone.utc).isoformat()
            rule["is_system"] = True
            await db.detection_rules.insert_one(rule)


async def get_rules() -> List[Dict]:
    await init_default_rules()
    return await db.detection_rules.find({}, {"_id": 0}).sort("created_at", 1).to_list(200)


async def create_rule(data: Dict) -> Dict:
    doc = {
        "rule_id": str(uuid.uuid4())[:8],
        "name": data["name"],
        "description": data.get("description", ""),
        "metric": data["metric"],
        "operator": data.get("operator", "gt"),
        "threshold": data["threshold"],
        "severity": data.get("severity", "warning"),
        "cooldown_min": data.get("cooldown_min", 10),
        "enabled": data.get("enabled", True),
        "category": data.get("category", "custom"),
        "is_system": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.detection_rules.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def update_rule(rule_id: str, updates: Dict) -> Dict:
    allowed = {"name", "description", "metric", "operator", "threshold", "severity", "cooldown_min", "enabled", "category"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if filtered:
        await db.detection_rules.update_one({"rule_id": rule_id}, {"$set": filtered})
    return await db.detection_rules.find_one({"rule_id": rule_id}, {"_id": 0})


async def delete_rule(rule_id: str) -> bool:
    rule = await db.detection_rules.find_one({"rule_id": rule_id}, {"_id": 0})
    if rule and rule.get("is_system"):
        return False
    r = await db.detection_rules.delete_one({"rule_id": rule_id})
    return r.deleted_count > 0


# ======================== INCIDENT INTELLIGENCE ========================

async def get_incidents_with_intelligence(hours: int = 24, limit: int = 20) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    # Gather recent alerts
    alerts = await db.uptime_alerts.find({"timestamp": {"$gte": cutoff}}, {"_id": 0}).sort("timestamp", -1).limit(100).to_list(100)
    threats = await db.security_threats.find({"timestamp": {"$gte": cutoff}, "status": "active"}, {"_id": 0}).sort("timestamp", -1).limit(50).to_list(50)

    # Group alerts by monitor into incidents
    incidents = {}
    for a in alerts:
        mid = a.get("monitor_id", "unknown")
        if mid not in incidents:
            incidents[mid] = {
                "id": str(uuid.uuid4())[:12],
                "monitor_id": mid,
                "monitor_name": a.get("monitor_name", "Unknown"),
                "url": a.get("url", ""),
                "type": "uptime",
                "alerts": [],
                "first_seen": a["timestamp"],
                "last_seen": a["timestamp"],
                "severity": "warning",
                "status": "active",
            }
        incidents[mid]["alerts"].append(a)
        if a.get("alert_type") == "down":
            incidents[mid]["severity"] = "critical"
        if a["timestamp"] < incidents[mid]["first_seen"]:
            incidents[mid]["first_seen"] = a["timestamp"]
        if a["timestamp"] > incidents[mid]["last_seen"]:
            incidents[mid]["last_seen"] = a["timestamp"]

    # Add security incidents
    for t in threats:
        tid = t.get("id", str(uuid.uuid4())[:12])
        incidents[f"sec-{tid}"] = {
            "id": tid,
            "monitor_id": None,
            "monitor_name": t.get("message", "Security Threat"),
            "url": t.get("source_ip", ""),
            "type": "security",
            "alerts": [t],
            "first_seen": t.get("timestamp", ""),
            "last_seen": t.get("timestamp", ""),
            "severity": t.get("severity", "warning"),
            "status": "active",
        }

    result = sorted(incidents.values(), key=lambda x: x["last_seen"], reverse=True)[:limit]

    # Generate AI summary for each
    for inc in result:
        inc["alert_count"] = len(inc["alerts"])
        inc["summary"] = _generate_summary(inc)
        inc["root_cause_hint"] = _guess_root_cause(inc)
        del inc["alerts"]  # Don't send raw alerts to frontend

    return result


def _generate_summary(incident: Dict) -> str:
    n = incident.get("alert_count", 0)
    name = incident.get("monitor_name", "service")
    if incident["type"] == "security":
        return f"Security threat detected: {name}. {n} related alert(s)."
    if incident["severity"] == "critical":
        return f"{name} experienced critical downtime with {n} alert(s). Immediate attention required."
    return f"{name} had {n} alert event(s) in the observation period."


def _guess_root_cause(incident: Dict) -> str:
    if incident["type"] == "security":
        return "Potential unauthorized access or attack pattern detected."
    if incident["severity"] == "critical":
        return "Service unreachable — check network connectivity, DNS resolution, or server health."
    return "Intermittent issues detected — may be caused by high load or upstream dependency."


async def get_detection_stats(hours: int = 24) -> Dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rules = await db.detection_rules.find({"enabled": True}, {"_id": 0}).to_list(200)
    alerts_count = await db.uptime_alerts.count_documents({"timestamp": {"$gte": cutoff}})
    threats_count = await db.security_threats.count_documents({"timestamp": {"$gte": cutoff}})

    return {
        "active_rules": len(rules),
        "alerts_fired_24h": alerts_count,
        "threats_detected_24h": threats_count,
        "categories": {
            "performance": sum(1 for r in rules if r.get("category") == "performance"),
            "availability": sum(1 for r in rules if r.get("category") == "availability"),
            "resource": sum(1 for r in rules if r.get("category") == "resource"),
            "security": sum(1 for r in rules if r.get("category") == "security"),
            "ai": sum(1 for r in rules if r.get("category") == "ai"),
            "custom": sum(1 for r in rules if r.get("category") == "custom"),
        },
    }
