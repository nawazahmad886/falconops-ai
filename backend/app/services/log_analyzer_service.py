"""
FalconOps AI — AI Log Analyzer Service
=========================================
Senior-AI-Architect-grade log triage pipeline:

  raw text → clean → deduplicate → prioritize → chunk → LLM → structured verdict

Stages:
  1. clean_logs()        Strip ANSI/whitespace, drop empty lines, normalize timestamps.
  2. prioritize_lines()  Push ERROR/WARN/FATAL/CRITICAL/Exception lines to the front;
                         drop INFO/DEBUG when the input is too large.
  3. chunk_logs()        Token-budgeted chunking (~3000 tokens / chunk by default).
  4. _call_llm()         One prompt per chunk → structured JSON verdict.
  5. merge_verdicts()    Fuse multi-chunk verdicts into a single result.
  6. Mongo TTL cache     SHA-256 of normalized input → cached verdict for 24 h.

All public functions are async. Failures never raise — they return a structured
error envelope that the route can surface to the UI.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..core.database import db
from .llm_provider_service import chat_completion

logger = logging.getLogger(__name__)

# Severity priority for merging
SEV_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
SEV_LABELS = list(SEV_ORDER.keys())

# Regex catalogue — used for cheap pre-screen / line prioritization
_LEVEL_RE = re.compile(
    r"\b(FATAL|CRITICAL|ERROR|EXCEPTION|TRACEBACK|WARN(?:ING)?|SEVERE|PANIC|EMERG)\b",
    re.IGNORECASE,
)
_INFO_RE  = re.compile(r"\b(INFO|DEBUG|TRACE|VERBOSE|NOTICE)\b", re.IGNORECASE)
_TS_RE    = re.compile(
    r"^\s*"
    r"(?:\[?"
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+\-]\d{2}:?\d{2})?"
    r"\]?)\s*"
)
_ANSI_RE  = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Approx tokens per char (English-ish text). Conservative for safety.
_CHARS_PER_TOKEN = 3.6


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — Clean
# ─────────────────────────────────────────────────────────────────────────────

def clean_logs(raw: str) -> List[str]:
    """Strip noise → return one cleaned line per log entry."""
    if not raw:
        return []
    text = _ANSI_RE.sub("", raw)
    out: List[str] = []
    seen: set = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Collapse exact duplicates while preserving order
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def extract_timestamps(lines: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return (earliest, latest) ISO timestamp strings found in the lines, or (None, None)."""
    ts: List[str] = []
    for line in lines[:5000]:  # cap scan
        m = _TS_RE.search(line)
        if m:
            ts.append(m.group(0).strip("[] "))
    if not ts:
        return None, None
    ts.sort()
    return ts[0], ts[-1]


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — Prioritize
# ─────────────────────────────────────────────────────────────────────────────

def prioritize_lines(lines: List[str], *, max_lines: int = 600) -> List[str]:
    """Sort error/warning lines to the front; drop INFO/DEBUG when oversize."""
    errors: List[str] = []
    warns:  List[str] = []
    info:   List[str] = []
    other:  List[str] = []
    for line in lines:
        if _LEVEL_RE.search(line):
            text = line.upper()
            if any(k in text for k in ("FATAL", "CRITICAL", "ERROR", "EXCEPTION",
                                       "TRACEBACK", "PANIC", "EMERG", "SEVERE")):
                errors.append(line)
            else:
                warns.append(line)
        elif _INFO_RE.search(line):
            info.append(line)
        else:
            other.append(line)

    # When over budget → drop INFO/DEBUG entirely
    budget = max_lines
    merged: List[str] = []
    for bucket in (errors, warns, other, info):
        if budget <= 0:
            break
        take = bucket[:budget]
        merged.extend(take)
        budget -= len(take)
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — Chunk
# ─────────────────────────────────────────────────────────────────────────────

def _approx_tokens(s: str) -> int:
    return max(1, int(len(s) / _CHARS_PER_TOKEN))


