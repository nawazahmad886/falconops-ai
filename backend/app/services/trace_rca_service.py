"""
FalconOps AI — Trace RCA Service
AI-powered root cause analysis for OpenTelemetry distributed traces.

Capabilities:
  - Slow-span detection      — compares each span's duration to its service+operation baseline.
  - Error-chain propagation  — walks the parent/child tree to find the root error.
  - Hotspot identification   — picks the span(s) consuming the largest share of total wall time.
  - AI summary               — uses the swappable LLM provider to explain the failure in plain English.

This module is deterministic on its statistical part, with the LLM only adding a final
human-readable summary. It works equally well with Ollama, OpenAI, or rule-based fallback.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from ..core.database import db
from . import llm_provider_service

logger = logging.getLogger(__name__)

# Span counts as "slow" when its duration exceeds:
#   max(SLOW_ABS_FLOOR_MS, baseline_avg_ms * SLOW_FACTOR)
SLOW_FACTOR = 2.0
SLOW_ABS_FLOOR_MS = 50.0

# Hotspot = span whose duration is at least HOTSPOT_PCT of the trace's total duration.
HOTSPOT_PCT = 0.30  # 30%

# Baseline window for service+operation.
BASELINE_HOURS = 24
MIN_BASELINE_SAMPLES = 3


# ─────────────────────────────────────────────────────
#  Statistical analysers
# ─────────────────────────────────────────────────────

async def _baseline_for(service: str, operation: str) -> Optional[Dict[str, float]]:
    """Return {avg_ms, p95_ms, samples} from the last BASELINE_HOURS for this service+op."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=BASELINE_HOURS)).isoformat()
    cursor = db.otel_spans.find(
        {"service": service, "operation": operation, "received_at": {"$gte": cutoff}},
        {"_id": 0, "duration_ms": 1},
    ).limit(500)
    durations = [d["duration_ms"] for d in await cursor.to_list(length=500) if d.get("duration_ms") is not None]
    if len(durations) < MIN_BASELINE_SAMPLES:
        return None
    durations.sort()
    p95_index = max(0, int(len(durations) * 0.95) - 1)
    return {
        "avg_ms": round(statistics.mean(durations), 2),
        "p95_ms": round(durations[p95_index], 2),
        "samples": len(durations),
    }


async def _detect_slow_spans(spans: List[Dict]) -> List[Dict]:
    """Annotate each span that is materially slower than its baseline."""
    flagged: List[Dict] = []
    # Cache baselines per (service, operation) within this trace
    cache: Dict[tuple, Optional[Dict]] = {}
    for s in spans:
        key = (s["service"], s["operation"])
        if key not in cache:
            cache[key] = await _baseline_for(*key)
        baseline = cache[key]
        dur = s.get("duration_ms") or 0.0
        if not baseline:
            # No baseline yet — only flag absolute outliers (>1s)
            if dur >= 1000:
                flagged.append({
                    "span_id": s["span_id"],
                    "service": s["service"],
                    "operation": s["operation"],
                    "duration_ms": dur,
                    "baseline": None,
                    "reason": f"{dur:.0f}ms — no historical baseline yet, flagged as absolute outlier (>1s)",
                })
            continue
        threshold = max(SLOW_ABS_FLOOR_MS, baseline["avg_ms"] * SLOW_FACTOR)
        if dur > threshold:
            mult = round(dur / max(baseline["avg_ms"], 1), 1)
            flagged.append({
                "span_id": s["span_id"],
                "service": s["service"],
                "operation": s["operation"],
                "duration_ms": dur,
                "baseline": baseline,
                "reason": f"{dur:.0f}ms vs avg {baseline['avg_ms']:.0f}ms — {mult}× normal (n={baseline['samples']})",
            })
    flagged.sort(key=lambda x: x["duration_ms"], reverse=True)
    return flagged


def _detect_error_chain(spans: List[Dict]) -> List[Dict]:
    """Find the root error span and the chain of error spans descending from it.

    Strategy: collect all ERROR spans, build a parent index, return the chain rooted at
    the most-ancestral ERROR span. If multiple disjoint error trees exist, return them all.
    """
    by_id = {s["span_id"]: s for s in spans}
    errs = [s for s in spans if s.get("status") == "ERROR"]
    if not errs:
        return []

    # An error span is a "root error" if its parent is not in the error set
    # (parent might still be present in the trace but as OK, or absent entirely).
    error_ids = {s["span_id"] for s in errs}
    chains: List[Dict] = []
    for s in errs:
        parent_id = s.get("parent_span_id")
        if parent_id and parent_id in error_ids:
            continue  # not a root error — its parent is also an error
        # Walk descendants that are also errors
        chain_nodes = []
        stack = [s]
        while stack:
            cur = stack.pop()
            chain_nodes.append({
                "span_id": cur["span_id"],
                "service": cur["service"],
                "operation": cur["operation"],
                "duration_ms": cur.get("duration_ms"),
            })
            # Find children
            for c in spans:
                if c.get("parent_span_id") == cur["span_id"] and c.get("status") == "ERROR":
                    stack.append(c)
        # Determine the parent (OK or absent) for context
        parent_context = None
        if parent_id and parent_id in by_id:
            p = by_id[parent_id]
            parent_context = {
                "span_id": p["span_id"],
                "service": p["service"],
                "operation": p["operation"],
                "status": p.get("status"),
            }
        chains.append({
            "root": chain_nodes[0],
            "chain": chain_nodes,
            "depth": len(chain_nodes),
            "triggered_by_parent": parent_context,
        })
    return chains


