"""
Tool binding dispatch — the ONLY place a Tool Catalog entry's binding is
actually invoked. Every function here is a thin call into code that already
exists and is already safe (RASED's action registry/adapters, the
Troubleshooting Command Center, the existing Connections/credentials layer,
RAG/vector memory search, RASED's real k8s client). There is no
"generic command" / "arbitrary code" branch anywhere in this module — the
dispatch table at the bottom has no default case, so a binding kind outside
the closed ToolBindingKind enum (models/agent_workflow_schemas.py) simply
cannot execute, even if a document were hand-edited in Mongo to claim one.
"""
import logging
import time
from typing import Any, Dict, Optional

from ..models.agent_workflow_schemas import ToolCatalogEntry, ToolDispatchResult

logger = logging.getLogger(__name__)


class ToolPermissionDenied(Exception):
    """Raised when the invoking actor lacks the tool's required_permission,
    or the tool's risk_tier isn't allowed in the current environment."""


async def _check_authorization(tool: ToolCatalogEntry, actor: Optional[Dict[str, Any]]) -> None:
    if not tool.required_permission:
        return
    if actor is None:
        raise ToolPermissionDenied(f"tool '{tool.tool_id}' requires '{tool.required_permission}' but no actor was provided")
    from .rbac_service import check_permission
    if not await check_permission(actor, tool.required_permission):
        raise ToolPermissionDenied(f"actor lacks required permission '{tool.required_permission}' for tool '{tool.tool_id}'")


async def _dispatch_rased_action(tool: ToolCatalogEntry, action_input: Dict[str, Any]) -> ToolDispatchResult:
    from .rased.actions.registry import ACTIONS
    from .rased.actions.executors import execute_action

    action_name = tool.binding.ref
    spec = ACTIONS.get(action_name)
    if spec is None:
        return ToolDispatchResult(success=False, error=f"unknown RASED action '{action_name}'", execution_mode="simulated")

    incident_id = action_input.get("incident_id") or f"tool-{tool.tool_id}"
    params = {**tool.binding.static_params, **{k: v for k, v in action_input.items() if k != "incident_id"}}
    result = await execute_action(action_name, spec.adapter, params, incident_id)
    return ToolDispatchResult(
        success=result.success, output=result.output, error=result.error,
        execution_mode=result.execution_mode, observation_kind="observed_data",
        duration_ms=result.duration_ms or 0,
    )


async def _dispatch_rased_adapter_readonly(tool: ToolCatalogEntry, action_input: Dict[str, Any]) -> ToolDispatchResult:
    from .rased.adapters import ADAPTERS

    adapter = ADAPTERS.get(tool.binding.ref)
    if adapter is None:
        return ToolDispatchResult(success=False, error=f"unknown RASED adapter source '{tool.binding.ref}'")

    params = {**tool.binding.static_params, **action_input}
    result = await adapter.query(params)
    return ToolDispatchResult(
        success=result.success, output={"data": result.data, "query": result.query} if result.success else {},
        error=result.error, execution_mode="read", observation_kind="observed_data",
        duration_ms=result.latency_ms,
    )


