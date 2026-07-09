"""
FalconOps AI - SOC Event Ingestion & Correlation Engine
Universal event ingestion, normalization, auto-correlation, AI trigger, WebSocket push
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

# ======================== NORMALIZATION ========================

def normalize_event(raw: Dict) -> Dict:
    """Normalize any external event into standard SOC format"""
    return {
        "event_id": str(uuid.uuid4()),
        "source": raw.get("source", "api"),
        "service": raw.get("service", raw.get("host", "unknown")),
        "severity": raw.get("severity", "info"),
        "category": raw.get("category", raw.get("type", "generic")),
        "message": raw.get("message", raw.get("description", "")),
        "host": raw.get("host", raw.get("hostname", "")),
        "ip": raw.get("ip", raw.get("source_ip", "")),
        "user": raw.get("user", raw.get("username", "")),
        "action": raw.get("action", ""),
        "metadata": {k: v for k, v in raw.items() if k not in ("source", "service", "severity", "message", "host", "ip", "user", "action", "category")},
        "status": "new",
        "correlated": False,
        "incident_id": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ======================== INGESTION ========================

async def ingest_event(raw: Dict) -> Dict:
    """Ingest, normalize, store, correlate, and push"""
    event = normalize_event(raw)
    await db.soc_events.insert_one(event)
    event.pop("_id", None)

    # Check correlation
    incident = await correlate_event(event)

    # Push to WebSocket
    try:
        from .soc_live_feed import soc_manager
        await soc_manager.broadcast({
            "type": "security_event",
            "data": event,
        })
    except Exception as e:
        logger.debug(f"WS broadcast skip: {e}")

    return {
        "status": "ingested",
        "event_id": event["event_id"],
        "severity": event["severity"],
        "correlated": event["correlated"],
        "incident_id": incident.get("incident_id") if incident else None,
    }


async def ingest_batch(events: List[Dict]) -> Dict:
    """Ingest multiple events"""
    results = []
    for raw in events:
        r = await ingest_event(raw)
        results.append(r)
    return {
        "ingested": len(results),
        "incidents_created": sum(1 for r in results if r.get("incident_id")),
        "results": results,
    }


# ======================== CORRELATION ========================

async def correlate_event(event: Dict) -> Optional[Dict]:
    """Auto-correlate: group by service + severity within time window"""
    config = await get_ingestion_config()
    window_min = config.get("correlation_window_min", 10)
    threshold = config.get("incident_threshold", 3)

    if not config.get("auto_correlate", True):
        return None

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_min)).isoformat()

    related = await db.soc_events.count_documents({
        "service": event["service"],
        "severity": event["severity"],
        "timestamp": {"$gte": cutoff},
        "correlated": False,
    })

    if related >= threshold:
        incident = await create_incident(event, related)

        # Mark events as correlated
        await db.soc_events.update_many(
            {"service": event["service"], "severity": event["severity"], "timestamp": {"$gte": cutoff}, "correlated": False},
            {"$set": {"correlated": True, "incident_id": incident["incident_id"]}}
        )

        # Auto-trigger AI if enabled
        if config.get("auto_ai_trigger", True):
            asyncio.create_task(_trigger_ai_on_incident(incident))

        return incident
    return None


async def create_incident(trigger_event: Dict, event_count: int) -> Dict:
    """Create a SOC incident from correlated events"""
    incident = {
        "incident_id": str(uuid.uuid4())[:12],
        "title": f"{trigger_event['severity'].upper()}: {trigger_event['service']} - {trigger_event['message'][:80]}",
        "service": trigger_event["service"],
        "severity": trigger_event["severity"],
        "source": trigger_event["source"],
        "event_count": event_count,
        "status": "open",
        "confidence": min(99, 50 + event_count * 10),
        "ai_analysis": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.soc_incidents.insert_one(incident)
    incident.pop("_id", None)

    # Push incident to WebSocket
    try:
        from .soc_live_feed import soc_manager
        await soc_manager.broadcast({"type": "incident", "data": incident})
    except Exception:
        pass

    logger.info(f"SOC Incident created: {incident['incident_id']} ({event_count} events)")
    return incident


async def _trigger_ai_on_incident(incident: Dict):
    """Auto-run AI agents on new incidents"""
    try:
        from .ai_agents_service import trigger_from_rule
        rule = {
            "rule_id": f"soc_{incident['incident_id'][:8]}",
            "name": f"SOC: {incident['title'][:50]}",
            "severity": incident["severity"],
            "metric": "soc_incident",
            "threshold": incident["event_count"],
            "cooldown_min": 2,
        }
        await trigger_from_rule(rule, {
            "incident_id": incident["incident_id"],
            "title": incident["title"],
            "service": incident["service"],
            "event_count": incident["event_count"],
            "confidence": incident["confidence"],
        })
    except Exception as e:
        logger.error(f"AI trigger on incident failed: {e}")


# ======================== QUERIES ========================

async def get_recent_events(limit: int = 50, source: str = None, severity: str = None) -> List[Dict]:
    query = {}
    if source:
        query["source"] = source
    if severity:
        query["severity"] = severity
    return await db.soc_events.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


async def get_incidents(status: str = None, limit: int = 20) -> List[Dict]:
    query = {}
    if status:
        query["status"] = status
    return await db.soc_incidents.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


async def get_ingestion_stats() -> Dict:
    total_events = await db.soc_events.count_documents({})
    last_hour = await db.soc_events.count_documents({
        "timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}
    })
    total_incidents = await db.soc_incidents.count_documents({})
    open_incidents = await db.soc_incidents.count_documents({"status": "open"})

    by_severity = {}
    for sev in ["critical", "high", "warning", "info"]:
        by_severity[sev] = await db.soc_events.count_documents({"severity": sev})

    by_source = await db.soc_events.aggregate([
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 10},
    ]).to_list(10)

    return {
        "total_events": total_events,
        "events_last_hour": last_hour,
        "total_incidents": total_incidents,
        "open_incidents": open_incidents,
        "by_severity": by_severity,
        "by_source": [{"source": s["_id"], "count": s["count"]} for s in by_source],
    }


# ======================== CONFIG ========================

DEFAULT_INGESTION_CONFIG = {
    "auto_correlate": True,
    "auto_ai_trigger": True,
    "correlation_window_min": 10,
    "incident_threshold": 3,
    "accepted_sources": ["api", "aws_cloudtrail", "aws_vpc", "syslog", "webhook", "agent"],
}


async def get_ingestion_config() -> Dict:
    doc = await db.soc_ingestion_config.find_one({"key": "config"}, {"_id": 0})
    return doc.get("value", DEFAULT_INGESTION_CONFIG) if doc else DEFAULT_INGESTION_CONFIG


async def update_ingestion_config(updates: Dict) -> Dict:
    cfg = await get_ingestion_config()
    cfg.update({k: v for k, v in updates.items() if k in DEFAULT_INGESTION_CONFIG})
    await db.soc_ingestion_config.update_one({"key": "config"}, {"$set": {"value": cfg}}, upsert=True)
    return cfg