def chunk_logs(lines: List[str], *, max_tokens_per_chunk: int = 3000) -> List[str]:
    """Group consecutive lines into chunks under ``max_tokens_per_chunk``."""
    if not lines:
        return []
    chunks: List[str] = []
    cur: List[str] = []
    cur_tokens = 0
    for line in lines:
        t = _approx_tokens(line) + 1  # +1 for newline
        if cur and cur_tokens + t > max_tokens_per_chunk:
            chunks.append("\n".join(cur))
            cur, cur_tokens = [], 0
        cur.append(line)
        cur_tokens += t
    if cur:
        chunks.append("\n".join(cur))
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4 — LLM call (single chunk)
# ─────────────────────────────────────────────────────────────────────────────

ANALYZE_SYSTEM = (
    "You are a senior DevOps / SRE engineer triaging production logs. "
    "Be precise, technical, and concise. Always return ONLY a single JSON object. "
    "Never invent log lines that aren't in the input."
)

ANALYZE_PROMPT_TEMPLATE = """Analyze the following logs and return a JSON object with EXACTLY these fields:

{{
  "summary": "<one-paragraph plain-English summary, <= 280 chars>",
  "error_type": "<short label e.g. 'NullPointerException', 'OOMKilled', 'DB Connection Timeout'>",
  "severity": "Low|Medium|High|Critical",
  "root_cause": "<2-4 sentences describing the most likely root cause>",
  "suggested_fix": "<2-4 sentences with a concrete remediation>",
  "recurring_pattern": {{
    "status": true,
    "explanation": "<short — if a pattern repeats, describe it; else 'No recurring pattern detected.'>"
  }},
  "affected_components": ["<service or module name>", "..."],
  "key_lines": ["<verbatim log line you found most important>", "..."]
}}

Rules:
- Use ONLY the logs below as evidence.
- "severity" must be one of: Low, Medium, High, Critical.
- If logs are healthy → severity "Low" and root_cause = "No significant errors detected."
- Output JSON ONLY. No markdown. No prose before/after.

LOGS:
{logs}
"""

EXPLAIN_PROMPT_TEMPLATE = """A user wants a plain-English explanation of this error message:

{error}

{context_block}

Respond with ONLY a JSON object:
{{
  "explanation": "<2-3 paragraphs in plain English>",
  "likely_causes": ["<cause 1>", "<cause 2>", "..."],
  "next_steps": ["<step 1>", "<step 2>", "..."],
  "external_docs_hint": "<one short search query that would help find docs>"
}}
"""


