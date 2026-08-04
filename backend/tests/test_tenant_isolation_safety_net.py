"""
Tenant-isolation safety net — static scan, not a functional test.

Tenant scoping today is per-route-handler discipline: every route that queries a
per-tenant collection is expected to call build_tenant_query()/filter by tenant_id
itself (see app/utils/auth.py). Nothing structurally prevents a new route from
forgetting to — there's no query-middleware or ORM-level auto-filter. This test is
the safety net for that gap: it parses every route file with Python's `ast` module
and flags any function that queries a tenant-sensitive collection without
`tenant_id` appearing anywhere in that function's source.

This is a heuristic, not a proof — it cannot tell whether a query is CORRECTLY
scoped, only whether tenant_id is mentioned at all in the same function. A route
that references tenant_id for an unrelated reason but still queries unscoped would
pass; a route that's correctly scoped via a helper called elsewhere (no tenant_id
token in this exact function) would false-positive. Treat findings as "worth a
human look," not "definitely broken."

IMPORTANT — this has never been run against the real codebase (no Python
interpreter was available while writing it). Run it once, triage every reported
finding by hand, and populate KNOWN_EXCEPTIONS below for the legitimate ones
(intentional cross-tenant admin/superadmin endpoints, webhook receivers
authenticated a different way, etc.) before relying on this as a CI gate. Until
then it runs in report-only mode (see TENANT_ISOLATION_STRICT below) — it will
never fail the build on its own the first time it's executed, specifically
because an un-triaged first run would likely contain false positives and a
hard-failing brand-new check with unreviewed output is worse than no check: it
either blocks unrelated work or gets disabled and forgotten.
"""
import ast
import os
from pathlib import Path
from typing import List, NamedTuple

import pytest

ROUTES_DIR = Path(__file__).resolve().parent.parent / "app" / "routes"

# Collections that hold per-tenant data — a query against one of these with no
# tenant_id mention in the enclosing function is the pattern this test looks for.
# Deliberately NOT exhaustive of every collection in the app — only the ones a
# cross-tenant leak would actually matter for (customer-visible monitoring data).
TENANT_SENSITIVE_COLLECTIONS = {
    "alerts_engine", "incidents_engine", "metrics_timeseries", "logs",
    "monitors", "db_instances", "servers", "synthetic_monitors",
    "ai_monitoring_events", "topology_nodes", "health_rules",
}

# (file_name, function_name) pairs already reviewed and confirmed intentional —
# e.g. a superadmin cross-tenant report, or a route that scopes via a helper
# function so tenant_id doesn't appear as a literal token in this function's own
# source. Empty until a human triages the first real run (see module docstring).
KNOWN_EXCEPTIONS: set = set()

# Report-only by default — see module docstring for why. Flip via env var once
# KNOWN_EXCEPTIONS has been populated from a real triaged run.
STRICT = os.environ.get("TENANT_ISOLATION_STRICT", "").lower() in ("1", "true", "yes")


class Finding(NamedTuple):
    file: str
    function: str
    collection: str
    line: int


def _scan_file(path: Path) -> List[Finding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []

    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        func_source = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
        if "tenant_id" in func_source:
            continue  # tenant_id mentioned somewhere in this function — assume scoped

        for sub in ast.walk(node):
            # Match db.<collection>.<method>(...) attribute-access chains.
            if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)):
                continue
            method = sub.func
            if not isinstance(method.value, ast.Attribute):
                continue
            collection_attr = method.value
            if not (isinstance(collection_attr.value, ast.Name) and collection_attr.value.id == "db"):
                continue
            collection = collection_attr.attr
            if collection in TENANT_SENSITIVE_COLLECTIONS:
                findings.append(Finding(
                    file=path.name, function=node.name, collection=collection,
                    line=sub.lineno,
                ))
    return findings


def _all_findings() -> List[Finding]:
    if not ROUTES_DIR.exists():
        return []
    out: List[Finding] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        out.extend(_scan_file(path))
    return [f for f in out if (f.file, f.function) not in KNOWN_EXCEPTIONS]


def test_tenant_isolation_safety_net():
    findings = _all_findings()
    if not findings:
        return

    report_lines = [
        f"{f.file}:{f.line} — {f.function}() queries db.{f.collection} without "
        f"tenant_id appearing anywhere in the function"
        for f in findings
    ]
    report = "\n".join(report_lines)

    if STRICT:
        pytest.fail(
            f"{len(findings)} route(s) query a tenant-sensitive collection with no "
            f"tenant_id in scope. Either add tenant scoping or add a reviewed "
            f"(file, function) entry to KNOWN_EXCEPTIONS:\n{report}"
        )
    else:
        print(
            f"\n[tenant-isolation safety net — REPORT ONLY, not failing] "
            f"{len(findings)} finding(s) to triage:\n{report}\n"
            f"Set TENANT_ISOLATION_STRICT=1 to make this blocking once triaged."
        )
