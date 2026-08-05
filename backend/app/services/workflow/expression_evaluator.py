"""
Expression evaluator — the workflow engine's ONLY interpreter of conditions
and data-mapping templates. Deliberately does not call eval()/exec()/compile()
anywhere in this file, and never will: resolve_template() does dot-path
dict/list lookups only (no function calls, no attribute access beyond
indexing), and evaluate_condition() walks a structured JSON tree the
frontend's ConditionBuilder.js produces (never a free-text expression
string) against a fixed comparison-operator table.

This is the concrete enforcement point for the workflow spec's own "no
arbitrary code execution" requirement, applied to conditions/templating the
same way tool_binding_dispatch.py applies it to tool execution.
"""
import operator
import re
from typing import Any, Dict, List, Optional, Union

_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.\[\]]+)\s*\}\}")

_OPERATORS = {
    ">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le,
    "==": operator.eq, "!=": operator.ne,
    "contains": lambda a, b: (b in a) if a is not None else False,
    "not_contains": lambda a, b: (b not in a) if a is not None else True,
}


def _resolve_path(path: str, context: Dict[str, Any]) -> Any:
    """Dot-path lookup only — 'node_id.output.field' or 'trigger.service'.
    No function calls, no attribute access beyond dict-key/list-index
    resolution. Returns None (never raises) when a segment is missing, so a
    condition referencing an upstream node that hasn't run yet degrades to
    "falsy" rather than crashing the walk."""
    current: Any = context
    for segment in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(segment)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def resolve_template(template: str, context: Dict[str, Any]) -> Any:
    """Resolves '{{node_id.output.path}}' style templates. If the entire
    string is exactly one '{{...}}' expression, returns the resolved value
    with its native type preserved (so a Condition comparing a number works).
    Otherwise does string substitution (multiple/partial placeholders)."""
    if template is None:
        return None
    matches = _TEMPLATE_RE.findall(template)
    if not matches:
        return template
    if len(matches) == 1 and template.strip() == f"{{{{{matches[0]}}}}}":
        return _resolve_path(matches[0], context)

    def _sub(m: "re.Match") -> str:
        value = _resolve_path(m.group(1), context)
        return "" if value is None else str(value)

    return _TEMPLATE_RE.sub(_sub, template)


def _resolve_leaf(value: Any, context: Dict[str, Any]) -> Any:
    if isinstance(value, str) and _TEMPLATE_RE.search(value):
        return resolve_template(value, context)
    return value


def evaluate_condition(expr: Optional[Dict[str, Any]], context: Dict[str, Any]) -> bool:
    """Walks a structured condition tree:
      {"op": "AND"|"OR", "terms": [<expr>, ...]}
      {"op": "NOT", "terms": [<expr>]}
      {"op": ">"|"<"|">="|"<="|"=="|"!="|"contains"|"not_contains",
       "left": "{{...}}"|literal, "right": "{{...}}"|literal}
    Never evaluates a raw string. An empty/None expr is treated as True
    (an unconfigured Condition node passes through rather than silently
    blocking the graph)."""
    if not expr:
        return True

    op = expr.get("op")
    if op in ("AND", "OR", "NOT"):
        terms: List[Dict[str, Any]] = expr.get("terms", [])
        results = [evaluate_condition(t, context) for t in terms]
        if op == "AND":
            return all(results) if results else True
        if op == "OR":
            return any(results) if results else False
        if op == "NOT":
            return not (results[0] if results else False)

    comparator = _OPERATORS.get(op)
    if comparator is None:
        return False

    left = _resolve_leaf(expr.get("left"), context)
    right = _resolve_leaf(expr.get("right"), context)
    left, right = _coerce_numeric_pair(left, right)
    try:
        return bool(comparator(left, right))
    except TypeError:
        return False


def _coerce_numeric_pair(left: Any, right: Any) -> "tuple[Any, Any]":
    """A '{{...}}' resolved value is often a string ("42") compared against a
    literal number typed in the ConditionBuilder UI (42) — coerce both sides
    to float when they both look numeric, otherwise leave as-is (string/bool
    comparisons still work via ==/!=)."""
    def _as_number(v: Any) -> Union[float, None]:
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return None

    ln, rn = _as_number(left), _as_number(right)
    if ln is not None and rn is not None:
        return ln, rn
    return left, right


__all__ = ["resolve_template", "evaluate_condition"]
