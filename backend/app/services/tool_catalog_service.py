"""
Tool Catalog — CRUD over db.tool_catalog.

This is the hard enforcement point for "never expose unrestricted execution":
ToolBindingKind (models/agent_workflow_schemas.py) is a closed Literal, and
Pydantic validation on create/update rejects anything outside it before a
document is ever written. tool_binding_dispatch.py's dispatch table then has
no default/fallback branch for an unrecognized kind — the two together mean
there is no path from "someone typed a new binding kind" to "arbitrary code
runs", not even via a hand-edited document.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ..models.agent_workflow_schemas import ToolCatalogEntry

logger = logging.getLogger(__name__)


async def _ensure_indexes() -> None:
    from ..core.database import db
    try:
        await db.tool_catalog.create_index("tool_id", unique=True)
        await db.tool_catalog.create_index("category")
        await db.tool_catalog.create_index("status")
        await db.tool_catalog.create_index("risk_tier")
        await db.tool_test_runs.create_index("tool_id")
    except Exception as e:
        logger.warning(f"tool_catalog index setup failed: {e}")


async def list_tools(category: Optional[str] = None, status: Optional[str] = None, risk_tier: Optional[str] = None) -> List[Dict]:
    from ..core.database import db
    query: Dict[str, Any] = {}
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    if risk_tier:
        query["risk_tier"] = risk_tier
    return await db.tool_catalog.find(query, {"_id": 0}).sort("name", 1).to_list(500)


async def get_tool(tool_id: str) -> Optional[Dict]:
    from ..core.database import db
    return await db.tool_catalog.find_one({"tool_id": tool_id}, {"_id": 0})


async def create_tool(payload: Dict[str, Any], created_by: str) -> Dict[str, Any]:
    await _ensure_indexes()
    from ..core.database import db

    payload = dict(payload)
    payload.setdefault("tool_id", str(uuid.uuid4()))
    payload["created_by"] = created_by
    payload["updated_by"] = created_by
    try:
        entry = ToolCatalogEntry(**payload)
    except ValidationError as e:
        return {"error": f"invalid tool definition: {e}"}

    doc = entry.model_dump(mode="json")
    await db.tool_catalog.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def update_tool(tool_id: str, updates: Dict[str, Any], updated_by: str) -> Dict[str, Any]:
    from ..core.database import db
    existing = await db.tool_catalog.find_one({"tool_id": tool_id}, {"_id": 0})
    if not existing:
        return {"error": "tool not found"}

    merged = {**existing, **updates, "tool_id": tool_id, "updated_by": updated_by}
    try:
        entry = ToolCatalogEntry(**merged)
    except ValidationError as e:
        return {"error": f"invalid tool definition: {e}"}

    doc = entry.model_dump(mode="json")
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.tool_catalog.update_one({"tool_id": tool_id}, {"$set": doc})
    return doc


async def set_tool_status(tool_id: str, status: str, updated_by: str) -> Dict[str, Any]:
    if status not in ("active", "disabled"):
        return {"error": "status must be 'active' or 'disabled'"}
    from ..core.database import db
    result = await db.tool_catalog.update_one(
        {"tool_id": tool_id},
        {"$set": {"status": status, "updated_by": updated_by, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        return {"error": "tool not found"}
    return {"tool_id": tool_id, "status": status}


async def new_tool_version(tool_id: str, updates: Dict[str, Any], updated_by: str) -> Dict[str, Any]:
    from ..core.database import db
    existing = await db.tool_catalog.find_one({"tool_id": tool_id}, {"_id": 0})
    if not existing:
        return {"error": "tool not found"}
    merged = {**existing, **updates, "tool_id": tool_id, "updated_by": updated_by, "version": existing.get("version", 1) + 1}
    try:
        entry = ToolCatalogEntry(**merged)
    except ValidationError as e:
        return {"error": f"invalid tool definition: {e}"}
    doc = entry.model_dump(mode="json")
    await db.tool_catalog.update_one({"tool_id": tool_id}, {"$set": doc})
    return doc


BINDING_KIND_METADATA = [
    {"kind": "rased_action", "label": "RASED Action", "description": "One of RASED's allowlisted, tiered actions (registry.py) — restart_pod, scale_out_service, etc.",
     "ref_hint": "action name, e.g. 'restart_pod'"},
    {"kind": "rased_adapter_readonly", "label": "RASED Evidence Adapter (read-only)", "description": "One of RASED's read-only telemetry adapters (elk, appdynamics, db, solarwinds, mq, cmdb, changes).",
     "ref_hint": "adapter source name, e.g. 'elk'"},
    {"kind": "troubleshooting_command", "label": "Troubleshooting Command", "description": "A read-only diagnostic command from the Troubleshooting Command Center catalog.",
     "ref_hint": "command id, e.g. 'k8s_get_pods'"},
    {"kind": "http_integration", "label": "HTTP Integration", "description": "A configured Connection (integration_id) — credentials resolved server-side, never embedded.",
     "ref_hint": "integration_id, e.g. 'custom_webhook'"},
    {"kind": "k8s_read", "label": "Kubernetes (read-only)", "description": "Real, read-only pod listing against the configured kubernetes_cluster integration.",
     "ref_hint": "not used — always list_pods"},
    {"kind": "k8s_restart_pod", "label": "Kubernetes Restart Pod", "description": "The one real, GUARDED-tier destructive action — deletes matched pods via RASED's real k8s executor.",
     "ref_hint": "not used — always restart_pod"},
    {"kind": "rag_search", "label": "RAG Search", "description": "Semantic search over incident history or logs (rag_service.py).",
     "ref_hint": "'incidents' or 'logs'"},
    {"kind": "memory_search", "label": "Memory Search", "description": "Semantic search over the shared vector memory store (vector_memory_service.py), filtered by kind.",
     "ref_hint": "memory kind, e.g. 'agent_ltm'"},
]


def list_binding_kinds() -> List[Dict[str, str]]:
    return BINDING_KIND_METADATA


async def record_test_run(tool_id: str, tool_version: int, input_payload: Dict[str, Any], result: Dict[str, Any], tested_by: str) -> None:
    from ..core.database import db
    try:
        await db.tool_test_runs.insert_one({
            "run_id": str(uuid.uuid4()), "tool_id": tool_id, "tool_version": tool_version,
            "input": input_payload, "output": result.get("output"), "success": result.get("success"),
            "error": result.get("error"), "latency_ms": result.get("duration_ms"),
            "tested_by": tested_by, "tested_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"tool_test_runs write failed: {e}")


__all__ = [
    "list_tools", "get_tool", "create_tool", "update_tool", "set_tool_status", "new_tool_version",
    "list_binding_kinds", "record_test_run", "BINDING_KIND_METADATA",
]
