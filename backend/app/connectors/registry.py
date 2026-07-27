"""
FalconOps AI - Connector SDK: registry

Plain dict registry, same idiom already established twice in this codebase
(connector_dispatcher.CONNECTOR_MAP, ai_tools_service._TOOL_FUNCS) — not a
novel discovery mechanism (no entry_points, no directory scanning).
"""
from typing import Dict, Type

from .base import BaseConnector

CONNECTOR_REGISTRY: Dict[str, Type[BaseConnector]] = {}


def register_connector(connector_id: str):
    """Class decorator: @register_connector("prometheus")"""

    def _wrap(cls: Type[BaseConnector]) -> Type[BaseConnector]:
        CONNECTOR_REGISTRY[connector_id] = cls
        return cls

    return _wrap
