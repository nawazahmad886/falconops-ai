"""
Action executors. Every executor returns an ActionResult carrying
config.EXECUTION_MODE — but every executor in this module only *simulates*
its effect regardless of that value, because no real k8s/MQ/gateway/
deployment client is wired into RASED in this build. EXECUTION_MODE=="live"
here means "the config gate that would unlock a real client was passed,"
not "a real client exists" — see integrations/jira.py and
integrations/teams.py for adapters that do draw that distinction (mock vs a
NotImplementedError live path), which is the more honest place for it given
none of these five execution targets (k8s, MQ, gateway, deployment system,
internal suppression) has any real backend to call in this codebase at all.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict

from ....models.rased_schemas import ActionResult
from ..config import EXECUTION_MODE

logger = logging.getLogger(__name__)


async def _simulate(action_name: str, params: Dict[str, Any], incident_id: str, note: str) -> ActionResult:
    started = datetime.now(timezone.utc)
    await asyncio.sleep(0.05)  # mirrors remediation_service's dry-run round-trip delay
    return ActionResult(
        action_id=str(params.get("action_id", action_name)),
        incident_id=incident_id,
        success=True,
        execution_mode=EXECUTION_MODE,
        output={"note": note, "params": {k: v for k, v in params.items() if k != "action_id"}},
        executed_at=started,
    )


def _executor(note_template: str) -> Callable[[str, Dict[str, Any], str], Awaitable[ActionResult]]:
    async def run(action_name: str, params: Dict[str, Any], incident_id: str) -> ActionResult:
        return await _simulate(action_name, params, incident_id, note_template.format(mode=EXECUTION_MODE.upper(), action=action_name))
    return run


EXECUTORS: Dict[str, Callable[[str, Dict[str, Any], str], Awaitable[ActionResult]]] = {
    "internal": _executor("[{mode}] suppressed duplicate alerts"),
    "elk": _executor("[{mode}] collected diagnostics from elk"),
    "k8s_mock": _executor("[{mode}] k8s action '{action}' simulated, no real cluster contacted"),
    "mq_mock": _executor("[{mode}] mq action '{action}' simulated, no real broker contacted"),
    "gateway_mock": _executor("[{mode}] gateway failover simulated, no real gateway contacted"),
    "changes_mock": _executor("[{mode}] rollback simulated, no real deployment system contacted"),
}


async def execute_action(action_name: str, adapter: str, params: Dict[str, Any], incident_id: str) -> ActionResult:
    executor = EXECUTORS.get(adapter)
    if executor is None:
        return ActionResult(
            action_id=str(params.get("action_id", action_name)), incident_id=incident_id, success=False,
            execution_mode=EXECUTION_MODE, error=f"no executor registered for adapter '{adapter}'",
            executed_at=datetime.now(timezone.utc),
        )
    try:
        return await executor(action_name, params, incident_id)
    except Exception as exc:
        logger.exception(f"action executor failed for {action_name}")
        return ActionResult(
            action_id=str(params.get("action_id", action_name)), incident_id=incident_id, success=False,
            execution_mode=EXECUTION_MODE, error=str(exc), executed_at=datetime.now(timezone.utc),
        )


__all__ = ["execute_action", "EXECUTORS"]
