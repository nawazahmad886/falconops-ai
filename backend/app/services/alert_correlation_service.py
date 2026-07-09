"""
FalconOps AI - Advanced NLP Alert Correlation Engine
Groups related alerts by text similarity, keyword overlap, service, and time window
"""
import uuid
import logging
import re
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from typing import Dict, List

from ..core.database import db

logger = logging.getLogger(__name__)

# ======================== CONFIG ========================

DEFAULT_CONFIG = {
    "correlation_window_min": 30,
    "similarity_threshold": 0.35,
    "max_group_size": 20,
    "enabled": True,
}


async def get_correlation_config() -> Dict:
    doc = await db.correlation_config.find_one({"key": "config"}, {"_id": 0})
    return doc.get("value", DEFAULT_CONFIG) if doc else DEFAULT_CONFIG


async def update_correlation_config(updates: Dict) -> Dict:
    cfg = await get_correlation_config()
    cfg.update({k: v for k, v in updates.items() if k in DEFAULT_CONFIG})
    await db.correlation_config.update_one(
        {"key": "config"}, {"$set": {"value": cfg}}, upsert=True
    )
    return cfg


# ======================== KEYWORD EXTRACTION ========================

STOP_WORDS = {"the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
              "have", "has", "had", "do", "does", "did", "will", "would", "could",
              "should", "may", "might", "shall", "can", "to", "of", "in", "for",
              "on", "with", "at", "by", "from", "as", "into", "through", "during",
              "and", "or", "but", "not", "no", "this", "that", "it", "its"}


def extract_keywords(text: str) -> set:
    words = re.findall(r'[a-zA-Z0-9_.-]+', text.lower())
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS}


def keyword_overlap(kw1: set, kw2: set) -> float:
    if not kw1 or not kw2:
        return 0.0
    intersection = kw1 & kw2
    return len(intersection) / min(len(kw1), len(kw2))


# ======================== CORRELATION ========================

async def correlate_alerts(hours: int = 24) -> Dict:
    cfg = await get_correlation_config()
    window_min = cfg["correlation_window_min"]
    threshold = cfg["similarity_threshold"]

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    # Gather alerts from multiple sources
    uptime_alerts = await db.uptime_alerts.find(
        {"timestamp": {"$gte": cutoff}}, {"_id": 0}
    ).sort("timestamp", -1).limit(200).to_list(200)

    security_threats = await db.security_threats.find(
        {"timestamp": {"$gte": cutoff}}, {"_id": 0}
    ).sort("timestamp", -1).limit(100).to_list(100)

    # Normalize all alerts into common format
    alerts = []
    for a in uptime_alerts:
        alerts.append({
            "id": a.get("id", str(uuid.uuid4())[:8]),
            "source": "uptime",
            "service": a.get("monitor_name", ""),
            "message": f"{a.get('monitor_name', '')} {a.get('alert_type', '')} - {a.get('url', '')}",
            "severity": "critical" if a.get("alert_type") == "down" else "info",
            "timestamp": a.get("timestamp", ""),
            "raw": a,
        })
    for t in security_threats:
        alerts.append({
            "id": t.get("id", str(uuid.uuid4())[:8]),
            "source": "security",
            "service": t.get("source", ""),
            "message": t.get("message", ""),
            "severity": t.get("severity", "warning"),
            "timestamp": t.get("timestamp", ""),
            "raw": t,
        })

    # Pre-compute keywords
    for a in alerts:
        a["keywords"] = extract_keywords(a["message"] + " " + a["service"])

    # Group by similarity
    groups = []
    used = set()

    for i, alert in enumerate(alerts):
        if i in used:
            continue
        group = {
            "id": str(uuid.uuid4())[:12],
            "primary": alert,
            "correlated": [],
            "severity": alert["severity"],
            "services": {alert["service"]},
            "sources": {alert["source"]},
            "keywords": set(alert["keywords"]),
        }
        used.add(i)

        for j, other in enumerate(alerts):
            if j in used or j == i:
                continue

            # Check time window
            try:
                t1 = datetime.fromisoformat(alert["timestamp"].replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(other["timestamp"].replace("Z", "+00:00"))
                if abs((t1 - t2).total_seconds()) > window_min * 60:
                    continue
            except Exception:
                pass

            # Compute similarity
            text_sim = SequenceMatcher(None, alert["message"].lower(), other["message"].lower()).ratio()
            kw_sim = keyword_overlap(alert["keywords"], other["keywords"])
            service_match = 1.0 if alert["service"] == other["service"] and alert["service"] else 0.0
            combined = (text_sim * 0.4) + (kw_sim * 0.4) + (service_match * 0.2)

            if combined >= threshold:
                group["correlated"].append({**other, "similarity": round(combined * 100, 1)})
                group["services"].add(other["service"])
                group["sources"].add(other["source"])
                group["keywords"] |= other["keywords"]
                if other["severity"] == "critical":
                    group["severity"] = "critical"
                used.add(j)

                if len(group["correlated"]) >= cfg["max_group_size"]:
                    break

        # Finalize group
        group["alert_count"] = 1 + len(group["correlated"])
        group["services"] = list(group["services"])
        group["sources"] = list(group["sources"])
        group["top_keywords"] = sorted(group["keywords"], key=lambda k: sum(1 for a in [alert] + group["correlated"] if k in a.get("keywords", set())), reverse=True)[:10]
        group["keywords"] = list(group["keywords"])[:20]
        del group["primary"]["keywords"]
        del group["primary"]["raw"]
        for c in group["correlated"]:
            c.pop("keywords", None)
            c.pop("raw", None)

        groups.append(group)

    # Stats
    total_alerts = len(alerts)
    total_groups = len(groups)
    noise_reduction = round((1 - total_groups / max(total_alerts, 1)) * 100, 1) if total_alerts > 0 else 0

    return {
        "total_alerts": total_alerts,
        "correlation_groups": total_groups,
        "noise_reduction_pct": noise_reduction,
        "groups": groups[:30],
        "config": cfg,
    }


async def get_correlation_stats(hours: int = 24) -> Dict:
    result = await correlate_alerts(hours)
    return {
        "total_alerts": result["total_alerts"],
        "groups": result["correlation_groups"],
        "noise_reduction_pct": result["noise_reduction_pct"],
        "config": result["config"],
    }