async def _dispatch_troubleshooting_command(tool: ToolCatalogEntry, action_input: Dict[str, Any]) -> ToolDispatchResult:
    from .troubleshooting_service import run_command

    command_id = tool.binding.ref
    params = {**tool.binding.static_params, **action_input}
    started = time.perf_counter()
    try:
        result = await run_command(command_id, params)
    except ValueError as e:
        return ToolDispatchResult(success=False, error=str(e))
    return ToolDispatchResult(
        success=bool(result.get("ok")), output=result.get("output", {}),
        error=(result.get("output") or {}).get("error") if not result.get("ok") else None,
        execution_mode="read", observation_kind="observed_data",
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


async def _dispatch_http_integration(tool: ToolCatalogEntry, action_input: Dict[str, Any]) -> ToolDispatchResult:
    """Generic, SSRF-guarded call against a configured Connection. Credentials
    are resolved server-side from db.integrations — never accepted as tool
    input and never present in the tool/agent/workflow definition itself."""
    from ..core.database import db
    from .integration_management_service import INTEGRATION_CATALOG
    from ..connectors.crypto import decrypt_config_secrets
    from .ssrf_guard import is_safe_outbound_url
    import httpx

    integration_id = tool.binding.ref
    doc = await db.integrations.find_one({"integration_id": integration_id, "enabled": True})
    if not doc:
        return ToolDispatchResult(success=False, error=f"integration '{integration_id}' not configured or disabled")

    catalog_item = next((c for c in INTEGRATION_CATALOG if c["id"] == integration_id), None)
    config = await decrypt_config_secrets(dict(doc.get("config", {})), catalog_item)

    url = tool.binding.static_params.get("url") or config.get("url") or config.get("webhook_url") or config.get("base_url")
    if not url:
        return ToolDispatchResult(success=False, error=f"integration '{integration_id}' has no configured URL for this tool")
    if not is_safe_outbound_url(url):
        return ToolDispatchResult(success=False, error="refused: URL resolves to a private/internal address")

    method = tool.binding.static_params.get("method", "POST")
    headers = {}
    if config.get("auth_header"):
        headers["Authorization"] = config["auth_header"]
    elif config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=tool.timeout_seconds) as client:
            resp = await client.request(method, url, json=action_input, headers=headers)
        ok = 200 <= resp.status_code < 300
        try:
            body: Any = resp.json()
        except ValueError:
            body = resp.text[:2000]
        return ToolDispatchResult(
            success=ok, output={"status_code": resp.status_code, "body": body},
            error=None if ok else f"HTTP {resp.status_code}", execution_mode="live",
            observation_kind="observed_data", duration_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as e:
        return ToolDispatchResult(success=False, error=str(e)[:500], execution_mode="live",
                                   duration_ms=int((time.perf_counter() - started) * 1000))


async def _get_k8s_cluster_config() -> Dict[str, Any]:
    from .rased.actions.executors import _get_k8s_cluster_config as _rased_get
    return await _rased_get()


async def _dispatch_k8s_read(tool: ToolCatalogEntry, action_input: Dict[str, Any]) -> ToolDispatchResult:
    from .rased.actions.adapters import k8s_real

    cluster_config = await _get_k8s_cluster_config()
    if not cluster_config:
        return ToolDispatchResult(success=False, error="no kubernetes_cluster integration configured", execution_mode="read")

    namespace = action_input.get("namespace", "default")
    label_selector = action_input.get("label_selector")
    started = time.perf_counter()
    try:
        result = await k8s_real.list_pods(cluster_config, namespace, label_selector)
        return ToolDispatchResult(success=True, output=result, execution_mode="live", observation_kind="observed_data",
                                   duration_ms=int((time.perf_counter() - started) * 1000))
    except k8s_real.KubernetesUnavailable as e:
        return ToolDispatchResult(success=False, error=str(e), execution_mode="read")
    except Exception as e:
        return ToolDispatchResult(success=False, error=str(e)[:500], execution_mode="live")


async def _dispatch_k8s_restart_pod(tool: ToolCatalogEntry, action_input: Dict[str, Any]) -> ToolDispatchResult:
    from .rased.actions.executors import execute_action

    incident_id = action_input.get("incident_id") or f"tool-{tool.tool_id}"
    params = {**tool.binding.static_params, **{k: v for k, v in action_input.items() if k != "incident_id"}}
    result = await execute_action("restart_pod", "k8s_restart_pod", params, incident_id)
    return ToolDispatchResult(
        success=result.success, output=result.output, error=result.error,
        execution_mode=result.execution_mode, observation_kind="observed_data",
        duration_ms=result.duration_ms or 0,
    )


async def _dispatch_rag_search(tool: ToolCatalogEntry, action_input: Dict[str, Any]) -> ToolDispatchResult:
    from . import rag_service

    query_text = action_input.get("query", "")
    top_k = int(action_input.get("top_k", 3))
    started = time.perf_counter()
    if tool.binding.ref == "logs":
        results = await rag_service.find_similar_logs(query_text, top_k=top_k, service=action_input.get("service"))
    else:
        results = await rag_service.find_similar_incidents(query_text, top_k=top_k, service=action_input.get("service"))
    return ToolDispatchResult(
        success=True, output={"results": results}, execution_mode="read",
        observation_kind="retrieved_knowledge", duration_ms=int((time.perf_counter() - started) * 1000),
    )


async def _dispatch_memory_search(tool: ToolCatalogEntry, action_input: Dict[str, Any]) -> ToolDispatchResult:
    from . import vector_memory_service

    query_text = action_input.get("query", "")
    top_k = int(action_input.get("top_k", 5))
    started = time.perf_counter()
    results = await vector_memory_service.search(
        query_text, top_k=top_k,
        tenant_id=action_input.get("tenant_id"),
        kinds=[tool.binding.ref] if tool.binding.ref else None,
    )
    return ToolDispatchResult(
        success=True, output={"results": results}, execution_mode="read",
        observation_kind="retrieved_knowledge", duration_ms=int((time.perf_counter() - started) * 1000),
    )


_DISPATCH_TABLE = {
    "rased_action": _dispatch_rased_action,
    "rased_adapter_readonly": _dispatch_rased_adapter_readonly,
    "troubleshooting_command": _dispatch_troubleshooting_command,
    "http_integration": _dispatch_http_integration,
    "k8s_read": _dispatch_k8s_read,
    "k8s_restart_pod": _dispatch_k8s_restart_pod,
    "rag_search": _dispatch_rag_search,
    "memory_search": _dispatch_memory_search,
}


async def dispatch_tool(
    tool_id: str, action_input: Dict[str, Any], actor: Optional[Dict[str, Any]] = None,
) -> ToolDispatchResult:
    """Look up a tool_catalog entry and invoke its binding. No caller — the
    ReAct engine, a workflow Data/Action node, or a manual /test call — has
    any other way to make a tool actually run."""
    from .tool_catalog_service import get_tool

    raw = await get_tool(tool_id)
    if raw is None:
        return ToolDispatchResult(success=False, error=f"unknown tool_id '{tool_id}'")
    tool = ToolCatalogEntry(**raw)
    if tool.status != "active":
        return ToolDispatchResult(success=False, error=f"tool '{tool_id}' is disabled")

    try:
        await _check_authorization(tool, actor)
    except ToolPermissionDenied as e:
        return ToolDispatchResult(success=False, error=str(e))

    handler = _DISPATCH_TABLE.get(tool.binding.kind)
    if handler is None:
        # Unreachable in practice — ToolCatalogEntry's Pydantic validation
        # already rejects any binding.kind outside the enum at write time —
        # but this is the dispatcher's own independent enforcement, not just
        # relying on validation upstream having run.
        return ToolDispatchResult(success=False, error=f"no dispatcher registered for binding kind '{tool.binding.kind}'")

    started = time.perf_counter()
    try:
        result = await handler(tool, action_input)
    except Exception as e:
        logger.exception(f"tool dispatch failed for '{tool_id}'")
        result = ToolDispatchResult(success=False, error=str(e)[:500])
    if not result.duration_ms:
        result.duration_ms = int((time.perf_counter() - started) * 1000)
    return result


__all__ = ["dispatch_tool", "ToolPermissionDenied"]
