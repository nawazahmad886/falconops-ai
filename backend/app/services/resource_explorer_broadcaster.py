"""
FalconOps AI - Resource Explorer live broadcaster

An 8th BroadcastManager instance (see broadcast_manager.py), same pattern as
problems_broadcaster.py — a lightweight delta payload per event.
"""
from datetime import datetime, timezone
from typing import Optional

from .broadcast_manager import BroadcastManager

resource_manager = BroadcastManager(name="resources")


async def broadcast_resource_event(
    *,
    event_type: str,
    resource_id: str,
    resource_category: Optional[str],
    lifecycle_status: Optional[str],
    name: Optional[str],
) -> None:
    await resource_manager.broadcast({
        "type": event_type,  # "resource.synced" | "resource.monitoring_toggled" | "resource.lifecycle_changed"
        "resource_id": resource_id,
        "resource_category": resource_category,
        "lifecycle_status": lifecycle_status,
        "name": name,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
