"""
FalconOps AI — Cost Optimizer Agent
Scans monitors, services, and uptime data; flags idle resources with proposed
remediation + estimated monthly savings.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from ..core.database import db

logger = logging.getLogger(__name__)

# Heuristic constants (override via Feature Console limits)
IDLE_CPU_THRESHOLD_PCT = 20.0
IDLE_DAYS_REQUIRED = 1
ESTIMATED_DAILY_COST = {"vm.small": 0.50, "vm.medium": 1.20, "vm.large": 3.00, "default": 1.50}


async def find_idle_monitors(idle_hours: int = 168) -> List[Dict]:
    """Monitors that have not had any check failures in N hours (good candidates to lower interval)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=idle_hours)).isoformat()
    candidates: List[Dict] = []
    async for mon in db.uptime_monitors.find({"enabled": {"$ne": False}}, {"_id": 0}):
        # Total checks in window vs failures
        pipeline = [
            {"$match": {"monitor_id": mon["id"], "timestamp": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total": {"$sum": 1},
                        "failures": {"$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}}}},
        ]
        agg = None
        async for r in db.uptime_checks.aggregate(pipeline):
            agg = r
        if not agg or agg["total"] < 50:
            continue
        if agg["failures"] == 0 and mon.get("interval", 60) <= 60:
            # 7d clean + checking every 60s — lower to 5min for cost saving
            candidates.append({
                "kind": "lower_check_interval",
                "monitor_id": mon["id"],
                "monitor_name": mon["name"],
                "current_interval_sec": mon.get("interval", 60),
                "proposed_interval_sec": 300,
                "rationale": f"100% success over {idle_hours}h ({agg['total']} checks). 5× check reduction.",
                "estimated_savings": "5× compute on this monitor",
                "confidence": 0.85,
            })
    return candidates


async def find_orphaned_data() -> List[Dict]:
    """Find old upload data, orphaned check results, etc."""
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    waste: List[Dict] = []
    # Old event_data uploads with no analysis
    old_uploads = await db.event_uploads.count_documents({
        "uploaded_at": {"$lt": cutoff_30d}, "analyzed": {"$ne": True}
    })
    if old_uploads > 0:
        waste.append({
            "kind": "delete_stale_uploads",
            "count": old_uploads,
            "rationale": f"{old_uploads} uploaded files older than 30 days that were never analyzed",
            "estimated_savings": f"~{old_uploads * 0.5:.0f} MB storage",
            "confidence": 0.95,
        })
    # Old uptime checks
    old_checks = await db.uptime_checks.count_documents({"timestamp": {"$lt": cutoff_30d}})
    if old_checks > 10000:
        waste.append({
            "kind": "archive_old_checks",
            "count": old_checks,
            "rationale": f"{old_checks:,} uptime check records older than 30d (Mongo doc retention)",
            "estimated_savings": f"~{old_checks * 0.001:.1f} MB index",
            "confidence": 0.90,
        })
    return waste


async def find_duplicate_monitors() -> List[Dict]:
    """Detect monitors with the same URL — candidates for consolidation."""
    pipeline = [
        {"$group": {"_id": "$url", "ids": {"$push": "$id"}, "names": {"$push": "$name"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]
    out: List[Dict] = []
    async for g in db.uptime_monitors.aggregate(pipeline):
        out.append({
            "kind": "deduplicate_monitors",
            "url": g["_id"],
            "monitor_ids": g["ids"],
            "monitor_names": g["names"],
            "count": g["count"],
            "rationale": f"{g['count']} monitors all check the same URL",
            "estimated_savings": f"{g['count'] - 1}× redundant compute",
            "confidence": 0.95,
        })
    return out


async def run_cost_scan() -> Dict:
    """One-shot scan returning all cost optimization opportunities."""
    idle = await find_idle_monitors()
    waste = await find_orphaned_data()
    dupes = await find_duplicate_monitors()
    all_recs = idle + waste + dupes
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "recommendations": all_recs,
        "summary": {
            "total_opportunities": len(all_recs),
            "idle_monitors": len(idle),
            "stale_data": len(waste),
            "duplicate_monitors": len(dupes),
        },
    }
