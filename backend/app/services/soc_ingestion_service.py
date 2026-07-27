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
        "assigned_to": None,
        "assignment_group": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ======================== INGESTION ========================

async def ingest_event(raw: Dict) -> Dict:
    """Ingest, normalize, store, correlate, and push"""
    event = normalize_event(raw)
    await db.soc_events.insert_one(event)
    event.pop("_id", None)

    # Best-effort secret-exposure scan — never allowed to affect ingestion itself.
    try:
        await _scan_event_for_secrets(event, raw)
    except Exception as e:
        logger.debug(f"Secret scan skipped: {e}")

    # 'Event trigger' workflows — best-effort, never allowed to affect ingestion itself.
    try:
        from . import workflow_trigger_service
        asyncio.create_task(workflow_trigger_service.evaluate_event_triggers(event))
    except Exception as e:
        logger.debug(f"Event trigger evaluation skipped: {e}")

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

    try:
        from .problems_broadcaster import broadcast_problem_event
        await broadcast_problem_event(
            event_type="problem.created", problem_id=f"se:{event['event_id']}",
            severity=event.get("severity"), status=event.get("status"),
            title=event.get("message"), source="soc_event",
        )
    except Exception:
        pass

    return {
        "status": "ingested",
        "event_id": event["event_id"],
        "severity": event["severity"],
        "correlated": event["correlated"],
        "incident_id": incident.get("incident_id") if incident else None,
    }


async def _scan_event_for_secrets(event: Dict, raw: Dict) -> None:
    """Scan an ingested event's text for leaked secrets. On a hit, raise a real
    security_threat (reusing the existing threat/dispatch pipeline in security_service.py
    / connector_dispatcher.py, not a parallel one) with masked values only."""
    from .secret_scanner_service import scan_text_for_secrets
    from . import mitre_mapping_service

    text = f"{event.get('message', '')} {raw.get('raw', '')}".strip()
    findings = scan_text_for_secrets(text)
    if not findings:
        return

    mitre = mitre_mapping_service.classify_mitre_primary("secret exposure leaked credential exposed api key") or {}
    threat = {
        "id": str(uuid.uuid4()),
        "type": "secret_exposure",
        "severity": "critical",
        "source_ip": event.get("ip", "unknown"),
        "user": event.get("user", "unknown"),
        "host": event.get("host", ""),
        "message": f"Potential secret exposure in ingested event from '{event.get('source')}': "
                   f"{', '.join(f['type'] for f in findings[:3])}",
        "findings": findings[:10],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "mitre_tactic": mitre.get("mitre_tactic", "Credential Access"),
        "mitre_technique": mitre.get("mitre_technique", "T1552 - Unsecured Credentials"),
    }
    await db.security_threats.insert_one(threat)
    try:
        from .connector_dispatcher import dispatch_threat
        await dispatch_threat(threat)
    except Exception as e:
        logger.warning(f"Secret-exposure threat dispatch skipped: {e}")


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
        "assigned_to": None,
        "assignment_group": None,
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

    try:
        from .problems_broadcaster import broadcast_problem_event
        asyncio.create_task(broadcast_problem_event(
            event_type="problem.created", problem_id=f"si:{incident['incident_id']}",
            severity=incident.get("severity"), status=incident.get("status"),
            title=incident.get("title"), source="soc_incident",
        ))
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


# ======================== LIFECYCLE ACTIONS (Problems console) ========================
# soc_events/soc_incidents had no acknowledge/resolve/close/assign path at all before
# this — event.status was always "new", incident.status was always "open". These are
# genuinely new lifecycle transitions, not a reuse of existing logic. Confirmed safe:
# no other code path reads/depends on those values staying fixed.

async def _broadcast_soc_event(prefix: str, raw_id: str, doc: Dict, event_type: str, source: str):
    try:
        from .problems_broadcaster import broadcast_problem_event
        await broadcast_problem_event(
            event_type=event_type, problem_id=f"{prefix}:{raw_id}",
            severity=doc.get("severity"), status=doc.get("status"),
            title=doc.get("message") or doc.get("title"), source=source,
        )
    except Exception:
        pass


