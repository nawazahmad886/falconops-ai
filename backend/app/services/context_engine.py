"""
FalconOps AI — Context Engine
Enriches an inbound event/incident with the surrounding context an AI agent needs:
- Last N events for the same service (history)
- Dependency topology (upstream/downstream services)
- Runbook lookup by alert name
- Severity baseline (frequency of this alert in last 7d)

The Context Engine is the foundation of the autonomous AI pipeline — every
agent (SRE, Security, Cost, Prevention) consumes context-enriched events.
"""
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)


async def get_history_for_service(service: str, limit: int = 50, hours: int = 168) -> List[Dict]:
    """Fetch the last N events for a given service across the last `hours` window."""
    if not service:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    cursor = db.event_data.aggregate([
        {"$unwind": "$events"},
        {"$match": {
            "events.service": {"$regex": f"^{re.escape(service)}$", "$options": "i"},
            "events.timestamp": {"$gte": cutoff},
        }},
        {"$replaceRoot": {"newRoot": "$events"}},
        {"$sort": {"timestamp": -1}},
        {"$limit": limit},
    ])
    out = []
    async for ev in cursor:
        ev.pop("_id", None)
        out.append(ev)
    return out


async def get_topology(service: str) -> Dict:
    """Return dependency map for a service: {upstream: [...], downstream: [...]}."""
    if not service:
        return {"upstream": [], "downstream": []}
    doc = await db.service_topology.find_one({"service": service}, {"_id": 0})
    if doc:
        return {
            "upstream": doc.get("upstream", []),
            "downstream": doc.get("downstream", []),
            "tier": doc.get("tier"),
            "owner": doc.get("owner"),
        }
    # Fall back to inferring from existing service_map / monitors collection
    upstream: List[str] = []
    downstream: List[str] = []
    try:
        async for m in db.service_dependencies.find({"$or": [{"service": service}, {"depends_on": service}]}, {"_id": 0}):
            if m.get("service") == service:
                upstream.extend(m.get("depends_on", []) if isinstance(m.get("depends_on"), list) else [])
            elif service in (m.get("depends_on") or []):
                downstream.append(m.get("service"))
    except Exception:
        pass
    return {"upstream": list(dict.fromkeys(upstream))[:10],
            "downstream": list(dict.fromkeys(downstream))[:10],
            "tier": None, "owner": None}


async def get_runbook(alert: str) -> Optional[Dict]:
    """Look up an alert-name-keyed runbook hint (case-insensitive). Returns {steps, links, owner}.
    Stored in db.alert_runbook_hints — a separate collection from db.runbooks (the
    structured, uuid-keyed workflow-automation entity runbooks.py/runbook_engine.py
    manage). The two used to share db.runbooks despite incompatible schemas
    (this one has no id/name/service/steps-as-dicts), which crashed
    GET /api/runbooks via Pydantic's RunbookResponse(**doc) construction."""
    if not alert:
        return None
    doc = await db.alert_runbook_hints.find_one(
        {"$or": [
            {"alert_name": {"$regex": f"^{re.escape(alert)}$", "$options": "i"}},
            {"matches": {"$regex": re.escape(alert), "$options": "i"}},
        ]},
        {"_id": 0},
    )
    return doc


async def get_severity_baseline(service: str, alert: str, hours: int = 168) -> Dict:
    """How often has this (service, alert) tuple fired in the last 7 days?"""
    if not service or not alert:
        return {"count": 0, "rate_per_day": 0.0, "first_seen": None, "is_recurring": False}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    pipeline = [
        {"$unwind": "$events"},
        {"$match": {
            "events.service": {"$regex": f"^{re.escape(service)}$", "$options": "i"},
            "events.alert": {"$regex": f"^{re.escape(alert)}$", "$options": "i"},
            "events.timestamp": {"$gte": cutoff},
        }},
        {"$count": "n"},
    ]
    n = 0
    async for r in db.event_data.aggregate(pipeline):
        n = r.get("n", 0)
    return {
        "count": n,
        "rate_per_day": round(n / (hours / 24), 2) if hours else 0.0,
        "is_recurring": n >= 5,
    }


async def enrich(event: Dict) -> Dict:
    """Main entry — return event + history + topology + runbook + baseline."""
    if not event or not isinstance(event, dict):
        return {"event": event, "history": [], "topology": {}, "runbook": None, "baseline": {}}

    service = (event.get("service") or "").strip()
    alert = (event.get("alert") or event.get("alert_description") or event.get("description") or "").strip()

    history = await get_history_for_service(service)
    topology = await get_topology(service)
    runbook = await get_runbook(alert) if alert else None
    baseline = await get_severity_baseline(service, alert) if service and alert else {}

    return {
        "event": event,
        "service": service,
        "alert": alert,
        "history_count": len(history),
        "history": history[:10],  # keep response light; agents can request more
        "topology": topology,
        "runbook": runbook,
        "baseline": baseline,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


async def upsert_topology(service: str, upstream: List[str], downstream: List[str],
                          tier: Optional[str] = None, owner: Optional[str] = None) -> Dict:
    doc = {
        "service": service,
        "upstream": list(dict.fromkeys(upstream or [])),
        "downstream": list(dict.fromkeys(downstream or [])),
        "tier": tier,
        "owner": owner,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.service_topology.update_one({"service": service}, {"$set": doc}, upsert=True)
    return doc


async def upsert_runbook(alert_name: str, steps: List[str], links: Optional[List[Dict]] = None,
                        owner: Optional[str] = None, matches: Optional[List[str]] = None) -> Dict:
    doc = {
        "alert_name": alert_name,
        "steps": steps or [],
        "links": links or [],
        "owner": owner,
        "matches": matches or [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.alert_runbook_hints.update_one({"alert_name": alert_name}, {"$set": doc}, upsert=True)
    return doc


async def migrate_alert_runbook_hints() -> Dict:
    """One-time, idempotent: move alert-name-keyed runbook hint docs (see get_runbook/
    upsert_runbook above) out of db.runbooks into their own db.alert_runbook_hints
    collection. Safe to run on every boot."""
    docs = await db.runbooks.find({"alert_name": {"$exists": True}}, {"_id": 0}).to_list(10000)
    if not docs:
        return {"migrated": 0}
    await db.alert_runbook_hints.insert_many(docs)
    await db.runbooks.delete_many({"alert_name": {"$exists": True}})
    return {"migrated": len(docs)}
