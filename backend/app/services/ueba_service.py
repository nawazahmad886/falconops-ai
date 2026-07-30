"""
FalconOps AI - UEBA (User & Entity Behavior Analytics) Service
Baselines normal user behavior, detects anomalies, calculates risk scores
"""
import uuid
import logging
import math
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import List, Dict, Any, Optional

from ..core.database import db

logger = logging.getLogger(__name__)


# ======================== BEHAVIOR PROFILING ========================

async def build_user_profiles(hours: int = 168, tenant_id: Optional[str] = None) -> List[Dict]:
    """Build behavioral profiles for all users from security events (default 7 days)"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    match_stage: Dict[str, Any] = {"timestamp": {"$gte": cutoff}, "user": {"$ne": "unknown"}}
    if tenant_id:
        match_stage["tenant_id"] = tenant_id

    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$user",
            "total_events": {"$sum": 1},
            "login_success": {"$sum": {"$cond": [{"$eq": ["$action", "login_success"]}, 1, 0]}},
            "login_failed": {"$sum": {"$cond": [{"$in": ["$action", ["login_failed", "auth_failure"]]}, 1, 0]}},
            "priv_actions": {"$sum": {"$cond": [{"$in": ["$action", ["privilege_escalation", "sudo_command", "role_change"]]}, 1, 0]}},
            "data_actions": {"$sum": {"$cond": [{"$in": ["$action", ["data_export", "bulk_download", "mass_delete"]]}, 1, 0]}},
            "unique_ips": {"$addToSet": "$source_ip"},
            "unique_services": {"$addToSet": "$service"},
            "unique_geos": {"$addToSet": "$geo_location"},
            "last_seen": {"$max": "$timestamp"},
            "first_seen": {"$min": "$timestamp"},
            "categories": {"$push": "$category"},
            "hours_active": {"$addToSet": {"$substr": ["$timestamp", 11, 2]}},
        }},
        {"$sort": {"total_events": -1}},
    ]

    raw_profiles = await db.security_events.aggregate(pipeline).to_list(500)

    profiles = []
    for p in raw_profiles:
        user = p["_id"]
        if not user:
            continue

        total = p["total_events"]
        failed = p["login_failed"]
        priv = p["priv_actions"]
        data_act = p["data_actions"]
        ips = [ip for ip in p["unique_ips"] if ip and ip != "unknown"]
        geos = [g for g in p["unique_geos"] if g]
        hours_active = sorted(p.get("hours_active", []))

        # Calculate risk score (0-100)
        risk = 0
        risk_factors = []

        # Failed login ratio
        if total > 0:
            fail_ratio = failed / total
            if fail_ratio > 0.5:
                risk += 25
                risk_factors.append(f"High failure rate ({int(fail_ratio*100)}%)")
            elif fail_ratio > 0.2:
                risk += 10
                risk_factors.append(f"Elevated failure rate ({int(fail_ratio*100)}%)")

        # Multiple IPs
        if len(ips) > 5:
            risk += 20
            risk_factors.append(f"Many source IPs ({len(ips)})")
        elif len(ips) > 3:
            risk += 10
            risk_factors.append(f"Multiple source IPs ({len(ips)})")

        # Geographic spread
        if len(geos) > 3:
            risk += 20
            risk_factors.append(f"Wide geographic spread ({len(geos)} locations)")
        elif len(geos) > 1:
            risk += 5

        # Privileged actions
        if priv > 5:
            risk += 20
            risk_factors.append(f"Frequent privilege escalation ({priv})")
        elif priv > 0:
            risk += 5
            risk_factors.append(f"Privilege escalation ({priv})")

        # Data exfiltration signals
        if data_act > 3:
            risk += 25
            risk_factors.append(f"Suspicious data access ({data_act})")
        elif data_act > 0:
            risk += 10
            risk_factors.append(f"Data access events ({data_act})")

        # Off-hours activity (crude: outside 06-20 local)
        off_hours = [h for h in hours_active if h and (int(h) < 6 or int(h) > 20)]
        if len(off_hours) > 3:
            risk += 10
            risk_factors.append(f"Frequent off-hours activity")

        risk = min(risk, 100)

        risk_level = "critical" if risk >= 70 else "high" if risk >= 50 else "medium" if risk >= 25 else "low"

        profile = {
            "user": user,
            "total_events": total,
            "login_success": p["login_success"],
            "login_failed": failed,
            "priv_actions": priv,
            "data_actions": data_act,
            "unique_ips": len(ips),
            "ips": ips[:10],
            "unique_geos": len(geos),
            "geos": geos[:10],
            "unique_services": len([s for s in p["unique_services"] if s]),
            "hours_active": hours_active,
            "risk_score": risk,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "last_seen": p["last_seen"],
            "first_seen": p["first_seen"],
        }
        profiles.append(profile)

    # Sort by risk_score descending
    profiles.sort(key=lambda x: x["risk_score"], reverse=True)
    return profiles


async def get_user_behavior_timeline(user: str, hours: int = 168) -> Dict:
    """Get detailed behavior timeline for a specific user"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    events = await db.security_events.find(
        {"user": user, "timestamp": {"$gte": cutoff}},
        {"_id": 0, "id": 1, "timestamp": 1, "action": 1, "category": 1, "severity": 1, "source_ip": 1, "geo_location": 1, "service": 1, "message": 1}
    ).sort("timestamp", -1).limit(200).to_list(200)

    # Hourly activity distribution
    hourly = defaultdict(int)
    for ev in events:
        try:
            h = ev["timestamp"][11:13]
            hourly[h] = hourly.get(h, 0) + 1
        except Exception:
            pass

    hourly_dist = [{"hour": f"{h:02d}:00", "count": hourly.get(f"{h:02d}", 0)} for h in range(24)]

    # Action breakdown
    action_counts = defaultdict(int)
    for ev in events:
        action_counts[ev.get("action", "unknown")] += 1

    # Threats for this user
    threats = await db.security_threats.find(
        {"user": user, "status": "active"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(20).to_list(20)

    return {
        "user": user,
        "events": events[:50],
        "total_events": len(events),
        "hourly_distribution": hourly_dist,
        "action_breakdown": [{"action": k, "count": v} for k, v in sorted(action_counts.items(), key=lambda x: -x[1])],
        "active_threats": threats,
    }


async def get_insider_threat_candidates(hours: int = 168, tenant_id: Optional[str] = None) -> List[Dict]:
    """Explicit insider-threat framing on top of the already-real UEBA risk score:
    a user is a candidate when their behavioral risk is high/critical AND they've
    actually touched privileged or data-sensitive actions — pure re-labeling of
    build_user_profiles() output, no new data source, no fabricated signal."""
    profiles = await build_user_profiles(hours, tenant_id=tenant_id)
    candidates = []
    for p in profiles:
        if p["risk_level"] not in ("high", "critical"):
            continue
        if p["priv_actions"] <= 0 and p["data_actions"] <= 0:
            continue
        reasons = []
        if p["priv_actions"] > 0:
            reasons.append(f"{p['priv_actions']} privileged action(s)")
        if p["data_actions"] > 0:
            reasons.append(f"{p['data_actions']} data-access event(s)")
        candidates.append({
            **p,
            "insider_threat_reason": f"Risk level {p['risk_level']} with {' and '.join(reasons)}",
        })
    return candidates


async def get_ueba_summary(hours: int = 168) -> Dict:
    """Get UEBA summary statistics"""
    profiles = await build_user_profiles(hours)

    critical_users = [p for p in profiles if p["risk_level"] == "critical"]
    high_users = [p for p in profiles if p["risk_level"] == "high"]
    medium_users = [p for p in profiles if p["risk_level"] == "medium"]
    low_users = [p for p in profiles if p["risk_level"] == "low"]

    # Top risk factors across all users
    all_factors = defaultdict(int)
    for p in profiles:
        for f in p["risk_factors"]:
            factor_type = f.split("(")[0].strip()
            all_factors[factor_type] += 1

    return {
        "total_users": len(profiles),
        "critical_count": len(critical_users),
        "high_count": len(high_users),
        "medium_count": len(medium_users),
        "low_count": len(low_users),
        "avg_risk_score": round(sum(p["risk_score"] for p in profiles) / max(len(profiles), 1), 1),
        "top_risk_factors": [{"factor": k, "count": v} for k, v in sorted(all_factors.items(), key=lambda x: -x[1])[:10]],
        "risk_distribution": [
            {"level": "critical", "count": len(critical_users)},
            {"level": "high", "count": len(high_users)},
            {"level": "medium", "count": len(medium_users)},
            {"level": "low", "count": len(low_users)},
        ],
    }
