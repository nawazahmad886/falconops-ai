"""
FalconOps AI - Impact Analysis Engine
Blast radius analysis — maps affected services, users, and dependencies from incidents
"""
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)


async def analyze_blast_radius(incident: Dict) -> Dict:
    """
    Analyze the blast radius of an incident.
    Takes an incident dict with: host, service, severity, type, source_ip, user
    Returns: affected services, affected users, dependency chain, risk score
    """
    host = incident.get("host", "")
    service = incident.get("service", "")
    severity = incident.get("severity", "warning")
    source_ip = incident.get("source_ip", "")
    incident_type = incident.get("type", "unknown")
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=1)).isoformat()

    # 1. Find directly affected services from topology
    affected_services = []
    try:
        service_nodes = await db.topology_services.find(
            {"$or": [
                {"name": {"$regex": re.escape(service), "$options": "i"}} if service else {"_id": None},
                {"host": host} if host else {"_id": None},
            ]},
            {"_id": 0}
        ).to_list(20)

        for svc in service_nodes:
            affected_services.append({
                "name": svc.get("name", ""),
                "type": svc.get("type", "service"),
                "host": svc.get("host", ""),
                "health": svc.get("health", "unknown"),
                "impact": "direct",
            })

        # Find downstream dependencies
        for svc in service_nodes:
            svc_id = svc.get("id", "")
            if svc_id:
                connections = await db.topology_connections.find(
                    {"source_id": svc_id},
                    {"_id": 0}
                ).to_list(20)
                for conn in connections:
                    target = await db.topology_services.find_one(
                        {"id": conn.get("target_id")},
                        {"_id": 0}
                    )
                    if target:
                        affected_services.append({
                            "name": target.get("name", ""),
                            "type": target.get("type", "service"),
                            "host": target.get("host", ""),
                            "health": target.get("health", "unknown"),
                            "impact": "downstream",
                            "connection_type": conn.get("type", "depends_on"),
                        })
    except Exception as e:
        logger.warning(f"Topology lookup failed: {e}")

    # 2. Find related active violations on the same host/service
    related_violations = []
    try:
        viol_query = {"state": {"$in": ["active", "critical", "warning"]}, "timestamp": {"$gte": cutoff}}
        if host:
            viol_query["source_name"] = {"$regex": re.escape(host), "$options": "i"}
        violations = await db["db.health_violations"].find(viol_query, {"_id": 0}).limit(10).to_list(10)
        for v in violations:
            related_violations.append({
                "rule_name": v.get("rule_name", ""),
                "metric": v.get("metric", ""),
                "severity": v.get("severity", ""),
                "value": v.get("value"),
                "source": v.get("source_name", ""),
            })
    except Exception as e:
        logger.warning(f"Violation lookup failed: {e}")

    # 3. Find related security threats
    related_threats = []
    try:
        threat_query = {"status": "active", "timestamp": {"$gte": cutoff}}
        if source_ip:
            threat_query["source_ip"] = source_ip
        elif host:
            threat_query["$or"] = [{"source_ip": host}, {"host": host}]
        threats = await db.security_threats.find(threat_query, {"_id": 0}).limit(10).to_list(10)
        for t in threats:
            related_threats.append({
                "type": t.get("type", ""),
                "severity": t.get("severity", ""),
                "message": t.get("message", ""),
                "source_ip": t.get("source_ip", ""),
            })
    except Exception as e:
        logger.warning(f"Threat lookup failed: {e}")

    # 4. Find affected users
    affected_users = []
    try:
        user_query = {"timestamp": {"$gte": cutoff}}
        if host:
            user_query["host"] = host
        elif source_ip:
            user_query["source_ip"] = source_ip
        user_pipeline = [
            {"$match": user_query},
            {"$group": {"_id": "$user", "event_count": {"$sum": 1}, "last_seen": {"$max": "$timestamp"}}},
            {"$match": {"_id": {"$ne": "unknown"}}},
            {"$sort": {"event_count": -1}},
            {"$limit": 15},
        ]
        users = await db.security_events.aggregate(user_pipeline).to_list(15)
        for u in users:
            if u["_id"]:
                affected_users.append({"user": u["_id"], "event_count": u["event_count"], "last_seen": u["last_seen"]})
    except Exception as e:
        logger.warning(f"User lookup failed: {e}")

    # 5. Find affected monitors
    affected_monitors = []
    try:
        mon_query = {"status": {"$in": ["down", "degraded"]}}
        if host:
            mon_query["$or"] = [{"url": {"$regex": re.escape(host), "$options": "i"}}, {"name": {"$regex": re.escape(host), "$options": "i"}}]
        monitors = await db.monitors.find(mon_query, {"_id": 0, "name": 1, "url": 1, "status": 1, "type": 1}).limit(10).to_list(10)
        for m in monitors:
            affected_monitors.append(m)
    except Exception as e:
        logger.warning(f"Monitor lookup failed: {e}")

    # 6. Calculate overall impact score (0-100)
    sev_weight = {"critical": 40, "high": 25, "warning": 10, "info": 0}
    base = sev_weight.get(severity, 10)
    service_impact = min(len(affected_services) * 8, 25)
    violation_impact = min(len(related_violations) * 5, 15)
    threat_impact = min(len(related_threats) * 8, 15)
    user_impact = min(len(affected_users) * 2, 10)

    impact_score = min(base + service_impact + violation_impact + threat_impact + user_impact, 100)

    impact_level = "critical" if impact_score >= 70 else "high" if impact_score >= 45 else "medium" if impact_score >= 20 else "low"

    analysis = {
        "id": str(uuid.uuid4()),
        "incident": incident,
        "impact_score": impact_score,
        "impact_level": impact_level,
        "affected_services": affected_services,
        "affected_service_count": len(affected_services),
        "related_violations": related_violations,
        "related_threats": related_threats,
        "affected_users": affected_users,
        "affected_user_count": len(affected_users),
        "affected_monitors": affected_monitors,
        "analysis_time": datetime.now(timezone.utc).isoformat(),
        "summary": _build_summary(incident, impact_score, impact_level, affected_services, related_violations, related_threats, affected_users),
    }

    # Store analysis
    await db.impact_analyses.insert_one(analysis)
    analysis.pop("_id", None)

    return analysis


