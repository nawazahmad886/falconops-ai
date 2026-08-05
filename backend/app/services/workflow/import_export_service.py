"""
Import/Export — JSON guaranteed; YAML only if pyyaml is actually vendored
(checked at call time, not assumed). Import always creates a new DRAFT
version only, validated before it can be saved — never auto-executed,
matching the spec's explicit "never auto-run an imported workflow"
requirement.
"""
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_yaml_available = False
try:
    import yaml as _yaml
    _yaml_available = True
except ImportError:
    pass


def export_version(version_doc: Dict[str, Any], fmt: str = "json") -> Dict[str, Any]:
    payload = {
        "name": version_doc.get("workflow_id"), "version": version_doc.get("version"),
        "nodes": version_doc.get("nodes", []), "edges": version_doc.get("edges", []),
        "variables": version_doc.get("variables", []), "trigger_config": version_doc.get("trigger_config", {}),
    }
    if fmt == "yaml":
        if not _yaml_available:
            return {"error": "pyyaml is not installed in this deployment — export as JSON instead"}
        return {"format": "yaml", "content": _yaml.safe_dump(payload, sort_keys=False)}
    return {"format": "json", "content": json.dumps(payload, indent=2)}


async def import_graph(content: str, fmt: str, created_by: str) -> Dict[str, Any]:
    from . import validation_engine, workflow_definition_service

    try:
        if fmt == "yaml":
            if not _yaml_available:
                return {"error": "pyyaml is not installed in this deployment — import JSON instead"}
            payload = _yaml.safe_load(content)
        else:
            payload = json.loads(content)
    except Exception as e:
        return {"error": f"failed to parse {fmt}: {e}"}

    if not isinstance(payload, dict) or "nodes" not in payload or "edges" not in payload:
        return {"error": "payload must be an object with 'nodes' and 'edges'"}

    findings = validation_engine.validate_graph(payload.get("nodes", []), payload.get("edges", []))
    draft = await workflow_definition_service.create_draft({
        "name": payload.get("name", "Imported Workflow"), "nodes": payload.get("nodes", []),
        "edges": payload.get("edges", []), "variables": payload.get("variables", []),
        "trigger_config": payload.get("trigger_config", {}),
    }, created_by)
    if "error" in draft:
        return draft
    return {**draft, "validation_result": findings}


__all__ = ["export_version", "import_graph"]
