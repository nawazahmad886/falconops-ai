"""
Workflow Definition CRUD + versioning — structurally identical to
agent_builder/agent_definition_service.py's header/version split, applied
to workflow_definitions/workflow_versions. Nodes/edges are embedded in the
version document rather than normalized into separate collections: a
500-node/2000-edge graph is well under MongoDB's 16MB document limit, and
embedding lets the canvas hydrate a whole workflow in one round trip —
material for the "100+ nodes without freezing" requirement.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ...models.agent_workflow_schemas import WorkflowDefinition, WorkflowVersion

logger = logging.getLogger(__name__)


async def _ensure_indexes() -> None:
    from ...core.database import db
    try:
        await db.workflow_definitions.create_index("workflow_id", unique=True)
        await db.workflow_definitions.create_index("status")
        await db.workflow_definitions.create_index("tags")
        await db.workflow_versions.create_index([("workflow_id", 1), ("version", 1)], unique=True)
        await db.workflow_versions.create_index([("workflow_id", 1), ("state", 1)])
    except Exception as e:
        logger.warning(f"workflow_definitions index setup failed: {e}")


async def _get_version(workflow_id: str, version: int) -> Optional[Dict]:
    from ...core.database import db
    return await db.workflow_versions.find_one({"workflow_id": workflow_id, "version": version}, {"_id": 0})


async def get_workflow(workflow_id: str, version: Optional[int] = None) -> Optional[Dict]:
    from ...core.database import db
    header = await db.workflow_definitions.find_one({"workflow_id": workflow_id}, {"_id": 0})
    if header is None:
        return None
    target_version = version or header.get("current_published_version") or header.get("latest_draft_version")
    version_doc = await _get_version(workflow_id, target_version) if target_version else None
    return {"definition": header, "version": version_doc}


async def list_workflows(status: Optional[str] = None, tag: Optional[str] = None, search: Optional[str] = None) -> List[Dict]:
    from ...core.database import db
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if tag:
        query["tags"] = tag
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    return await db.workflow_definitions.find(query, {"_id": 0}).sort("updated_at", -1).to_list(500)


async def create_draft(payload: Dict[str, Any], created_by: str) -> Dict[str, Any]:
    await _ensure_indexes()
    from ...core.database import db

    workflow_id = payload.get("workflow_id") or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    try:
        definition = WorkflowDefinition(
            workflow_id=workflow_id, name=payload.get("name", "Untitled Workflow"),
            description=payload.get("description", ""), category=payload.get("category", "custom"),
            tags=payload.get("tags", []), created_by=created_by, created_at=now, updated_at=now,
        )
        version = WorkflowVersion(
            version_id=str(uuid.uuid4()), workflow_id=workflow_id, version=1, state="draft",
            created_by=created_by,
            **{k: v for k, v in payload.items() if k in WorkflowVersion.model_fields and k not in ("version_id", "workflow_id", "version", "state")},
        )
    except ValidationError as e:
        return {"error": f"invalid workflow definition: {e}"}

    await db.workflow_definitions.insert_one(definition.model_dump(mode="json"))
    await db.workflow_versions.insert_one(version.model_dump(mode="json"))
    return {"definition": definition.model_dump(mode="json"), "version": version.model_dump(mode="json")}


async def update_draft(workflow_id: str, updates: Dict[str, Any], updated_by: str) -> Dict[str, Any]:
    from ...core.database import db
    header = await db.workflow_definitions.find_one({"workflow_id": workflow_id})
    if header is None:
        return {"error": "workflow not found"}

    draft_version = header.get("latest_draft_version")
    existing = await _get_version(workflow_id, draft_version)
    if existing is None or existing.get("state") != "draft":
        draft_version = (header.get("latest_draft_version") or 0) + 1
        existing = existing or {}

    merged = {**existing, **updates, "workflow_id": workflow_id, "version": draft_version, "state": "draft"}
    try:
        version = WorkflowVersion(**merged)
    except ValidationError as e:
        return {"error": f"invalid workflow definition: {e}"}

    doc = version.model_dump(mode="json")
    await db.workflow_versions.update_one({"workflow_id": workflow_id, "version": draft_version}, {"$set": doc}, upsert=True)
    await db.workflow_definitions.update_one(
        {"workflow_id": workflow_id},
        {"$set": {"latest_draft_version": draft_version, "updated_at": datetime.now(timezone.utc).isoformat(),
                   **{k: updates[k] for k in ("name", "description", "category", "tags") if k in updates}}},
    )
    return doc


async def publish(workflow_id: str, published_by: str, force: bool = False) -> Dict[str, Any]:
    from ...core.database import db
    from . import validation_engine

    header = await db.workflow_definitions.find_one({"workflow_id": workflow_id})
    if header is None:
        return {"error": "workflow not found"}
    draft_version = header.get("latest_draft_version")
    version_doc = await _get_version(workflow_id, draft_version)
    if version_doc is None:
        return {"error": "no draft version to publish"}

    findings = await validation_engine.validate_workflow_version(workflow_id, draft_version)
    errors = [f for f in findings if f["severity"] == "error"]
    if errors and not force:
        return {"error": "validation failed", "findings": findings}

    now = datetime.now(timezone.utc)
    await db.workflow_versions.update_one(
        {"workflow_id": workflow_id, "version": draft_version},
        {"$set": {"state": "published", "published_at": now.isoformat()}},
    )
    await db.workflow_definitions.update_one(
        {"workflow_id": workflow_id},
        {"$set": {"status": "published", "current_published_version": draft_version, "updated_at": now.isoformat()}},
    )
    return {"workflow_id": workflow_id, "published_version": draft_version, "findings": findings}


async def set_status(workflow_id: str, status: str, actor: str) -> Dict[str, Any]:
    if status not in ("draft", "published", "paused", "disabled", "archived"):
        return {"error": "invalid status"}
    from ...core.database import db
    result = await db.workflow_definitions.update_one(
        {"workflow_id": workflow_id}, {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        return {"error": "workflow not found"}
    return {"workflow_id": workflow_id, "status": status}


async def rollback(workflow_id: str, target_version: int, actor: str) -> Dict[str, Any]:
    from ...core.database import db
    version_doc = await _get_version(workflow_id, target_version)
    if version_doc is None or version_doc.get("state") != "published":
        return {"error": f"version {target_version} is not a published version"}
    await db.workflow_definitions.update_one(
        {"workflow_id": workflow_id},
        {"$set": {"current_published_version": target_version, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"workflow_id": workflow_id, "current_published_version": target_version}


async def clone(workflow_id: str, source_version: int, actor: str) -> Dict[str, Any]:
    from ...core.database import db
    header = await db.workflow_definitions.find_one({"workflow_id": workflow_id})
    source = await _get_version(workflow_id, source_version)
    if header is None or source is None:
        return {"error": "workflow or version not found"}

    new_version = (header.get("latest_draft_version") or 0) + 1
    doc = {**source, "version": new_version, "state": "draft", "version_id": str(uuid.uuid4()),
           "created_by": actor, "created_at": datetime.now(timezone.utc).isoformat(), "published_at": None,
           "changelog": f"cloned from v{source_version}"}
    await db.workflow_versions.insert_one(doc)
    await db.workflow_definitions.update_one(
        {"workflow_id": workflow_id}, {"$set": {"latest_draft_version": new_version, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return doc


async def compare(workflow_id: str, v1: int, v2: int) -> Dict[str, Any]:
    a = await _get_version(workflow_id, v1)
    b = await _get_version(workflow_id, v2)
    if a is None or b is None:
        return {"error": "one or both versions not found"}
    a_nodes = {n["node_id"] for n in a.get("nodes", [])}
    b_nodes = {n["node_id"] for n in b.get("nodes", [])}
    return {
        "workflow_id": workflow_id, "v1": v1, "v2": v2,
        "nodes_added": sorted(b_nodes - a_nodes), "nodes_removed": sorted(a_nodes - b_nodes),
        "trigger_changed": a.get("trigger_config") != b.get("trigger_config"),
        "edge_count_v1": len(a.get("edges", [])), "edge_count_v2": len(b.get("edges", [])),
    }


async def new_draft_from_template(template_id: str, name: str, created_by: str) -> Dict[str, Any]:
    from . import templates_seed
    template = await templates_seed.get_template(template_id)
    if template is None:
        return {"error": "template not found"}
    snapshot = template.get("graph_snapshot", {})
    return await create_draft({
        "name": name, "description": template.get("description", ""), "category": template.get("category", "custom"),
        "nodes": snapshot.get("nodes", []), "edges": snapshot.get("edges", []),
        "variables": snapshot.get("variables", []), "trigger_config": snapshot.get("trigger_config", {}),
    }, created_by)


__all__ = [
    "get_workflow", "list_workflows", "create_draft", "update_draft", "publish", "set_status",
    "rollback", "clone", "compare", "new_draft_from_template",
]
