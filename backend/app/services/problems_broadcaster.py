"""
FalconOps AI - Problems console live broadcaster

A 5th BroadcastManager instance (see broadcast_manager.py), same pattern as
call_flow_broadcaster.py — a lightweight delta payload per event, not a full
enriched Problem (avoids recomputing impact/AI analysis on every broadcast).
"""
from datetime import datetime, timezone
from typing import Optional

from .broadcast_manager import BroadcastManager

problems_manager = BroadcastManager(name="problems")


async def broadcast_problem_event(
    *,
    event_type: str,
    problem_id: str,
    severity: Optional[str],
    status: Optional[str],
    title: Optional[str],
    source: str,
) -> None:
    await problems_manager.broadcast({
        "type": event_type,  # "problem.created" | "problem.updated" | "problem.assigned"
        "problem_id": problem_id,
        "severity": severity,
        "status": status,
        "title": title,
        "source": source,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
