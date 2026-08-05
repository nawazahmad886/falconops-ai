"""
AI Workflow Generator — natural language -> draft workflow JSON.

Has NO write path to workflow_versions. generate() returns {graph,
validation_result} to the route layer; creating an actual draft from that
JSON is a separate, explicit POST (workflow_builder_routes.py's
/from-generated endpoint), which the frontend only calls after the user
reviews the Preview and clicks "Create Draft". Publishing is a further,
separate, explicit call gated by workflow.publish. This is what "AI never
auto-deploys" means concretely here — not a policy note, an actual missing
code path.
"""
import json
import logging
from typing import Any, Dict, List

from ..rased.redaction import sanitize_for_llm

logger = logging.getLogger(__name__)

_NODE_TYPE_LIST = (
    "trigger_manual, trigger_schedule, trigger_alert, trigger_incident, trigger_api, trigger_webhook, "
    "trigger_threshold, trigger_event, agent, planner, ai_decision, synthesizer, judge, "
    "data_elasticsearch, data_apm, data_sql, data_metrics, data_logs, data_http, data_rag_search, data_memory, "
    "condition, switch, parallel, join, loop, wait, retry, timeout, "
    "action_restart_pod, action_scale_service, action_run_workflow, action_create_ticket, action_send_email, "
    "action_send_teams, action_send_slack, action_create_incident, "
    "human_approval, risk_check, permission_check, policy_check, verification, health_check, slo_check"
)


def _build_prompt(description: str, agent_catalog: List[Dict], tool_catalog: List[Dict]) -> List[Dict[str, str]]:
    agents_desc = "\n".join(f"  - {a['agent_id']}: {a.get('description', '')}" for a in agent_catalog[:30])
    tools_desc = "\n".join(f"  - {t['tool_id']} ({t.get('risk_tier', 'SAFE')}): {t.get('description', '')}" for t in tool_catalog[:50])
    system = (
        "You design FalconOps AI Operations workflow graphs. Output ONLY a single JSON object with keys "
        '"nodes" and "edges" — no prose, no markdown fences.\n\n'
        f"Allowed node 'type' values: {_NODE_TYPE_LIST}\n\n"
        "Each node: {\"node_id\": str, \"type\": str, \"position\": {\"x\": num, \"y\": num}, "
        "\"config\": {...type-specific...}, \"label\": str}\n"
        "Each edge: {\"edge_id\": str, \"source\": node_id, \"target\": node_id, \"condition_branch\": str|null}\n\n"
        "Rules:\n"
        "- Every graph MUST start with exactly one trigger_* node.\n"
        "- 'agent' nodes need config.agent_id from this list:\n" + (agents_desc or "  (none available)") + "\n"
        "- Data/Action/health/slo nodes need config.tool_id from this list (leave \"\" if nothing fits — never invent a tool_id):\n"
        + (tools_desc or "  (none available)") + "\n"
        "- Any node whose action could be DESTRUCTIVE (action_restart_pod, action_scale_service) MUST have a "
        "human_approval or risk_check node upstream of it on every path.\n"
        "- Do not invent agent_id or tool_id values outside the lists above.\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": description}]


async def generate(description: str) -> Dict[str, Any]:
    from ..llm_provider_service import chat_completion
    from . import validation_engine
    from ..agent_builder import agent_definition_service
    from ..tool_catalog_service import list_tools

    agent_catalog = await agent_definition_service.get_agent_catalog()
    tool_catalog = await list_tools(status="active")

    messages = _build_prompt(description, agent_catalog, tool_catalog)
    result = await chat_completion(sanitize_for_llm(messages), session_id="workflow-ai-generator")
    raw = result.get("response") or ""

    try:
        start, end = raw.find("{"), raw.rfind("}")
        graph = json.loads(raw[start:end + 1]) if start != -1 and end != -1 else {}
    except (ValueError, json.JSONDecodeError):
        graph = {}

    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    if not nodes:
        return {"graph": {"nodes": [], "edges": []},
                "validation_result": [{"severity": "error", "node_id": None, "rule": "generation_failed",
                                        "message": "The model did not return a parseable workflow graph. Try rephrasing, or build manually."}]}

    tools_by_id = {t["tool_id"]: t for t in tool_catalog}
    findings = validation_engine.validate_graph(nodes, edges, tools_by_id)
    return {"graph": {"nodes": nodes, "edges": edges}, "validation_result": findings}


__all__ = ["generate"]
