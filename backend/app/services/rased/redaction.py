"""
RASED redaction boundary.

Every piece of text RASED sends to an LLM passes through sanitize_for_llm()
first. On well-formed synthetic data this is a no-op by design — Part A's
constraint is that the generator never produces real hostnames, IPs,
endpoints, or identifiers in the first place, so there should be nothing here
to catch. The filter exists anyway, unconditionally, so the boundary is real
and demonstrable rather than a claim resting on "nothing real is connected
upstream." If a real identifier, secret, or PII pattern ever reaches this
module — synthetic data that regressed, a live adapter added later, a copy-
pasted incident description — it gets masked before it leaves the process.
"""
import re
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class RedactionRule:
    name: str
    pattern: "re.Pattern[str]"


@dataclass
class RedactionResult:
    text: str
    redacted: bool
    matched_rules: List[str] = field(default_factory=list)


_RULES: List[RedactionRule] = [
    RedactionRule("ipv4", re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    )),
    RedactionRule("ipv6", re.compile(
        r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b"
    )),
    RedactionRule("fqdn", re.compile(
        r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
        r"(?:com|net|org|io|ai|co|internal|local|corp|prod|dev|gov)\b",
        re.IGNORECASE,
    )),
    RedactionRule("email", re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )),
    RedactionRule("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    RedactionRule("jwt", re.compile(
        r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    )),
    RedactionRule("credential_assignment", re.compile(
        r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"]?"
        r"[A-Za-z0-9\-_./+]{8,}['\"]?"
    )),
    RedactionRule("credit_card", re.compile(
        r"\b(?:\d[ -]?){13,16}\b"
    )),
]


# Rule names that are unambiguously bad to store/display anywhere, regardless of
# context — real secrets/credentials/PII. Distinct from ipv4/ipv6/fqdn, which are
# masked for RASED's use case (nothing may leave the process toward an external
# LLM) but are exactly the operational diagnostic content a monitoring platform's
# own UI needs to show (e.g. ai_monitoring_service's own event log — see its use
# of only_categories below).
SECRET_RULE_NAMES = {"email", "aws_access_key", "jwt", "credential_assignment", "credit_card"}


def redact_text(text: str, only_categories: "set | None" = None) -> RedactionResult:
    """Mask every rule match in text with [REDACTED:<rule_name>].

    only_categories: if given, only rules whose name is in this set run — e.g.
    SECRET_RULE_NAMES for a caller that wants to keep IPs/hostnames visible
    (operationally useful) while still masking credentials. Default (None) runs
    every rule, RASED's original all-or-nothing behavior — unchanged for
    existing callers of sanitize_for_llm()."""
    if not text:
        return RedactionResult(text=text, redacted=False, matched_rules=[])

    matched: List[str] = []
    out = text
    for rule in _RULES:
        if only_categories is not None and rule.name not in only_categories:
            continue
        if rule.pattern.search(out):
            matched.append(rule.name)
            out = rule.pattern.sub(f"[REDACTED:{rule.name}]", out)

    return RedactionResult(text=out, redacted=bool(matched), matched_rules=matched)


def redact_payload(payload: Any) -> Any:
    """Recursively walk a dict/list/str structure, redacting every string
    leaf. Non-string leaves (numbers, bools, None, datetimes) pass through
    untouched — the rules above only ever match against text."""
    if isinstance(payload, str):
        return redact_text(payload).text
    if isinstance(payload, dict):
        return {k: redact_payload(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [redact_payload(item) for item in payload]
    return payload


def sanitize_for_llm(messages: List[dict]) -> List[dict]:
    """The enforced boundary. Every call site that builds an LLM prompt from
    RASED state (evidence summaries, alert descriptions, SOP excerpts) must
    route the message list through this function immediately before it is
    handed to llm_provider_service.chat_completion(). Content is redacted;
    role and any non-string metadata pass through unchanged."""
    sanitized = []
    for message in messages:
        sanitized.append({**message, "content": redact_payload(message.get("content", ""))})
    return sanitized


__all__ = ["RedactionRule", "RedactionResult", "redact_text", "redact_payload", "sanitize_for_llm", "SECRET_RULE_NAMES"]
