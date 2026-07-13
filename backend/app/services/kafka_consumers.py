"""
FalconOps AI - Kafka Consumer Handlers

Registers one handler per real-event topic (threats, alerts, ai_monitoring) on the
shared kafka_pipeline.consumer. Each handler fans an event out to two places:
  1. The existing SOC live-feed WebSocket broadcaster (soc_live_feed.py) — proves
     genuine decoupled pub/sub: producers (security_service.py, alert_engine.py,
     ai_monitoring_service.py) no longer need to know about the SOC live feed at all,
     they just publish to Kafka.
  2. db.event_log — a durable record of every consumed event, replacing db.event_stream
     (which was only ever kafka_pipeline.py's own Mongo-fallback demo store) as the
     real audit trail.

register_handlers() must be called once, before kafka_pipeline.consumer.connect() /
start_consuming(), so the handlers are in place before any messages arrive.
"""
import logging
from datetime import datetime, timezone
from typing import Dict

from ..core.database import db
from . import kafka_pipeline
from . import soc_live_feed

logger = logging.getLogger(__name__)


async def _log_event(topic_key: str, event: Dict):
    await db.event_log.insert_one({
        "topic": topic_key,
        "event": event,
        "consumed_at": datetime.now(timezone.utc).isoformat(),
    })


async def _handle_threat(event: Dict):
    try:
        await soc_live_feed.push_threat(event)
    except Exception as e:
        logger.warning(f"SOC live feed push_threat failed: {e}")
    await _log_event("threats", event)


async def _handle_alert(event: Dict):
    try:
        await soc_live_feed.soc_manager.broadcast({
            "type": "alert",
            "data": {
                "id": event.get("id", ""),
                "title": event.get("title", ""),
                "severity": event.get("severity", ""),
                "entity_name": event.get("entity_name", ""),
                "metric_name": event.get("metric_name", ""),
                "status": event.get("status", ""),
                "timestamp": event.get("created_at", datetime.now(timezone.utc).isoformat()),
            },
        })
    except Exception as e:
        logger.warning(f"SOC live feed alert broadcast failed: {e}")
    await _log_event("alerts", event)


async def _handle_ai_monitoring(event: Dict):
    try:
        verdict = event.get("verdict", {}) or {}
        await soc_live_feed.soc_manager.broadcast({
            "type": "ai_monitoring",
            "data": {
                "id": event.get("id", ""),
                "system_status": verdict.get("system_status", ""),
                "agents": [a.get("agent") for a in event.get("agents", []) if a.get("flagged")],
                "timestamp": event.get("received_at", datetime.now(timezone.utc).isoformat()),
            },
        })
    except Exception as e:
        logger.warning(f"SOC live feed ai_monitoring broadcast failed: {e}")
    await _log_event("ai_monitoring", event)


def register_handlers():
    """Wire up all real-event consumer handlers. Call once at startup, before
    kafka_pipeline.consumer.connect()/start_consuming()."""
    kafka_pipeline.consumer.register_handler("threats", _handle_threat)
    kafka_pipeline.consumer.register_handler("alerts", _handle_alert)
    kafka_pipeline.consumer.register_handler("ai_monitoring", _handle_ai_monitoring)
    logger.info("Kafka consumer handlers registered: threats, alerts, ai_monitoring")
