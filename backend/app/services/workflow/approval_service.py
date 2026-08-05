"""
Human Approval — a persisted-state pause, not an in-memory suspension.

RASED's own DESTRUCTIVE-tier approval uses LangGraph's interrupt()/resume
mechanism, which its own code (graph/checkpointer.py) flags as the
least-verified, highest-risk piece of the whole RASED build in this
environment (no local langgraph install to test against). The workflow
engine is not a LangGraph graph, so it cannot use interrupt() anyway — and
deliberately doesn't try to. Instead: dag_engine.py simply stops walking
past a Human Approval node and returns (the asyncio task ends normally,
nothing is suspended in memory). decide() re-reads workflow_node_executions
from Mongo to know what's already done and calls dag_engine.resume_execution
to continue — no checkpoint/replay semantics, no risk of re-running a
node's side effects, because nothing is replayed.

Reuses RASED's remediation.approve_destructive PERMISSION (the same bar for
deciding a DESTRUCTIVE-tier action), not RASED's interrupt MECHANISM.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def _ensure_indexes() -> None:
    from ...core.database import db
    try:
        await db.workflow_approvals.create_index("approval_id", unique=True)
        await db.workflow_approvals.create_index("execution_id")
        await db.workflow_approvals.create_index("status")
    except Exception as e:
        logger.warning(f"workflow_approvals index setup failed: {e}")


async def request_approval(
    *, execution_id: str, node_execution_id: str, node_id: str, workflow_id: str,
    title: str = "Approval required", risk_tier: str = "GUARDED",
    requested_permission: str = "remediation.approve_destructive",
) -> str:
    await _ensure_indexes()
    from ...core.database import db

    approval_id = str(uuid.uuid4())
    doc = {
        "approval_id": approval_id, "execution_id": execution_id, "node_execution_id": node_execution_id,
        "workflow_id": workflow_id, "node_id": node_id, "title": title, "risk_tier": risk_tier,
        "requested_permission": requested_permission, "status": "pending",
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.workflow_approvals.insert_one(doc)
    await db.workflow_node_executions.update_one(
        {"node_execution_id": node_execution_id}, {"$set": {"approval_id": approval_id}},
    )
    return approval_id


async def get_approval(approval_id: str) -> Optional[Dict[str, Any]]:
    from ...core.database import db
    return await db.workflow_approvals.find_one({"approval_id": approval_id}, {"_id": 0})


async def list_pending_for_execution(execution_id: str) -> list:
    from ...core.database import db
    return await db.workflow_approvals.find({"execution_id": execution_id, "status": "pending"}, {"_id": 0}).to_list(50)


async def decide(approval_id: str, approved: bool, reason: Optional[str], decided_by: str, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from ...core.database import db
    from . import dag_engine

    approval = await db.workflow_approvals.find_one({"approval_id": approval_id}, {"_id": 0})
    if approval is None:
        return {"error": "approval not found"}
    if approval.get("status") != "pending":
        return {"error": f"approval already {approval.get('status')}"}

    if approved:
        from ..rbac_service import check_permission
        if actor is None or not await check_permission(actor, approval.get("requested_permission", "remediation.approve_destructive")):
            return {"error": f"actor lacks required permission '{approval.get('requested_permission')}'"}

    now = datetime.now(timezone.utc)
    new_status = "approved" if approved else "rejected"
    await db.workflow_approvals.update_one(
        {"approval_id": approval_id},
        {"$set": {"status": new_status, "decided_at": now.isoformat(), "decided_by": decided_by, "reason": reason}},
    )
    # Both outcomes complete the node — a rejection routes via its own "rejected"
    # branch edge (Notify/Escalate), it is not itself a workflow failure.
    await db.workflow_node_executions.update_one(
        {"node_execution_id": approval["node_execution_id"]},
        {"$set": {"status": "completed", "output": {"approved": approved, "reason": reason, "branch": new_status},
                   "finished_at": now.isoformat()}},
    )

    await dag_engine.resume_execution(approval["execution_id"], actor)
    return {"approval_id": approval_id, "status": new_status}


__all__ = ["request_approval", "get_approval", "list_pending_for_execution", "decide"]
