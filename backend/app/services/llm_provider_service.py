"""
FalconOps AI — Pluggable LLM Provider
Replaces hard-coded Emergent LLM Key dependency with a swappable provider.

Supported providers (in order of preference):
  1. ollama       — local self-hosted (FREE, on-prem, no API cost)  ← DEFAULT for on-prem
  2. openai       — user-supplied OPENAI_API_KEY
  3. anthropic    — user-supplied ANTHROPIC_API_KEY
  4. gemini       — user-supplied GOOGLE_API_KEY
  5. emergent     — Emergent Universal LLM Key (legacy, costs credits)
  6. rule_based   — no LLM, returns templated responses (always works, limited)

Provider is resolved at request time from:
  - Admin Console → AI Copilot tab → provider field (highest priority)
  - LLM_PROVIDER env var
  - Auto-detect: ollama if reachable on http://localhost:11434, else emergent if EMERGENT_LLM_KEY set
  - Fallback: rule_based

AI Monitoring coverage (env AI_MONITORING_FULL_EVAL_SAMPLE_RATE, default 0.05): every call gets the
cheap statistical/regex agents (cost, performance, PII, drift). A sampled fraction additionally gets
the 5 LLM-judged agents (hallucination, injection, quality, toxicity, policy) + root-cause — full
LLM-judge coverage on every call would multiply LLM spend, so it's sampled rather than blanket.
"""
import os
import json
import logging
import random
from typing import Dict, List, Optional, AsyncIterable

import httpx

logger = logging.getLogger(__name__)

# See module docstring above — bounds the cost of the 5 LLM-judged AI Monitoring agents.
AI_MONITORING_FULL_EVAL_SAMPLE_RATE = float(os.environ.get("AI_MONITORING_FULL_EVAL_SAMPLE_RATE", "0.05"))


# ─────────────────────────────────────────────────────
#  Provider implementations
# ─────────────────────────────────────────────────────

async def _chat_ollama(messages: List[Dict], model: str, base_url: str) -> tuple:
    """Call a local Ollama instance. Default base_url=http://localhost:11434.
    Returns (text, usage) — Ollama reports real prompt_eval_count/eval_count
    per non-streaming response, so this is real usage, not an estimate."""
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.4}}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        text = (data.get("message") or {}).get("content", "") or ""
        in_tok, out_tok = data.get("prompt_eval_count"), data.get("eval_count")
        usage = {"input_tokens": in_tok, "output_tokens": out_tok, "total_tokens": (in_tok or 0) + (out_tok or 0)} \
            if in_tok is not None or out_tok is not None else None
        return text, usage


async def _chat_openai(messages: List[Dict], model: str, api_key: str) -> tuple:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": 0.4}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage") or {}
        usage = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                  "total_tokens": u.get("total_tokens")} if u else None
        return text, usage


async def _chat_anthropic(messages: List[Dict], model: str, api_key: str) -> tuple:
    url = "https://api.anthropic.com/v1/messages"
    # Anthropic separates system from messages
    sys_text = next((m["content"] for m in messages if m["role"] == "system"), None)
    convo = [m for m in messages if m["role"] != "system"]
    payload = {"model": model, "max_tokens": 2048, "messages": convo}
    if sys_text:
        payload["system"] = sys_text
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        text = data["content"][0]["text"]
        u = data.get("usage") or {}
        usage = {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
                  "total_tokens": (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)} if u else None
        return text, usage