def _parse_json_strict(text: str) -> Optional[Dict[str, Any]]:
    """Try fence-extraction then widest-brace fallback."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidate = fenced.group(1).strip() if fenced else text.strip()
    try:
        d = json.loads(candidate)
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", candidate)
    if m:
        try:
            d = json.loads(m.group(0))
            return d if isinstance(d, dict) else None
        except json.JSONDecodeError:
            return None
    return None


async def _analyze_chunk(chunk: str, *, session_id: str = "log-analyzer") -> Dict[str, Any]:
    """Send one chunk to the LLM and return a parsed verdict dict.
    Always returns a dict — never raises."""
    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM},
        {"role": "user",   "content": ANALYZE_PROMPT_TEMPLATE.format(logs=chunk)},
    ]
    t0 = time.perf_counter()
    try:
        resp = await chat_completion(messages, session_id=session_id)
    except Exception as e:
        logger.warning("log analyzer LLM call failed: %s", e)
        return {
            "summary": "AI provider error — using rule-based fallback.",
            "error_type": "LLM Provider Error",
            "severity": "Medium",
            "root_cause": f"{type(e).__name__}: {str(e)[:240]}",
            "suggested_fix": "Verify Emergent LLM key has budget; retry analysis.",
            "recurring_pattern": {"status": False, "explanation": "Not evaluated due to LLM error."},
            "affected_components": [],
            "key_lines": [],
            "_provider": None,
            "_model": None,
            "_latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "_fallback": True,
        }
    text = (resp.get("response") or "").strip()
    parsed = _parse_json_strict(text) or {}
    # Normalize / defaults
    parsed.setdefault("summary", text[:280] if text else "No summary available.")
    parsed.setdefault("error_type", "Unknown")
    sev = parsed.get("severity", "Medium")
    if sev not in SEV_ORDER:
        sev = "Medium"
    parsed["severity"] = sev
    parsed.setdefault("root_cause", "Not determined.")
    parsed.setdefault("suggested_fix", "Investigate the highlighted lines manually.")
    rec = parsed.get("recurring_pattern") or {}
    if not isinstance(rec, dict):
        rec = {}
    rec.setdefault("status", False)
    rec.setdefault("explanation", "No recurring pattern detected.")
    parsed["recurring_pattern"] = rec
    parsed.setdefault("affected_components", [])
    parsed.setdefault("key_lines", [])
    parsed["_provider"] = resp.get("provider")
    parsed["_model"] = resp.get("model")
    parsed["_latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    parsed["_tokens_in"] = _approx_tokens(messages[0]["content"]) + _approx_tokens(messages[1]["content"])
    parsed["_tokens_out"] = _approx_tokens(text)
    return parsed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5 — Merge verdicts from N chunks → 1 verdict
# ─────────────────────────────────────────────────────────────────────────────

def merge_verdicts(verdicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not verdicts:
        return {
            "summary": "No logs to analyze.",
            "error_type": "None",
            "severity": "Low",
            "root_cause": "Empty input.",
            "suggested_fix": "Paste log lines and click Analyze.",
            "recurring_pattern": {"status": False, "explanation": ""},
            "affected_components": [],
            "key_lines": [],
        }
    if len(verdicts) == 1:
        return verdicts[0]

    # Highest severity wins
    worst = max(verdicts, key=lambda v: SEV_ORDER.get(v.get("severity", "Low"), 0))
    merged: Dict[str, Any] = {
        "severity": worst["severity"],
        "error_type": worst.get("error_type") or "Multiple",
        "root_cause": worst.get("root_cause") or "",
        "suggested_fix": worst.get("suggested_fix") or "",
        "summary": ("Multi-chunk analysis: " + " | ".join(
            (v.get("summary") or "")[:90] for v in verdicts
        ))[:320],
        "recurring_pattern": {
            "status": any(v.get("recurring_pattern", {}).get("status") for v in verdicts),
            "explanation": " ".join(
                (v.get("recurring_pattern", {}).get("explanation") or "")
                for v in verdicts if v.get("recurring_pattern", {}).get("status")
            )[:400] or "No recurring pattern detected.",
        },
        "affected_components": sorted({
            c for v in verdicts for c in (v.get("affected_components") or []) if c
        })[:20],
        "key_lines": [
            ln for v in verdicts for ln in (v.get("key_lines") or [])
        ][:20],
        "_chunks_analyzed": len(verdicts),
    }
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# CACHE (Mongo TTL — 24 h)
# ─────────────────────────────────────────────────────────────────────────────

CACHE_TTL_SECONDS = 24 * 3600
_cache_ttl_ready = False


async def _ensure_cache_ttl() -> None:
    global _cache_ttl_ready
    if _cache_ttl_ready:
        return
    try:
        await db.log_analyzer_cache.create_index(
            "created_at", expireAfterSeconds=CACHE_TTL_SECONDS, name="log_cache_ttl"
        )
        _cache_ttl_ready = True
    except Exception as e:
        logger.debug("ttl index create skipped: %s", e)


def _hash_logs(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip().lower()[:50000]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def _cache_lookup(h: str) -> Optional[Dict[str, Any]]:
    try:
        doc = await db.log_analyzer_cache.find_one({"hash": h}, {"_id": 0})
        return doc.get("result") if doc else None
    except Exception:
        return None


async def _cache_store(h: str, result: Dict[str, Any]) -> None:
    try:
        await db.log_analyzer_cache.update_one(
            {"hash": h},
            {"$set": {
                "hash": h,
                "result": result,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug("cache store skipped: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_logs(
    raw_logs: str,
    *,
    source: str = "manual",
    user_id: Optional[str] = None,
    use_cache: bool = True,
    max_lines: int = 600,
    max_tokens_per_chunk: int = 3000,
) -> Dict[str, Any]:
    """End-to-end pipeline. Returns a dict with the merged verdict + metadata."""
    await _ensure_cache_ttl()
    t0 = time.perf_counter()

    cleaned = clean_logs(raw_logs)
    earliest, latest = extract_timestamps(cleaned)
    if not cleaned:
        verdict = merge_verdicts([])
        verdict.update({
            "line_count": 0, "cached": False, "chunks": 0,
            "pipeline_latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        })
        return verdict

    prioritized = prioritize_lines(cleaned, max_lines=max_lines)
    chunks = chunk_logs(prioritized, max_tokens_per_chunk=max_tokens_per_chunk)
    if not chunks:
        verdict = merge_verdicts([])
        verdict.update({"line_count": len(cleaned), "cached": False, "chunks": 0})
        return verdict

    # Cache key uses the prioritized+joined view (insensitive to whitespace noise)
    cache_text = "\n".join(prioritized)
    cache_hash = _hash_logs(cache_text)
    if use_cache:
        cached = await _cache_lookup(cache_hash)
        if cached:
            cached.update({
                "cached": True,
                "line_count": len(cleaned),
                "chunks": len(chunks),
                "earliest_ts": earliest,
                "latest_ts": latest,
                "pipeline_latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            })
            return cached

    # LLM-analyze every chunk (sequentially — chunks rarely > 3 in practice)
    verdicts: List[Dict[str, Any]] = []
    total_tokens_in = total_tokens_out = 0
    for c in chunks:
        v = await _analyze_chunk(c)
        verdicts.append(v)
        total_tokens_in  += int(v.pop("_tokens_in",  0) or 0)
        total_tokens_out += int(v.pop("_tokens_out", 0) or 0)

    result = merge_verdicts(verdicts)
    # Strip _provider/_model from intermediate, surface from first one
    provider = next((v.get("_provider") for v in verdicts if v.get("_provider")), None)
    model    = next((v.get("_model")    for v in verdicts if v.get("_model")),    None)
    for v in verdicts:
        v.pop("_provider", None)
        v.pop("_model", None)
        v.pop("_latency_ms", None)

    result.update({
        "cached": False,
        "line_count": len(cleaned),
        "chunks": len(chunks),
        "earliest_ts": earliest,
        "latest_ts": latest,
        "tokens_in": total_tokens_in,
        "tokens_out": total_tokens_out,
        "provider": provider,
        "model": model,
        "pipeline_latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    })

    if use_cache:
        await _cache_store(cache_hash, result)
    return result


async def explain_error(error: str, *, context: str = "") -> Dict[str, Any]:
    """The "Explain this error" feature — short, focused LLM call."""
    context_block = f"\nContext (preceding lines):\n{context[:1500]}" if context else ""
    prompt = EXPLAIN_PROMPT_TEMPLATE.format(error=error[:1500], context_block=context_block)
    messages = [
        {"role": "system", "content": "You are a senior SRE. Be precise and brief."},
        {"role": "user", "content": prompt},
    ]
    try:
        resp = await chat_completion(messages, session_id="log-analyzer-explain")
    except Exception as e:
        return {
            "explanation": f"AI provider error: {type(e).__name__}",
            "likely_causes": [],
            "next_steps": ["Check Emergent LLM key budget", "Retry shortly"],
            "external_docs_hint": "",
            "_error": str(e)[:240],
        }
    parsed = _parse_json_strict(resp.get("response") or "") or {}
    parsed.setdefault("explanation", (resp.get("response") or "")[:600])
    parsed.setdefault("likely_causes", [])
    parsed.setdefault("next_steps", [])
    parsed.setdefault("external_docs_hint", "")
    parsed["_provider"] = resp.get("provider")
    parsed["_model"] = resp.get("model")
    return parsed
