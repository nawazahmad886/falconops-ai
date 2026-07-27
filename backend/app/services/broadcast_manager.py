"""
FalconOps AI - Shared WebSocket Broadcast Manager

A single connection-registry/broadcast abstraction shared by every real-time
push channel in the backend (alerts, SOC live feed, AI monitoring live feed,
live call flow). Behavior differences between channels (raw send_json vs
json.dumps+send_text, auth vs no auth, "send a snapshot on connect" vs not)
are handled via the `use_send_json`/`authenticate`/`on_connect` hooks rather
than forking the class, so each channel keeps its exact existing wire
behavior after migrating onto this.
"""
import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

AuthHook = Callable[[WebSocket], Awaitable[bool]]
ConnectHook = Callable[[WebSocket], Awaitable[Optional[Dict[str, Any]]]]


class BroadcastManager:
    """Manages a set of WebSocket connections for one real-time channel."""

    def __init__(
        self,
        *,
        name: str,
        use_send_json: bool = False,
        on_connect: Optional[ConnectHook] = None,
        authenticate: Optional[AuthHook] = None,
    ):
        self.name = name
        self.use_send_json = use_send_json
        self.on_connect = on_connect
        self.authenticate = authenticate
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> bool:
        """Accept the socket, run optional auth, register it, run optional
        on_connect. Returns False if auth rejected the connection — callers
        must return immediately in that case, not enter their receive loop
        (the auth hook is responsible for closing the socket itself)."""
        await websocket.accept()
        if self.authenticate and not await self.authenticate(websocket):
            return False
        async with self._lock:
            self._clients.add(websocket)
        logger.info(f"[{self.name}] client connected. Total: {len(self._clients)}")
        if self.on_connect:
            payload = await self.on_connect(websocket)
            if payload:
                await websocket.send_json(payload)
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
        logger.info(f"[{self.name}] client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._clients)
        dead = []
        for ws in targets:
            try:
                if self.use_send_json:
                    await ws.send_json(message)
                else:
                    await ws.send_text(json.dumps(message, default=str))
            except Exception as e:
                logger.debug(f"[{self.name}] error sending to client: {e}")
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)