async def _chat_gemini(messages: List[Dict], model: str, api_key: str) -> tuple:
    sys_text = next((m["content"] for m in messages if m["role"] == "system"), None)
    convo = [m for m in messages if m["role"] != "system"]
    contents = []
    for m in convo:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {"contents": contents, "generationConfig": {"temperature": 0.4}}
    if sys_text:
        payload["systemInstruction"] = {"parts": [{"text": sys_text}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        u = data.get("usageMetadata") or {}
        usage = {"input_tokens": u.get("promptTokenCount"), "output_tokens": u.get("candidatesTokenCount"),
                  "total_tokens": u.get("totalTokenCount")} if u else None
        return text, usage


async def _chat_emergent(messages: List[Dict], model: str, api_key: str, session_id: str) -> str:
    """Legacy Emergent path via emergentintegrations library."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    sys_text = next((m["content"] for m in messages if m["role"] == "system"), "")
    convo = [m for m in messages if m["role"] != "system"]
    # Compress history into a single user message (Emergent library limitation)
    parts = []
    for m in convo[:-1]:
        prefix = "User" if m["role"] == "user" else "Assistant"
        parts.append(f"{prefix}: {m['content']}")
    last_user = convo[-1]["content"] if convo else ""
    if parts:
        combined = "Prior conversation:\n" + "\n".join(parts) + f"\n\nCurrent user message:\n{last_user}"
    else:
        combined = last_user
    chat = LlmChat(api_key=api_key, session_id=session_id, system_message=sys_text)
    # Map model id → (provider, name)
    if "claude" in model.lower():
        chat = chat.with_model("anthropic", model)
    elif "gemini" in model.lower():
        chat = chat.with_model("google", model)
    else:
        chat = chat.with_model("openai", model)
    return await chat.send_message(UserMessage(text=combined))


def _chat_rule_based(messages: List[Dict]) -> str:
    """Last-resort: parse the user's request with regex and emit a templated response.
    Useful for offline / disabled-LLM mode. Recognises basic 'monitor X' requests."""
    import re
    user_text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    user_lower = user_text.lower()

    url_match = re.search(r"https?://[^\s'\"]+", user_text)
    interval_match = re.search(r"(\d+)\s*(?:s|sec|seconds|m|min|minutes)", user_lower)

    if "monitor" in user_lower and url_match:
        url = url_match.group(0)
        interval_sec = int(interval_match.group(1)) if interval_match else 60
        if interval_match and ("m" in interval_match.group(0) or "min" in interval_match.group(0)):
            interval_sec *= 60

        action_json = {
            "action": "create_url_monitor",
            "summary": f"Create a monitor for {url} every {interval_sec}s",
            "params": {
                "name": f"Monitor for {url[:60]}",
                "url": url,
                "method": "GET",
                "interval": interval_sec,
                "timeout": 10,
                "expected_status": 200,
                "regions": ["us-east"],
                "consecutive_failures": 2,
            },
        }
        return (
            "I've drafted a monitor for that URL. Note: I'm running in **rule-based mode** "
            "(no LLM provider configured). For richer responses, configure Ollama or an API key "
            "in Admin → Control Console → AI Copilot.\n\n"
            f"```json\n{json.dumps(action_json, indent=2)}\n```"
        )

    return (
        "I'm currently running in rule-based mode (no LLM provider configured). I can still help "
        "with simple monitor-creation requests like:\n\n"
        "  • *“Monitor https://api.example.com/health every 60 seconds”*\n"
        "  • *“Monitor https://my-site.com every 5 min”*\n\n"
        "For natural-language understanding and incident triage, configure a provider in "
        "**Admin → Control Console → AI Copilot**:\n"
        "  • **Ollama** (free, local, on-prem) — recommended for self-hosted setups\n"
        "  • **OpenAI / Anthropic / Gemini** — bring your own API key\n"
        "  • **Emergent** — universal credit-based key"
    )


# ─────────────────────────────────────────────────────
#  Provider resolution + main entry
# ─────────────────────────────────────────────────────

DEFAULT_MODELS = {
    "ollama":    "llama3.1:8b",
    "openai":    "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini":    "gemini-1.5-flash",
    "emergent":  "claude-sonnet-4-5-20250929",
}


async def _ollama_reachable(base_url: str = "http://localhost:11434") -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{base_url.rstrip('/')}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


async def resolve_provider() -> Dict:
    """Determine which provider + model + api_key to use right now."""
    # 1. Admin Console override (highest priority)
    try:
        from .feature_flags_service import get_ai_copilot_config
        ai = await get_ai_copilot_config()
        provider = (ai.get("provider") or "").lower().strip() or None
        model = ai.get("model")
        ollama_url = ai.get("ollama_base_url") or os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434"
    except Exception:
        provider, model = None, None
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    # 2. Env var
    if not provider:
        provider = (os.environ.get("LLM_PROVIDER") or "").lower().strip() or None

    # 3. Auto-detect
    if not provider:
        if await _ollama_reachable(ollama_url):
            provider = "ollama"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        elif os.environ.get("GOOGLE_API_KEY"):
            provider = "gemini"
        elif os.environ.get("EMERGENT_LLM_KEY"):
            provider = "emergent"
        else:
            provider = "rule_based"

    # Default model if not set
    if not model:
        model = DEFAULT_MODELS.get(provider, "")

    # API key resolution
    api_key = None
    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    elif provider == "gemini":
        api_key = os.environ.get("GOOGLE_API_KEY")
    elif provider == "emergent":
        api_key = os.environ.get("EMERGENT_LLM_KEY")

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
        "ollama_base_url": ollama_url,
        "available": provider == "rule_based" or provider == "ollama" or bool(api_key),
    }


def _prompt_hash(messages: List[Dict]) -> Optional[str]:
    """Short hash of the system-role message content — lets a stored AI output be
    traced back to which prompt version produced it (see ai_monitoring_events'
    prompt_hash field). Only the system prompt: that's what changes when an
    engineer edits agent behavior, while user/assistant turns vary per-call by
    design — hashing those too would make every call's hash unique, defeating
    the point (grouping outputs by prompt version). None if there's no system
    message to hash."""
    import hashlib
    sys_text = next((m.get("content", "") for m in messages if m.get("role") == "system"), None)
    if not sys_text:
        return None
    return hashlib.sha256(sys_text.encode("utf-8")).hexdigest()[:16]


async def chat_completion(messages: List[Dict], session_id: Optional[str] = None) -> Dict:
    """Main entry: send a chat completion via the configured provider.

    messages: list of {role: 'system'|'user'|'assistant', content: str}
    Returns: {provider, model, response, fallback_used, blocked?, prompt_hash}
    """
    import time as _time
    cfg = await resolve_provider()
    provider, model, key = cfg["provider"], cfg["model"], cfg["api_key"]
    fallback_used = False
    err_msg: Optional[str] = None
    started = _time.monotonic()
    prompt_hash = _prompt_hash(messages)

    # ─── PRE-FLIGHT INJECTION GUARD ───
    # Synchronous regex pre-screen on the user-content portion of the messages.
    # If a known injection pattern is matched AND we're not running from inside
    # the monitoring agent itself, we short-circuit BEFORE the LLM call and
    # return a safe refusal. This costs ~0.5ms per call. Free, fast, on by default.
    # Operators can disable via env LLM_PREFLIGHT_INJECTION_BLOCK=false.
    blocked_info = None
    if session_id != "ai-monitor-agent" and os.environ.get(
        "LLM_PREFLIGHT_INJECTION_BLOCK", "true"
    ).lower() not in ("false", "0", "no"):
        try:
            from . import ai_monitoring_service as _aim
            user_blob = "\n".join(
                m.get("content", "") for m in messages if m.get("role") == "user"
            )
            if user_blob and _aim.INJECTION_REGEX.search(user_blob):
                matches = _aim.INJECTION_REGEX.findall(user_blob)
                blocked_info = {
                    "blocked": True,
                    "blocked_reason": "prompt-injection regex matched",
                    "matched_patterns": [
                        (m if isinstance(m, str) else " | ".join(x for x in m if x))[:120]
                        for m in matches[:3]
                    ],
                }
                logger.warning(
                    "Pre-flight injection block — session=%s patterns=%s",
                    session_id, blocked_info["matched_patterns"]
                )
        except Exception as e:
            logger.debug("pre-flight guard skipped: %s", e)

    if blocked_info:
        # Auto-instrument so this attempt shows up on the AI Monitoring dashboard
        try:
            import asyncio as _asyncio
            from . import ai_monitoring_service as _aim
            last_user = next(
                (m["content"] for m in reversed(messages) if m.get("role") == "user"),
                "",
            )
            _asyncio.create_task(_aim.evaluate_exchange(
                user_input=last_user,
                ai_output="[BLOCKED — pre-flight injection guard]",
                latency_ms=(_time.monotonic() - started) * 1000.0,
                errored=False,
                model=model or "",
                provider=provider,
                session_id=session_id,
                source="llm_provider_preflight_block",
                skip_llm_agents=(random.random() >= AI_MONITORING_FULL_EVAL_SAMPLE_RATE),
            ))
        except Exception:
            pass
        return {
            "provider": provider,
            "model": model,
            "response": (
                "I can't process that request — it matches a known prompt-injection "
                "pattern. If this was unintentional, please rephrase without phrases "
                "like 'ignore previous instructions' or attempts to reveal the system prompt."
            ),
            "fallback_used": False,
            **blocked_info,
        }

    # usage stays None unless a provider function returns real token counts —
    # never backfilled with a guess here. See ai_monitoring_service.evaluate_exchange
    # for the character-count estimate used only when this is None.
    usage: Optional[Dict] = None
    try:
        if provider == "ollama":
            text, usage = await _chat_ollama(messages, model, cfg["ollama_base_url"])
        elif provider == "openai" and key:
            text, usage = await _chat_openai(messages, model, key)
        elif provider == "anthropic" and key:
            text, usage = await _chat_anthropic(messages, model, key)
        elif provider == "gemini" and key:
            text, usage = await _chat_gemini(messages, model, key)
        elif provider == "emergent" and key:
            # emergentintegrations doesn't expose the underlying provider's usage
            # object — real usage isn't available on this path, stays estimated.
            text = await _chat_emergent(messages, model, key, session_id or "default")
        else:
            text = _chat_rule_based(messages)
            provider = "rule_based"
    except Exception as e:
        logger.warning("Provider '%s' failed: %s — falling back to rule_based", provider, e)
        text = _chat_rule_based(messages)
        provider = "rule_based"
        fallback_used = True
        err_msg = str(e)[:200]

    latency_ms = (_time.monotonic() - started) * 1000.0

    # ─── Auto-instrument: kick off cheap statistical monitoring on EVERY LLM
    # call. Skipped automatically when called from inside the monitoring agents
    # themselves (session_id == 'ai-monitor-agent') to prevent infinite loops.
    # Fully fire-and-forget — never blocks the caller and never raises.
    if session_id != "ai-monitor-agent":
        try:
            import asyncio as _asyncio
            from . import ai_monitoring_service as _aim
            last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
            _asyncio.create_task(_aim.evaluate_exchange(
                user_input=last_user or "",
                ai_output=text or "",
                latency_ms=latency_ms,
                errored=fallback_used,
                error_message=err_msg,
                model=model or "",
                provider=provider,
                session_id=session_id,
                source="llm_provider_auto",
                # Statistical agents always run; LLM-judged agents + root-cause only on a sampled
                # fraction (AI_MONITORING_FULL_EVAL_SAMPLE_RATE) to bound LLM spend.
                skip_llm_agents=(random.random() >= AI_MONITORING_FULL_EVAL_SAMPLE_RATE),
                usage=usage,
                prompt_hash=prompt_hash,
            ))
        except Exception as _e:
            logger.debug("auto-instrument schedule failed (non-fatal): %s", _e)

    return {
        "provider": provider,
        "model": model if provider != "rule_based" else None,
        "response": text,
        "fallback_used": fallback_used,
        # None unless the provider's API actually reported token usage — never
        # a character-count guess at this layer. See ai_monitoring_service for
        # where the estimate (clearly labeled) is used as a fallback.
        "usage": usage,
        "prompt_hash": prompt_hash,
    }


async def health_check() -> Dict:
    """Used by the Admin Console to show provider status."""
    cfg = await resolve_provider()
    out = {
        "active_provider": cfg["provider"],
        "active_model": cfg["model"],
        "configured": cfg["available"],
        "providers": {
            "ollama":    {"reachable": await _ollama_reachable(cfg["ollama_base_url"]),
                          "base_url": cfg["ollama_base_url"]},
            "openai":    {"key_set": bool(os.environ.get("OPENAI_API_KEY"))},
            "anthropic": {"key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))},
            "gemini":    {"key_set": bool(os.environ.get("GOOGLE_API_KEY"))},
            "emergent":  {"key_set": bool(os.environ.get("EMERGENT_LLM_KEY"))},
            "rule_based":{"always_available": True},
        },
    }
    return out
