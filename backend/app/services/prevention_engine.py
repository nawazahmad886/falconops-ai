"""
FalconOps AI — Prevention Engine
Watches rolling baselines (latency p95, error rate, response time) per service/monitor
and emits early-warning events when current metric crosses 1.5×–2× the 7-day baseline.

Runs scheduled every 5 min via the existing scheduler infrastructure.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

# Configurable thresholds
WARNING_MULTIPLIER = 1.5     # warning when current > 1.5× baseline
CRITICAL_MULTIPLIER = 2.0    # early-warning critical when current > 2× baseline
BASELINE_LOOKBACK_DAYS = 7


async def _baseline_for_monitor(monitor_id: str) -> Optional[Dict]:
    """Return rolling-7d {avg_response_time_ms, p95_response_time_ms, success_rate}."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=BASELINE_LOOKBACK_DAYS)).isoformat()
    cursor = db.uptime_checks.find(
        {"monitor_id": monitor_id, "timestamp": {"$gte": cutoff}, "response_time_ms": {"$gt": 0}},
        {"_id": 0, "response_time_ms": 1, "success": 1},
    ).limit(5000)
    rts: List[float] = []
    successes = 0
    total = 0
    async for c in cursor:
        rts.append(float(c.get("response_time_ms", 0)))
        total += 1
        if c.get("success"):
            successes += 1
    if not rts:
        return None
    rts.sort()
    p95_idx = max(0, int(0.95 * len(rts)) - 1)
    return {
        "avg_response_time_ms": round(sum(rts) / len(rts), 1),
        "p95_response_time_ms": round(rts[p95_idx], 1),
        "success_rate": round((successes / total) * 100, 2) if total else 100.0,
        "sample_size": len(rts),
    }


async def detect_degradation_for_monitor(monitor: Dict) -> Optional[Dict]:
    """Compare last 1h of checks against the 7-day baseline; emit warning if drift detected."""
    mid = monitor["id"]
    baseline = await _baseline_for_monitor(mid)
    if not baseline or baseline["sample_size"] < 20:
        return None

    # Recent window (last 1h)
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    rts: List[float] = []
    successes = 0
    total = 0
    async for c in db.uptime_checks.find(
        {"monitor_id": mid, "timestamp": {"$gte": recent_cutoff}, "response_time_ms": {"$gt": 0}},
        {"_id": 0, "response_time_ms": 1, "success": 1}
    ).limit(500):
        rts.append(float(c.get("response_time_ms", 0)))
        total += 1
        if c.get("success"):
            successes += 1
    if total < 5:
        return None

    rts.sort()
    p95_idx = max(0, int(0.95 * len(rts)) - 1)
    recent = {
        "avg_response_time_ms": round(sum(rts) / len(rts), 1),
        "p95_response_time_ms": round(rts[p95_idx], 1),
        "success_rate": round((successes / total) * 100, 2) if total else 100.0,
        "sample_size": len(rts),
    }

    drift_avg = recent["avg_response_time_ms"] / baseline["avg_response_time_ms"] if baseline["avg_response_time_ms"] else 1.0
    drift_p95 = recent["p95_response_time_ms"] / baseline["p95_response_time_ms"] if baseline["p95_response_time_ms"] else 1.0
    success_drop = baseline["success_rate"] - recent["success_rate"]

    severity = None
    drivers: List[str] = []
    if drift_avg >= CRITICAL_MULTIPLIER or drift_p95 >= CRITICAL_MULTIPLIER:
        severity = "critical"
    elif drift_avg >= WARNING_MULTIPLIER or drift_p95 >= WARNING_MULTIPLIER:
        severity = "warning"
    if drift_avg >= WARNING_MULTIPLIER:
        drivers.append(f"avg latency {drift_avg:.1f}× baseline")
    if drift_p95 >= WARNING_MULTIPLIER:
        drivers.append(f"p95 latency {drift_p95:.1f}× baseline")
    if success_drop > 5:
        severity = severity or "warning"
        drivers.append(f"success rate dropped {success_drop:.1f}pp")

    if not severity:
        return None

    # Estimate time-to-incident
    rate_of_change = drift_avg if drift_avg > drift_p95 else drift_p95
    eta_min = max(5, int(60 / max(0.5, (rate_of_change - 1.0) * 4)))

    warning = {
        "monitor_id": mid,
        "monitor_name": monitor.get("name"),
        "severity": severity,
        "kind": "degradation_drift",
        "drivers": drivers,
        "current": recent,
        "baseline": baseline,
        "eta_minutes_to_incident": eta_min,
        "message": f"Possible incident in ~{eta_min} min — {', '.join(drivers)}",
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist as an early-warning record (idempotent within the hour per monitor)
    hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    warning["dedupe_key"] = f"{mid}:{hour_key}"
    await db.early_warnings.update_one(
        {"dedupe_key": warning["dedupe_key"]},
        {"$set": warning, "$setOnInsert": {"id": warning["dedupe_key"]}},
        upsert=True,
    )
    return warning


async def scan_all_monitors() -> List[Dict]:
    """Run prevention scan across every enabled monitor; return all detected warnings."""
    warnings: List[Dict] = []
    async for mon in db.uptime_monitors.find({"enabled": {"$ne": False}}, {"_id": 0}):
        try:
            w = await detect_degradation_for_monitor(mon)
            if w:
                warnings.append(w)
        except Exception as e:
            logger.warning("prevention scan failed for %s: %s", mon.get("id"), e)
    return warnings


async def list_recent_warnings(hours: int = 24) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    cursor = db.early_warnings.find({"detected_at": {"$gte": cutoff}}, {"_id": 0}).sort("detected_at", -1).limit(100)
    out = []
    async for w in cursor:
        out.append(w)
    return out
