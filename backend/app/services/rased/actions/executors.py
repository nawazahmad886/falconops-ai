"""
Action executors. Every executor returns an ActionResult carrying
config.EXECUTION_MODE — but every executor in this module only *simulates*
its effect regardless of that value, because no real MQ/gateway/deployment
client is wired into RASED in this build. EXECUTION_MODE=="live" here means
"the config gate that would unlock a real client was passed," not "a real
client exists" — see integrations/jira.py and integrations/teams.py for
adapters that do draw that distinction (mock vs a NotImplementedError live
path), which is the more honest place for it given four of these five
execution targets (MQ, gateway, deployment system, internal suppression)
have no real backend to call in this codebase at all.

restart_pod is the one exception: adapters/k8s_real.py wires a genuine
Kubernetes client, gated on a configured "kubernetes_cluster" integration.
See _restart_pod_executor below for the real/fallback dispatch — every other
action here is unchanged, still simulation-only.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict

from ....models.rased_schemas import ActionResult
from ..config import EXECUTION_MODE
from .adapters import k8s_real

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


async def _get_k8s_cluster_config() -> Dict[str, Any]:
    """Loads + decrypts the "kubernetes_cluster" integration, same pattern
    integration_management_service.test_integration() uses for connector-SDK
    entries. Returns {} (not an error) when unconfigured — the caller treats
    an empty config as "fall back to simulation", not a crash."""
    try:
        from ....core.database import db
        from ....services.integration_management_service import INTEGRATION_CATALOG
        from ....connectors.crypto import decrypt_config_secrets
        doc = await db.integrations.find_one({"integration_id": "kubernetes_cluster", "enabled": True})
        if not doc:
            return {}
        catalog_item = next((c for c in INTEGRATION_CATALOG if c["id"] == "kubernetes_cluster"), None)
        return await decrypt_config_secrets(dict(doc.get("config", {})), catalog_item)
    except Exception as e:
        logger.warning(f"kubernetes_cluster integration lookup failed: {e}")
        return {}


async def _restart_pod_executor(action_name: str, params: Dict[str, Any], incident_id: str) -> ActionResult:
    """restart_pod's real/fallback dispatch. Three outcomes, each a genuinely
    different signal — never collapsed into one:
      1. No cluster configured / no pod mapping for this service -> falls back
         to the same simulated result every other action produces. This is a
         GUARDED action; failing outright over a missing optional integration
         would be worse than a clearly-labeled simulated run (execution_mode
         says which happened).
      2. Cluster configured and the real delete succeeds -> execution_mode
         "live", output carries the actual pods deleted.
      3. Cluster configured but the API call genuinely fails (auth rejected,
         network error, etc.) -> success=False, real error surfaced. This does
         NOT fall back to simulation — a cluster that actively rejected the
         request is a materially different, more important signal than "not
         configured", and silently papering over it with a fake success would
         be exactly the kind of fabrication this session has been fixing.
    """
    started = datetime.now(timezone.utc)
    service = params.get("service", "")
    cluster_config = await _get_k8s_cluster_config()

    if not cluster_config:
        return await _simulate(action_name, params, incident_id,
                                f"[{EXECUTION_MODE.upper()}] k8s action '{action_name}' simulated — "
                                f"no kubernetes_cluster integration configured")

    try:
        result = await k8s_real.restart_pod(cluster_config, service)
        return ActionResult(
            action_id=str(params.get("action_id", action_name)), incident_id=incident_id, success=True,
            execution_mode="live", output=result, executed_at=started,
            duration_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )
    except k8s_real.KubernetesUnavailable as e:
        # Configured but this specific service has no pod mapping, or the
        # client library isn't installed — same honest fallback as "not configured".
        return await _simulate(action_name, params, incident_id,
                                f"[{EXECUTION_MODE.upper()}] k8s action '{action_name}' simulated — {e}")
    except Exception as e:
        logger.warning(f"real restart_pod failed for service '{service}': {e}")
        return ActionResult(
            action_id=str(params.get("action_id", action_name)), incident_id=incident_id, success=False,
            execution_mode="live", error=str(e)[:500], executed_at=started,
            duration_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )


EXECUTORS: Dict[str, Callable[[str, Dict[str, Any], str], Awaitable[ActionResult]]] = {
    "internal": _executor("[{mode}] suppressed duplicate alerts"),
    "elk": _executor("[{mode}] collected diagnostics from elk"),
    "k8s_mock": _executor("[{mode}] k8s action '{action}' simulated, no real cluster contacted"),
    "k8s_restart_pod": _restart_pod_executor,
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
