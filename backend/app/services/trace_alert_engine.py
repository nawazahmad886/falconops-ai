"""
FalconOps AI — Trace-Driven Alerting Engine
Periodically evaluates user-defined rules against OpenTelemetry trace data and
triggers alerts via the existing AlertEngine.

Rule schema (stored in `trace_alert_rules`):
  {
    "id": str,
    "name": str,
    "service": str,                       # required — service name to evaluate
    "operation": Optional[str],           # if set, scoped to this operation
    "rule_type": "latency" | "error_rate",
    "threshold_ms": float,                # for latency
    "threshold_pct": float,               # for error_rate (0-100)
    "metric": "p95" | "avg" | "max",      # for latency only
    "window_minutes": int,                # default 5
    "min_traces": int,                    # default 5 — won't fire below this volume
    "severity": "critical"|"high"|"medium"|"low"|"info",
    "enabled": bool,
    "tenant_id": Optional[str],
    "last_evaluated_at": ISO,
    "last_state": "ok" | "breaching",
    "created_at": ISO,
    "updated_at": ISO,
  }
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from ..core.database import db
from .alert_engine import AlertEngine, AlertSeverity

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_MIN = 5
DEFAULT_MIN_TRACES = 5
EVAL_INTERVAL_SEC = 60  # background evaluator interval


# ─────────────────────────────────────────────────────
#  CRUD helpers
# ─────────────────────────────────────────────────────

def _normalize_rule(raw: Dict) -> Dict:
    """Apply defaults + light validation."""
    rule_type = (raw.get("rule_type") or "latency").lower()
    if rule_type not in ("latency", "error_rate"):
        raise ValueError(f"rule_type must be 'latency' or 'error_rate', got {rule_type}")
    metric = (raw.get("metric") or "p95").lower()
    if metric not in ("p95", "avg", "max"):
        raise ValueError(f"metric must be 'p95', 'avg', or 'max', got {metric}")
    severity = (raw.get("severity") or "high").lower()
    if severity not in ("critical", "high", "medium", "low", "info"):
        raise ValueError(f"severity must be one of critical/high/medium/low/info, got {severity}")
    if not raw.get("service"):
        raise ValueError("service is required")
    if rule_type == "latency" and not isinstance(raw.get("threshold_ms"), (int, float)):
        raise ValueError("latency rule requires threshold_ms (number)")
    if rule_type == "error_rate" and not isinstance(raw.get("threshold_pct"), (int, float)):
        raise ValueError("error_rate rule requires threshold_pct (number 0-100)")

    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": raw.get("id") or str(uuid.uuid4()),
        "name": raw.get("name") or f"{rule_type} rule for {raw['service']}",
        "service": raw["service"],
        "operation": raw.get("operation"),
        "rule_type": rule_type,
        "threshold_ms": float(raw.get("threshold_ms") or 0),
        "threshold_pct": float(raw.get("threshold_pct") or 0),
        "metric": metric,
        "window_minutes": int(raw.get("window_minutes") or DEFAULT_WINDOW_MIN),
        "min_traces": int(raw.get("min_traces") or DEFAULT_MIN_TRACES),
        "severity": severity,
        "enabled": bool(raw.get("enabled", True)),
        "tenant_id": raw.get("tenant_id"),
        "last_evaluated_at": raw.get("last_evaluated_at"),
        "last_state": raw.get("last_state") or "ok",
        "last_value": raw.get("last_value"),
        "created_at": raw.get("created_at") or now,
        "updated_at": now,
    }


async def list_rules(tenant_id: Optional[str] = None) -> List[Dict]:
    q: Dict = {}
    if tenant_id:
        q["tenant_id"] = tenant_id
    cursor = db.trace_alert_rules.find(q, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=500)


async def upsert_rule(raw: Dict) -> Dict:
    rule = _normalize_rule(raw)
    await db.trace_alert_rules.update_one({"id": rule["id"]}, {"$set": rule}, upsert=True)
    return rule


async def delete_rule(rule_id: str) -> bool:
    res = await db.trace_alert_rules.delete_one({"id": rule_id})
    return res.deleted_count > 0


# ─────────────────────────────────────────────────────
#  Evaluation
# ─────────────────────────────────────────────────────

async def _gather_metrics(rule: Dict) -> Dict:
    """Fetch the data this rule needs and compute its current value."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=rule["window_minutes"])).isoformat()
    span_query: Dict = {"service": rule["service"], "received_at": {"$gte": cutoff}}
    if rule.get("operation"):
        span_query["operation"] = rule["operation"]

    if rule["rule_type"] == "latency":
        cursor = db.otel_spans.find(span_query, {"_id": 0, "duration_ms": 1}).limit(5000)
        durations = [d["duration_ms"] for d in await cursor.to_list(length=5000) if d.get("duration_ms") is not None]
        n = len(durations)
        if n == 0:
            return {"value": 0.0, "samples": 0, "metric": rule["metric"]}
        durations.sort()
        if rule["metric"] == "avg":
            value = statistics.mean(durations)
        elif rule["metric"] == "max":
            value = max(durations)
        else:  # p95
            idx = max(0, int(n * 0.95) - 1)
            value = durations[idx]
        return {"value": round(value, 2), "samples": n, "metric": rule["metric"]}

    if rule["rule_type"] == "error_rate":
        cursor = db.otel_spans.find(span_query, {"_id": 0, "status": 1}).limit(10000)
        rows = await cursor.to_list(length=10000)
        n = len(rows)
        if n == 0:
            return {"value": 0.0, "samples": 0}
        errors = sum(1 for r in rows if r.get("status") == "ERROR")
        return {"value": round(errors * 100.0 / n, 2), "samples": n, "errors": errors}

    return {"value": 0.0, "samples": 0}


