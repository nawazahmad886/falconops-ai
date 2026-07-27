"""
FalconOps AI - Connector SDK: AI-context auto-registration

Wires every AIContextCapable connector's get_ai_context() into
ai_tools_service.py's existing three module-level registries (TOOL_DEFS,
_TOOL_FUNCS, _ALLOWED_PARAMS) rather than inventing a second AI-tool
registry — a connector-sourced tool is then indistinguishable from a
hand-written one to the LLM tool-calling layer, and is exercised via the
existing GET /api/ai-intelligence/tools / POST .../execute routes with no
new AI-tool HTTP surface needed.
"""
import inspect
import logging
from typing import Any, Dict

from ..services import ai_tools_service
from .base import AIContextCapable
from .registry import CONNECTOR_REGISTRY
from .service import build_connector

logger = logging.getLogger(__name__)


def _params_schema(get_ai_context_method) -> Dict[str, str]:
    """Builds a TOOL_DEFS-style free-text params schema from the connector's
    real get_ai_context() override signature — same convention as every
    hand-written tool's "params" dict in ai_tools_service.TOOL_DEFS."""
    schema: Dict[str, str] = {}
    try:
        sig = inspect.signature(get_ai_context_method)
    except (TypeError, ValueError):
        return schema
    for name, param in sig.parameters.items():
        if name == "self" or param.kind in (param.VAR_KEYWORD, param.VAR_POSITIONAL):
            continue
        type_hint = getattr(param.annotation, "__name__", None) or "any"
        has_default = param.default is not inspect.Parameter.empty
        schema[name] = f"{type_hint}?" + (f" (default {param.default!r})" if has_default else "")
    return schema


def _allowed_params(get_ai_context_method) -> set:
    try:
        sig = inspect.signature(get_ai_context_method)
    except (TypeError, ValueError):
        return set()
    return {
        name for name, param in sig.parameters.items()
        if name != "self" and param.kind not in (param.VAR_KEYWORD, param.VAR_POSITIONAL)
    }


def register_ai_context_tools() -> int:
    """Called once at app startup, after connectors are registered. Returns
    the number of tools registered (for a startup log line)."""
    registered = 0
    for integration_id, cls in CONNECTOR_REGISTRY.items():
        if not issubclass(cls, AIContextCapable):
            continue

        tool_name = f"connector_{integration_id}_context"
        meta = cls.metadata()

        async def _tool(_integration_id: str = integration_id, **params) -> Dict[str, Any]:
            connector = await build_connector(_integration_id)
            if connector is None or not isinstance(connector, AIContextCapable):
                return {
                    "tool": f"connector_{_integration_id}_context",
                    "count": 0,
                    "data": [],
                    "summary": f"{_integration_id} connector not configured",
                    "error": "not_configured",
                }
            return await connector.get_ai_context(**params)

        ai_tools_service.TOOL_DEFS.append({
            "name": tool_name,
            "description": f"[{meta.vendor} connector] AI-facing context query.",
            "params": _params_schema(cls.get_ai_context),
        })
        ai_tools_service._TOOL_FUNCS[tool_name] = _tool
        ai_tools_service._ALLOWED_PARAMS[tool_name] = _allowed_params(cls.get_ai_context)
        registered += 1

    return registered
