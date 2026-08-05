"""Explain Workflow — read-only natural-language summary of a real graph.
No execution, no side effects."""
from typing import Any, Dict

from ..rased.redaction import sanitize_for_llm


def _describe_graph(nodes: list, edges: list) -> str:
    lines = ["Nodes:"]
    for n in nodes:
        lines.append(f"  - {n['node_id']} ({n['type']}): {n.get('label', '')} config={n.get('config', {})}")
    lines.append("Edges:")
    for e in edges:
        branch = f" [branch={e['condition_branch']}]" if e.get("condition_branch") else ""
        lines.append(f"  - {e['source']} -> {e['target']}{branch}")
    return "\n".join(lines)


async def explain(workflow_id: str) -> Dict[str, Any]:
    from ..llm_provider_service import chat_completion
    from . import workflow_definition_service

    record = await workflow_definition_service.get_workflow(workflow_id)
    if record is None or record.get("version") is None:
        return {"error": "workflow or version not found"}

    version = record["version"]
    graph_desc = _describe_graph(version.get("nodes", []), version.get("edges", []))
    messages = [
        {"role": "system", "content": "Summarize this FalconOps AI Operations workflow graph for an operator. "
                                        "Cover: purpose, flow (in order), agents used, tools used, conditions/branches, "
                                        "risks and potential side effects (call out any DESTRUCTIVE-tier actions "
                                        "explicitly), and required permissions. Be concise, plain language."},
        {"role": "user", "content": graph_desc},
    ]
    result = await chat_completion(sanitize_for_llm(messages), session_id=f"workflow-explain-{workflow_id}")
    return {"workflow_id": workflow_id, "explanation": result.get("response", ""), "model": result.get("model")}


__all__ = ["explain"]
