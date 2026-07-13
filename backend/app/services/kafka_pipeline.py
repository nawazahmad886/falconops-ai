"""
FalconOps AI - Kafka Streaming Pipeline (with MongoDB fallback)
Producer/consumer abstraction for real-time event streaming
"""
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable

from ..core.database import db

logger = logging.getLogger(__name__)

_kafka_available = False
_producer = None
_consumer_tasks = {}

try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    _kafka_available = True
except ImportError:
    logger.info("aiokafka not available - using MongoDB fallback for event streaming")


# ======================== KAFKA CONFIG ========================

KAFKA_TOPICS = {
    "security_events": "falconops.security.events",
    "metrics": "falconops.metrics.ingest",
    "threats": "falconops.security.threats",
    "audit": "falconops.audit.logs",
    "alerts": "falconops.alerts.notifications",
    "ai_monitoring": "falconops.ai.monitoring",
}


# ======================== PRODUCER ========================

class EventProducer:
    """Produces events to Kafka or MongoDB fallback"""

    def __init__(self):
        self._kafka_producer = None
        self._use_kafka = False

    async def connect(self, bootstrap_servers: str = None):
        if not _kafka_available or not bootstrap_servers:
            logger.info("Kafka producer using MongoDB fallback")
            return

        try:
            self._kafka_producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            await self._kafka_producer.start()
            self._use_kafka = True
            logger.info(f"Kafka producer connected to {bootstrap_servers}")
        except Exception as e:
            logger.warning(f"Kafka producer connection failed, using MongoDB fallback: {e}")
            self._use_kafka = False

    async def send(self, topic_key: str, event: Dict) -> bool:
        """Send an event to a topic"""
        topic = KAFKA_TOPICS.get(topic_key, topic_key)
        event["_produced_at"] = datetime.now(timezone.utc).isoformat()

        if self._use_kafka and self._kafka_producer:
            try:
                await self._kafka_producer.send_and_wait(topic, event)
                return True
            except Exception as e:
                logger.warning(f"Kafka send failed, falling back to MongoDB: {e}")

        # MongoDB fallback
        await db.event_stream.insert_one({
            "topic": topic,
            "event": event,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return True

    async def close(self):
        if self._kafka_producer:
            await self._kafka_producer.stop()

    @property
    def is_kafka(self):
        return self._use_kafka


# ======================== CONSUMER ========================

class EventConsumer:
    """Consumes events from Kafka or polls MongoDB fallback"""

    def __init__(self):
        self._kafka_consumer = None
        self._use_kafka = False
        self._handlers: Dict[str, Callable] = {}
        self._running = False

    async def connect(self, bootstrap_servers: str = None, group_id: str = "falconops-group"):
        if not _kafka_available or not bootstrap_servers:
            logger.info("Kafka consumer using MongoDB fallback")
            return

        try:
            topics = list(KAFKA_TOPICS.values())
            self._kafka_consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            await self._kafka_consumer.start()
            self._use_kafka = True
            logger.info(f"Kafka consumer connected to {bootstrap_servers}")
        except Exception as e:
            logger.warning(f"Kafka consumer connection failed, using MongoDB fallback: {e}")

    def register_handler(self, topic_key: str, handler: Callable):
        topic = KAFKA_TOPICS.get(topic_key, topic_key)
        self._handlers[topic] = handler

    async def start_consuming(self):
        self._running = True
        if self._use_kafka:
            await self._consume_kafka()
        else:
            await self._consume_mongodb()

    async def _consume_kafka(self):
        try:
            async for msg in self._kafka_consumer:
                if not self._running:
                    break
                handler = self._handlers.get(msg.topic)
                if handler:
                    await handler(msg.value)
        except Exception as e:
            logger.error(f"Kafka consumer error: {e}")

    async def _consume_mongodb(self):
        """Poll MongoDB for pending events"""
        while self._running:
            try:
                pending = await db.event_stream.find({"status": "pending"}).sort("created_at", 1).limit(50).to_list(50)
                for item in pending:
                    handler = self._handlers.get(item.get("topic"))
                    if handler:
                        await handler(item.get("event", {}))
                    await db.event_stream.update_one({"_id": item["_id"]}, {"$set": {"status": "processed"}})
            except Exception as e:
                logger.error(f"MongoDB consumer poll error: {e}")
            await asyncio.sleep(2)

    async def close(self):
        self._running = False
        if self._kafka_consumer:
            await self._kafka_consumer.stop()


# ======================== SINGLETONS ========================

producer = EventProducer()
consumer = EventConsumer()


async def get_stream_stats() -> Dict:
    """Get streaming pipeline statistics"""
    total = await db.event_stream.count_documents({})
    pending = await db.event_stream.count_documents({"status": "pending"})
    processed = await db.event_stream.count_documents({"status": "processed"})

    topic_pipeline = [
        {"$group": {"_id": "$topic", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    by_topic = await db.event_stream.aggregate(topic_pipeline).to_list(20)

    return {
        "mode": "kafka" if producer.is_kafka else "mongodb_fallback",
        "kafka_available": _kafka_available,
        "total_events": total,
        "pending": pending,
        "processed": processed,
        "by_topic": [{"topic": t["_id"], "count": t["count"]} for t in by_topic],
        "topics": KAFKA_TOPICS,
    }
