"""
FalconOps AI - SLA Calculation Service
Computes uptime SLA percentages, breach detection, and compliance reporting
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from calendar import monthrange

from ..core.database import db

logger = logging.getLogger(__name__)

SLA_TARGETS = {
    "99.9": {"label": "99.9% (Three Nines)", "max_downtime_month_min": 43.8},
    "99.95": {"label": "99.95%", "max_downtime_month_min": 21.9},
    "99.99": {"label": "99.99% (Four Nines)", "max_downtime_month_min": 4.38},
    "99.999": {"label": "99.999% (Five Nines)", "max_downtime_month_min": 0.44},
}


async def set_sla_target(monitor_id: str, target: str) -> Dict:
    await db.uptime_monitors.update_one({"id": monitor_id}, {"$set": {"sla_target": target}})
    return {"monitor_id": monitor_id, "sla_target": target}


async def get_sla_summary(monitor_id: str, months: int = 3) -> Dict:
    mon = await db.uptime_monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not mon:
        return {"error": "Monitor not found"}

    target = float(mon.get("sla_target", "99.9"))
    now = datetime.now(timezone.utc)
    monthly = []

    for i in range(months):
        if i == 0:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            start = now.replace(year=y, month=m, day=1, hour=0, minute=0, second=0, microsecond=0)

        days_in_month = monthrange(start.year, start.month)[1]
        end = start.replace(day=days_in_month, hour=23, minute=59, second=59)
        if end > now:
            end = now

        total = await db.uptime_checks.count_documents({
            "monitor_id": monitor_id,
            "timestamp": {"$gte": start.isoformat(), "$lte": end.isoformat()},
        })
        failures = await db.uptime_checks.count_documents({
            "monitor_id": monitor_id,
            "timestamp": {"$gte": start.isoformat(), "$lte": end.isoformat()},
            "success": False,
        })
        uptime_pct = round(((total - failures) / max(total, 1)) * 100, 4)
        breached = uptime_pct < target
        total_minutes = (end - start).total_seconds() / 60
        downtime_min = round(total_minutes * (1 - uptime_pct / 100), 2)
        max_allowed = total_minutes * (1 - target / 100)

        monthly.append({
            "month": start.strftime("%Y-%m"),
            "month_label": start.strftime("%B %Y"),
            "total_checks": total,
            "failures": failures,
            "uptime_pct": uptime_pct,
            "target_pct": target,
            "breached": breached,
            "downtime_minutes": downtime_min,
            "max_downtime_minutes": round(max_allowed, 2),
            "remaining_budget_min": round(max(0, max_allowed - downtime_min), 2),
        })

    overall_checks = sum(m["total_checks"] for m in monthly)
    overall_failures = sum(m["failures"] for m in monthly)
    overall_uptime = round(((overall_checks - overall_failures) / max(overall_checks, 1)) * 100, 4)

    return {
        "monitor_id": monitor_id,
        "monitor_name": mon.get("name", ""),
        "url": mon.get("url", ""),
        "sla_target": target,
        "overall_uptime_pct": overall_uptime,
        "overall_compliant": overall_uptime >= target,
        "months_breached": sum(1 for m in monthly if m["breached"]),
        "monthly": monthly,
    }


async def get_sla_overview(months: int = 1) -> Dict:
    monitors = await db.uptime_monitors.find({"enabled": True}, {"_id": 0}).to_list(200)
    results = []
    for mon in monitors:
        summary = await get_sla_summary(mon["id"], months)
        if "error" not in summary:
            results.append({
                "monitor_id": mon["id"],
                "name": mon.get("name", ""),
                "url": mon.get("url", ""),
                "sla_target": float(mon.get("sla_target", "99.9")),
                "uptime_pct": summary["overall_uptime_pct"],
                "compliant": summary["overall_compliant"],
                "months_breached": summary["months_breached"],
                "status": mon.get("status", "pending"),
            })

    compliant = sum(1 for r in results if r["compliant"])
    total = len(results)
    return {
        "total_monitors": total,
        "compliant": compliant,
        "breached": total - compliant,
        "compliance_rate": round((compliant / max(total, 1)) * 100, 1),
        "monitors": results,
        "targets_available": [{"id": k, **v} for k, v in SLA_TARGETS.items()],
    }


async def get_incident_timeline(monitor_id: str, days: int = 30) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    alerts = await db.uptime_alerts.find(
        {"monitor_id": monitor_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("timestamp", 1).to_list(200)

    incidents = []
    current_incident = None
    for a in alerts:
        if a["alert_type"] == "down":
            current_incident = {
                "start": a["timestamp"],
                "end": None,
                "duration_min": None,
                "status_code": a.get("status_code"),
                "error": a.get("error"),
            }
        elif a["alert_type"] == "recovered" and current_incident:
            current_incident["end"] = a["timestamp"]
            try:
                s = datetime.fromisoformat(current_incident["start"])
                e = datetime.fromisoformat(current_incident["end"])
                current_incident["duration_min"] = round((e - s).total_seconds() / 60, 1)
            except Exception:
                pass
            incidents.append(current_incident)
            current_incident = None

    if current_incident:
        current_incident["end"] = "ongoing"
        current_incident["duration_min"] = None
        incidents.append(current_incident)

    return incidents