async def acknowledge_event(event_id: str, user_email: str) -> Optional[Dict]:
    result = await db.soc_events.find_one_and_update(
        {"event_id": event_id, "status": "new"},
        {"$set": {"status": "acknowledged", "acknowledged_by": user_email,
                   "acknowledged_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True,
    )
    if result:
        clean = {k: v for k, v in result.items() if k != "_id"}
        asyncio.create_task(_broadcast_soc_event("se", event_id, clean, "problem.updated", "soc_event"))
        return clean
    return None


async def resolve_event(event_id: str, user_email: str) -> Optional[Dict]:
    result = await db.soc_events.find_one_and_update(
        {"event_id": event_id, "status": {"$in": ["new", "acknowledged"]}},
        {"$set": {"status": "resolved", "resolved_by": user_email,
                   "resolved_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True,
    )
    if result:
        clean = {k: v for k, v in result.items() if k != "_id"}
        asyncio.create_task(_broadcast_soc_event("se", event_id, clean, "problem.updated", "soc_event"))
        return clean
    return None


async def close_event(event_id: str, user_email: str) -> Optional[Dict]:
    result = await db.soc_events.find_one_and_update(
        {"event_id": event_id, "status": "resolved"},
        {"$set": {"status": "closed", "closed_by": user_email,
                   "closed_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True,
    )
    if result:
        clean = {k: v for k, v in result.items() if k != "_id"}
        asyncio.create_task(_broadcast_soc_event("se", event_id, clean, "problem.updated", "soc_event"))
        return clean
    return None


async def assign_event(event_id: str, assigned_to: Optional[str], assignment_group: Optional[str]) -> Optional[Dict]:
    result = await db.soc_events.find_one_and_update(
        {"event_id": event_id},
        {"$set": {"assigned_to": assigned_to, "assignment_group": assignment_group}},
        return_document=True,
    )
    if result:
        clean = {k: v for k, v in result.items() if k != "_id"}
        asyncio.create_task(_broadcast_soc_event("se", event_id, clean, "problem.assigned", "soc_event"))
        return clean
    return None


async def acknowledge_soc_incident(incident_id: str, user_email: str) -> Optional[Dict]:
    result = await db.soc_incidents.find_one_and_update(
        {"incident_id": incident_id, "status": "open"},
        {"$set": {"status": "acknowledged", "acknowledged_by": user_email,
                   "acknowledged_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True,
    )
    if result:
        clean = {k: v for k, v in result.items() if k != "_id"}
        asyncio.create_task(_broadcast_soc_event("si", incident_id, clean, "problem.updated", "soc_incident"))
        return clean
    return None


async def resolve_soc_incident(incident_id: str, user_email: str) -> Optional[Dict]:
    result = await db.soc_incidents.find_one_and_update(
        {"incident_id": incident_id, "status": {"$in": ["open", "acknowledged"]}},
        {"$set": {"status": "resolved", "resolved_by": user_email,
                   "resolved_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True,
    )
    if result:
        clean = {k: v for k, v in result.items() if k != "_id"}
        asyncio.create_task(_broadcast_soc_event("si", incident_id, clean, "problem.updated", "soc_incident"))
        return clean
    return None


async def close_soc_incident(incident_id: str, user_email: str) -> Optional[Dict]:
    result = await db.soc_incidents.find_one_and_update(
        {"incident_id": incident_id, "status": "resolved"},
        {"$set": {"status": "closed", "closed_by": user_email,
                   "closed_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True,
    )
    if result:
        clean = {k: v for k, v in result.items() if k != "_id"}
        asyncio.create_task(_broadcast_soc_event("si", incident_id, clean, "problem.updated", "soc_incident"))
        return clean
    return None


async def assign_soc_incident(incident_id: str, assigned_to: Optional[str], assignment_group: Optional[str]) -> Optional[Dict]:
    result = await db.soc_incidents.find_one_and_update(
        {"incident_id": incident_id},
        {"$set": {"assigned_to": assigned_to, "assignment_group": assignment_group}},
        return_document=True,
    )
    if result:
        clean = {k: v for k, v in result.items() if k != "_id"}
        asyncio.create_task(_broadcast_soc_event("si", incident_id, clean, "problem.assigned", "soc_incident"))
        return clean
    return None


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
    # Any source name is accepted at ingest_event()/normalize_event() today (unknown
    # fields already fall through into `metadata`) — this list is descriptive/UI-facing,
    # not an enforced allowlist. Includes the generic pull-source mechanism below so a
    # future Splunk/Elastic/Datadog connector can plug in via poll_generic_source()
    # without inventing a parallel ingestion path.
    "accepted_sources": ["api", "aws_cloudtrail", "aws_vpc", "syslog", "webhook", "agent", "generic_pull"],
}


async def get_ingestion_config() -> Dict:
    doc = await db.soc_ingestion_config.find_one({"key": "config"}, {"_id": 0})
    return doc.get("value", DEFAULT_INGESTION_CONFIG) if doc else DEFAULT_INGESTION_CONFIG


async def update_ingestion_config(updates: Dict) -> Dict:
    cfg = await get_ingestion_config()
    cfg.update({k: v for k, v in updates.items() if k in DEFAULT_INGESTION_CONFIG})
    await db.soc_ingestion_config.update_one({"key": "config"}, {"$set": {"value": cfg}}, upsert=True)
    return cfg


# ======================== GENERIC PULL-SOURCE FRAMEWORK ========================
# The real, generic mechanism a future vendor connector (Splunk/Elastic/Datadog/etc.)
# would plug into by supplying its own url/auth_header/field_mapping — no vendor-specific
# code is written here. Feeds straight into ingest_batch(), not a parallel pipeline.

async def register_ingestion_source(config: Dict) -> Dict:
    """Register a generic HTTP pull source. config: {name, url, method, auth_header,
    poll_interval_seconds, field_mapping, enabled}. field_mapping maps this source's
    response field names onto normalize_event()'s expected keys (service/severity/
    message/host/ip/user/action/category)."""
    doc = {
        "id": str(uuid.uuid4()),
        "name": config.get("name", "unnamed source"),
        "url": config["url"],
        "method": config.get("method", "GET").upper(),
        "auth_header": config.get("auth_header"),
        "poll_interval_seconds": max(30, int(config.get("poll_interval_seconds", 300))),
        "field_mapping": config.get("field_mapping", {}),
        "enabled": config.get("enabled", True),
        "last_polled_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ingestion_sources.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_ingestion_sources() -> List[Dict]:
    return await db.ingestion_sources.find({}, {"_id": 0}).to_list(100)


async def delete_ingestion_source(source_id: str) -> bool:
    result = await db.ingestion_sources.delete_one({"id": source_id})
    return result.deleted_count > 0


def _map_response_items(items: List[Dict], field_mapping: Dict, source_name: str) -> List[Dict]:
    mapped = []
    for item in items:
        raw = {"source": f"generic_pull:{source_name}"}
        for target_field, source_field in field_mapping.items():
            if source_field in item:
                raw[target_field] = item[source_field]
        if not field_mapping:
            raw.update(item)  # no mapping configured — pass through, normalize_event() still applies safe defaults
        mapped.append(raw)
    return mapped


async def poll_generic_source(source_config: Dict) -> Dict:
    """Poll one registered generic source over real HTTP and feed results through the
    existing ingest_batch() pipeline. Network/parse failures are logged and return a
    zero-ingested result — never raised into the scheduler loop."""
    import httpx

    url = source_config["url"]
    method = source_config.get("method", "GET").upper()
    headers = {}
    if source_config.get("auth_header"):
        headers["Authorization"] = source_config["auth_header"]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(method, url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Generic source '{source_config.get('name')}' returned status {resp.status_code}")
                return {"ingested": 0, "incidents_created": 0, "results": []}
            payload = resp.json()
    except Exception as e:
        logger.warning(f"Generic source '{source_config.get('name')}' poll failed: {e}")
        return {"ingested": 0, "incidents_created": 0, "results": []}

    items = payload if isinstance(payload, list) else payload.get("items", payload.get("results", []))
    if not isinstance(items, list):
        items = []
    raw_events = _map_response_items(items, source_config.get("field_mapping", {}), source_config.get("name", "generic"))
    if not raw_events:
        return {"ingested": 0, "incidents_created": 0, "results": []}
    return await ingest_batch(raw_events)


GENERIC_INGESTION_TICK_SECONDS = 60


async def generic_ingestion_scheduler():
    """Background loop: each tick, polls any registered generic source whose
    poll_interval has elapsed. Mirrors the shape of the other schedulers in this codebase
    (e.g. autonomous_ops_orchestrator.sla_breach_scheduler)."""
    while True:
        try:
            sources = await list_ingestion_sources()
            now = datetime.now(timezone.utc)
            for source in sources:
                if not source.get("enabled", True):
                    continue
                last_polled = source.get("last_polled_at")
                due = True
                if last_polled:
                    try:
                        last_dt = datetime.fromisoformat(last_polled.replace("Z", "+00:00"))
                        due = (now - last_dt).total_seconds() >= source["poll_interval_seconds"]
                    except Exception:
                        due = True
                if not due:
                    continue
                result = await poll_generic_source(source)
                await db.ingestion_sources.update_one(
                    {"id": source["id"]}, {"$set": {"last_polled_at": now.isoformat()}}
                )
                if result.get("ingested"):
                    logger.info(f"Generic source '{source.get('name')}': ingested {result['ingested']} event(s)")
        except Exception as e:
            logger.error(f"Generic ingestion scheduler error: {e}")
        await asyncio.sleep(GENERIC_INGESTION_TICK_SECONDS)