def _build_summary(incident, score, level, services, violations, threats, users):
    """Build a human-readable impact summary"""
    parts = [f"Impact Analysis for {incident.get('type', 'incident')} on {incident.get('host', 'unknown')}:"]
    parts.append(f"Overall impact: {level.upper()} (score: {score}/100)")

    if services:
        direct = [s for s in services if s["impact"] == "direct"]
        downstream = [s for s in services if s["impact"] == "downstream"]
        if direct:
            parts.append(f"Directly affected: {', '.join(s['name'] for s in direct)}")
        if downstream:
            parts.append(f"Downstream impact: {', '.join(s['name'] for s in downstream)}")

    if violations:
        parts.append(f"{len(violations)} active health violations detected")
    if threats:
        parts.append(f"{len(threats)} active security threats correlated")
    if users:
        parts.append(f"{len(users)} users potentially affected")

    return " | ".join(parts)


async def get_impact_history(limit: int = 20) -> List[Dict]:
    """Get recent impact analyses"""
    return await db.impact_analyses.find({}, {"_id": 0}).sort("analysis_time", -1).limit(limit).to_list(limit)


async def get_impact_stats() -> Dict:
    """Get impact analysis statistics"""
    total = await db.impact_analyses.count_documents({})

    level_pipeline = [
        {"$group": {"_id": "$impact_level", "count": {"$sum": 1}}},
    ]
    by_level = await db.impact_analyses.aggregate(level_pipeline).to_list(10)

    avg_pipeline = [
        {"$group": {"_id": None, "avg_score": {"$avg": "$impact_score"}, "max_score": {"$max": "$impact_score"}}},
    ]
    avg_result = await db.impact_analyses.aggregate(avg_pipeline).to_list(1)
    avg_data = avg_result[0] if avg_result else {"avg_score": 0, "max_score": 0}

    return {
        "total_analyses": total,
        "avg_impact_score": round(avg_data.get("avg_score", 0), 1),
        "max_impact_score": avg_data.get("max_score", 0),
        "by_level": [{"level": l["_id"], "count": l["count"]} for l in by_level],
    }
