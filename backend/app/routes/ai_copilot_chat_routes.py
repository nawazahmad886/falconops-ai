"""
FalconOps AI — AI Copilot Chat Routes
Conversational monitor creation + agent approval workflow.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..utils.auth import require_auth, require_admin
from ..services.ai_copilot_chat_service import (
    send_chat_message, list_sessions, get_session_messages, delete_session,
    list_actions, get_action, reject_action, approve_and_execute,
)

router = APIRouter(prefix="/api/ai-copilot", tags=["AI Copilot"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = ""


# ──────────────── Sessions ────────────────

@router.get("/sessions")
async def sessions_list(user: dict = Depends(require_auth), limit: int = Query(50, ge=1, le=200)):
    return {"sessions": await list_sessions(user, limit)}


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str, user: dict = Depends(require_auth),
                           limit: int = Query(200, ge=1, le=500)):
    msgs = await get_session_messages(session_id, user, limit)
    return {"session_id": session_id, "messages": msgs}


@router.delete("/sessions/{session_id}")
async def session_delete(session_id: str, user: dict = Depends(require_auth)):
    ok = await delete_session(session_id, user)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"deleted": True}


# ──────────────── Chat ────────────────

@router.post("/chat")
async def chat(req: ChatRequest, user: dict = Depends(require_auth)):
    try:
        return await send_chat_message(req.session_id, user, req.message)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"AI chat failed: {str(e)[:300]}")


# ──────────────── Actions / Approvals ────────────────

@router.get("/actions")
async def actions_list(
    user: dict = Depends(require_auth),
    status: Optional[str] = Query(None, regex="^(pending|approved|rejected|executed|failed)$"),
    limit: int = Query(100, ge=1, le=500),
):
    return {"actions": await list_actions(user, status, limit)}


@router.get("/actions/{action_id}")
async def action_detail(action_id: str, user: dict = Depends(require_auth)):
    action = await get_action(action_id)
    if not action:
        raise HTTPException(404, "Action not found")
    if user.get("role") != "admin" and action.get("user_id") != user["id"]:
        raise HTTPException(403, "Not allowed")
    return action


@router.post("/actions/{action_id}/approve")
async def action_approve(action_id: str, admin_user: dict = Depends(require_admin)):
    """Admin-only: approve the AI-proposed action and execute it immediately."""
    result = await approve_and_execute(action_id, admin_user)
    if not result or result.get("error"):
        raise HTTPException(400, result.get("error", "Approval failed") if result else "Action not found")
    return result


@router.post("/actions/{action_id}/reject")
async def action_reject(action_id: str, req: RejectRequest, admin_user: dict = Depends(require_admin)):
    """Admin-only: reject the AI-proposed action. It will not be executed."""
    result = await reject_action(action_id, admin_user, req.reason or "")
    if not result or result.get("error"):
        raise HTTPException(400, result.get("error", "Rejection failed") if result else "Action not found")
    return result
