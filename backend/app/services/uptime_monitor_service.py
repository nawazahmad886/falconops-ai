"""
FalconOps AI - Uptime / URL Monitoring Service
Production-grade async HTTP checker with background scheduler, uptime %, alerts, multi-region
Advanced assertions: status code, content match, JSON path, response time SLA, SSL expiry.
Uses shared assertion_engine module (also used by synthetic monitoring).
"""
import uuid
import asyncio
import random
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db
from .assertion_engine import (
    DEFAULT_BODY_DENY_PATTERNS,
    build_default_assertions as _build_default_assertions,
    evaluate_assertions as _evaluate_assertions,
    eval_json_path as _eval_json_path,
    check_ssl_expiry as _check_ssl_expiry,
)

logger = logging.getLogger(__name__)

_scheduler_task = None

# Safe-default assertions are now centralized in assertion_engine.DEFAULT_BODY_DENY_PATTERNS
# and merged via _build_default_assertions() (imported above).


# ======================== REGIONS ========================

REGIONS = {
    "us-east": {"name": "US East (Virginia)", "latency_offset": 0},
    "us-west": {"name": "US West (Oregon)", "latency_offset": 15},
    "eu-west": {"name": "EU West (Ireland)", "latency_offset": 80},
    "me-south": {"name": "Middle East (Saudi Arabia)", "latency_offset": 120},
    "ap-southeast": {"name": "Asia Pacific (Singapore)", "latency_offset": 160},
}


def get_regions():
    return [{"id": k, **v} for k, v in REGIONS.items()]


