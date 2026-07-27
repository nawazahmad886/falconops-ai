"""
FalconOps AI - Real-time SOC WebSocket & Live Feed Service
WebSocket endpoint for pushing threats, events, and alerts in real-time

Backed by the shared BroadcastManager (see broadcast_manager.py) — kept as a
thin adapter module so existing callers (`soc_manager.broadcast(...)`,
`soc_manager.client_count`) are unaffected.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from fastapi import WebSocket

from ..core.database import db
from .broadcast_manager import BroadcastManager

logger = logging.getLogger(__name__)

# ======================== CONNECTION MANAGER ========================

async def _send_initial_snapshot(websocket: WebSocket) -> Optional[Dict]:
    """on_connect hook — sends the same {"type": "initial", "data": recent}
    snapshot this channel has always sent right after connecting."""
    recent = await get_recent_feed(30)
    return {"type": "initial", "data": recent}


soc_manager = BroadcastManager(name="soc-feed", on_connect=_send_initial_snapshot)

# Back-compat alias for the old class name.
SOCConnectionManager = BroadcastManager


# ======================== LIVE FEED HELPERS ========================

async def push_threat(threat: Dict):
    """Push a new threat to all connected SOC clients"""
    await soc_manager.broadcast({
        "type": "threat",
        "data": {
            "id": threat.get("id", ""),
            "threat_type": threat.get("type", ""),
            "severity": threat.get("severity", ""),
            "message": threat.get("message", ""),
            "source_ip": threat.get("source_ip", ""),
            "user": threat.get("user", ""),
            "mitre_technique": threat.get("mitre_technique", ""),
            "timestamp": threat.get("timestamp", datetime.now(timezone.utc).isoformat()),
        },
    })


async def push_event(event: Dict):
    """Push a security event to all connected SOC clients"""
    if event.get("severity") in ("critical", "high"):
        await soc_manager.broadcast({
            "type": "security_event",
            "data": {
                "id": event.get("id", ""),
                "action": event.get("action", ""),
                "severity": event.get("severity", ""),
                "message": event.get("message", ""),
                "source_ip": event.get("source_ip", ""),
                "user": event.get("user", ""),
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
            },
        })


async def push_remediation(action: Dict):
    """Push a remediation execution event"""
    await soc_manager.broadcast({
        "type": "remediation",
        "data": {
            "id": action.get("id", ""),
            "action_name": action.get("action_name", ""),
            "status": action.get("status", ""),
            "resolved_script": action.get("resolved_script", ""),
            "trigger": action.get("trigger", ""),
            "timestamp": action.get("completed_at", datetime.now(timezone.utc).isoformat()),
        },
    })


async def get_recent_feed(limit: int = 30) -> List[Dict]:
    """Get recent SOC feed items from DB for initial load"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    threats = await db.security_threats.find(
        {"timestamp": {"$gte": cutoff}}, {"_id": 0, "id": 1, "type": 1, "severity": 1, "message": 1, "source_ip": 1, "user": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    feed = [{"type": "threat", "data": t} for t in threats]
    feed.sort(key=lambda x: x["data"].get("timestamp", ""), reverse=True)
    return feed[:limit]
