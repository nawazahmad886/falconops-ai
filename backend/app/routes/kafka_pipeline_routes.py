"""
FalconOps AI - Kafka Pipeline Routes
Stream stats and event production endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..utils.auth import require_auth, require_write_access
from ..services.kafka_pipeline import producer, get_stream_stats

router = APIRouter(prefix="/api/kafka", tags=["Kafka Pipeline"])


class ProduceEventRequest(BaseModel):
    topic: str  # topic key e.g. "security_events"
    event: dict


@router.get("/stats")
async def stream_stats(current_user: dict = Depends(require_auth)):
    """Get streaming pipeline statistics"""
    return await get_stream_stats()


@router.post("/produce")
async def produce_event(req: ProduceEventRequest, current_user: dict = Depends(require_write_access)):
    """Produce an event to the streaming pipeline"""
    ok = await producer.send(req.topic, req.event)
    return {"sent": ok, "topic": req.topic}
