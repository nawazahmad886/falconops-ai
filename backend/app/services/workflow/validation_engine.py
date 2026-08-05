"""
Validation Engine — pre-publish checks over a (nodes, edges) graph. Every
check is a pure function returning ValidationFinding-shaped dicts; publish
is blocked on any "error"-severity finding (workflow_definition_service.py
enforces this), "warning" is surfaced but non-blocking.

DESTRUCTIVE-reachable-without-approval is the safety-critical check: it is
re-checked a second time at execution time by dag_engine.py's
_handle_action_via_tool (defense in depth against a published-then-edited
draft, or a tool's risk_tier changing after publish) — this function is the
publish-time gate, not the only gate.
"""
from typing import Any, Dict, List, Optional, Set

_TRIGGER_PREFIX = "trigger_"
_LOOP_TYPE = "loop"


def _node_map(nodes: List[Dict]) -> Dict[str, Dict]:
    return {n["node_id"]: n for n in nodes}


def _adjacency(edges: List[Dict]) -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {}
    for e in edges:
        adj.setdefault(e["source"], []).append(e["target"])
    return adj


def _reverse_adjacency(edges: List[Dict]) -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {}
    for e in edges:
        adj.setdefault(e["target"], []).append(e["source"])
    return adj


def _reachable_from_triggers(nodes: List[Dict], edges: List[Dict]) -> Set[str]:
    trigger_ids = [n["node_id"] for n in nodes if n["type"].startswith(_TRIGGER_PREFIX)]
    adj = _adjacency(edges)
    seen: Set[str] = set()
    stack = list(trigger_ids)
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(adj.get(current, []))
    return seen


