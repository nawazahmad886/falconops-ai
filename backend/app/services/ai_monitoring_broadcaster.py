"""
FalconOps AI — In-process WebSocket broadcaster for AI Monitoring live feed.

A tiny singleton that holds the set of currently-connected dashboard websockets
and lets `ai_monitoring_service.evaluate_exchange` fan-out fresh events to all
subscribers in real time. Backed by the shared BroadcastManager — kept as a
thin adapter module so `broadcaster.broadcast(...)` callers are unaffected.
`ai_monitoring_routes.py` assigns `broadcaster.authenticate`/`.on_connect` at
import time (its token-check + hello-message logic needs `_AGENT_FLAG_FIELDS`,
which lives in that route module).
"""
from __future__ import annotations

from .broadcast_manager import BroadcastManager

broadcaster = BroadcastManager(name="ai-monitoring-live")
