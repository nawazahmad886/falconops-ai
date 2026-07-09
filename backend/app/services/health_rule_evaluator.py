"""
FalconOps AI - Health Rule Evaluation Service
Auto-evaluates health rules against incoming metrics and creates violation events.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.database import db

# Metric mapping: health rule metric_id → how to extract from server/DB metrics
SERVER_METRIC_MAP = {
    "cpu_usage": lambda m: m.get("cpu_percent") or m.get("cpu_usage"),
    "memory_usage": lambda m: m.get("memory_percent") or m.get("memory_usage"),
    "disk_usage": lambda m: m.get("disk_percent") or m.get("disk_usage"),
    "load_average": lambda m: m.get("load_average_1m") or m.get("load_average"),
    "network_in": lambda m: m.get("network_in_mbps") or m.get("network_in"),
    "network_out": lambda m: m.get("network_out_mbps") or m.get("network_out"),
    "availability": lambda m: 100 if m else 0,
}

DB_METRIC_MAP = {
    "active_sessions": lambda m: m.get("active_sessions"),
    "connection_count": lambda m: m.get("total_connections"),
    "connection_utilization": lambda m: m.get("connection_utilization"),
    "cache_hit_ratio": lambda m: m.get("cache_hit_ratio"),
    "deadlocks": lambda m: m.get("deadlocks"),
    "replication_lag": lambda m: m.get("replication_lag_sec"),
    "tps": lambda m: m.get("tps"),
    "database_size": lambda m: m.get("database_size_mb"),
    "slow_query_count": lambda m: m.get("slow_query_count"),
    "cpu_usage": lambda m: m.get("cpu_usage"),
    "memory_usage": lambda m: m.get("memory_usage"),
}


def _evaluate_condition(value: float, operator: str, threshold: float, threshold_max: float = None) -> bool:
    """Evaluate a single condition."""
    if value is None:
        return False
    try:
        value = float(value)
        threshold = float(threshold)
    except (TypeError, ValueError):
        return False

    if operator in ("greater_than", ">"):
        return value > threshold
    elif operator in ("less_than", "<"):
        return value < threshold
    elif operator in ("greater_than_or_equal", ">="):
        return value >= threshold
    elif operator in ("less_than_or_equal", "<="):
        return value <= threshold
    elif operator in ("equals", "="):
        return value == threshold
    elif operator in ("not_equals", "!="):
        return value != threshold
    elif operator in ("between", "BETWEEN"):
        return threshold <= value <= (threshold_max or threshold)
    elif operator in ("not_between", "NOT BETWEEN"):
        return not (threshold <= value <= (threshold_max or threshold))
    return False


def _get_metric_value(metric_id: str, metrics: dict, metric_map: dict) -> Optional[float]:
    """Extract metric value from metrics dict."""
    extractor = metric_map.get(metric_id)
    if extractor:
        val = extractor(metrics)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    # Direct key lookup as fallback
    val = metrics.get(metric_id)
    if val is not None:
        try:
            return float(val)
        except (TypeError, ValueError):
            pass
    return None


async def evaluate_rules_for_server(server_id: str, server_name: str, metrics: dict):
    """Evaluate all active health rules against server metrics."""
    rules = await db.health_rules.find(
        {"enabled": True, "component_type": {"$in": ["infrastructure", "custom"]}},
        {"_id": 0}
    ).to_list(length=200)

    for rule in rules:
        # Check host filter
        if rule.get("host_filter") and rule["host_filter"] not in (server_name, server_id):
            continue
        await _evaluate_single_rule(rule, metrics, SERVER_METRIC_MAP, "server", server_id, server_name)


async def evaluate_rules_for_db(instance_id: str, instance_name: str, metrics: dict):
    """Evaluate all active health rules against DB metrics."""
    rules = await db.health_rules.find(
        {"enabled": True, "component_type": {"$in": ["database", "custom"]}},
        {"_id": 0}
    ).to_list(length=200)

    for rule in rules:
        if rule.get("host_filter") and rule["host_filter"] not in (instance_name, instance_id):
            continue
        await _evaluate_single_rule(rule, metrics, DB_METRIC_MAP, "database", instance_id, instance_name)


async def _evaluate_single_rule(rule: dict, metrics: dict, metric_map: dict, source_type: str, source_id: str, source_name: str):
    """Evaluate a single rule and create/update violations."""
    rule_id = rule["id"]
    ts = datetime.now(timezone.utc).isoformat()

    # Evaluate primary condition
    value = _get_metric_value(rule["metric"], metrics, metric_map)
    if value is None:
        return

    primary_violated = _evaluate_condition(value, rule["operator"], rule["threshold"], rule.get("threshold_max"))

    # Evaluate compound conditions
    conditions = rule.get("conditions") or []
    all_violated = primary_violated

    for cond in conditions:
        cond_value = _get_metric_value(cond.get("metric", ""), metrics, metric_map)
        if cond_value is None:
            continue
        cond_result = _evaluate_condition(cond_value, cond.get("operator", ">"), cond.get("threshold", 0))
        logic = cond.get("logic", "AND")
        if logic == "AND":
            all_violated = all_violated and cond_result
        elif logic == "OR":
            all_violated = all_violated or cond_result

    # Find existing active violation for this rule + source
    existing = await db.db.health_violations.find_one(
        {"rule_id": rule_id, "source_id": source_id, "state": {"$in": ["active", "warning", "critical"]}},
        {"_id": 0}
    )

    if all_violated:
        if existing:
            # Update existing violation (severity may change)
            new_severity = rule.get("severity", "warning")
            events = existing.get("events", [])
            if existing.get("severity") != new_severity:
                events.append({
                    "type": f"Upgraded to {new_severity}",
                    "timestamp": ts,
                    "severity": new_severity,
                    "value": value,
                })
            else:
                events.append({
                    "type": "Ongoing",
                    "timestamp": ts,
                    "value": value,
                })

            await db.db.health_violations.update_one(
                {"id": existing["id"]},
                {"$set": {
                    "severity": new_severity,
                    "actual_value": value,
                    "last_checked": ts,
                    "events": events[-50:],  # Keep last 50 events
                    "violation_count": existing.get("violation_count", 0) + 1,
                }}
            )
        else:
            # Create new violation
            import hashlib
            fp_raw = f"{rule.get('name','')}|{rule['metric']}|{source_id}".lower().strip()
            fingerprint = hashlib.sha256(fp_raw.encode()).hexdigest()[:16]

            violation_doc = {
                "id": str(uuid.uuid4()),
                "rule_id": rule_id,
                "rule_name": rule.get("name", ""),
                "fingerprint": fingerprint,
                "metric": rule["metric"],
                "operator": rule["operator"],
                "threshold": rule["threshold"],
                "actual_value": value,
                "severity": rule.get("severity", "warning"),
                "state": "active",
                "source_type": source_type,
                "source_id": source_id,
                "source_name": source_name,
                "description": f"{rule.get('name', '')} - {rule['metric']} is {value} (threshold: {rule['operator']} {rule['threshold']})",
                "timestamp": ts,
                "last_checked": ts,
                "violation_count": 1,
                "events": [
                    {"type": "Started", "timestamp": ts, "severity": rule.get("severity", "warning"), "value": value}
                ],
                "actions_executed": [],
            }
            await db.db.health_violations.insert_one(violation_doc)

            # Increment rule violation count
            await db.health_rules.update_one(
                {"id": rule_id},
                {"$inc": {"violations_count": 1, "alerts_triggered": 1}, "$set": {"last_evaluated": ts}}
            )
    else:
        if existing:
            # Resolve violation
            events = existing.get("events", [])
            events.append({"type": "Resolved", "timestamp": ts, "value": value})
            await db.db.health_violations.update_one(
                {"id": existing["id"]},
                {"$set": {"state": "resolved", "resolved_at": ts, "events": events[-50:]}}
            )
