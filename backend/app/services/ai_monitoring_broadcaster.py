"""
FalconOps AI — In-process WebSocket broadcaster for AI Monitoring live feed.

A tiny singleton that holds the set of currently-connected dashboard websockets
and lets `ai_monitoring_service.evaluate_exchange` fan-out fresh events to all
subscribers in real time. Designed to be lightweight (no extra deps) and safe
to call from any async coroutine — failures broadcasting are swallowed so they
can never break the monitoring pipeline itself.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class _Broadcaster:
    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def register(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self._clients:
            return
        data = json.dumps(message, default=str)
        # Snapshot to avoid mutation during iteration
        async with self._lock:
            targets = list(self._clients)
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception as e:  # pragma: no cover — best-effort fan-out
                logger.debug("ai_monitoring_broadcaster: dropping client (%s)", e)
                await self.unregister(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


broadcaster = _Broadcaster()
