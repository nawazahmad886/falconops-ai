"""
FalconOps AI — AI Copilot Chat Service
Conversational agent that parses natural-language requests and proposes
structured platform actions (create monitor, fix issue, etc.) for human approval.

Uses Emergent LLM Key → Claude Sonnet 4.5 via emergentintegrations.
Every AI-proposed action requires explicit admin approval before execution.
"""
import os
import re
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
load_dotenv()

# Lazy-guarded so the platform boots even when the optional `emergentintegrations`
# wheel isn't installed. This module already falls through to llm_provider_service
# (which supports Ollama / OpenAI / Anthropic / Gemini / rule-based) — the import
# stays available only for legacy direct calls.
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    EMERGENT_LIB_AVAILABLE = True
except Exception:  # pragma: no cover — library is optional
    LlmChat = None  # type: ignore
    UserMessage = None  # type: ignore
    EMERGENT_LIB_AVAILABLE = False

from ..core.database import db
from .uptime_monitor_service import (
    create_monitor as svc_create_monitor,
    delete_monitor as svc_delete_monitor,
    toggle_monitor as svc_toggle_monitor,
    update_monitor_config as svc_update_monitor,
    check_now as svc_check_now,
)

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"

SYSTEM_PROMPT = """You are FalconOps Copilot — an AI SRE assistant embedded inside the
FalconOps AIOps platform. You help operators create monitors, triage incidents, and
fix availability issues by proposing structured actions that a human admin must approve
before they execute.

## Your capabilities (the only actions you can propose):
1. `create_url_monitor` — create a new HTTP/HTTPS uptime monitor
2. `toggle_monitor` — enable/disable an existing monitor
3. `delete_monitor` — remove a monitor
4. `update_monitor` — modify interval, timeout, assertions, etc.
5. `run_check_now` — trigger an immediate check of an existing monitor

## Output contract
When the user asks for an operational change, reply in TWO parts:
1. A short natural-language explanation of what you'll do and why (under 80 words).
2. A fenced JSON block (```json ... ```) with the exact action proposal:

```json
{
  "action": "create_url_monitor",
  "summary": "Monitor the checkout API for 5xx errors every 1 min",
  "params": {
    "name": "Checkout API Health",
    "url": "https://api.example.com/health",
    "method": "GET",
    "interval": 60,
    "timeout": 10,
    "expected_status": 200,
    "regions": ["us-east"],
    "consecutive_failures": 2,
    "max_response_time_ms": 2000,
    "assertions": [
      {"type": "not_contains", "value": "error", "case_sensitive": false},
      {"type": "json_path_eq", "path": "$.status", "value": "ok"}
    ]
  }
}
```

## Assertion types
- `contains` / `not_contains` — substring match against response body (case_sensitive optional)
- `json_path_eq` / `json_path_neq` — dotted JSON path e.g. `$.status`, `$.data.items[0].id`
- `status_in` — allowed HTTP status codes, value is a list e.g. `[200, 201, 204]`

## Rules
- If the user is just asking a question, reply naturally WITHOUT a JSON block.
- Always propose strong assertions to avoid HTTP-200-with-error-body false-positives. Default: assert body does NOT contain "internal server error", "traceback", or similar.
- Never invent monitor IDs. If the user refers to an existing monitor, ask for the ID or name.
- Default region: us-east. Default interval: 60 seconds. Default timeout: 10 seconds.
- Be crisp, SRE-tone, confident. No fluff.
"""


# ──────────────────────────────────────────────────────────────
#  Sessions + Messages
# ──────────────────────────────────────────────────────────────

async def get_or_create_session(session_id: Optional[str], user: Dict) -> Dict:
    if session_id:
        existing = await db.ai_copilot_sessions.find_one(
            {"id": session_id, "user_id": user["id"]}, {"_id": 0}
        )
        if existing:
            return existing

    new_id = session_id or str(uuid.uuid4())
    doc = {
        "id": new_id,
        "user_id": user["id"],
        "user_email": user.get("email", ""),
        "title": "New conversation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "message_count": 0,
    }
    await db.ai_copilot_sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_sessions(user: Dict, limit: int = 50) -> List[Dict]:
    return await db.ai_copilot_sessions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("last_activity", -1).limit(limit).to_list(length=limit)


