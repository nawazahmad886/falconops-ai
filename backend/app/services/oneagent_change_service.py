"""
OneAgent change detection — diffs a heartbeat's discovered-services list and
agent_version against the previously stored db.oneagent_agents doc *before*
the upsert overwrites it, and records real, derived state transitions.

No uptime metric exists anywhere in this agent's collectors today (confirmed
by reading collector/system.go's SystemStats struct) — host-reboot detection
would need one and none is fabricated here; this only detects the change
types genuinely derivable from two successive heartbeats' service lists.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def _ensure_indexes() -> None:
    from .core.database import db
    try:
        await db.oneagent_changes.create_index("host")
        await db.oneagent_changes.create_index("detected_at")
        await db.oneagent_changes.create_index("change_type")
    except Exception as e:
        logger.warning(f"oneagent_changes index setup failed: {e}")


def _service_key(svc: Dict[str, Any]) -> Optional[str]:
    name = svc.get("name")
    return name if name else None


async def detect_and_record_changes(host: str, previous_doc: Optional[Dict[str, Any]], new_payload: Dict[str, Any]) -> None:
    if previous_doc is None:
        return  # first-ever heartbeat for this host — nothing to diff against, not a "change"

    await _ensure_indexes()
    from .core.database import db

    now = datetime.now(timezone.utc).isoformat()
    events: List[Dict[str, Any]] = []

    old_services = {s: v for s, v in ((_service_key(x), x) for x in (previous_doc.get("services") or [])) if s}
    new_services = {s: v for s, v in ((_service_key(x), x) for x in (new_payload.get("services") or [])) if s}

    for name in new_services.keys() - old_services.keys():
        events.append(_event(host, "process_started", f"Process '{name}' newly discovered", {
            "service": name, "runtime": new_services[name].get("runtime"), "pid": new_services[name].get("pid"),
        }))

    for name in old_services.keys() - new_services.keys():
        events.append(_event(host, "process_stopped", f"Process '{name}' no longer discovered", {
            "service": name, "runtime": old_services[name].get("runtime"), "last_pid": old_services[name].get("pid"),
        }))

    for name in old_services.keys() & new_services.keys():
        old_pid, new_pid = old_services[name].get("pid"), new_services[name].get("pid")
        if old_pid is not None and new_pid is not None and old_pid != new_pid:
            events.append(_event(host, "service_restarted", f"Process '{name}' restarted (new PID)", {
                "service": name, "previous_pid": old_pid, "new_pid": new_pid,
            }))

    old_version, new_version = previous_doc.get("agent_version"), new_payload.get("agent_version")
    if old_version and new_version and old_version != new_version:
        events.append(_event(host, "agent_version_changed", f"OneAgent upgraded {old_version} -> {new_version}", {
            "previous_version": old_version, "new_version": new_version,
        }))

    if events:
        try:
            await db.oneagent_changes.insert_many(events)
        except Exception as e:
            logger.warning(f"oneagent_changes write failed for host {host}: {e}")


def _event(host: str, change_type: str, message: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()), "host": host, "change_type": change_type, "message": message,
        "detail": detail, "detected_at": datetime.now(timezone.utc).isoformat(),
    }


async def list_changes(host: Optional[str] = None, change_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    from .core.database import db
    query: Dict[str, Any] = {}
    if host:
        query["host"] = host
    if change_type:
        query["change_type"] = change_type
    return await db.oneagent_changes.find(query, {"_id": 0}).sort("detected_at", -1).limit(limit).to_list(limit)


__all__ = ["detect_and_record_changes", "list_changes"]
