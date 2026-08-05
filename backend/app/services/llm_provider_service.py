"""
FalconOps AI — Pluggable LLM Provider
Replaces hard-coded Emergent LLM Key dependency with a swappable provider.

Supported providers (in order of preference):
  1. ollama       — local self-hosted (FREE, on-prem, no API cost)  ← DEFAULT for on-prem
  2. openai       — user-supplied OPENAI_API_KEY
  3. anthropic    — user-supplied ANTHROPIC_API_KEY
  4. gemini       — user-supplied GOOGLE_API_KEY
  5. azure_openai — user-supplied AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT (+ AZURE_OPENAI_DEPLOYMENT)
  6. bedrock      — AWS credentials (AWS_BEDROCK_ACCESS_KEY_ID/AWS_ACCESS_KEY_ID + secret), via boto3
  7. emergent     — Emergent Universal LLM Key (legacy, costs credits)
  8. rule_based   — no LLM, returns templated responses (always works, limited)

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
        usage = None
        if u:
            # cached_tokens only present when OpenAI's prompt-caching actually
            # applied to this request — absent key means no cache hit, not "unknown".
            cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens")
            usage = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                      "total_tokens": u.get("total_tokens"), "cached_tokens": cached}
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
        usage = None
        if u:
            # Anthropic reports cache_read_input_tokens (tokens served from cache)
            # separately from cache_creation_input_tokens (tokens newly cached this
            # call) — cache_read is the one that represents realized savings.
            cached = u.get("cache_read_input_tokens")
            usage = {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
                      "total_tokens": (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0),
                      "cached_tokens": cached}
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
        usage = None
        if u:
            cached = u.get("cachedContentTokenCount")
            usage = {"input_tokens": u.get("promptTokenCount"), "output_tokens": u.get("candidatesTokenCount"),
                      "total_tokens": u.get("totalTokenCount"), "cached_tokens": cached}
        return text, usage


async def _chat_azure_openai(messages: List[Dict], model: str, api_key: str, endpoint: str, deployment: str,
                              api_version: str = "2024-06-01") -> tuple:
    """Azure OpenAI — same request/response shape as OpenAI's Chat Completions
    API, different URL (per-resource endpoint + named deployment) and auth
    header (api-key, not Bearer). Unverified against a live Azure resource in
    this environment, same disclosed status as every provider integration
    this session — the request/response shape follows Azure's published REST
    API contract exactly."""
    if not endpoint or not deployment:
        raise ValueError("azure openai requires both endpoint and deployment to be configured")
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload = {"messages": messages, "temperature": 0.4}
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage") or {}
        usage = None
        if u:
            cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens")
            usage = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                      "total_tokens": u.get("total_tokens"), "cached_tokens": cached}
        return text, usage


async def _chat_bedrock(messages: List[Dict], model: str, region: str, access_key: str, secret_key: str) -> tuple:
    """AWS Bedrock — uses boto3's bedrock-runtime client (already a project
    dependency; handles SigV4 signing, which a raw httpx call cannot do
    without reimplementing AWS's signing algorithm). boto3 is a synchronous
    SDK, so the actual invoke_model call runs via asyncio.to_thread — same
    pattern rased/actions/adapters/k8s_real.py already uses for kubernetes's
    sync client, so this never blocks the event loop. Uses the Anthropic
    Claude Messages format on Bedrock (model ids like
    'anthropic.claude-3-5-sonnet-20241022-v2:0') since that's the most common
    Bedrock chat model family — a Titan/Llama/Mistral-specific payload shape
    would need its own branch here, not attempted this pass."""
    import asyncio as _asyncio_bedrock
    import boto3

    sys_text = next((m["content"] for m in messages if m["role"] == "system"), None)
    convo = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31", "max_tokens": 2048, "messages": convo,
    }
    if sys_text:
        body["system"] = sys_text

    def _invoke():
        client = boto3.client(
            "bedrock-runtime", region_name=region,
            aws_access_key_id=access_key or None, aws_secret_access_key=secret_key or None,
        )
        response = client.invoke_model(modelId=model, body=json.dumps(body))
        return json.loads(response["body"].read())

    data = await _asyncio_bedrock.to_thread(_invoke)
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    u = data.get("usage") or {}
    usage = None
    if u:
        cached = u.get("cache_read_input_tokens")
        usage = {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
                  "total_tokens": (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0),
                  "cached_tokens": cached}
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
    "azure_openai": "gpt-4o-mini",
    "bedrock":   "anthropic.claude-3-5-sonnet-20241022-v2:0",
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
        elif os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
            provider = "azure_openai"
        elif os.environ.get("AWS_BEDROCK_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID"):
            provider = "bedrock"
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
    elif provider == "azure_openai":
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    elif provider == "bedrock":
        # Falls back to the standard AWS_* env vars (also read by boto3's own
        # default credential chain) if the Bedrock-specific ones aren't set —
        # api_key stays None either way; "available" below checks the
        # bedrock-specific fields, not this generic api_key slot.
        api_key = os.environ.get("AWS_BEDROCK_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID")
    elif provider == "emergent":
        api_key = os.environ.get("EMERGENT_LLM_KEY")

    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    azure_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or model
    aws_region = os.environ.get("AWS_BEDROCK_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
    aws_secret_key = os.environ.get("AWS_BEDROCK_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")

    bedrock_available = provider == "bedrock" and bool(api_key and aws_secret_key)
    azure_available = provider == "azure_openai" and bool(api_key and azure_endpoint and azure_deployment)

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
        "ollama_base_url": ollama_url,
        "azure_endpoint": azure_endpoint,
        "azure_deployment": azure_deployment,
        "aws_region": aws_region,
        "aws_secret_key": aws_secret_key,
        "available": (
            provider == "rule_based" or provider == "ollama"
            or (provider == "azure_openai" and azure_available)
            or (provider == "bedrock" and bedrock_available)
            or (provider not in ("azure_openai", "bedrock") and bool(api_key))
        ),
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


async def chat_completion(
    messages: List[Dict], session_id: Optional[str] = None,
    trace_id: Optional[str] = None, parent_span_id: Optional[str] = None,
) -> Dict:
    """Main entry: send a chat completion via the configured provider.

    messages: list of {role: 'system'|'user'|'assistant', content: str}
    Returns: {provider, model, response, fallback_used, blocked?, prompt_hash, trace_id, span_id}

    trace_id/parent_span_id: OPTIONAL — link this LLM call into an existing
    distributed trace (e.g. a request trace the caller is already inside).
    Every existing caller passes neither, and the call still becomes a real,
    queryable span (trace_id defaults to a fresh id, making it a trace-of-one)
    — this param pair is purely additive, nothing about the default behavior
    for existing callers changes.
    """
    import time as _time
    import uuid as _uuid
    from datetime import datetime as _datetime, timezone as _timezone
    cfg = await resolve_provider()
    provider, model, key = cfg["provider"], cfg["model"], cfg["api_key"]
    fallback_used = False
    err_msg: Optional[str] = None
    started = _time.monotonic()
    started_wall_iso = _datetime.now(_timezone.utc).isoformat()
    prompt_hash = _prompt_hash(messages)
    call_trace_id = trace_id or str(_uuid.uuid4())
    call_span_id = str(_uuid.uuid4())

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
        elif provider == "azure_openai" and key and cfg.get("azure_endpoint"):
            text, usage = await _chat_azure_openai(messages, model, key, cfg["azure_endpoint"], cfg["azure_deployment"])
        elif provider == "bedrock" and key and cfg.get("aws_secret_key"):
            text, usage = await _chat_bedrock(messages, model, cfg["aws_region"], key, cfg["aws_secret_key"])
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

    # ─── Emit this call as a real span, reusing the exact persistence path
    # OneAgent-sourced and direct-OTLP-sourced traces already share
    # (trace_persistence_service.persist_normalized_spans) — an LLM call
    # becomes a real, queryable node in the existing Trace Explorer, and (when
    # parent_span_id links it into a caller's own trace) a real topology edge
    # via that function's already-wired auto_discover_from_traces call.
    # Fire-and-forget, same as the AI-monitoring auto-instrument below — a
    # trace-persistence failure must never slow down or break the LLM call.
    if session_id != "ai-monitor-agent":
        try:
            import asyncio as _asyncio2
            from .trace_persistence_service import persist_normalized_spans
            end_wall_iso = _datetime.now(_timezone.utc).isoformat()
            span = {
                "id": str(_uuid.uuid4()), "trace_id": call_trace_id, "span_id": call_span_id,
                "parent_span_id": parent_span_id, "service": f"llm:{provider}", "operation": model or "unknown",
                "kind": "CLIENT", "start_time": started_wall_iso, "end_time": end_wall_iso,
                "duration_ms": latency_ms, "status": "ERROR" if fallback_used else "OK",
                "exception_type": "provider_fallback" if fallback_used else None,
                "exception_message": err_msg, "attributes": {
                    "llm.provider": provider, "llm.model": model,
                    "llm.tokens.input": (usage or {}).get("input_tokens"),
                    "llm.tokens.output": (usage or {}).get("output_tokens"),
                    "llm.tokens.cached": (usage or {}).get("cached_tokens"),
                }, "resource": {"service.name": f"llm:{provider}"}, "scope": "llm_provider_service",
                "received_at": end_wall_iso,
            }
            _asyncio2.create_task(persist_normalized_spans([span]))
        except Exception as e:
            logger.debug(f"llm call span emit failed (non-fatal): {e}")

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
                trace_id=call_trace_id,
                span_id=call_span_id,
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
        # This call's own span in the distributed trace store — always real,
        # even standalone (see chat_completion's own docstring on trace_id/
        # parent_span_id). Lets a caller open this exact call in Trace Explorer.
        "trace_id": call_trace_id,
        "span_id": call_span_id,
    }


async def chat_completion_stream(
    messages: List[Dict], session_id: Optional[str] = None,
    trace_id: Optional[str] = None, parent_span_id: Optional[str] = None,
):
    """Opt-in streaming variant — nothing in this codebase calls this today;
    it exists for the LLM Observability dashboard's live-request view and any
    future caller that wants token-by-token output. Deliberately separate
    from chat_completion() above so the ~15 existing blocking callers are
    completely unaffected by this addition.

    Implemented for openai/anthropic/ollama only (their streaming wire
    formats — SSE and NDJSON — are stable/standard); gemini/emergent/
    azure_openai/bedrock/rule_based fall back to one non-streaming call
    whose full response is yielded as a single chunk, honestly disclosed via
    streamed=False rather than faked as token-by-token.

    Yields dicts: {"delta": str} zero or more times, then exactly one final
    {"done": True, provider, model, response, usage, ttft_ms, ttlt_ms,
    streamed, trace_id, span_id}. ttft_ms/ttlt_ms are None on the non-
    streaming-fallback path (no per-token timing exists there) — never
    estimated.
    """
    import time as _time
    import uuid as _uuid
    from datetime import datetime as _datetime, timezone as _timezone

    cfg = await resolve_provider()
    provider, model, key = cfg["provider"], cfg["model"], cfg["api_key"]
    call_trace_id = trace_id or str(_uuid.uuid4())
    call_span_id = str(_uuid.uuid4())
    started = _time.monotonic()
    started_wall_iso = _datetime.now(_timezone.utc).isoformat()
    prompt_hash = _prompt_hash(messages)

    ttft_ms: Optional[float] = None
    full_text_parts: List[str] = []
    usage: Optional[Dict] = None
    streamed = provider in ("openai", "anthropic", "ollama") and bool(key or provider == "ollama")
    fallback_used = False
    err_msg: Optional[str] = None

    try:
        if not streamed:
            result = await chat_completion(messages, session_id=session_id, trace_id=call_trace_id, parent_span_id=parent_span_id)
            yield {"delta": result["response"] or ""}
            yield {"done": True, "provider": result["provider"], "model": result["model"],
                   "response": result["response"], "usage": result["usage"],
                   "ttft_ms": None, "ttlt_ms": None, "streamed": False,
                   "trace_id": result["trace_id"], "span_id": result["span_id"]}
            return

        if provider == "openai":
            async for delta in _stream_openai(messages, model, key):
                if isinstance(delta, dict):
                    usage = delta.get("usage")
                    continue
                if ttft_ms is None:
                    ttft_ms = (_time.monotonic() - started) * 1000.0
                full_text_parts.append(delta)
                yield {"delta": delta}
        elif provider == "anthropic":
            async for delta in _stream_anthropic(messages, model, key):
                if isinstance(delta, dict):
                    usage = delta.get("usage")
                    continue
                if ttft_ms is None:
                    ttft_ms = (_time.monotonic() - started) * 1000.0
                full_text_parts.append(delta)
                yield {"delta": delta}
        elif provider == "ollama":
            async for delta in _stream_ollama(messages, model, cfg["ollama_base_url"]):
                if isinstance(delta, dict):
                    usage = delta.get("usage")
                    continue
                if ttft_ms is None:
                    ttft_ms = (_time.monotonic() - started) * 1000.0
                full_text_parts.append(delta)
                yield {"delta": delta}
    except Exception as e:
        logger.warning("Streaming provider '%s' failed: %s", provider, e)
        fallback_used = True
        err_msg = str(e)[:200]

    ttlt_ms = (_time.monotonic() - started) * 1000.0
    text = "".join(full_text_parts)

    if session_id != "ai-monitor-agent":
        try:
            import asyncio as _asyncio3
            from .trace_persistence_service import persist_normalized_spans
            end_wall_iso = _datetime.now(_timezone.utc).isoformat()
            span = {
                "id": str(_uuid.uuid4()), "trace_id": call_trace_id, "span_id": call_span_id,
                "parent_span_id": parent_span_id, "service": f"llm:{provider}", "operation": model or "unknown",
                "kind": "CLIENT", "start_time": started_wall_iso, "end_time": end_wall_iso,
                "duration_ms": ttlt_ms, "status": "ERROR" if fallback_used else "OK",
                "exception_type": "provider_error" if fallback_used else None, "exception_message": err_msg,
                "attributes": {"llm.provider": provider, "llm.model": model, "llm.streamed": True,
                               "llm.ttft_ms": ttft_ms, "llm.tokens.input": (usage or {}).get("input_tokens"),
                               "llm.tokens.output": (usage or {}).get("output_tokens")},
                "resource": {"service.name": f"llm:{provider}"}, "scope": "llm_provider_service",
                "received_at": end_wall_iso,
            }
            _asyncio3.create_task(persist_normalized_spans([span]))
            from . import ai_monitoring_service as _aim
            last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
            _asyncio3.create_task(_aim.evaluate_exchange(
                user_input=last_user or "", ai_output=text, latency_ms=ttlt_ms, errored=fallback_used,
                error_message=err_msg, model=model or "", provider=provider, session_id=session_id,
                source="llm_provider_stream", skip_llm_agents=(random.random() >= AI_MONITORING_FULL_EVAL_SAMPLE_RATE),
                usage=usage, prompt_hash=prompt_hash, trace_id=call_trace_id, span_id=call_span_id,
            ))
        except Exception as e:
            logger.debug(f"stream auto-instrument failed (non-fatal): {e}")

    yield {"done": True, "provider": provider, "model": model, "response": text, "usage": usage,
           "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None, "ttlt_ms": round(ttlt_ms, 1),
           "streamed": True, "trace_id": call_trace_id, "span_id": call_span_id}


async def _stream_openai(messages: List[Dict], model: str, api_key: str):
    """Yields text deltas, then one final dict {"usage": {...}}. Real usage
    only if the API actually returns it (stream_options.include_usage)."""
    url = "https://api.openai.com/v1/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": 0.4, "stream": True,
               "stream_options": {"include_usage": True}}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if obj.get("usage"):
                    u = obj["usage"]
                    yield {"usage": {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                                      "total_tokens": u.get("total_tokens"),
                                      "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens")}}
                    continue
                choices = obj.get("choices") or []
                if choices:
                    delta_text = (choices[0].get("delta") or {}).get("content")
                    if delta_text:
                        yield delta_text


async def _stream_anthropic(messages: List[Dict], model: str, api_key: str):
    """Yields text deltas, then one final dict {"usage": {...}}."""
    url = "https://api.anthropic.com/v1/messages"
    sys_text = next((m["content"] for m in messages if m["role"] == "system"), None)
    convo = [m for m in messages if m["role"] != "system"]
    payload = {"model": model, "max_tokens": 2048, "messages": convo, "stream": True}
    if sys_text:
        payload["system"] = sys_text
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    input_tokens = None
    output_tokens = None
    cached_tokens = None
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    obj = json.loads(line[len("data: "):].strip())
                except (json.JSONDecodeError, ValueError):
                    continue
                event_type = obj.get("type")
                if event_type == "message_start":
                    u = (obj.get("message") or {}).get("usage") or {}
                    input_tokens = u.get("input_tokens")
                    cached_tokens = u.get("cache_read_input_tokens")
                elif event_type == "content_block_delta":
                    delta_text = (obj.get("delta") or {}).get("text")
                    if delta_text:
                        yield delta_text
                elif event_type == "message_delta":
                    u = obj.get("usage") or {}
                    if u.get("output_tokens") is not None:
                        output_tokens = u["output_tokens"]
    if input_tokens is not None or output_tokens is not None:
        yield {"usage": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                          "total_tokens": (input_tokens or 0) + (output_tokens or 0), "cached_tokens": cached_tokens}}


async def _stream_ollama(messages: List[Dict], model: str, base_url: str):
    """NDJSON, not SSE — one JSON object per line, no 'data: ' prefix."""
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {"model": model, "messages": messages, "stream": True, "options": {"temperature": 0.4}}
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta_text = (obj.get("message") or {}).get("content")
                if delta_text:
                    yield delta_text
                if obj.get("done"):
                    in_tok, out_tok = obj.get("prompt_eval_count"), obj.get("eval_count")
                    if in_tok is not None or out_tok is not None:
                        yield {"usage": {"input_tokens": in_tok, "output_tokens": out_tok,
                                          "total_tokens": (in_tok or 0) + (out_tok or 0), "cached_tokens": None}}


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
            "azure_openai": {"key_set": bool(os.environ.get("AZURE_OPENAI_API_KEY")),
                              "endpoint_set": bool(os.environ.get("AZURE_OPENAI_ENDPOINT"))},
            "bedrock":   {"key_set": bool(os.environ.get("AWS_BEDROCK_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID"))},
            "emergent":  {"key_set": bool(os.environ.get("EMERGENT_LLM_KEY"))},
            "rule_based":{"always_available": True},
        },
    }
    return out
