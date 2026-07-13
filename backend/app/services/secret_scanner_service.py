"""
FalconOps AI - Secret Exposure Scanner
Real regex + entropy-based scanning of ingested text (logs/events) for leaked
credentials. Matches are always masked before persistence/dispatch — this service
never stores or forwards a live secret value.
"""
import re
import math
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private_key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")),
]

_GENERIC_TOKEN_RE = re.compile(r"[A-Za-z0-9+/_=-]{24,}")
ENTROPY_THRESHOLD = 4.0


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def scan_text_for_secrets(text: str) -> List[Dict]:
    """Scan free text for likely-leaked secrets. Returns masked matches only — never
    the raw secret value — so a hit is safe to persist/dispatch/log downstream."""
    if not text:
        return []
    findings: List[Dict] = []
    matched_spans: List[tuple] = []

    for secret_type, pattern in SECRET_PATTERNS:
        for m in pattern.finditer(text):
            findings.append({
                "type": secret_type,
                "masked_value": _mask(m.group(0)),
                "position": m.start(),
            })
            matched_spans.append((m.start(), m.end()))

    for m in _GENERIC_TOKEN_RE.finditer(text):
        span = (m.start(), m.end())
        if any(a <= span[0] < b or a < span[1] <= b for a, b in matched_spans):
            continue  # already matched by a specific pattern above
        candidate = m.group(0)
        if _shannon_entropy(candidate) >= ENTROPY_THRESHOLD:
            findings.append({
                "type": "high_entropy_token",
                "masked_value": _mask(candidate),
                "position": m.start(),
            })

    return findings