def _detect_hotspots(spans: List[Dict], total_duration_ms: float) -> List[Dict]:
    """Spans consuming a large share of the trace's total wall time."""
    if total_duration_ms <= 0:
        return []
    hot = []
    for s in spans:
        dur = s.get("duration_ms") or 0
        share = dur / total_duration_ms
        if share >= HOTSPOT_PCT:
            hot.append({
                "span_id": s["span_id"],
                "service": s["service"],
                "operation": s["operation"],
                "duration_ms": dur,
                "share_pct": round(share * 100, 1),
            })
    hot.sort(key=lambda x: x["share_pct"], reverse=True)
    return hot


# ─────────────────────────────────────────────────────
#  AI summary
# ─────────────────────────────────────────────────────

def _build_ai_prompt(trace: Dict, slow: List[Dict], errors: List[Dict], hotspots: List[Dict]) -> List[Dict]:
    services = trace.get("services") or []
    parts = [
        f"Trace ID: {trace.get('trace_id')}",
        f"Root: {trace.get('root_service')} · {trace.get('root_operation')}",
        f"Status: {trace.get('status')} · Total duration: {trace.get('duration_ms', 0):.1f} ms",
        f"Services involved ({len(services)}): {', '.join(services) or 'n/a'}",
        f"Span count: {trace.get('span_count')} · Errors: {trace.get('error_count')}",
        "",
    ]
    if errors:
        parts.append("ERROR SPANS:")
        for e in errors:
            root = e["root"]
            parent = e.get("triggered_by_parent")
            parents_txt = f" (called by {parent['service']}.{parent['operation']} status={parent['status']})" if parent else ""
            parts.append(f"  - {root['service']}.{root['operation']} → cascaded to {len(e['chain'])} child error span(s){parents_txt}")
        parts.append("")
    if slow:
        parts.append("SLOW SPANS (vs 24h baseline):")
        for s in slow[:10]:
            parts.append(f"  - {s['service']}.{s['operation']}: {s['reason']}")
        parts.append("")
    if hotspots:
        parts.append("HOTSPOTS (% of total trace wall time):")
        for h in hotspots[:5]:
            parts.append(f"  - {h['service']}.{h['operation']}: {h['duration_ms']:.0f}ms ({h['share_pct']}%)")
        parts.append("")
    parts.append("Write a concise root-cause analysis (max 6 bullet points, no markdown headers): "
                 "(1) one-sentence verdict, (2) most likely root cause, (3) evidence pointing to it, "
                 "(4) blast radius, (5) immediate mitigation, (6) longer-term fix. "
                 "Keep each bullet under 30 words.")
    return [
        {"role": "system", "content": "You are a Senior SRE diagnosing a distributed trace. Be specific, concise, and evidence-based."},
        {"role": "user", "content": "\n".join(parts)},
    ]


def _rule_based_summary(trace: Dict, slow: List[Dict], errors: List[Dict], hotspots: List[Dict]) -> str:
    """Deterministic fallback when LLM is unavailable."""
    bullets = []
    if errors:
        root = errors[0]["root"]
        bullets.append(f"Verdict: trace failed — {root['service']}.{root['operation']} returned ERROR")
        if errors[0].get("triggered_by_parent"):
            p = errors[0]["triggered_by_parent"]
            bullets.append(f"Likely root cause: failure originated in {root['service']} after being called from {p['service']}.{p['operation']}")
        else:
            bullets.append(f"Likely root cause: {root['service']} appears to be the originating point of failure")
        bullets.append(f"Evidence: {len(errors[0]['chain'])} error span(s) in the chain (depth={errors[0]['depth']})")
    elif slow:
        s = slow[0]
        bullets.append(f"Verdict: trace completed but is materially slow — {s['service']}.{s['operation']} dominates")
        bullets.append(f"Likely root cause: {s['reason']}")
        bullets.append("Evidence: see slow-span details above")
    else:
        bullets.append("Verdict: trace looks healthy — no errors, no spans materially slower than baseline")
        bullets.append("No action required")
        return "\n".join(f"- {b}" for b in bullets)

    # Blast radius
    services = trace.get("services") or []
    bullets.append(f"Blast radius: {len(services)} service(s) traversed — {', '.join(services[:5])}")

    # Mitigation
    if hotspots:
        h = hotspots[0]
        bullets.append(f"Immediate mitigation: investigate {h['service']}.{h['operation']} (consumes {h['share_pct']}% of total time)")
    elif errors:
        bullets.append("Immediate mitigation: roll back the most recent deploy of the originating service or scale it horizontally")
    else:
        bullets.append("Immediate mitigation: check capacity / DB locks on the slow service")

    # Long-term
    bullets.append("Longer-term fix: add caching / async processing / circuit breaker around the offending operation, and a per-operation latency SLO")

    return "\n".join(f"- {b}" for b in bullets)


