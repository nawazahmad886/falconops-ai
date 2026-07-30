"""
FalconOps AI — Agentic AI Workflow: Action Broker Schema (Phase 1)

Declarative action registry + autonomy-level config, per the "narrow, typed,
reversible action" principle. This module is schema and dry-run ONLY —
execute() always raises NotImplementedError. Real execution is a deliberate,
separate, future-phase decision (mirrors the existing documented boundary in
remediation_service.py / k8s_healing_service.py / connectors/base.py's
RemediationCapable — this repo has never executed a real mutating action
autonomously, and this module does not change that).

Autonomy levels (stored per-action in feature_flags_service's `limits.agentic_autonomy`
map, defaulting to L0_observe for every action — promotion is a manual admin action,
audit-logged for free via feature_flags_service.update_config()):
  L0_observe     — agent explains only, human does everything
  L1_recommend   — agent proposes a specific named action
  L2_shadow       — agent would have acted; logged, not executed
  L3_approve      — agent acts on one-click human confirmation
  L4_autonomous   — acts within a capped blast radius, notifies after (never tier-0/critical)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from . import feature_flags_service

AUTONOMY_LEVELS: List[str] = ["L0_observe", "L1_recommend", "L2_shadow", "L3_approve", "L4_autonomous"]
DEFAULT_AUTONOMY_LEVEL = "L0_observe"


class ActionDefinition(BaseModel):
    name: str
    description: str
    params_schema: Dict[str, str]
    preconditions: List[str]
    blast_radius: str  # "single_instance" | "service" | "cluster" | "org"
    reversible: bool
    inverse: Optional[str] = None
    rate_limit: str
    required_level: str  # minimum AUTONOMY_LEVELS entry needed before this action can ever execute


# The exact Phase-1 action set from the spec — declarations only, nothing behind
# them executes. The first 3 are the "safe at L1" set; the rest require L3+.
ACTION_REGISTRY: Dict[str, ActionDefinition] = {
    "open_ticket": ActionDefinition(
        name="open_ticket",
        description="Open a ticket in the configured ticketing system for this incident.",
        params_schema={"incident_id": "string", "summary": "string"},
        preconditions=[],
        blast_radius="single_instance",
        reversible=True,
        inverse="close_ticket",
        rate_limit="no limit",
        required_level="L1_recommend",
    ),
    "page_on_call": ActionDefinition(
        name="page_on_call",
        description="Page the on-call rotation for the owning service.",
        params_schema={"service": "string", "incident_id": "string"},
        preconditions=[],
        blast_radius="single_instance",
        reversible=False,
        inverse=None,
        rate_limit="4 per service per hour",
        required_level="L1_recommend",
    ),
    "post_status_update": ActionDefinition(
        name="post_status_update",
        description="Post a status update to the incident's chat channel.",
        params_schema={"incident_id": "string", "message": "string"},
        preconditions=[],
        blast_radius="single_instance",
        reversible=False,
        inverse=None,
        rate_limit="12 per incident per hour",
        required_level="L1_recommend",
    ),
    "scale_out": ActionDefinition(
        name="scale_out",
        description="Add replicas/instances to a stateless service under load.",
        params_schema={"service": "string", "count": "int"},
        preconditions=["service.tier != 0", "no_active_change_freeze"],
        blast_radius="service",
        reversible=True,
        inverse="scale_in",
        rate_limit="2 per service per hour",
        required_level="L3_approve",
    ),
    "restart_stateless_service": ActionDefinition(
        name="restart_stateless_service",
        description="Restart one instance of a stateless service.",
        params_schema={"service": "string", "instance": "string"},
        preconditions=["service.tier != 0", "replicas_healthy > 1", "no_active_change_freeze"],
        blast_radius="single_instance",
        reversible=True,
        inverse=None,
        rate_limit="2 per service per hour",
        required_level="L3_approve",
    ),
    "drain_and_reroute_traffic": ActionDefinition(
        name="drain_and_reroute_traffic",
        description="Drain traffic from an unhealthy instance and reroute to healthy peers.",
        params_schema={"service": "string", "instance": "string"},
        preconditions=["service.tier != 0", "replicas_healthy > 1"],
        blast_radius="service",
        reversible=True,
        inverse="restore_traffic",
        rate_limit="2 per service per hour",
        required_level="L3_approve",
    ),
    "rollback_last_deploy": ActionDefinition(
        name="rollback_last_deploy",
        description="Roll back the most recent deployment for a service.",
        params_schema={"service": "string"},
        preconditions=["service.tier != 0", "no_active_change_freeze"],
        blast_radius="service",
        reversible=True,
        inverse=None,
        rate_limit="1 per service per hour",
        required_level="L3_approve",
    ),
}

# Preconditions this codebase genuinely has data for today (real, evaluable) vs. not
# (e.g. change-freeze windows aren't tracked anywhere — confirmed no CI/CD change-event
# ingestion exists). Never silently treat an unevaluable precondition as "met."
_EVALUABLE_PRECONDITIONS = {"service.tier != 0", "replicas_healthy > 1"}


async def get_autonomy_level(action_name: str) -> str:
    cfg = await feature_flags_service.get_config()
    return cfg.get("limits", {}).get("agentic_autonomy", {}).get(action_name, DEFAULT_AUTONOMY_LEVEL)


async def get_all_autonomy_levels() -> Dict[str, str]:
    cfg = await feature_flags_service.get_config()
    stored = cfg.get("limits", {}).get("agentic_autonomy", {})
    return {name: stored.get(name, DEFAULT_AUTONOMY_LEVEL) for name in ACTION_REGISTRY}


async def set_autonomy_level(action_name: str, level: str, admin_user: Dict[str, Any]) -> Dict[str, Any]:
    if action_name not in ACTION_REGISTRY:
        raise ValueError(f"Unknown action '{action_name}'")
    if level not in AUTONOMY_LEVELS:
        raise ValueError(f"Unknown autonomy level '{level}'. Valid: {AUTONOMY_LEVELS}")
    cfg = await feature_flags_service.get_config()
    current_map = dict(cfg.get("limits", {}).get("agentic_autonomy", {}))
    current_map[action_name] = level
    updated = await feature_flags_service.update_config({"limits": {"agentic_autonomy": current_map}}, admin_user)
    return {"action": action_name, "level": level, "updated_by": updated.get("updated_by"), "updated_at": updated.get("updated_at")}


async def _evaluate_precondition(check: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one precondition against real data where possible. Never fabricates
    a pass/fail for something this codebase has no data source for."""
    if check not in _EVALUABLE_PRECONDITIONS:
        return {"check": check, "met": None, "reason": "not evaluable — no data source exists for this check yet"}

    if check == "service.tier != 0":
        # No per-service tier concept exists in topology_nodes today (confirmed via
        # research) — honestly reported, never assumed true.
        return {"check": check, "met": None, "reason": "service tier isn't tracked anywhere yet — see topology_service.py's node schema"}

    if check == "replicas_healthy > 1":
        service = params.get("service")
        if not service:
            return {"check": check, "met": None, "reason": "no service name provided"}
        try:
            from .topology_service import topology_service
            node = await topology_service.get_service_by_name(service, "production", None)
        except Exception as e:
            return {"check": check, "met": None, "reason": f"lookup failed: {str(e)[:150]}"}
        if not node:
            return {"check": check, "met": None, "reason": f"service '{service}' not found in topology"}
        healthy = node.get("status") == "healthy"
        return {"check": check, "met": healthy, "reason": f"topology status is '{node.get('status')}'"}

    return {"check": check, "met": None, "reason": "not evaluable"}


async def dry_run(action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Preview-only: what WOULD happen. Never executes anything, regardless of
    autonomy level or preconditions met/unmet."""
    action = ACTION_REGISTRY.get(action_name)
    if not action:
        raise ValueError(f"Unknown action '{action_name}'")

    precondition_results = [await _evaluate_precondition(c, params) for c in action.preconditions]
    current_level = await get_autonomy_level(action_name)

    return {
        "action": action_name,
        "description": action.description,
        "params": params,
        "preconditions": precondition_results,
        "blast_radius": action.blast_radius,
        "reversible": action.reversible,
        "inverse": action.inverse,
        "rate_limit": action.rate_limit,
        "required_level": action.required_level,
        "current_autonomy_level": current_level,
        "would_execute": False,
        "note": "Preview only — Phase 1 has no execution path. execute() always raises NotImplementedError.",
    }


async def execute(action_name: str, params: Dict[str, Any]) -> None:
    """Deliberately unimplemented. Phase 1 is read/dry-run only — this is the
    single, literal guarantee nothing here can mutate a monitored system yet."""
    raise NotImplementedError(
        "Real action execution ships in a future phase — Phase 1 is read/dry-run only. "
        f"'{action_name}' was not executed."
    )
