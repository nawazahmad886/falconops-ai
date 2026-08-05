"""
Built-in workflow templates — seeded idempotently at startup (same pattern
as rbac_service.init_default_roles() / agent_definition_service.seed_rased_
wrapper_agents()). These exercise the full node-type set the DAG engine
supports; they reference RASED-wrapper agent_ids directly (rased-rcaagent,
rased-verificationagent) but leave config.tool_id fields on Data/Action
nodes UNSET — an operator must bind real Tool Catalog entries before these
templates can run for real. This is disclosed via each template's
description rather than pre-wired to a guessed tool_id that might not exist
in a given deployment.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _node(node_id: str, node_type: str, label: str, x: float, y: float, config: Optional[Dict] = None) -> Dict:
    return {"node_id": node_id, "type": node_type, "position": {"x": x, "y": y}, "config": config or {}, "data_mapping": {}, "label": label}


def _edge(edge_id: str, source: str, target: str, branch: Optional[str] = None) -> Dict:
    return {"edge_id": edge_id, "source": source, "target": target, "condition_branch": branch}


def _api_incident_investigation() -> Dict[str, Any]:
    nodes = [
        _node("trigger", "trigger_incident", "Incident Created", 0, 0),
        _node("planner", "planner", "Planner", 0, 150, {"agent_id": "rased-orchestratoragent"}),
        _node("elastic", "data_elasticsearch", "Elastic Agent", -300, 300, {"tool_id": ""}),
        _node("apm", "data_apm", "APM Agent", -100, 300, {"tool_id": ""}),
        _node("sql", "data_sql", "SQL Agent", 100, 300, {"tool_id": ""}),
        _node("network", "data_http", "Network Agent", 300, 300, {"tool_id": ""}),
        _node("join1", "join", "Join", 0, 450),
        _node("rca", "agent", "RCA Agent", 0, 600, {"agent_id": "rased-rcaagent"}),
        _node("confidence_gate", "condition", "Confidence >= 0.85", 0, 750,
              {"condition": {"op": ">=", "left": "{{rca.output.confidence}}", "right": 0.85}}),
        _node("risk_check", "risk_check", "Risk Check", 0, 900, {"block_at_or_above": "DESTRUCTIVE"}),
        _node("approval", "human_approval", "Human Approval", 0, 1050, {"title": "Approve remediation?", "risk_tier": "GUARDED"}),
        _node("remediation", "action_restart_pod", "Remediation", 0, 1200, {"tool_id": ""}),
        _node("verify", "verification", "Verification", 0, 1350),
        _node("recovered_gate", "condition", "Recovered?", 0, 1500,
              {"condition": {"op": "==", "left": "{{verify.output.verification.recovered}}", "right": True}}),
        _node("report", "action_create_ticket", "Generate Report", -150, 1650, {"tool_id": ""}),
        _node("notify_ok", "action_send_slack", "Notify Team", -150, 1800, {"tool_id": ""}),
        _node("escalate", "action_create_incident", "Escalate", 150, 1650, {"tool_id": ""}),
    ]
    edges = [
        _edge("e1", "trigger", "planner"), _edge("e2", "planner", "elastic"), _edge("e3", "planner", "apm"),
        _edge("e4", "planner", "sql"), _edge("e5", "planner", "network"),
        _edge("e6", "elastic", "join1"), _edge("e7", "apm", "join1"), _edge("e8", "sql", "join1"), _edge("e9", "network", "join1"),
        _edge("e10", "join1", "rca"), _edge("e11", "rca", "confidence_gate"),
        _edge("e12", "confidence_gate", "risk_check", "true"), _edge("e13", "risk_check", "approval", "pass"),
        _edge("e14", "approval", "remediation", "approved"), _edge("e15", "remediation", "verify"),
        _edge("e16", "verify", "recovered_gate"),
        _edge("e17", "recovered_gate", "report", "true"), _edge("e18", "report", "notify_ok"),
        _edge("e19", "recovered_gate", "escalate", "false"), _edge("e20", "approval", "escalate", "rejected"),
    ]
    return {"nodes": nodes, "edges": edges, "variables": [], "trigger_config": {"type": "incident", "config": {}}}


def _high_cpu_investigation() -> Dict[str, Any]:
    nodes = [
        _node("trigger", "trigger_threshold", "CPU > 90% for 5min", 0, 0, {"metric": "cpu_percent", "threshold": 90}),
        _node("infra", "data_metrics", "Infrastructure Agent", 0, 150, {"tool_id": ""}),
        _node("process", "data_metrics", "Process Analysis", 0, 300, {"tool_id": ""}),
        _node("app_agent", "agent", "Application Agent", 0, 450, {"agent_id": ""}),
        _node("known_gate", "condition", "Known Process?", 0, 600, {"condition": {"op": "==", "left": "{{app_agent.output.final_output.known}}", "right": True}}),
        _node("recommend", "action_create_ticket", "Recommend Action", -150, 750, {"tool_id": ""}),
        _node("rca", "agent", "RCA Agent", 150, 750, {"agent_id": "rased-rcaagent"}),
        _node("approval", "human_approval", "Human Approval", 0, 900, {"title": "Approve scale/restart?", "risk_tier": "GUARDED"}),
        _node("action", "action_scale_service", "Scale / Restart", 0, 1050, {"tool_id": ""}),
        _node("verify", "verification", "Verification", 0, 1200),
        _node("close_gate", "condition", "Recovered?", 0, 1350, {"condition": {"op": "==", "left": "{{verify.output.verification.recovered}}", "right": True}}),
        _node("close", "action_create_ticket", "Close", -150, 1500, {"tool_id": ""}),
        _node("escalate", "action_create_incident", "Escalate", 150, 1500, {"tool_id": ""}),
    ]
    edges = [
        _edge("e1", "trigger", "infra"), _edge("e2", "infra", "process"), _edge("e3", "process", "app_agent"),
        _edge("e4", "app_agent", "known_gate"),
        _edge("e5", "known_gate", "recommend", "true"), _edge("e6", "known_gate", "rca", "false"),
        _edge("e7", "recommend", "approval"), _edge("e8", "rca", "approval"),
        _edge("e9", "approval", "action", "approved"), _edge("e10", "action", "verify"),
        _edge("e11", "verify", "close_gate"),
        _edge("e12", "close_gate", "close", "true"), _edge("e13", "close_gate", "escalate", "false"),
        _edge("e14", "approval", "escalate", "rejected"),
    ]
    return {"nodes": nodes, "edges": edges, "variables": [], "trigger_config": {"type": "threshold", "config": {"metric": "cpu_percent", "operator": ">", "value": 90}}}


def _database_performance_investigation() -> Dict[str, Any]:
    nodes = [
        _node("trigger", "trigger_threshold", "DB Latency Threshold Exceeded", 0, 0),
        _node("slow_queries", "data_sql", "Slow Query Analysis", 0, 150, {"tool_id": ""}),
        _node("locks", "data_sql", "Lock Analysis", 0, 300, {"tool_id": ""}),
        _node("connections", "data_sql", "Connection Analysis", 0, 450, {"tool_id": ""}),
        _node("join1", "join", "Join", 0, 600),
        _node("rca", "agent", "RCA Agent", 0, 750, {"agent_id": "rased-rcaagent"}),
        _node("risk_check", "risk_check", "Risk Check", 0, 900),
        _node("recommendation", "action_create_ticket", "Recommendation", 0, 1050, {"tool_id": ""}),
        _node("approval", "human_approval", "Approval", 0, 1200, {"title": "Approve action?", "risk_tier": "GUARDED"}),
        _node("action", "action_restart_pod", "Action", 0, 1350, {"tool_id": ""}),
        _node("verify", "verification", "Verification", 0, 1500),
    ]
    edges = [
        _edge("e1", "trigger", "slow_queries"), _edge("e2", "trigger", "locks"), _edge("e3", "trigger", "connections"),
        _edge("e4", "slow_queries", "join1"), _edge("e5", "locks", "join1"), _edge("e6", "connections", "join1"),
        _edge("e7", "join1", "rca"), _edge("e8", "rca", "risk_check"), _edge("e9", "risk_check", "recommendation", "pass"),
        _edge("e10", "recommendation", "approval"), _edge("e11", "approval", "action", "approved"),
        _edge("e12", "action", "verify"),
    ]
    return {"nodes": nodes, "edges": edges, "variables": [], "trigger_config": {"type": "threshold", "config": {"metric": "db_latency_ms"}}}


BUILT_IN_TEMPLATES = [
    {"template_id": "api_incident_autonomous_investigation", "name": "API Incident Autonomous Investigation",
     "description": "Parallel Elastic/APM/SQL/Network evidence gathering -> RCA -> risk-gated human approval -> "
                     "remediation -> verification -> report or escalate. Data/Action nodes need Tool Catalog "
                     "bindings configured before this can run for real.",
     "category": "incident-response", "graph_snapshot": _api_incident_investigation()},
    {"template_id": "high_cpu_autonomous_investigation", "name": "High CPU Autonomous Investigation",
     "description": "Infra + process analysis -> known-process fast path or RCA -> approval -> scale/restart -> "
                     "verification -> close or escalate.",
     "category": "infrastructure", "graph_snapshot": _high_cpu_investigation()},
    {"template_id": "database_performance_investigation", "name": "Database Performance Investigation",
     "description": "Slow-query/lock/connection analysis in parallel -> RCA -> risk check -> approval -> action -> verification.",
     "category": "database", "graph_snapshot": _database_performance_investigation()},
]


async def seed_built_in_templates() -> None:
    from ...core.database import db
    try:
        await db.workflow_templates.create_index("template_id", unique=True)
    except Exception as e:
        logger.warning(f"workflow_templates index setup failed: {e}")

    for template in BUILT_IN_TEMPLATES:
        existing = await db.workflow_templates.find_one({"template_id": template["template_id"]})
        if existing:
            continue
        doc = {**template, "is_built_in": True, "tags": [template["category"]], "created_by": "system",
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.workflow_templates.insert_one(doc)
        logger.info(f"seeded built-in workflow template '{template['template_id']}'")


async def list_templates() -> List[Dict[str, Any]]:
    from ...core.database import db
    return await db.workflow_templates.find({}, {"_id": 0}).sort("name", 1).to_list(200)


async def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    from ...core.database import db
    return await db.workflow_templates.find_one({"template_id": template_id}, {"_id": 0})


__all__ = ["seed_built_in_templates", "list_templates", "get_template", "BUILT_IN_TEMPLATES"]