async def get_session_messages(session_id: str, user: Dict, limit: int = 200) -> List[Dict]:
    session = await db.ai_copilot_sessions.find_one(
        {"id": session_id, "user_id": user["id"]}, {"_id": 0}
    )
    if not session:
        return []
    return await db.ai_copilot_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", 1).limit(limit).to_list(length=limit)


async def delete_session(session_id: str, user: Dict) -> bool:
    r = await db.ai_copilot_sessions.delete_one({"id": session_id, "user_id": user["id"]})
    if r.deleted_count:
        await db.ai_copilot_messages.delete_many({"session_id": session_id})
        await db.ai_copilot_actions.delete_many({"session_id": session_id, "status": "pending"})
        return True
    return False


def _extract_action_proposal(text: str) -> Tuple[str, Optional[Dict]]:
    """Find a ```json action block inside the LLM response. Returns (clean_text, action_dict)."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return text, None
    raw = match.group(1)
    try:
        action = json.loads(raw)
        if not isinstance(action, dict) or "action" not in action:
            return text, None
        clean = (text[:match.start()] + text[match.end():]).strip()
        return clean, action
    except Exception:
        return text, None


# ──────────────────────────────────────────────────────────────
#  Chat
# ──────────────────────────────────────────────────────────────

async def send_chat_message(session_id: Optional[str], user: Dict, text: str) -> Dict:
    # Pull live system prompt from Feature Control Console (admin-editable)
    try:
        from .feature_flags_service import get_ai_copilot_config, is_module_enabled
        if not await is_module_enabled("ai_copilot"):
            raise RuntimeError("AI Copilot module is disabled by admin")
        ai_cfg = await get_ai_copilot_config()
        system_prompt = ai_cfg.get("system_prompt") or SYSTEM_PROMPT
        max_history = int(ai_cfg.get("max_history_turns") or 20)
    except RuntimeError:
        raise
    except Exception:
        system_prompt = SYSTEM_PROMPT
        max_history = 20

    session = await get_or_create_session(session_id, user)
    sid = session["id"]

    user_msg = {
        "id": str(uuid.uuid4()),
        "session_id": sid,
        "role": "user",
        "content": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_copilot_messages.insert_one(user_msg)
    user_msg.pop("_id", None)

    # ─── Vector memory recall: find similar past conversations / insights ───
    rag_block = ""
    try:
        from . import vector_memory_service
        memories = await vector_memory_service.search(
            text,
            top_k=4,
            user_id=user["id"],
            min_score=0.35,
            exclude_session_id=sid,  # don't recall current session
            kinds=["chat_message", "ai_insight"],
        )
        rag_block = vector_memory_service.format_for_prompt(memories)
    except Exception as e:
        logger.debug("vector recall failed (non-fatal): %s", e)
        memories = []

    # Replay last N messages (configurable via Feature Console) as conversation context
    history = await db.ai_copilot_messages.find(
        {"session_id": sid}, {"_id": 0}
    ).sort("created_at", 1).limit(max_history).to_list(length=max_history)

    # ─── Pluggable LLM provider (Ollama / OpenAI / Anthropic / Gemini / Emergent / rule-based) ───
    from . import llm_provider_service
    chat_messages = [{"role": "system", "content": system_prompt}]
    if rag_block:
        chat_messages.append({"role": "system", "content": rag_block})
    # Replay history (skip the just-inserted user message; we'll append it last)
    if len(history) > 1:
        for m in history[:-1]:
            chat_messages.append({"role": m["role"], "content": m["content"]})
    chat_messages.append({"role": "user", "content": text})

    llm_result = await llm_provider_service.chat_completion(chat_messages, session_id=sid)
    response_text = llm_result["response"]
    provider_used = llm_result["provider"]
    model_used = llm_result["model"]

    clean_text, action = _extract_action_proposal(response_text or "")

    # If the LLM emitted ONLY a JSON action block (no narrative preamble),
    # synthesize a friendly explanation from the action summary so the chat
    # bubble never renders empty. Fixes the "response body coming empty for URL" bug.
    if action and (not clean_text or len(clean_text.strip()) < 8):
        action_kind = action.get("action", "action")
        action_summary = action.get("summary", "")
        params = action.get("params") or {}
        if action_summary:
            clean_text = f"I'll {action_summary.lower().rstrip('.')}. Review and approve below."
        elif action_kind == "create_url_monitor" and params.get("url"):
            interval = params.get("interval", 60)
            clean_text = (
                f"I'll create an uptime monitor for {params['url']} "
                f"checking every {interval}s. Review and approve below."
            )
        else:
            clean_text = f"I'm proposing a `{action_kind}` action. Review and approve below."

    assistant_msg = {
        "id": str(uuid.uuid4()),
        "session_id": sid,
        "role": "assistant",
        "content": clean_text or response_text,
        "raw_content": response_text,
        "provider": provider_used,
        "model": model_used,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "action_id": None,
    }

    proposed_action_doc = None
    if action:
        proposed_action_doc = {
            "id": str(uuid.uuid4()),
            "session_id": sid,
            "message_id": assistant_msg["id"],
            "user_id": user["id"],
            "proposed_by_email": user.get("email", ""),
            "action": action.get("action"),
            "summary": action.get("summary", ""),
            "params": action.get("params", {}),
            "status": "pending",  # pending | approved | rejected | executed | failed
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": None,
            "approved_by": None,
            "executed_at": None,
            "execution_result": None,
            "rejection_reason": None,
        }
        await db.ai_copilot_actions.insert_one(proposed_action_doc)
        assistant_msg["action_id"] = proposed_action_doc["id"]
        proposed_action_doc.pop("_id", None)

    await db.ai_copilot_messages.insert_one(assistant_msg)
    assistant_msg.pop("_id", None)

    # ─── Persist user + assistant messages into vector memory (best-effort, non-blocking) ───
    try:
        from . import vector_memory_service
        await vector_memory_service.remember(
            text=text,
            kind="chat_message",
            user_id=user["id"],
            session_id=sid,
            source_id=user_msg["id"],
            metadata={"role": "user"},
        )
        await vector_memory_service.remember(
            text=clean_text or response_text,
            kind="chat_message",
            user_id=user["id"],
            session_id=sid,
            source_id=assistant_msg["id"],
            metadata={"role": "assistant", "has_action": bool(action)},
        )
    except Exception as e:
        logger.warning("vector remember failed: %s", e, exc_info=True)

    new_title = session["title"]
    if session.get("message_count", 0) == 0:
        new_title = text[:60] + ("…" if len(text) > 60 else "")
    await db.ai_copilot_sessions.update_one(
        {"id": sid},
        {"$set": {"last_activity": datetime.now(timezone.utc).isoformat(), "title": new_title},
         "$inc": {"message_count": 2}}
    )

    return {
        "session_id": sid,
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "proposed_action": proposed_action_doc,
        "recalled_memories": memories or [],
    }


# ──────────────────────────────────────────────────────────────
#  Action approval + execution
# ──────────────────────────────────────────────────────────────

async def list_actions(user: Dict, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
    q: Dict = {}
    if user.get("role") != "admin":
        q["user_id"] = user["id"]
    if status:
        q["status"] = status
    return await db.ai_copilot_actions.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(length=limit)


async def get_action(action_id: str) -> Optional[Dict]:
    return await db.ai_copilot_actions.find_one({"id": action_id}, {"_id": 0})


async def reject_action(action_id: str, admin_user: Dict, reason: str = "") -> Dict:
    action = await get_action(action_id)
    if not action:
        return {"error": "Action not found"}
    if action["status"] != "pending":
        return {"error": f"Action already {action['status']}"}
    await db.ai_copilot_actions.update_one(
        {"id": action_id},
        {"$set": {
            "status": "rejected",
            "approved_by": admin_user.get("email", ""),
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": (reason or "")[:300],
        }}
    )
    return await get_action(action_id)


async def approve_and_execute(action_id: str, admin_user: Dict) -> Dict:
    action = await get_action(action_id)
    if not action:
        return {"error": "Action not found"}
    if action["status"] != "pending":
        return {"error": f"Action already {action['status']}"}

    now = datetime.now(timezone.utc).isoformat()
    await db.ai_copilot_actions.update_one(
        {"id": action_id},
        {"$set": {"status": "approved", "approved_by": admin_user.get("email", ""), "approved_at": now}}
    )

    atype = action["action"]
    params = action.get("params", {}) or {}
    result: Dict = {"ok": False}

    # ── Param-recovery: if the LLM proposed an action with empty params (a known
    # weakness on smaller / faster models), try to recover sane defaults from
    # the originating chat turns. Today this primarily rescues create_url_monitor
    # by regex-extracting the first URL the user typed.
    if atype == "create_url_monitor" and not params.get("url") and action.get("session_id"):
        try:
            import re as _re
            session_msgs = await db.ai_copilot_messages.find(
                {"session_id": action["session_id"], "role": "user"},
                {"_id": 0, "content": 1, "created_at": 1},
            ).sort("created_at", -1).limit(6).to_list(length=6)
            combined = "\n".join(m.get("content", "") for m in session_msgs)
            url_match = _re.search(r"https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+", combined)
            interval_match = _re.search(r"every\s+(\d{1,4})\s*(second|sec|s|minute|min|m|hour|h)\b",
                                        combined, _re.IGNORECASE)
            timeout_match = _re.search(r"timeout\s+(\d{1,4})\s*(second|sec|s|minute|min|m)\b",
                                       combined, _re.IGNORECASE)
            if url_match:
                params["url"] = url_match.group(0).rstrip(".,;:!?)\"'")
                logger.info("create_url_monitor params recovered from chat — url=%s", params["url"])
            if interval_match and not params.get("interval"):
                num = int(interval_match.group(1))
                unit = interval_match.group(2).lower()
                params["interval"] = num * 60 if unit.startswith(("min", "m")) and unit != "m" else (
                    num * 3600 if unit.startswith("hour") or unit == "h" else num
                )
            if timeout_match and not params.get("timeout"):
                num = int(timeout_match.group(1))
                unit = timeout_match.group(2).lower()
                params["timeout"] = num * 60 if unit.startswith("min") or unit == "m" else num
            # Persist the recovered params so they show in the action history
            if url_match:
                await db.ai_copilot_actions.update_one(
                    {"id": action_id},
                    {"$set": {"params": params, "params_recovered": True}},
                )
        except Exception as e:
            logger.warning("param recovery failed for action %s: %s", action_id, e)

    try:
        if atype == "create_url_monitor":
            if not params.get("url"):
                raise ValueError(
                    "url is required — couldn't parse a URL from the original chat turn. "
                    "Edit the action params or re-ask the AI with the URL inline."
                )
            mon = await svc_create_monitor(
                name=params.get("name", "AI-created monitor"),
                url=params["url"],
                interval=int(params.get("interval", 60)),
                method=params.get("method", "GET"),
                expected_status=int(params.get("expected_status", 200)),
                timeout=int(params.get("timeout", 10)),
                headers=params.get("headers") or {},
                created_by=f"ai-copilot:{admin_user.get('email','')}",
                regions=params.get("regions") or ["us-east"],
                alert_channels=params.get("alert_channels") or [],
                consecutive_failures=int(params.get("consecutive_failures", 3)),
                assertions=params.get("assertions") or [],
                max_response_time_ms=params.get("max_response_time_ms"),
                ssl_expiry_warn_days=int(params.get("ssl_expiry_warn_days", 14)),
                apply_safe_defaults=bool(params.get("apply_safe_defaults", True)),
            )
            result = {"ok": True, "created_monitor": mon}
        elif atype == "toggle_monitor":
            result = {"ok": True, **(await svc_toggle_monitor(params["monitor_id"]))}
        elif atype == "delete_monitor":
            ok = await svc_delete_monitor(params["monitor_id"])
            result = {"ok": bool(ok), "deleted": ok}
        elif atype == "update_monitor":
            updates = {k: v for k, v in params.items() if k != "monitor_id"}
            result = {"ok": True, **(await svc_update_monitor(params["monitor_id"], updates))}
        elif atype == "run_check_now":
            check = await svc_check_now(params["monitor_id"])
            result = {"ok": True, "check": check}
        else:
            result = {"ok": False, "error": f"Unsupported action '{atype}'"}
    except Exception as e:
        logger.exception("AI Copilot action execution failed")
        result = {"ok": False, "error": str(e)[:300]}

    final_status = "executed" if result.get("ok") else "failed"
    await db.ai_copilot_actions.update_one(
        {"id": action_id},
        {"$set": {
            "status": final_status,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "execution_result": result,
        }}
    )

    # ─── Agent memory: persist the full monitor-creation rationale to vector
    # memory so future related queries get full context. Captures:
    #   - the original user request (the chat turn that proposed the action)
    #   - the AI's explanation
    #   - the resolved action params
    #   - which admin approved + when
    #   - the resulting monitor id (if any)
    # Stored as kind="copilot_action" so the next chat's RAG recall pulls it.
    if final_status == "executed":
        try:
            from . import vector_memory_service
            user_turn = ""
            ai_turn = ""
            if action.get("session_id"):
                last_messages = await db.ai_copilot_messages.find(
                    {"session_id": action["session_id"]}, {"_id": 0}
                ).sort("created_at", -1).limit(4).to_list(length=4)
                for m in last_messages:
                    if m.get("role") == "user" and not user_turn:
                        user_turn = m.get("content", "")
                    elif m.get("role") == "assistant" and not ai_turn:
                        ai_turn = m.get("content", "")

            created_monitor = (result.get("created_monitor") or {})
            monitor_id = created_monitor.get("id") or params.get("monitor_id") or ""
            monitor_url = created_monitor.get("url") or params.get("url") or ""
            monitor_name = created_monitor.get("name") or params.get("name") or ""

            # Compose the rationale paragraph that will be embedded
            rationale_parts = [
                f"AI Copilot action executed: {atype}.",
                f"User request: {user_turn[:400]}" if user_turn else "",
                f"AI explanation: {ai_turn[:400]}" if ai_turn else "",
                f"Summary: {action.get('summary', '')}" if action.get("summary") else "",
                f"Resulting monitor: {monitor_name} ({monitor_url}) id={monitor_id}" if monitor_id else "",
                f"Approved by {admin_user.get('email', '')} on {now}.",
                f"Key params: interval={params.get('interval')}s, "
                f"timeout={params.get('timeout')}s, "
                f"method={params.get('method', 'GET')}, "
                f"expected_status={params.get('expected_status', 200)}, "
                f"assertions={len(params.get('assertions') or [])}",
            ]
            rationale = "\n".join([p for p in rationale_parts if p])

            await vector_memory_service.remember(
                text=rationale,
                kind="copilot_action",
                user_id=action.get("user_id"),
                session_id=action.get("session_id"),
                source_id=action_id,
                metadata={
                    "action_type": atype,
                    "monitor_id": monitor_id,
                    "monitor_url": monitor_url,
                    "monitor_name": monitor_name,
                    "approved_by": admin_user.get("email", ""),
                    "params_snapshot": {k: v for k, v in params.items()
                                        if k in ("url", "method", "interval", "timeout",
                                                 "expected_status", "regions",
                                                 "consecutive_failures",
                                                 "max_response_time_ms")},
                },
            )
            logger.info("Vector memory persisted for copilot action %s (monitor=%s)",
                        action_id, monitor_id)
        except Exception as e:
            logger.warning("Vector memory persist for copilot action failed: %s", e)

    return await get_action(action_id)
