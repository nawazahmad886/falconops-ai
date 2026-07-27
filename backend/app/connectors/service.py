"""
FalconOps AI - Connector SDK: wiring layer

Loads a connector's stored config, decrypts its secrets, instantiates and
connects the registered class. Used by both the API routes and the scheduler
so there's exactly one path for "turn a db.integrations doc into a live
connector instance."
"""
import logging
from typing import Any, Dict, List, Optional, Type

from ..core.database import db
from .base import (
    BaseConnector,
    AIContextCapable,
    EventsCapable,
    InventoryCapable,
    LogsCapable,
    MetricsCapable,
    RemediationCapable,
    TopologyCapable,
)
from .crypto import decrypt_config_secrets
from .registry import CONNECTOR_REGISTRY

logger = logging.getLogger(__name__)


def _capabilities_of_class(cls: Type[BaseConnector]) -> List[str]:
    """Class-level equivalent of BaseConnector.capabilities() — used where we
    only have the registered class, not a live (configured/connected) instance,
    e.g. listing every registered connector's capabilities in GET /api/connectors
    regardless of whether it's configured yet."""
    caps: List[str] = []
    if issubclass(cls, MetricsCapable):
        caps.append("metrics")
    if issubclass(cls, EventsCapable):
        caps.append("events")
    if issubclass(cls, LogsCapable):
        caps.append("logs")
    if issubclass(cls, TopologyCapable):
        caps.append("topology")
    if issubclass(cls, InventoryCapable):
        caps.append("inventory")
    if issubclass(cls, RemediationCapable):
        caps.append("remediation")
    if issubclass(cls, AIContextCapable):
        caps.append("ai_context")
    return caps


async def _catalog_item(integration_id: str) -> Optional[Dict[str, Any]]:
    from ..services.integration_management_service import INTEGRATION_CATALOG
    return next((c for c in INTEGRATION_CATALOG if c["id"] == integration_id), None)


async def build_connector(integration_id: str, tenant_id: Optional[str] = None) -> Optional[BaseConnector]:
    """None if not registered or not configured — never raises for that case,
    so callers can treat "no connector" as a normal, expected outcome."""
    cls = CONNECTOR_REGISTRY.get(integration_id)
    if not cls:
        return None
    doc = await db.integrations.find_one({"integration_id": integration_id}, {"_id": 0})
    if not doc:
        return None

    catalog_item = await _catalog_item(integration_id)
    config = await decrypt_config_secrets(doc.get("config", {}), catalog_item)
    connector = cls(config, tenant_id=tenant_id)
    await connector.connect()
    return connector


async def test_connector(integration_id: str) -> Dict[str, Any]:
    if integration_id not in CONNECTOR_REGISTRY:
        return {"success": False, "error": f"Unknown connector: {integration_id}"}
    connector = await build_connector(integration_id)
    if connector is None:
        return {"success": False, "error": "Connector not configured"}
    result = await connector.test_connection()
    return {"success": result.status == "healthy", **result.to_dict()}


async def list_connectors_status() -> List[Dict[str, Any]]:
    docs = await db.integrations.find(
        {"integration_id": {"$in": list(CONNECTOR_REGISTRY.keys())}}, {"_id": 0}
    ).to_list(200)
    doc_map = {d["integration_id"]: d for d in docs}

    result = []
    for integration_id, cls in CONNECTOR_REGISTRY.items():
        meta = cls.metadata()
        doc = doc_map.get(integration_id)
        result.append({
            "id": integration_id,
            "name": meta.name,
            "vendor": meta.vendor,
            "version": meta.version,
            "category": meta.category,
            "capabilities": _capabilities_of_class(cls),
            "configured": doc is not None,
            "enabled": bool(doc.get("enabled", False)) if doc else False,
        })
    return result


async def get_connector_recommendations(integration_id: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    connector = await build_connector(integration_id)
    if connector is None or not isinstance(connector, RemediationCapable):
        return []
    return await connector.get_recommendations(context)
