"""Workflow observability — aggregation queries only, no new detection
logic, same pattern as executive_routes.py's existing composite scores."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


async def get_summary(workflow_id: Optional[str] = None, hours: int = 24) -> Dict[str, Any]:
    from ...core.database import db

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query: Dict[str, Any] = {"started_at": {"$gte": cutoff}}
    if workflow_id:
        query["workflow_id"] = workflow_id

    executions = await db.workflow_executions.find(query, {"_id": 0}).to_list(5000)
    total = len(executions)
    if total == 0:
        return {"total_executions": 0, "success_rate": None, "failure_rate": None,
                 "avg_duration_ms": None, "p95_duration_ms": None, "retries_total": 0,
                 "approval_wait_ms_avg": None, "agent_tokens_total": None, "agent_cost_estimate_total": None}

    completed = [e for e in executions if e.get("status") == "completed"]
    failed = [e for e in executions if e.get("status") == "failed"]
    durations = sorted(e["metrics"]["duration_ms"] for e in executions if (e.get("metrics") or {}).get("duration_ms") is not None)
    retries_total = sum((e.get("metrics") or {}).get("retries_total", 0) for e in executions)

    approvals = await db.workflow_approvals.find(
        {"execution_id": {"$in": [e["execution_id"] for e in executions]}, "decided_at": {"$exists": True}}, {"_id": 0},
    ).to_list(2000)
    wait_times = []
    for a in approvals:
        try:
            requested = datetime.fromisoformat(a["requested_at"])
            decided = datetime.fromisoformat(a["decided_at"])
            wait_times.append((decided - requested).total_seconds() * 1000)
        except Exception:
            continue

    tokens_total = sum((e.get("metrics") or {}).get("agent_tokens_input_total") or 0 for e in executions) + \
        sum((e.get("metrics") or {}).get("agent_tokens_output_total") or 0 for e in executions)
    has_real_tokens = any((e.get("metrics") or {}).get("agent_tokens_input_total") is not None for e in executions)
    cost_total = sum((e.get("metrics") or {}).get("agent_cost_estimate_total") or 0 for e in executions)
    has_real_cost = any((e.get("metrics") or {}).get("agent_cost_estimate_total") is not None for e in executions)

    return {
        "total_executions": total,
        "success_rate": round(len(completed) / total * 100, 1),
        "failure_rate": round(len(failed) / total * 100, 1),
        "avg_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "p95_duration_ms": durations[int(len(durations) * 0.95) - 1] if durations else None,
        "retries_total": retries_total,
        "approval_wait_ms_avg": round(sum(wait_times) / len(wait_times)) if wait_times else None,
        "agent_tokens_total": tokens_total if has_real_tokens else None,
        "agent_cost_estimate_total": round(cost_total, 4) if has_real_cost else None,
    }


__all__ = ["get_summary"]