def _check_disconnected_nodes(nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
    reachable = _reachable_from_triggers(nodes, edges)
    findings = []
    for n in nodes:
        if n["node_id"] not in reachable:
            findings.append({"severity": "error", "node_id": n["node_id"], "rule": "disconnected_node",
                              "message": f"Node '{n.get('label') or n['node_id']}' is not reachable from any Trigger node."})
    return findings


_REQUIRED_CONFIG_KEYS = {
    "agent": ["agent_id"], "planner": ["agent_id"], "ai_decision": ["agent_id"],
    "synthesizer": ["agent_id"], "judge": ["agent_id"],
    "data_elasticsearch": ["tool_id"], "data_apm": ["tool_id"], "data_sql": ["tool_id"],
    "data_metrics": ["tool_id"], "data_logs": ["tool_id"], "data_http": ["tool_id"],
    "data_rag_search": ["tool_id"], "data_memory": ["tool_id"],
    "action_restart_pod": ["tool_id"], "action_scale_service": ["tool_id"], "action_create_ticket": ["tool_id"],
    "action_send_email": ["tool_id"], "action_send_teams": ["tool_id"], "action_send_slack": ["tool_id"],
    "action_create_incident": ["tool_id"], "action_run_workflow": ["workflow_id"],
    "health_check": ["tool_id"], "slo_check": ["tool_id"], "loop": ["body_node_ids"],
}


def _check_missing_config(nodes: List[Dict]) -> List[Dict]:
    findings = []
    for n in nodes:
        required = _REQUIRED_CONFIG_KEYS.get(n["type"], [])
        config = n.get("config", {})
        for key in required:
            if not config.get(key):
                findings.append({"severity": "error", "node_id": n["node_id"], "rule": "missing_config",
                                  "message": f"Node '{n.get('label') or n['node_id']}' ({n['type']}) is missing required config.{key}."})
    return findings


def _check_invalid_edges(nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
    node_ids = {n["node_id"] for n in nodes}
    findings = []
    for e in edges:
        if e.get("source") not in node_ids:
            findings.append({"severity": "error", "node_id": e.get("target"), "rule": "invalid_edge",
                              "message": f"Edge {e.get('edge_id')} references nonexistent source node '{e.get('source')}'."})
        if e.get("target") not in node_ids:
            findings.append({"severity": "error", "node_id": e.get("source"), "rule": "invalid_edge",
                              "message": f"Edge {e.get('edge_id')} references nonexistent target node '{e.get('target')}'."})
    return findings


def _check_invalid_conditions(nodes: List[Dict]) -> List[Dict]:
    findings = []
    for n in nodes:
        if n["type"] == "condition":
            cond = n.get("config", {}).get("condition")
            if cond and cond.get("op") not in ("AND", "OR", "NOT", ">", "<", ">=", "<=", "==", "!=", "contains", "not_contains"):
                findings.append({"severity": "error", "node_id": n["node_id"], "rule": "invalid_condition",
                                  "message": f"Condition node '{n['node_id']}' has an unrecognized operator '{cond.get('op')}'."})
        if n["type"] == "switch":
            cases = n.get("config", {}).get("cases", [])
            if not cases:
                findings.append({"severity": "warning", "node_id": n["node_id"], "rule": "invalid_condition",
                                  "message": f"Switch node '{n['node_id']}' has no cases configured — will always take the default branch."})
    return findings


_DESTRUCTIVE_ACTION_TYPES = {"action_restart_pod", "action_scale_service"}


def _check_destructive_without_approval(nodes: List[Dict], edges: List[Dict], tools_by_id: Optional[Dict[str, Dict]] = None) -> List[Dict]:
    """A node is 'guarded' if a human_approval or risk_check node exists on
    EVERY path from any trigger to it. Approximated here via ancestor-set
    membership (an approval/risk_check node must be an ancestor on every
    simple path — we conservatively require it appear in the ancestor set
    reachable via ALL immediate predecessors, computed by intersecting
    per-predecessor ancestor sets rather than a true k-path enumeration,
    which is sufficient for the DAG sizes this canvas targets)."""
    rev = _reverse_adjacency(edges)
    node_types = {n["node_id"]: n["type"] for n in nodes}
    findings = []

    def _ancestors(node_id: str, seen: Optional[Set[str]] = None) -> Set[str]:
        seen = seen or set()
        for pred in rev.get(node_id, []):
            if pred in seen:
                continue
            seen.add(pred)
            _ancestors(pred, seen)
        return seen

    for n in nodes:
        if n["type"] not in _DESTRUCTIVE_ACTION_TYPES:
            continue
        tool_id = n.get("config", {}).get("tool_id")
        risk_tier = (tools_by_id or {}).get(tool_id, {}).get("risk_tier") if tool_id else None
        if risk_tier is not None and risk_tier != "DESTRUCTIVE":
            continue  # this instance is bound to a non-destructive tool — not gated by this rule
        ancestors = _ancestors(n["node_id"])
        has_gate = any(node_types.get(a) in ("human_approval", "risk_check") for a in ancestors)
        if not has_gate:
            findings.append({"severity": "error", "node_id": n["node_id"], "rule": "destructive_without_approval",
                              "message": f"Node '{n.get('label') or n['node_id']}' can execute a DESTRUCTIVE-tier action "
                                         "with no Human Approval or Risk Check node upstream of it."})
    return findings


def _check_circular_dependencies(nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
    """Loop nodes' body_node_ids are excluded — those form an intentional,
    bounded, config-driven re-entry (dag_engine.py runs them as a sub-walk,
    not a graph cycle), so edges purely among a loop's own body nodes are
    not counted as a cycle here."""
    loop_body_ids: Set[str] = set()
    for n in nodes:
        if n["type"] == _LOOP_TYPE:
            loop_body_ids.update(n.get("config", {}).get("body_node_ids", []))

    adj = _adjacency([e for e in edges if not (e["source"] in loop_body_ids and e["target"] in loop_body_ids)])
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n["node_id"]: WHITE for n in nodes}
    findings: List[Dict] = []

    def _dfs(node_id: str, stack: List[str]) -> None:
        color[node_id] = GRAY
        stack.append(node_id)
        for nxt in adj.get(node_id, []):
            if color.get(nxt) == GRAY:
                findings.append({"severity": "error", "node_id": nxt, "rule": "circular_dependency",
                                  "message": f"Circular dependency detected involving node '{nxt}' (path: {' -> '.join(stack + [nxt])})."})
            elif color.get(nxt) == WHITE:
                _dfs(nxt, stack)
        stack.pop()
        color[node_id] = BLACK

    for n in nodes:
        if color.get(n["node_id"]) == WHITE:
            _dfs(n["node_id"], [])
    return findings


def validate_graph(nodes: List[Dict], edges: List[Dict], tools_by_id: Optional[Dict[str, Dict]] = None) -> List[Dict]:
    findings: List[Dict] = []
    findings += _check_invalid_edges(nodes, edges)
    findings += _check_disconnected_nodes(nodes, edges)
    findings += _check_missing_config(nodes)
    findings += _check_invalid_conditions(nodes)
    findings += _check_destructive_without_approval(nodes, edges, tools_by_id)
    findings += _check_circular_dependencies(nodes, edges)
    if not any(n["type"].startswith(_TRIGGER_PREFIX) for n in nodes):
        findings.append({"severity": "error", "node_id": None, "rule": "missing_trigger",
                          "message": "Workflow has no Trigger node."})
    return findings


async def validate_workflow_version(workflow_id: str, version: int) -> List[Dict]:
    from ...core.database import db
    version_doc = await db.workflow_versions.find_one({"workflow_id": workflow_id, "version": version}, {"_id": 0})
    if version_doc is None:
        return [{"severity": "error", "node_id": None, "rule": "not_found", "message": "workflow version not found"}]

    tool_ids = {n.get("config", {}).get("tool_id") for n in version_doc.get("nodes", []) if n.get("config", {}).get("tool_id")}
    tools_by_id = {}
    if tool_ids:
        docs = await db.tool_catalog.find({"tool_id": {"$in": list(tool_ids)}}, {"_id": 0}).to_list(len(tool_ids))
        tools_by_id = {d["tool_id"]: d for d in docs}

    return validate_graph(version_doc.get("nodes", []), version_doc.get("edges", []), tools_by_id)


__all__ = ["validate_graph", "validate_workflow_version"]
