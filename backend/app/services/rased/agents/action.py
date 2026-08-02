"""
ActionAgent — proposes and, for SAFE/GUARDED tiers, executes exactly one
action per investigation. Every action name is validated against the static
ACTIONS registry in code before anything reaches an executor — an LLM may
help pick which registered action fits the top hypothesis, but "propose only
from the registry" is enforced by a membership check, not by trusting the
model to follow that instruction.

Hard gates apply before any action is proposed, in this order: suppressed
investigations propose nothing; blast radius over the threshold escalates
without proposing anything; confidence below the floor escalates without
proposing anything; an active maintenance window suppresses. Only past all
four gates does an action get proposed at all.

DESTRUCTIVE-tier actions pause via LangGraph's interrupt() — see the risk
note below and in graph/checkpointer.py. This is the second place (after
checkpointer.py) where this build's correctness depends on LangGraph's exact
interrupt/resume semantics, which were not verified against a live install.
LangGraph replays a node from the top on resume, re-executing any code
before the interrupt() call (here, only the cheap-ish LLM action-pick, not
anything with a real side effect) — the actual execute_action() call, the
part that matters for safety, only happens once, after interrupt() returns
an approved decision.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from ....models.rased_schemas import Action, InvestigationState
from ..actions.executors import execute_action
from ..actions.registry import ACTIONS, BLAST_RADIUS_THRESHOLD, CONFIDENCE_FLOOR
from ..redaction import sanitize_for_llm

logger = logging.getLogger(__name__)

# Deterministic fallback: used if no LLM provider is configured, the LLM
# response isn't a valid registry key, or the LLM call fails outright.
_ENTITY_ACTION_HINTS = {
    "payment-gateway": "failover_dependency",
    "invoice-db": "restart_pod",
    "order-queue-consumer": "clear_queue_backlog",
    "queue": "clear_queue_backlog",
    "notification-svc": "rollback_deployment",
    "edge-router-cluster": "suppress_duplicate_alerts",
}


class ActionAgent:
    async def run(self, state: InvestigationState) -> dict:
        if state.status == "suppressed":
            return {}

        blast_radius = len({a.service for a in state.alerts})
        if blast_radius > BLAST_RADIUS_THRESHOLD:
            return {"status": "escalated"}

        if state.confidence < CONFIDENCE_FLOOR:
            return {"status": "escalated"}

        if state.policy_decision and state.policy_decision.maintenance_window_active:
            return {"status": "suppressed"}

        action_name = await self._pick_action(state)
        if action_name is None:
            return {"status": "escalated"}

        spec = ACTIONS[action_name]
        action = Action(
            action_id=str(uuid.uuid4()),
            incident_id=state.incident_id,
            name=action_name,
            spec=spec,
            params={"service": state.alerts[0].service} if state.alerts else {},
            status="proposed",
            proposed_at=datetime.now(timezone.utc),
        )

        if spec.tier == "DESTRUCTIVE":
            approved = await self._await_approval(state, action)
            if not approved:
                action.status = "rejected"
                return {"actions": state.actions + [action], "status": "escalated"}
            action.status = "approved"

        result = await execute_action(
            action.name, spec.adapter, {"action_id": action.action_id, **action.params}, state.incident_id,
        )
        action.status = "executed" if result.success else "failed"

        return {
            "actions": state.actions + [action],
            "action_results": state.action_results + [result],
            "status": "resolved" if result.success else "escalated",
        }

    @staticmethod
    async def _await_approval(state: InvestigationState, action: Action) -> bool:
        from langgraph.types import interrupt
        decision = interrupt({
            "reason": "destructive_action_awaiting_approval",
            "incident_id": state.incident_id,
            "action_id": action.action_id,
            "action_name": action.name,
        })
        return bool((decision or {}).get("approved"))

    async def _pick_action(self, state: InvestigationState) -> Optional[str]:
        top_hypothesis = self._top_hypothesis(state)
        entity = (top_hypothesis.root_cause_entity if top_hypothesis else None) or ""

        llm_pick = await self._ask_llm_to_pick(entity)
        if llm_pick in ACTIONS:
            return llm_pick

        for hint, action_name in _ENTITY_ACTION_HINTS.items():
            if hint in entity:
                return action_name

        return None

    @staticmethod
    def _top_hypothesis(state: InvestigationState):
        surviving = [h for h in state.hypotheses if not h.superseded]
        if not surviving:
            return None
        return max(surviving, key=lambda h: h.confidence)

    async def _ask_llm_to_pick(self, entity: str) -> Optional[str]:
        registry_text = "\n".join(f"- {name} ({spec.tier}): {spec.description}" for name, spec in ACTIONS.items())
        messages = sanitize_for_llm([
            {"role": "system", "content": (
                "You choose exactly one action name from the registry below to "
                "remediate the given root cause. Respond with ONLY the action "
                "name, nothing else — no punctuation, no explanation. If none of "
                "the registered actions fit, respond with exactly: none"
            )},
            {"role": "user", "content": f"Root cause entity: {entity or 'unknown'}\n\nRegistry:\n{registry_text}"},
        ])
        try:
            from ..llm import rased_chat_completion
            result = await rased_chat_completion(messages, session_id="rased-action")
            text = (result or {}).get("response", "").strip()
            return text or None
        except Exception as exc:
            logger.warning(f"rased action LLM pick failed, falling back to entity hints: {exc}")
            return None


__all__ = ["ActionAgent"]