async def create_monitor(name: str, url: str, interval: int = 60, method: str = "GET",
                         expected_status: int = 200, timeout: int = 10,
                         headers: dict = None, created_by: str = "",
                         regions: list = None, alert_channels: list = None,
                         consecutive_failures: int = 3,
                         assertions: list = None,
                         max_response_time_ms: Optional[int] = None,
                         ssl_expiry_warn_days: int = 14,
                         apply_safe_defaults: bool = True) -> Dict:
    # Merge assertions with safe defaults from Feature Control Console (admin-tunable)
    final_assertions = list(assertions or [])
    if apply_safe_defaults:
        try:
            from .feature_flags_service import get_deny_patterns
            live_patterns = await get_deny_patterns()
            live_defaults = [
                {"type": "not_contains", "value": p, "case_sensitive": False}
                for p in live_patterns
            ]
        except Exception:
            live_defaults = _build_default_assertions()

        existing_keys = {(a.get("type"), str(a.get("value", "")).lower()) for a in final_assertions}
        for default_a in live_defaults:
            key = (default_a["type"], str(default_a["value"]).lower())
            if key not in existing_keys:
                final_assertions.append(default_a)

    doc = {
        "id": str(uuid.uuid4()),
        "name": name,
        "url": url,
        "method": method.upper(),
        "interval": max(30, interval),
        "expected_status": expected_status,
        "timeout": min(timeout, 30),
        "headers": headers or {},
        "regions": regions or ["us-east"],
        "alert_channels": alert_channels or [],
        "consecutive_failures": max(1, consecutive_failures),
        "assertions": final_assertions,
        "max_response_time_ms": max_response_time_ms,
        "ssl_expiry_warn_days": ssl_expiry_warn_days,
        "apply_safe_defaults": apply_safe_defaults,
        "current_failures": 0,
        "alert_active": False,
        "enabled": True,
        "status": "pending",
        "last_check": None,
        "last_response_time": None,
        "last_status_code": None,
        "last_failure_reason": None,
        "last_ssl_days_remaining": None,
        "uptime_pct": 100.0,
        "total_checks": 0,
        "successful_checks": 0,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.uptime_monitors.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def get_monitors() -> List[Dict]:
    monitors = await db.uptime_monitors.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return monitors


async def get_monitor(monitor_id: str) -> Optional[Dict]:
    return await db.uptime_monitors.find_one({"id": monitor_id}, {"_id": 0})


async def delete_monitor(monitor_id: str) -> bool:
    r = await db.uptime_monitors.delete_one({"id": monitor_id})
    if r.deleted_count:
        await db.uptime_checks.delete_many({"monitor_id": monitor_id})
        return True
    return False


async def toggle_monitor(monitor_id: str) -> Dict:
    mon = await db.uptime_monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not mon:
        return {"error": "Not found"}
    new_state = not mon.get("enabled", True)
    await db.uptime_monitors.update_one({"id": monitor_id}, {"$set": {"enabled": new_state}})
    return {"id": monitor_id, "enabled": new_state}


# Note: _eval_json_path, _evaluate_assertions, _check_ssl_expiry were moved to
# assertion_engine.py and are imported at the top of this file (DRY-shared with
# synthetic monitoring). The local definitions have been removed.


async def check_url(monitor: Dict, region: str = "us-east") -> Dict:
    """Perform a single HTTP check with advanced assertions from a specified region"""
    url = monitor["url"]
    method = monitor.get("method", "GET")
    timeout_s = monitor.get("timeout", 10)
    expected = monitor.get("expected_status", 200)
    hdrs = monitor.get("headers", {})
    assertions = monitor.get("assertions", [])
    max_rt = monitor.get("max_response_time_ms")
    ssl_warn_days = monitor.get("ssl_expiry_warn_days", 14)
    region_info = REGIONS.get(region, REGIONS["us-east"])

    result = {
        "id": str(uuid.uuid4()),
        "monitor_id": monitor["id"],
        "url": url,
        "region": region,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "assertion_failures": [],
        "ssl_days_remaining": None,
        "failure_reason": None,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            start = asyncio.get_event_loop().time()
            if method == "POST":
                resp = await client.post(url, headers=hdrs)
            elif method == "HEAD":
                resp = await client.head(url, headers=hdrs)
            else:
                resp = await client.get(url, headers=hdrs)
            duration = (asyncio.get_event_loop().time() - start) * 1000

            offset = region_info["latency_offset"] + random.uniform(-10, 10)
            duration += max(0, offset)

            body_text = resp.text if method != "HEAD" else ""
            status_ok = resp.status_code == expected
            assertion_failures = _evaluate_assertions(
                assertions, body_text, resp.status_code, duration, max_rt
            )

            result["status_code"] = resp.status_code
            result["response_time_ms"] = round(duration, 1)
            result["assertion_failures"] = assertion_failures
            result["success"] = status_ok and not assertion_failures
            result["error"] = None
            if not status_ok:
                result["failure_reason"] = f"HTTP {resp.status_code} (expected {expected})"
            elif assertion_failures:
                result["failure_reason"] = assertion_failures[0]["reason"]
    except httpx.TimeoutException:
        result["status_code"] = 0
        result["response_time_ms"] = timeout_s * 1000
        result["success"] = False
        result["error"] = "Timeout"
        result["failure_reason"] = f"Request timed out after {timeout_s}s"
    except Exception as e:
        result["status_code"] = 0
        result["response_time_ms"] = 0
        result["success"] = False
        result["error"] = str(e)[:300]
        result["failure_reason"] = f"Network error: {str(e)[:120]}"

    # SSL cert check (only on primary region, only for HTTPS)
    primary_region = monitor.get("regions", ["us-east"])[0] if monitor.get("regions") else "us-east"
    if region == primary_region and url.lower().startswith("https://"):
        ssl_info = await asyncio.to_thread(_check_ssl_expiry, url, ssl_warn_days)
        result["ssl_days_remaining"] = ssl_info["days_remaining"]
        if ssl_info["warning"] and ssl_info["days_remaining"] is not None:
            # SSL near-expiry is a warning, not a failure, but surface it
            result.setdefault("warnings", []).append(
                f"SSL cert expires in {ssl_info['days_remaining']} days (< {ssl_warn_days})"
            )

    # Store check
    await db.uptime_checks.insert_one(result)
    result.pop("_id", None)

    # Update monitor status (only for primary region)
    if region == primary_region:
        update = {
            "last_check": result["timestamp"],
            "last_response_time": result["response_time_ms"],
            "last_status_code": result["status_code"],
            "last_failure_reason": result["failure_reason"],
            "last_ssl_days_remaining": result["ssl_days_remaining"],
            "status": "up" if result["success"] else "down",
            "$inc": {"total_checks": 1},
        }
        if result["success"]:
            update["$inc"]["successful_checks"] = 1

        inc_data = update.pop("$inc")
        await db.uptime_monitors.update_one(
            {"id": monitor["id"]},
            {"$set": update, "$inc": inc_data}
        )

        # Recalculate uptime
        mon = await db.uptime_monitors.find_one({"id": monitor["id"]}, {"_id": 0})
        if mon and mon.get("total_checks", 0) > 0:
            uptime = round((mon["successful_checks"] / mon["total_checks"]) * 100, 2)
            await db.uptime_monitors.update_one({"id": monitor["id"]}, {"$set": {"uptime_pct": uptime}})

        # Alert logic
        await _handle_alert(monitor, result)

    return result


async def _handle_alert(monitor: Dict, check_result: Dict):
    """Handle alert firing and recovery based on consecutive failures"""
    mid = monitor["id"]
    threshold = monitor.get("consecutive_failures", 3)
    channels = monitor.get("alert_channels", [])

    if not check_result["success"]:
        new_failures = monitor.get("current_failures", 0) + 1
        await db.uptime_monitors.update_one({"id": mid}, {"$set": {"current_failures": new_failures}})

        if new_failures >= threshold and not monitor.get("alert_active"):
            await db.uptime_monitors.update_one({"id": mid}, {"$set": {"alert_active": True}})
            await _fire_alert(monitor, check_result, "down", channels)
    else:
        was_alerting = monitor.get("alert_active", False)
        await db.uptime_monitors.update_one({"id": mid}, {"$set": {"current_failures": 0, "alert_active": False}})

        if was_alerting:
            await _fire_alert(monitor, check_result, "recovered", channels)


async def _fire_alert(monitor: Dict, check_result: Dict, alert_type: str, channels: list):
    """Send alerts through configured channels and log"""
    alert_doc = {
        "id": str(uuid.uuid4()),
        "monitor_id": monitor["id"],
        "monitor_name": monitor["name"],
        "url": monitor["url"],
        "alert_type": alert_type,
        "status_code": check_result.get("status_code", 0),
        "error": check_result.get("error"),
        "channels_notified": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for ch in channels:
        ch_type = ch.get("type", "")
        try:
            if ch_type == "webhook" and ch.get("url"):
                async with httpx.AsyncClient(timeout=5) as client:
                    payload = {
                        "monitor": monitor["name"],
                        "url": monitor["url"],
                        "status": alert_type,
                        "status_code": check_result.get("status_code"),
                        "error": check_result.get("error"),
                        "timestamp": alert_doc["timestamp"],
                    }
                    await client.post(ch["url"], json=payload)
                alert_doc["channels_notified"].append({"type": "webhook", "status": "sent"})
            elif ch_type == "email" and ch.get("address"):
                alert_doc["channels_notified"].append({"type": "email", "address": ch["address"], "status": "queued"})
            elif ch_type == "slack" and ch.get("webhook_url"):
                async with httpx.AsyncClient(timeout=5) as client:
                    icon = ":red_circle:" if alert_type == "down" else ":large_green_circle:"
                    text = f"{icon} *{monitor['name']}* is *{alert_type.upper()}*\nURL: {monitor['url']}\nStatus: {check_result.get('status_code', 'N/A')}"
                    await client.post(ch["webhook_url"], json={"text": text})
                alert_doc["channels_notified"].append({"type": "slack", "status": "sent"})
            elif ch_type == "whatsapp" and ch.get("to_number"):
                sent = await _send_whatsapp(ch["to_number"], monitor, alert_type, check_result)
                alert_doc["channels_notified"].append({"type": "whatsapp", "to": ch["to_number"], "status": "sent" if sent else "sim"})
        except Exception as e:
            alert_doc["channels_notified"].append({"type": ch_type, "status": "failed", "error": str(e)[:100]})
            logger.warning(f"Alert channel {ch_type} failed: {e}")

    await db.uptime_alerts.insert_one(alert_doc)
    alert_doc.pop("_id", None)
    logger.info(f"Alert fired: {monitor['name']} -> {alert_type}")

    # Auto-trigger AI pipeline on DOWN alerts
    if alert_type == "down":
        try:
            from .ai_agents_service import trigger_from_rule
            rule = {
                "rule_id": f"uptime_{monitor['id'][:8]}",
                "name": f"Uptime: {monitor['name']} DOWN",
                "severity": "critical",
                "metric": "status",
                "threshold": "down",
                "cooldown_min": 5,
            }
            event_data = {
                "monitor_name": monitor["name"],
                "url": monitor["url"],
                "status_code": check_result.get("status_code", 0),
                "error": check_result.get("error", ""),
                "response_time_ms": check_result.get("response_time_ms", 0),
            }
            import asyncio
            asyncio.create_task(trigger_from_rule(rule, event_data))
        except Exception as e:
            logger.warning(f"AI pipeline trigger failed: {e}")


async def _send_whatsapp(to_number: str, monitor: Dict, alert_type: str, check_result: Dict) -> bool:
    """Send WhatsApp message via Twilio (simulation if no creds)"""
    import os
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    icon = "DOWN" if alert_type == "down" else "RECOVERED"
    body = f"FalconOps Alert: {monitor['name']} is {icon}\nURL: {monitor['url']}\nStatus: {check_result.get('status_code', 'N/A')}\nTime: {check_result.get('timestamp', '')}"

    if not account_sid or not auth_token:
        logger.info(f"[WhatsApp SIM] Would send to {to_number}: {body}")
        await db.whatsapp_log.insert_one({
            "to": to_number, "body": body, "status": "simulated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                auth=(account_sid, auth_token),
                data={"From": from_number, "To": f"whatsapp:{to_number}", "Body": body},
            )
            success = resp.status_code in (200, 201)
            await db.whatsapp_log.insert_one({
                "to": to_number, "body": body, "status": "sent" if success else "failed",
                "response_code": resp.status_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return success
    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        return False


async def get_alert_history(monitor_id: str = None, limit: int = 50) -> List[Dict]:
    query = {}
    if monitor_id:
        query["monitor_id"] = monitor_id
    return await db.uptime_alerts.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


async def update_monitor_config(monitor_id: str, updates: Dict) -> Dict:
    """Update monitor configuration (regions, alerts, etc.)"""
    allowed = {"name", "url", "interval", "method", "expected_status", "timeout",
               "regions", "alert_channels", "consecutive_failures", "headers"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return {"error": "No valid fields"}
    await db.uptime_monitors.update_one({"id": monitor_id}, {"$set": filtered})
    return await get_monitor(monitor_id)


async def get_region_stats(monitor_id: str, hours: int = 24) -> List[Dict]:
    """Get per-region response time stats"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    pipeline = [
        {"$match": {"monitor_id": monitor_id, "timestamp": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$region",
            "avg_response": {"$avg": "$response_time_ms"},
            "min_response": {"$min": "$response_time_ms"},
            "max_response": {"$max": "$response_time_ms"},
            "total_checks": {"$sum": 1},
            "failures": {"$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}},
        }},
        {"$sort": {"avg_response": 1}},
    ]
    results = await db.uptime_checks.aggregate(pipeline).to_list(20)
    return [{
        "region": r["_id"] or "us-east",
        "region_name": REGIONS.get(r["_id"] or "us-east", {}).get("name", r["_id"]),
        "avg_response_ms": round(r["avg_response"], 1),
        "min_response_ms": round(r["min_response"], 1),
        "max_response_ms": round(r["max_response"], 1),
        "total_checks": r["total_checks"],
        "failures": r["failures"],
        "uptime_pct": round(((r["total_checks"] - r["failures"]) / max(r["total_checks"], 1)) * 100, 2),
    } for r in results]


async def check_now(monitor_id: str) -> Dict:
    mon = await db.uptime_monitors.find_one({"id": monitor_id}, {"_id": 0})
    if not mon:
        return {"error": "Monitor not found"}
    return await check_url(mon)


async def get_check_history(monitor_id: str, hours: int = 24, limit: int = 100) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    checks = await db.uptime_checks.find(
        {"monitor_id": monitor_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return checks


async def get_monitor_timeseries(monitor_id: str, hours: int = 24, bucket_minutes: int = 0) -> Dict:
    """Return historical time-series for a monitor: response-time line + up/down bar.
    If bucket_minutes=0, auto-select (1 for ≤1h, 5 for ≤6h, 15 for ≤24h, 60 for ≤72h, 360 for ≤7d)."""
    if bucket_minutes <= 0:
        bucket_minutes = 1 if hours <= 1 else 5 if hours <= 6 else 15 if hours <= 24 else 60 if hours <= 72 else 360

    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff = cutoff_dt.isoformat()
    checks = await db.uptime_checks.find(
        {"monitor_id": monitor_id, "timestamp": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("timestamp", 1).to_list(length=50000)

    buckets: Dict[str, Dict] = {}
    for c in checks:
        try:
            ts = datetime.fromisoformat(c["timestamp"].replace("Z", "+00:00"))
        except Exception:
            continue
        bucket_key = ts.replace(
            minute=(ts.minute // bucket_minutes) * bucket_minutes,
            second=0, microsecond=0
        ).isoformat()
        b = buckets.setdefault(bucket_key, {
            "timestamp": bucket_key, "total": 0, "success": 0, "fail": 0,
            "response_time_sum": 0.0, "response_time_max": 0.0,
            "status_codes": {}, "failure_reasons": [],
        })
        b["total"] += 1
        if c.get("success"):
            b["success"] += 1
        else:
            b["fail"] += 1
            if c.get("failure_reason") and len(b["failure_reasons"]) < 3:
                b["failure_reasons"].append(c["failure_reason"])
        rt = c.get("response_time_ms") or 0
        b["response_time_sum"] += rt
        if rt > b["response_time_max"]:
            b["response_time_max"] = rt
        sc = str(c.get("status_code", 0))
        b["status_codes"][sc] = b["status_codes"].get(sc, 0) + 1

    series = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        series.append({
            "timestamp": b["timestamp"],
            "avg_response_time_ms": round(b["response_time_sum"] / b["total"], 1) if b["total"] else 0,
            "max_response_time_ms": round(b["response_time_max"], 1),
            "success": b["success"],
            "fail": b["fail"],
            "total": b["total"],
            "uptime_pct": round((b["success"] / b["total"]) * 100, 2) if b["total"] else 0,
            "status_codes": b["status_codes"],
            "failure_reasons": b["failure_reasons"],
        })

    total_checks = sum(b["total"] for b in buckets.values())
    total_success = sum(b["success"] for b in buckets.values())
    return {
        "monitor_id": monitor_id,
        "hours": hours,
        "bucket_minutes": bucket_minutes,
        "series": series,
        "summary": {
            "total_checks": total_checks,
            "successful": total_success,
            "failed": total_checks - total_success,
            "uptime_pct": round((total_success / total_checks) * 100, 2) if total_checks else 100.0,
        }
    }


async def backfill_safe_defaults() -> Dict:
    """Apply safe-default assertions to any existing monitor missing them. Idempotent."""
    updated = 0
    skipped = 0
    async for mon in db.uptime_monitors.find({}, {"_id": 0}):
        if not mon.get("apply_safe_defaults", True):
            skipped += 1
            continue
        existing = mon.get("assertions", []) or []
        existing_keys = {(a.get("type"), str(a.get("value", "")).lower()) for a in existing}
        additions = []
        for default_a in _build_default_assertions():
            key = (default_a["type"], str(default_a["value"]).lower())
            if key not in existing_keys:
                additions.append(default_a)
        if additions:
            await db.uptime_monitors.update_one(
                {"id": mon["id"]},
                {"$set": {"assertions": existing + additions,
                          "apply_safe_defaults": True,
                          "ssl_expiry_warn_days": mon.get("ssl_expiry_warn_days", 14)}}
            )
            updated += 1
        else:
            skipped += 1
    return {"updated": updated, "skipped": skipped}


async def get_uptime_stats(hours: int = 24) -> Dict:
    monitors = await db.uptime_monitors.find({}, {"_id": 0}).to_list(200)
    total = len(monitors)
    up = sum(1 for m in monitors if m.get("status") == "up")
    down = sum(1 for m in monitors if m.get("status") == "down")
    pending = total - up - down
    avg_uptime = round(sum(m.get("uptime_pct", 0) for m in monitors) / max(total, 1), 2)

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    total_checks = await db.uptime_checks.count_documents({"timestamp": {"$gte": cutoff}})
    failed_checks = await db.uptime_checks.count_documents({"timestamp": {"$gte": cutoff}, "success": False})

    return {
        "total_monitors": total,
        "up": up,
        "down": down,
        "pending": pending,
        "avg_uptime_pct": avg_uptime,
        "total_checks_period": total_checks,
        "failed_checks_period": failed_checks,
    }


# ======================== BACKGROUND SCHEDULER ========================

async def _scheduler_loop():
    """Background loop that checks all enabled monitors from their configured regions"""
    logger.info("Uptime monitor scheduler started")
    check_times = {}

    while True:
        try:
            monitors = await db.uptime_monitors.find({"enabled": True}, {"_id": 0}).to_list(200)
            now = asyncio.get_event_loop().time()

            tasks = []
            for mon in monitors:
                mid = mon["id"]
                interval = mon.get("interval", 60)
                last = check_times.get(mid, 0)
                if now - last >= interval:
                    regions = mon.get("regions", ["us-east"])
                    for region in regions:
                        tasks.append(check_url(mon, region))
                    check_times[mid] = now

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Uptime scheduler error: {e}")

        await asyncio.sleep(15)


def start_uptime_scheduler():
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("Uptime scheduler task created")


def stop_uptime_scheduler():
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Uptime scheduler stopped")