async def _ai_summary(trace: Dict, slow: List[Dict], errors: List[Dict], hotspots: List[Dict]) -> Dict:
    """Generate the AI-written RCA summary. Always returns a string; uses rule-based fallback on any error."""
    fallback_text = _rule_based_summary(trace, slow, errors, hotspots)
    try:
        resp = await llm_provider_service.chat_completion(
            _build_ai_prompt(trace, slow, errors, hotspots),
            session_id=f"trace-rca-{trace.get('trace_id', 'unknown')}",
        )
        text = (resp.get("response") or "").strip()
        if not text or len(text) < 30:
            return {"text": fallback_text, "provider": "rule_based", "used_llm": False}
        return {
            "text": text,
            "provider": resp.get("provider"),
            "model": resp.get("model"),
            "used_llm": resp.get("provider") != "rule_based",
            "fallback_used": resp.get("fallback_used", False),
        }
    except Exception as e:
        logger.warning("Trace RCA AI summary failed, using rule-based: %s", e)
        return {"text": fallback_text, "provider": "rule_based", "used_llm": False}


# ─────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────

async def analyze_window(hours: int = 24, max_traces: int = 50) -> Dict[str, Any]:
    """Bulk anomaly analysis across the trace window.

    Strategy:
      1. Pull all error traces in the window
      2. Pull the top-N slowest non-error traces (≥ p95 of window)
      3. Group spans by (service, operation) and compute:
           - error_count, error_rate
           - avg_duration, p95_duration
           - sample trace_ids
      4. Rank groups by error_rate desc, then p95_duration desc — top 10
      5. AI summary explains the top anomalies in plain English

    Returns a JSON dashboard payload, NOT a per-trace report.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    # All traces in window — filter on received_at (server clock) to mirror /api/traces
    # so historical/skewed app clocks don't drop recent ingests.
    all_traces = await db.otel_traces.find(
        {"$or": [{"received_at": {"$gte": cutoff}}, {"start_time": {"$gte": cutoff}}]},
        {"_id": 0},
    ).to_list(length=10000)

    error_traces = [t for t in all_traces if t.get("status") == "ERROR"]
    durations = sorted([t.get("duration_ms") or 0 for t in all_traces])
    p95 = durations[max(0, int(len(durations) * 0.95) - 1)] if durations else 0

    slow_traces = sorted(
        [t for t in all_traces if (t.get("duration_ms") or 0) >= p95 and t.get("status") != "ERROR"],
        key=lambda x: x.get("duration_ms") or 0,
        reverse=True,
    )[:max_traces]

    # Sample spans for the anomalous traces — cap the join to keep query small
    sample_ids = list({t["trace_id"] for t in error_traces + slow_traces})[:max_traces]
    spans = await db.otel_spans.find(
        {"trace_id": {"$in": sample_ids}},
        {"_id": 0},
    ).to_list(length=10000)

    # Group by (service, operation)
    groups: Dict[tuple, Dict[str, Any]] = {}
    for s in spans:
        key = (s["service"], s["operation"])
        g = groups.setdefault(key, {
            "service": s["service"],
            "operation": s["operation"],
            "trace_ids": set(),
            "error_count": 0,
            "total_count": 0,
            "durations": [],
        })
        g["trace_ids"].add(s["trace_id"])
        g["total_count"] += 1
        g["durations"].append(s.get("duration_ms") or 0.0)
        if s.get("status") == "ERROR":
            g["error_count"] += 1

    ranked = []
    for (svc, op), g in groups.items():
        durs = sorted(g["durations"])
        n = len(durs)
        g_p95 = durs[max(0, int(n * 0.95) - 1)] if durs else 0
        g_avg = (sum(durs) / n) if n else 0
        ranked.append({
            "service": svc,
            "operation": op,
            "samples": n,
            "error_count": g["error_count"],
            "error_rate_pct": round(g["error_count"] * 100.0 / n, 2) if n else 0,
            "avg_duration_ms": round(g_avg, 2),
            "p95_duration_ms": round(g_p95, 2),
            "sample_trace_ids": list(g["trace_ids"])[:5],
        })
    ranked.sort(
        key=lambda r: (r["error_rate_pct"], r["p95_duration_ms"]),
        reverse=True,
    )
    anomalies = ranked[:10]

    # AI summary
    services_in_play = sorted({a["service"] for a in anomalies})
    summary_prompt = [
        {"role": "system", "content": "You are a Senior SRE summarising a distributed-trace anomaly report."},
        {"role": "user", "content": (
            f"Time window: last {hours}h.\n"
            f"Total traces: {len(all_traces)}\n"
            f"Error traces: {len(error_traces)} ({round(len(error_traces) * 100.0 / max(len(all_traces), 1), 1)}%)\n"
            f"Services with anomalies: {', '.join(services_in_play) or 'none'}\n\n"
            f"Top 10 anomalous (service, operation) groups, ranked by error_rate then p95:\n" +
            "\n".join(
                f"  - {a['service']}.{a['operation']}: "
                f"{a['error_count']}/{a['samples']} errors ({a['error_rate_pct']}%) · "
                f"p95={a['p95_duration_ms']}ms · avg={a['avg_duration_ms']}ms"
                for a in anomalies
            ) +
            "\n\nProduce a concise SRE-style report:\n"
            " (1) one-paragraph executive summary (max 3 sentences),\n"
            " (2) up to 4 distinct root-cause hypotheses with the evidence that supports each,\n"
            " (3) recommended immediate actions ranked by impact,\n"
            " (4) longer-term hardening suggestions.\n"
            "No markdown headers."
        )},
    ]
    try:
        from . import llm_provider_service as _llm
        resp = await _llm.chat_completion(summary_prompt, session_id=f"bulk-rca-{hours}h")
        text = (resp.get("response") or "").strip()
        ai_provider = resp.get("provider", "rule_based")
        ai_model = resp.get("model")
    except Exception as e:
        logger.warning("Bulk RCA AI summary failed: %s", e)
        text = (
            f"Executive summary: {len(all_traces)} traces in the last {hours}h, "
            f"{len(error_traces)} errors. Top anomaly: "
            f"{anomalies[0]['service']}.{anomalies[0]['operation']} "
            f"({anomalies[0]['error_rate_pct']}% errors, p95 {anomalies[0]['p95_duration_ms']}ms)."
            if anomalies else "No anomalies detected in this window."
        )
        ai_provider = "rule_based"
        ai_model = None

    report = {
        "hours": hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "traces": len(all_traces),
            "error_traces": len(error_traces),
            "error_rate_pct": round(len(error_traces) * 100.0 / max(len(all_traces), 1), 2),
            "p95_duration_ms": round(p95, 2),
            "services": len({t.get("root_service") for t in all_traces if t.get("root_service")}),
        },
        "anomalies": anomalies,
        "summary": {"text": text, "provider": ai_provider, "model": ai_model},
    }

    try:
        await db.ai_insights.insert_one({**report, "_id": None, "kind": "bulk_trace_rca"})
    except Exception:
        pass
    return report


async def analyze_trace(trace_id: str) -> Dict[str, Any]:
    """Run the full RCA pipeline for one trace_id and return a JSON report."""
    trace = await db.otel_traces.find_one({"trace_id": trace_id}, {"_id": 0})
    if not trace:
        return {"error": "Trace not found", "trace_id": trace_id}
    spans = await db.otel_spans.find({"trace_id": trace_id}, {"_id": 0}).to_list(length=2000)
    if not spans:
        return {"error": "No spans for this trace", "trace_id": trace_id}

    slow = await _detect_slow_spans(spans)
    errors = _detect_error_chain(spans)
    hotspots = _detect_hotspots(spans, trace.get("duration_ms") or 0)
    summary = await _ai_summary(trace, slow, errors, hotspots)

    report = {
        "trace_id": trace_id,
        "trace_status": trace.get("status"),
        "duration_ms": trace.get("duration_ms"),
        "services": trace.get("services"),
        "slow_spans": slow,
        "error_chains": errors,
        "hotspots": hotspots,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist to ai_insights for the AI Insight Panel timeline
    try:
        await db.ai_insights.insert_one({
            **report,
            "_id": None,
            "kind": "trace_rca",
        })
    except Exception:
        # _id collision shouldn't happen; collection insert is best-effort
        pass
    return report
