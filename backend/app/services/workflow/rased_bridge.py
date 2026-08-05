"""
RASED integration bridge — how a workflow's AI/Action/Validation nodes call
RASED's real, unmodified classes instead of a reimplementation.

RCAAgent.run(state) and VerificationAgent.run(state) both require the FULL
InvestigationState (confirmed by reading rased/agents/rca.py and
rased/agents/verification.py) — not a narrow input/output pair. A workflow
execution that touches any RASED-wrapper node therefore carries a "shadow"
InvestigationState alongside its own WorkflowExecution record: seeded from
the trigger payload, incrementally populated with Evidence as upstream Data
nodes run, serialized into execution.variables["_shadow_state"] between
node dispatches (Pydantic round-trips it via model_validate/model_dump —
datetimes go through as ISO strings).

This keeps the actual RASED agent classes completely unmodified — they are
imported and called directly, exactly as RASED's own graph nodes call them.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ...models.rased_schemas import Alert, Evidence, InvestigationState

_SHADOW_KEY = "_shadow_state"


def build_initial_shadow_state(execution_id: str, trigger_payload: Dict[str, Any], tenant_id: Optional[str] = None) -> InvestigationState:
    now = datetime.now(timezone.utc)
    alert = Alert(
        alert_id=trigger_payload.get("alert_id") or f"{execution_id}-alert-workflow",
        signature=trigger_payload.get("signature", f"workflow-{execution_id}"),
        source=trigger_payload.get("source", "elk"),
        service=trigger_payload.get("service", "unknown-service"),
        host=trigger_payload.get("host"),
        severity=trigger_payload.get("severity", "medium"),
        title=trigger_payload.get("title", "Workflow-triggered investigation"),
        description=trigger_payload.get("description", ""),
        tenant_id=tenant_id, observed_at=now, raw=trigger_payload,
    )
    return InvestigationState(
        incident_id=execution_id, tenant_id=tenant_id, execution_mode="simulated",
        alerts=[alert], created_at=now, updated_at=now,
    )


def load_shadow_state(execution: Dict[str, Any]) -> Optional[InvestigationState]:
    raw = (execution.get("variables") or {}).get(_SHADOW_KEY)
    if raw is None:
        return None
    return InvestigationState.model_validate(raw)


def dump_shadow_state(state: InvestigationState) -> Dict[str, Any]:
    return state.model_dump(mode="json")


def append_evidence(state: InvestigationState, source: str, query: str, summary: str, data: Dict[str, Any], tier: str = "deep") -> InvestigationState:
    now = datetime.now(timezone.utc)
    evidence = Evidence(
        evidence_id=str(uuid.uuid4()), tier=tier, source=source if source in
        ("elk", "appdynamics", "solarwinds", "mq", "db", "cmdb", "changes") else "elk",
        query=query, summary=summary, data=data, observed_at=now, retrieved_at=now,
    )
    return state.model_copy(update={"evidence": state.evidence + [evidence]})


async def run_rased_agent(rased_agent_class: str, state: InvestigationState) -> Dict[str, Any]:
    """Directly imports and calls the real RASED agent class — the same
    class RASED's own LangGraph nodes call, unmodified. Returns the partial
    state-update dict each RASED agent's run() produces."""
    from ..rased.agents.orchestrator import OrchestratorAgent
    from ..rased.agents.telemetry import TelemetryRetrievalAgent
    from ..rased.agents.rca import RCAAgent
    from ..rased.agents.policy import PolicyAgent
    from ..rased.agents.action import ActionAgent
    from ..rased.agents.verification import VerificationAgent
    from ..rased.agents.impact import ImpactAgent
    from ..rased.agents.case_mgmt import CaseManagementAgent

    registry = {
        "OrchestratorAgent": OrchestratorAgent, "TelemetryRetrievalAgent": TelemetryRetrievalAgent,
        "RCAAgent": RCAAgent, "PolicyAgent": PolicyAgent, "ActionAgent": ActionAgent,
        "VerificationAgent": VerificationAgent, "ImpactAgent": ImpactAgent,
        "CaseManagementAgent": CaseManagementAgent,
    }
    agent_cls = registry.get(rased_agent_class)
    if agent_cls is None:
        return {}
    return await agent_cls().run(state)


__all__ = ["build_initial_shadow_state", "load_shadow_state", "dump_shadow_state", "append_evidence", "run_rased_agent", "_SHADOW_KEY"]
