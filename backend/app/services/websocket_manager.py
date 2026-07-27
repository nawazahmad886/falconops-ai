"""
FalconOps AI - WebSocket Manager
Real-time alert broadcasting to connected clients

Backed by the shared BroadcastManager (see broadcast_manager.py) — kept as a
thin adapter module so existing callers (`from ..services.websocket_manager
import ws_manager`) and the `ConnectionManager` type name are unaffected.
"""
from .broadcast_manager import BroadcastManager

# `use_send_json=True` preserves this channel's original wire format exactly.
ws_manager = BroadcastManager(name="alerts", use_send_json=True)

# Back-compat alias for the old class name.
ConnectionManager = BroadcastManager


def get_ws_manager() -> BroadcastManager:
    """Get the WebSocket manager instance"""
    return ws_manager
