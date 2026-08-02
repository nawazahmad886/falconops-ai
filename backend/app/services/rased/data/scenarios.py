"""
RASED scenario catalog.

Every scenario builder is a pure function of (rng, anchor_time) — no wall-clock
reads, no unseeded randomness, no network I/O. That is what makes
`generate_scenario(scenario_id, sink, seed=42, anchor_time=...)` produce byte-
identical output across two runs with the same seed and anchor_time.

S1 is the one scenario where evidence tiering matters most: the trigger-tier
subset (what the alert payload alone already contains) has to genuinely
support "database contention" as a plausible conclusion, while the deep-tier
subset (only visible after an adapter is queried) flips that to "payment
gateway failure, database saturation is a symptom." Nothing downstream should
have to be told to change its mind — the data has to earn it.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from random import Random
from typing import Any, Callable, Dict, List, Optional

from ....models.rased_schemas import Alert, Evidence

# ---------------------------------------------------------------------------
# Service catalogue — diurnal curve, not a flat rate. Business-hours-shaped:
# trough overnight (~02:00), peak early afternoon (~14:00). No real hostnames,
# IPs, or endpoints anywhere in this module by design; entities are abstract
# service slugs.
# ---------------------------------------------------------------------------

SERVICE_CATALOG: Dict[str, Dict[str, Any]] = {
    "checkout-api": {"business_capability": "Checkout & Payments", "baseline_tpm": 4200, "depends_on": ["invoice-db", "payment-gateway"]},
    "payment-gateway": {"business_capability": "Checkout & Payments", "baseline_tpm": 3900, "depends_on": []},
    "invoice-db": {"business_capability": "Checkout & Payments", "baseline_tpm": 6000, "depends_on": []},
    "notification-svc": {"business_capability": "Customer Communications", "baseline_tpm": 1500, "depends_on": []},
    "reporting-svc": {"business_capability": "Merchant Analytics", "baseline_tpm": 800, "depends_on": ["invoice-db"]},
    "inventory-svc": {"business_capability": "Catalog & Inventory", "baseline_tpm": 2100, "depends_on": ["invoice-db"]},
    "order-queue-consumer": {"business_capability": "Order Fulfillment", "baseline_tpm": 1800, "depends_on": []},
    "edge-router-cluster": {"business_capability": "Network Edge", "baseline_tpm": 0, "depends_on": []},
}


def diurnal_multiplier(hour: int) -> float:
    """Traffic multiplier for a given hour-of-day, 0-23. Smooth cosine curve
    peaking ~14:00 (1.0x) and troughing ~02:00 (~0.12x) — deliberately not a
    flat rate, so any transaction-volume number in generated data survives
    being asked "why that number, at that hour?"."""
    hour = hour % 24
    radians = 2 * math.pi * (hour - 14) / 24
    return round(0.56 + 0.44 * math.cos(radians), 4)


def _tpm(rng: Random, service: str, at: datetime) -> int:
    baseline = SERVICE_CATALOG[service]["baseline_tpm"]
    jitter = rng.uniform(0.94, 1.06)
    return round(baseline * diurnal_multiplier(at.hour) * jitter)


@dataclass
class GenerationContext:
    scenario_id: str
    rng: Random
    anchor_time: datetime


@dataclass
class ScenarioData:
    alerts: List[Alert] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    source_records: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def add_source_record(self, source: str, record: Dict[str, Any]) -> None:
        self.source_records.setdefault(source, []).append(record)


@dataclass
class ScenarioSpec:
    scenario_id: str
    name: str
    description: str
    builder: Callable[[GenerationContext], ScenarioData]


def _offset(anchor: datetime, minutes: float) -> datetime:
    return anchor + timedelta(minutes=minutes)


# ---------------------------------------------------------------------------
# S1 — payment_gateway_degradation. The headline demo.
# ---------------------------------------------------------------------------

def _build_s1(ctx: GenerationContext) -> ScenarioData:
    rng, anchor = ctx.rng, ctx.anchor_time
    data = ScenarioData()

    pool_pct = round(rng.uniform(89.0, 95.0), 1)
    slow_queries = rng.randint(14, 22)
    checkout_error_rate = round(rng.uniform(9.0, 15.0), 1)
    exit_span_failure_pct = round(rng.uniform(30.0, 38.0), 1)
    gateway_lead_minutes = rng.randint(5, 8)

    alert = Alert(
        alert_id=f"{ctx.scenario_id}-alert-01",
        signature="checkout-api:elevated-error-rate",
        source="db",
        service="checkout-api",
        host="checkout-api-pod-3",
        severity="critical",
        title="Checkout API error rate elevated",
        description=(
            f"checkout-api error rate at {checkout_error_rate}%; invoice-db connection "
            f"pool at {pool_pct}% capacity with {slow_queries} slow-query warnings in the "
            "preceding 5 minutes."
        ),
        tenant_id="tenant-demo",
        observed_at=anchor,
        raw={
            "db_connection_pool_pct": pool_pct,
            "db_slow_query_count_5m": slow_queries,
            "checkout_error_rate_pct": checkout_error_rate,
            "estimated_tpm": _tpm(rng, "checkout-api", anchor),
        },
    )
    data.alerts.append(alert)

    # Trigger tier — derivable straight from the alert payload, no adapter
    # call. Plausible and wrong: it reads like database contention.
    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-01",
        tier="trigger",
        source="db",
        query="alert.raw.db_connection_pool_pct",
        summary=f"DB connection-pool saturation: invoice-db pool at {pool_pct}% capacity",
        data={"service": "invoice-db", "pool_usage_pct": pool_pct},
        observed_at=anchor,
        retrieved_at=anchor,
    ))
    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-02",
        tier="trigger",
        source="db",
        query="alert.raw.db_slow_query_count_5m",
        summary=f"{slow_queries} slow-query warnings observed on invoice-db in the 5 minutes preceding the alert",
        data={"service": "invoice-db", "slow_query_count_5m": slow_queries},
        observed_at=anchor,
        retrieved_at=anchor,
    ))

    # Deep tier — only surfaces once an adapter is actually queried. Flips
    # the conclusion to the payment gateway.
    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-03",
        tier="deep",
        source="appdynamics",
        query="db.rased_synthetic_appdynamics.find(service=payment-gateway, metric=exit_span_failure_rate)",
        summary=f"Exit-span failure rate {exit_span_failure_pct}% on the checkout-api -> payment-gateway dependency",
        data={"dependency": "payment-gateway", "exit_span_failure_rate_pct": exit_span_failure_pct},
        observed_at=_offset(anchor, -2),
        retrieved_at=_offset(anchor, 3),
    ))
    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-04",
        tier="deep",
        source="appdynamics",
        query="db.rased_synthetic_appdynamics.find(service=payment-gateway, metric=degradation_onset)",
        summary=(
            f"Payment-gateway exit-span degradation began {gateway_lead_minutes} minutes before "
            "invoice-db pool saturation — the database is a downstream symptom, not the origin"
        ),
        data={
            "gateway_degradation_offset_min": -gateway_lead_minutes,
            "db_saturation_offset_min": 0,
        },
        observed_at=_offset(anchor, -gateway_lead_minutes),
        retrieved_at=_offset(anchor, 4),
    ))
    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-05",
        tier="deep",
        source="changes",
        query="db.rased_synthetic_changes.find(service in [checkout-api, invoice-db, payment-gateway], window=60m)",
        summary="No deployment correlated with checkout-api, invoice-db, or payment-gateway in the 60-minute window preceding the alert",
        data={"deployments_in_window": []},
        observed_at=anchor,
        retrieved_at=_offset(anchor, 5),
    ))

    data.add_source_record("db", {
        "service": "invoice-db", "metric": "connection_pool_pct", "value": pool_pct,
        "slow_query_count_5m": slow_queries, "at": anchor,
    })
    data.add_source_record("appdynamics", {
        "service": "payment-gateway", "metric": "exit_span_failure_rate_pct",
        "value": exit_span_failure_pct, "at": _offset(anchor, -2),
    })
    data.add_source_record("appdynamics", {
        "service": "payment-gateway", "metric": "degradation_onset_offset_min",
        "value": -gateway_lead_minutes, "at": _offset(anchor, -gateway_lead_minutes),
    })
    data.add_source_record("changes", {
        "service": "checkout-api", "window_minutes": 60, "deployments": [], "at": anchor,
    })

    return data


# ---------------------------------------------------------------------------
# S2 — mq_backlog. Guarded auto-remediation, no approval needed.
# ---------------------------------------------------------------------------

def _build_s2(ctx: GenerationContext) -> ScenarioData:
    rng, anchor = ctx.rng, ctx.anchor_time
    data = ScenarioData()

    queue_depth = rng.randint(18000, 26000)
    consumer_lag_s = rng.randint(180, 300)

    alert = Alert(
        alert_id=f"{ctx.scenario_id}-alert-01",
        signature="order-queue-consumer:backlog",
        source="mq",
        service="order-queue-consumer",
        host="order-queue-consumer-pod-1",
        severity="medium",
        title="Order queue backlog growing",
        description=f"order-events queue depth at {queue_depth} messages, consumer lag {consumer_lag_s}s.",
        tenant_id="tenant-demo",
        observed_at=anchor,
        raw={"queue_depth": queue_depth, "consumer_lag_seconds": consumer_lag_s},
    )
    data.alerts.append(alert)

    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-01",
        tier="trigger",
        source="mq",
        query="alert.raw.queue_depth",
        summary=f"order-events queue depth at {queue_depth} messages",
        data={"queue": "order-events", "depth": queue_depth},
        observed_at=anchor,
        retrieved_at=anchor,
    ))
    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-02",
        tier="deep",
        source="appdynamics",
        query="db.rased_synthetic_appdynamics.find(service=order-queue-consumer, metric=health)",
        summary="Downstream consumer is healthy and processing at normal throughput — pure backlog, not an outage",
        data={"consumer_error_rate_pct": 0.1, "consumer_throughput_normal": True},
        observed_at=anchor,
        retrieved_at=_offset(anchor, 2),
    ))

    data.add_source_record("mq", {
        "queue": "order-events", "depth": queue_depth, "consumer_lag_seconds": consumer_lag_s, "at": anchor,
    })
    data.add_source_record("appdynamics", {
        "service": "order-queue-consumer", "metric": "error_rate_pct", "value": 0.1, "at": _offset(anchor, 2),
    })

    return data


# ---------------------------------------------------------------------------
# S3 — db_slow_query_cascade. Multi-service blast radius.
# ---------------------------------------------------------------------------

def _build_s3(ctx: GenerationContext) -> ScenarioData:
    rng, anchor = ctx.rng, ctx.anchor_time
    data = ScenarioData()

    affected_services = ["checkout-api", "reporting-svc", "inventory-svc", "notification-svc"]
    avg_query_ms = rng.randint(2200, 3800)

    for i, service in enumerate(affected_services):
        error_rate = round(rng.uniform(4.0, 18.0), 1)
        data.alerts.append(Alert(
            alert_id=f"{ctx.scenario_id}-alert-{i+1:02d}",
            signature="shared-db-cluster:slow-query-cascade",
            source="db",
            service=service,
            host=f"{service}-pod-{i+1}",
            severity="high",
            title=f"{service} elevated latency",
            description=f"{service} p95 latency elevated, error rate {error_rate}%, dependent on shared invoice-db cluster.",
            tenant_id="tenant-demo",
            observed_at=_offset(anchor, i * 0.5),
            raw={"error_rate_pct": error_rate, "estimated_tpm": _tpm(rng, service, anchor)},
        ))
        data.evidence.append(Evidence(
            evidence_id=f"{ctx.scenario_id}-ev-trigger-{i+1:02d}",
            tier="trigger",
            source="db",
            query="alert.raw.error_rate_pct",
            summary=f"{service} error rate elevated to {error_rate}%",
            data={"service": service, "error_rate_pct": error_rate},
            observed_at=_offset(anchor, i * 0.5),
            retrieved_at=_offset(anchor, i * 0.5),
        ))

    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-deep-01",
        tier="deep",
        source="db",
        query="db.rased_synthetic_db.find(service=invoice-db, metric=avg_query_duration_ms)",
        summary=f"Shared invoice-db cluster average query duration at {avg_query_ms}ms, well above baseline",
        data={"service": "invoice-db", "avg_query_duration_ms": avg_query_ms},
        observed_at=anchor,
        retrieved_at=_offset(anchor, 3),
    ))

    data.add_source_record("db", {
        "service": "invoice-db", "metric": "avg_query_duration_ms", "value": avg_query_ms, "at": anchor,
    })
    for service in affected_services:
        data.add_source_record("cmdb", {
            "service": service, "depends_on": SERVICE_CATALOG[service]["depends_on"], "at": anchor,
        })

    return data


# ---------------------------------------------------------------------------
# S4 — post_deploy_memory_leak. Change-event correlation.
# ---------------------------------------------------------------------------

def _build_s4(ctx: GenerationContext) -> ScenarioData:
    rng, anchor = ctx.rng, ctx.anchor_time
    data = ScenarioData()

    memory_pct = round(rng.uniform(88.0, 96.0), 1)
    restart_count = rng.randint(3, 7)
    deploy_lead_minutes = rng.randint(35, 55)
    version = f"2.{rng.randint(14, 40)}.{rng.randint(0, 9)}"
    deployment_id = f"{ctx.scenario_id}-deploy-01"

    alert = Alert(
        alert_id=f"{ctx.scenario_id}-alert-01",
        signature="notification-svc:memory-growth",
        source="solarwinds",
        service="notification-svc",
        host="notification-svc-pod-2",
        severity="high",
        title="notification-svc memory usage climbing",
        description=f"notification-svc heap usage at {memory_pct}%, {restart_count} OOM restarts in the last hour.",
        tenant_id="tenant-demo",
        observed_at=anchor,
        raw={"memory_pct": memory_pct, "oom_restart_count_1h": restart_count},
    )
    data.alerts.append(alert)

    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-01",
        tier="trigger",
        source="solarwinds",
        query="alert.raw.memory_pct",
        summary=f"notification-svc heap usage climbing, currently at {memory_pct}%",
        data={"service": "notification-svc", "memory_pct": memory_pct},
        observed_at=anchor,
        retrieved_at=anchor,
    ))
    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-02",
        tier="deep",
        source="changes",
        query=f"db.rased_synthetic_changes.find(service=notification-svc, window={deploy_lead_minutes + 10}m)",
        summary=f"Deployment {deployment_id} shipped version {version} to notification-svc {deploy_lead_minutes} minutes before the alert",
        data={
            "deployment_id": deployment_id,
            "service": "notification-svc",
            "version": version,
            "offset_min": -deploy_lead_minutes,
        },
        observed_at=_offset(anchor, -deploy_lead_minutes),
        retrieved_at=_offset(anchor, 3),
    ))

    data.add_source_record("solarwinds", {
        "service": "notification-svc", "metric": "memory_pct", "value": memory_pct, "at": anchor,
    })
    data.add_source_record("changes", {
        "deployment_id": deployment_id,
        "service": "notification-svc",
        "version": version,
        "author": "svc-deploy-bot",
        "timestamp": _offset(anchor, -deploy_lead_minutes),
    })

    return data


# ---------------------------------------------------------------------------
# S5 — network_flap_alert_storm. 40+ alerts, one root signature, zero impact.
# ---------------------------------------------------------------------------

def _build_s5(ctx: GenerationContext) -> ScenarioData:
    rng, anchor = ctx.rng, ctx.anchor_time
    data = ScenarioData()

    alert_count = rng.randint(42, 55)
    for i in range(alert_count):
        flap_ms = rng.randint(80, 400)
        data.alerts.append(Alert(
            alert_id=f"{ctx.scenario_id}-alert-{i+1:03d}",
            signature="edge-router-cluster:network-flap",
            source="solarwinds",
            service="edge-router-cluster",
            host=f"edge-router-{(i % 6) + 1}",
            severity="low",
            title="Transient network flap detected",
            description=f"Interface flap of {flap_ms}ms detected on edge-router-cluster, auto-recovered.",
            tenant_id="tenant-demo",
            observed_at=_offset(anchor, i * 0.1),
            raw={"flap_duration_ms": flap_ms, "auto_recovered": True},
        ))

    data.evidence.append(Evidence(
        evidence_id=f"{ctx.scenario_id}-ev-01",
        tier="trigger",
        source="solarwinds",
        query="alert.raw.flap_duration_ms (aggregated across storm)",
        summary=f"{alert_count} transient network-flap alerts on edge-router-cluster, all auto-recovered, one root signature",
        data={"alert_count": alert_count, "root_signature": "edge-router-cluster:network-flap", "customer_impact": False},
        observed_at=anchor,
        retrieved_at=anchor,
    ))

    data.add_source_record("solarwinds", {
        "service": "edge-router-cluster", "metric": "flap_alert_count", "value": alert_count, "at": anchor,
    })

    return data


SCENARIOS: Dict[str, ScenarioSpec] = {
    "S1": ScenarioSpec("S1", "payment_gateway_degradation", "Tiered evidence flips DB contention to payment-gateway failure", _build_s1),
    "S2": ScenarioSpec("S2", "mq_backlog", "Guarded auto-remediation candidate, no approval needed", _build_s2),
    "S3": ScenarioSpec("S3", "db_slow_query_cascade", "Multi-service blast radius from one shared DB cluster", _build_s3),
    "S4": ScenarioSpec("S4", "post_deploy_memory_leak", "Memory leak correlated to a specific deployment record", _build_s4),
    "S5": ScenarioSpec("S5", "network_flap_alert_storm", "40+ alerts, one root signature, zero impact, zero actions", _build_s5),
}

__all__ = [
    "SERVICE_CATALOG",
    "diurnal_multiplier",
    "GenerationContext",
    "ScenarioData",
    "ScenarioSpec",
    "SCENARIOS",
]
