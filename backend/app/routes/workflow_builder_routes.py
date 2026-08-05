"""AI Operations — Agentic Workflow Builder routes (design-time: CRUD,
versioning, validation, templates, AI generation, import/export, explain).
Runtime/execution routes live in workflow_execution_routes.py."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services.workflow import (
    workflow_definition_service, validation_engine, ai_workflow_generator,
    explain_workflow_service, import_export_service, templates_seed,
)
from ..services.rbac_service import check_permission
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/v1/workflows", tags=["Agentic Workflow Builder"])


async def _require(current_user: dict, permission: str) -> None:
    if not await check_permission(current_user, permission):
        raise HTTPException(status_code=403, detail=f"requires '{permission}' permission")


@router.get("/templates")
async def list_templates(current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    return {"templates": await templates_seed.list_templates()}


@router.get("")
async def list_workflows(status: Optional[str] = None, tag: Optional[str] = None, search: Optional[str] = None,
                          current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    return {"workflows": await workflow_definition_service.list_workflows(status, tag, search)}


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, version: Optional[int] = None, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    result = await workflow_definition_service.get_workflow(workflow_id, version)
    if result is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return result


class CreateWorkflowPayload(BaseModel):
    payload: Dict[str, Any]


@router.post("")
async def create_workflow(body: CreateWorkflowPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.create")
    result = await workflow_definition_service.create_draft(body.payload, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class UpdateWorkflowPayload(BaseModel):
    updates: Dict[str, Any]


@router.put("/{workflow_id}/draft")
async def update_workflow_draft(workflow_id: str, body: UpdateWorkflowPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.edit")
    result = await workflow_definition_service.update_draft(workflow_id, body.updates, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{workflow_id}/validate")
async def validate_workflow(workflow_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    record = await workflow_definition_service.get_workflow(workflow_id)
    if record is None or record.get("version") is None:
        raise HTTPException(status_code=404, detail="workflow or version not found")
    findings = await validation_engine.validate_workflow_version(workflow_id, record["version"]["version"])
    return {"findings": findings}


class PublishPayload(BaseModel):
    force: bool = False


@router.post("/{workflow_id}/publish")
async def publish_workflow(workflow_id: str, body: PublishPayload = PublishPayload(), current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.publish")
    result = await workflow_definition_service.publish(workflow_id, current_user.get("email", "unknown"), force=body.force)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/{workflow_id}/versions/{version}/rollback")
async def rollback_workflow(workflow_id: str, version: int, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.publish")
    result = await workflow_definition_service.rollback(workflow_id, version, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{workflow_id}/versions/{version}/clone")
async def clone_workflow(workflow_id: str, version: int, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.create")
    result = await workflow_definition_service.clone(workflow_id, version, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{workflow_id}/versions/{v1}/compare/{v2}")
async def compare_workflow(workflow_id: str, v1: int, v2: int, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    result = await workflow_definition_service.compare(workflow_id, v1, v2)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class SetStatusPayload(BaseModel):
    status: str


@router.post("/{workflow_id}/status")
async def set_workflow_status(workflow_id: str, body: SetStatusPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.edit")
    result = await workflow_definition_service.set_status(workflow_id, body.status, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{workflow_id}/explain")
async def explain_workflow(workflow_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    result = await explain_workflow_service.explain(workflow_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


class GeneratePayload(BaseModel):
    description: str


@router.post("/generate")
async def generate_workflow(body: GeneratePayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.create")
    return await ai_workflow_generator.generate(body.description)


class FromGeneratedPayload(BaseModel):
    name: str
    graph: Dict[str, Any]


@router.post("/from-generated")
async def create_from_generated(body: FromGeneratedPayload, current_user: dict = Depends(require_auth)):
    """The one explicit, human-triggered step between an AI-generated
    preview and an actual draft — generate() itself never writes to
    workflow_versions (see ai_workflow_generator.py)."""
    await _require(current_user, "workflow.create")
    result = await workflow_definition_service.create_draft({
        "name": body.name, "nodes": body.graph.get("nodes", []), "edges": body.graph.get("edges", []),
        "variables": body.graph.get("variables", []), "trigger_config": body.graph.get("trigger_config", {}),
    }, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class FromTemplatePayload(BaseModel):
    name: str


@router.post("/from-template/{template_id}")
async def create_from_template(template_id: str, body: FromTemplatePayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.create")
    result = await workflow_definition_service.new_draft_from_template(template_id, body.name, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{workflow_id}/save-as-template")
async def save_as_template(workflow_id: str, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.edit")
    from ..core.database import db
    import uuid
    from datetime import datetime, timezone

    record = await workflow_definition_service.get_workflow(workflow_id)
    if record is None or record.get("version") is None:
        raise HTTPException(status_code=404, detail="workflow or version not found")
    version = record["version"]
    doc = {
        "template_id": str(uuid.uuid4()), "name": f"{record['definition']['name']} (template)",
        "description": record["definition"].get("description", ""), "category": record["definition"].get("category", "custom"),
        "is_built_in": False,
        "graph_snapshot": {"nodes": version.get("nodes", []), "edges": version.get("edges", []),
                            "variables": version.get("variables", []), "trigger_config": version.get("trigger_config", {})},
        "tags": record["definition"].get("tags", []), "created_by": current_user.get("email", "unknown"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.workflow_templates.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/{workflow_id}/export")
async def export_workflow(workflow_id: str, format: str = "json", current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    record = await workflow_definition_service.get_workflow(workflow_id)
    if record is None or record.get("version") is None:
        raise HTTPException(status_code=404, detail="workflow or version not found")
    result = import_export_service.export_version(record["version"], format)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class ImportPayload(BaseModel):
    content: str
    format: str = "json"


@router.post("/import")
async def import_workflow(body: ImportPayload, current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.create")
    result = await import_export_service.import_graph(body.content, body.format, current_user.get("email", "unknown"))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{workflow_id}/agent-catalog")
async def workflow_agent_catalog(current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    from ..services.agent_builder import agent_definition_service
    return {"agents": await agent_definition_service.get_agent_catalog()}


@router.get("/{workflow_id}/tool-catalog")
async def workflow_tool_catalog(current_user: dict = Depends(require_auth)):
    await _require(current_user, "workflow.read")
    from ..services.tool_catalog_service import list_tools
    return {"tools": await list_tools(status="active")}


__all__ = ["router"]
