"""
FalconOps AI — Shared Assertion Engine
DRY assertion + variable-substitution + SSL-probe helpers used by:
- URL Monitor (single-shot HTTP)
- Synthetic Monitor multi-step journeys

Lifted from uptime_monitor_service so both modules share the exact same logic.
"""
import re
import ssl
import socket
import json as _json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Default deny patterns auto-applied to catch HTTP-200-with-error-body false-positives.
DEFAULT_BODY_DENY_PATTERNS: List[str] = [
    "internal server error",
    "\"status\":\"error\"",
    "\"status\": \"error\"",
    "\"error\":true",
    "\"error\": true",
    "\"code\":500",
    "\"code\": 500",
    "\"code\":502",
    "\"code\":503",
    "\"code\":504",
    "traceback (most recent call last)",
    "uncaught exception",
]


def build_default_assertions() -> List[Dict]:
    """Return safe-default not_contains assertions (case-insensitive)."""
    return [
        {"type": "not_contains", "value": p, "case_sensitive": False}
        for p in DEFAULT_BODY_DENY_PATTERNS
    ]


def merge_safe_defaults(assertions: Optional[List[Dict]], enable: bool = True) -> List[Dict]:
    """Merge user assertions with safe defaults; dedupe by (type, value)."""
    final = list(assertions or [])
    if not enable:
        return final
    existing = {(a.get("type"), str(a.get("value", "")).lower()) for a in final}
    for default_a in build_default_assertions():
        key = (default_a["type"], str(default_a["value"]).lower())
        if key not in existing:
            final.append(default_a)
    return final


# ─────────────────────────────────────────────────────
#  JSON-path resolver
# ─────────────────────────────────────────────────────

def eval_json_path(body_text: str, path: str) -> Any:
    """Tiny $.a.b.c[0].d JSON-path resolver. Returns the value or sentinel string."""
    try:
        data = _json.loads(body_text)
    except Exception:
        return "<<not-json>>"
    if not path.startswith("$"):
        return "<<bad-path>>"
    parts = [p for p in path.lstrip("$").split(".") if p]
    cur = data
    for p in parts:
        if "[" in p and p.endswith("]"):
            key, idx_str = p.split("[", 1)
            try:
                idx = int(idx_str.rstrip("]"))
            except ValueError:
                return "<<bad-index>>"
            if key:
                cur = cur.get(key) if isinstance(cur, dict) else None
            if isinstance(cur, list) and 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return "<<missing>>"
        else:
            cur = cur.get(p) if isinstance(cur, dict) else None
            if cur is None:
                return "<<missing>>"
    return cur


# ─────────────────────────────────────────────────────
#  Variable substitution (for multi-step journeys)
# ─────────────────────────────────────────────────────

_VAR_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def substitute_vars(value: Any, variables: Dict[str, Any]) -> Any:
    """Replace ${var_name} placeholders in strings / dicts / lists recursively."""
    if isinstance(value, str):
        def _sub(m):
            return str(variables.get(m.group(1), m.group(0)))
        return _VAR_RE.sub(_sub, value)
    if isinstance(value, dict):
        return {k: substitute_vars(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute_vars(v, variables) for v in value]
    return value


def extract_variables(extract_map: Dict[str, str], body_text: str) -> Dict[str, Any]:
    """Resolve a {var_name: $.json.path} map against the response body."""
    out: Dict[str, Any] = {}
    for var_name, path in (extract_map or {}).items():
        value = eval_json_path(body_text, path)
        if isinstance(value, str) and value.startswith("<<"):
            continue
        out[var_name] = value
    return out


# ─────────────────────────────────────────────────────
#  Assertion evaluation
# ─────────────────────────────────────────────────────

def evaluate_assertions(
    assertions: Optional[List[Dict]],
    body_text: str,
    status_code: int,
    response_time_ms: float,
    max_response_time_ms: Optional[int] = None,
) -> List[Dict]:
    """Run all assertions; return list of {type, reason, ...} for FAILED ones. Empty = pass."""
    failures: List[Dict] = []
    body_lower = body_text.lower() if body_text else ""

    for a in assertions or []:
        atype = a.get("type")
        val = a.get("value")
        case_sensitive = a.get("case_sensitive", False)

        if atype == "contains":
            hay = body_text if case_sensitive else body_lower
            needle = val if case_sensitive else (val or "").lower()
            if needle and needle not in hay:
                failures.append({"type": atype, "value": val,
                                 "reason": f"Response body does not contain '{val}'"})
        elif atype == "not_contains":
            hay = body_text if case_sensitive else body_lower
            needle = val if case_sensitive else (val or "").lower()
            if needle and needle in hay:
                failures.append({"type": atype, "value": val,
                                 "reason": f"Response body contains forbidden string '{val}'"})
        elif atype == "json_path_eq":
            path = a.get("path", "$")
            got = eval_json_path(body_text, path)
            if str(got) != str(val):
                failures.append({"type": atype, "path": path, "expected": val, "got": str(got)[:80],
                                 "reason": f"JSON {path}: expected '{val}', got '{str(got)[:80]}'"})
        elif atype == "json_path_neq":
            path = a.get("path", "$")
            got = eval_json_path(body_text, path)
            if str(got) == str(val):
                failures.append({"type": atype, "path": path, "forbidden": val,
                                 "reason": f"JSON {path} equals forbidden value '{val}'"})
        elif atype == "status_in":
            allowed = val if isinstance(val, list) else [val]
            if status_code not in allowed:
                failures.append({"type": atype, "allowed": allowed, "got": status_code,
                                 "reason": f"Status {status_code} not in allowed {allowed}"})

    if max_response_time_ms and response_time_ms > max_response_time_ms:
        failures.append({"type": "max_response_time_ms", "limit": max_response_time_ms,
                         "got": response_time_ms,
                         "reason": f"Response time {response_time_ms}ms exceeds SLA {max_response_time_ms}ms"})

    return failures


# ─────────────────────────────────────────────────────
#  SSL expiry probe
# ─────────────────────────────────────────────────────

def check_ssl_expiry(url: str, warn_days: int = 14) -> Dict:
    """Return {days_remaining, warning, error} for the URL's TLS cert."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return {"days_remaining": None, "warning": False, "error": None}
        host = parsed.hostname
        port = parsed.port or 443
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days = (not_after - datetime.now(timezone.utc)).days
        return {"days_remaining": days, "warning": days < warn_days, "error": None}
    except Exception as e:
        return {"days_remaining": None, "warning": False, "error": str(e)[:120]}