def _is_breaching(rule: Dict, metric: Dict) -> bool:
    """Return True if the metric breaches the rule threshold AND has enough samples."""
    if metric.get("samples", 0) < rule["min_traces"]:
        return False
    value = metric.get("value", 0.0)
    if rule["rule_type"] == "latency":
        return value > rule["threshold_ms"]
    if rule["rule_type"] == "error_rate":
        return value > rule["threshold_pct"]
    return False


async def evaluate_rule(rule: Dict, alert_engine: AlertEngine) -> Dict:
    """Evaluate one rule, fire/resolve alerts on transition."""
    metric = await _gather_metrics(rule)
    breaching = _is_breaching(rule, metric)
    new_state = "breaching" if breaching else "ok"
    transitioned = new_state != rule.get("last_state", "ok")

    now = datetime.now(timezone.utc).isoformat()
    update_payload = {
        "last_evaluated_at": now,
        "last_state": new_state,
        "last_value": metric.get("value"),
        "last_samples": metric.get("samples", 0),
        "updated_at": now,
    }
    await db.trace_alert_rules.update_one({"id": rule["id"]}, {"$set": update_payload})

    fired_alert: Optional[Dict] = None
    if transitioned and breaching:
        title, description = _build_alert_text(rule, metric)
        fired_alert = await alert_engine.create_alert(
            title=title,
            description=description,
            severity=rule["severity"],
            source="trace_alert_engine",
            entity_type="service",
            entity_id=rule["service"],
            entity_name=rule["service"],
            metric_name=f"{rule['rule_type']}.{rule.get('metric', '')}".strip("."),
            metric_value=metric.get("value"),
            threshold=rule.get("threshold_ms") if rule["rule_type"] == "latency" else rule.get("threshold_pct"),
            rule_id=rule["id"],
            tags={"trace_rule": rule["name"], "operation": rule.get("operation") or "*"},
            tenant_id=rule.get("tenant_id"),
        )
    elif transitioned and not breaching:
        # Auto-resolve any open alert for this rule
        await db.alerts_engine.update_many(
            {"rule_id": rule["id"], "status": "triggered"},
            {"$set": {
                "status": "resolved",
                "resolved_at": now,
                "resolution_note": "Trace rule recovered automatically",
            }},
        )

    return {
        "rule_id": rule["id"],
        "value": metric.get("value"),
        "samples": metric.get("samples", 0),
        "breaching": breaching,
        "transitioned": transitioned,
        "fired_alert_id": (fired_alert or {}).get("id"),
    }


def _build_alert_text(rule: Dict, metric: Dict):
    if rule["rule_type"] == "latency":
        title = f"[{rule['service']}] {rule['metric']} latency {metric['value']:.0f}ms exceeds {rule['threshold_ms']:.0f}ms"
    else:
        title = f"[{rule['service']}] error rate {metric['value']:.1f}% exceeds {rule['threshold_pct']:.1f}%"
    description = (
        f"Trace alert rule '{rule['name']}' breached.\n"
        f"  Service: {rule['service']}{' / ' + rule['operation'] if rule.get('operation') else ''}\n"
        f"  Window: last {rule['window_minutes']} min ({metric.get('samples')} samples)\n"
        f"  Type: {rule['rule_type']} ({rule.get('metric', '')})\n"
        f"  Observed: {metric.get('value')}, Threshold: "
        f"{rule['threshold_ms'] if rule['rule_type'] == 'latency' else rule['threshold_pct']}"
    )
    return title, description


async def evaluate_all() -> Dict:
    """Evaluate every enabled rule once."""
    cursor = db.trace_alert_rules.find({"enabled": True}, {"_id": 0})
    rules = await cursor.to_list(length=500)
    if not rules:
        return {"evaluated": 0, "results": []}
    engine = AlertEngine()
    results = []
    for r in rules:
        try:
            results.append(await evaluate_rule(r, engine))
        except Exception as e:
            logger.error("Trace rule eval failed for %s: %s", r.get("id"), e)
            results.append({"rule_id": r.get("id"), "error": str(e)})
    return {"evaluated": len(rules), "results": results}


# ─────────────────────────────────────────────────────
#  Background scheduler
# ─────────────────────────────────────────────────────

_eval_task: Optional[asyncio.Task] = None


async def _eval_loop():
    while True:
        try:
            await evaluate_all()
        except Exception as e:
            logger.error("Trace alert evaluator loop error: %s", e)
        await asyncio.sleep(EVAL_INTERVAL_SEC)


def start_scheduler():
    """Idempotently start the background trace-alert evaluator."""
    global _eval_task
    if _eval_task and not _eval_task.done():
        return
    try:
        loop = asyncio.get_event_loop()
        _eval_task = loop.create_task(_eval_loop())
        logger.info("Trace alert evaluator scheduler started (every %ds)", EVAL_INTERVAL_SEC)
    except RuntimeError:
        # Outside an event loop (e.g., on import) — caller must invoke from lifespan
        pass


def stop_scheduler():
    global _eval_task
    if _eval_task and not _eval_task.done():
        _eval_task.cancel()
        _eval_task = None
