"""
Static action registry. Risk tier is declared here, never inferred at
runtime by an LLM — ActionAgent may only propose actions that exist in this
dict (see agents/action.py's validation against ACTIONS before anything
reaches an executor), never a free-text action.
"""
from typing import Dict

from ....models.rased_schemas import ActionSpec

ACTIONS: Dict[str, ActionSpec] = {
    "suppress_duplicate_alerts": ActionSpec(
        tier="SAFE", adapter="internal",
        description="Suppress duplicate/storm alerts sharing a root signature",
    ),
    "collect_diagnostics": ActionSpec(
        tier="SAFE", adapter="elk",
        description="Pull recent logs for the affected service",
    ),
    "scale_out_service": ActionSpec(
        tier="GUARDED", adapter="k8s_mock",
        description="Add replicas to the affected service",
    ),
    "restart_pod": ActionSpec(
        tier="GUARDED", adapter="k8s_restart_pod",
        description="Restart the affected service's pod(s)",
    ),
    "clear_queue_backlog": ActionSpec(
        tier="GUARDED", adapter="mq_mock",
        description="Fast-forward/drain a backlogged queue",
    ),
    "failover_dependency": ActionSpec(
        tier="DESTRUCTIVE", adapter="gateway_mock",
        description="Fail over to a backup dependency",
    ),
    "rollback_deployment": ActionSpec(
        tier="DESTRUCTIVE", adapter="changes_mock",
        description="Roll back the correlated deployment",
    ),
}

CONFIDENCE_FLOOR = 0.70
BLAST_RADIUS_THRESHOLD = 3
APPROVAL_EXPIRY_MINUTES = 10

__all__ = ["ACTIONS", "CONFIDENCE_FLOOR", "BLAST_RADIUS_THRESHOLD", "APPROVAL_EXPIRY_MINUTES"]
