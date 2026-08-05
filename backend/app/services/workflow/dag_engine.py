"""
Workflow DAG engine — walks a workflow_versions graph (nodes/edges) and
dispatches each node to the right handler. This is the runtime RASED slots
into, not a second orchestrator: Agent nodes bound to one of RASED's 8
wrapper agents call the real RASED class directly (rased_bridge.py), Action
nodes bound to a rased_action tool call RASED's own execute_action(), and
Verification nodes call RASED's real VerificationAgent — none of RASED's
own code is reimplemented here.

Execution model, simplified deliberately and disclosed as such:
- Readiness is computed each round over ALL non-terminal nodes (fixed-point
  BFS), not just nodes newly reached by the last batch — this is what makes
  Join correct for asymmetric-depth parallel branches (a join must wait for
  every branch, not just the first one to arrive).
- Plain (unconditional) incoming edges use AND semantics (a Join is
  therefore just a node with multiple plain incoming edges — no special
  casing needed). Conditional incoming edges (condition_branch set, i.e. the
  branches of an upstream Condition/Switch/RiskCheck/PermissionCheck) use OR
  semantics — the node is ready once ANY matching branch's source
  completes; a branch that provably didn't match marks the node "skipped"
  once every conditional source is terminal with no match.
- Loop is a bounded sub-walk over an explicitly configured node_id list
  (config.body_node_ids), not a graph cycle — validation_engine.py excludes
  loop bodies from its cycle-detection pass for the same reason.
- Retry/Timeout are enforced generically on every node dispatch via that
  node's own config.retry/config.timeout_seconds (not only by the dedicated
  retry/timeout palette node types, which are pass-through markers useful
  for visually documenting intent on the canvas).
- Human Approval is a persisted-state pause, not an in-memory suspension —
  see approval_service.py's module docstring for why this deliberately does
  not depend on RASED's LangGraph interrupt()/checkpoint-replay mechanism.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from ...models.agent_workflow_schemas import WorkflowExecution, WorkflowNodeExecution
from .expression_evaluator import evaluate_condition, resolve_template
from .trace import WorkflowTraceRecorder
from . import rased_bridge

logger = logging.getLogger(__name__)

DESTRUCTIVE_ACTION_NODE_TYPES = {
    "action_restart_pod", "action_scale_service",
}
_MAX_LOOP_ITERATIONS_HARD_CAP = 25
_MAX_WAIT_SECONDS_CAP = 300
_MAX_SUBWORKFLOW_POLL_SECONDS = 300


class WorkflowPaused(Exception):
    """Raised internally to unwind the current round when a Human Approval
    node is reached — the asyncio task driving _walk ends normally after
    this; approval_service.decide() calls resume() to continue later."""


# ─────────────────────────── execution lifecycle ───────────────────────────

async def _ensure_indexes() -> None:
    from ...core.database import db
    try:
        await db.workflow_executions.create_index("execution_id", unique=True)
        await db.workflow_executions.create_index("workflow_id")
        await db.workflow_executions.create_index("status")
        await db.workflow_node_executions.create_index("execution_id")
        await db.workflow_node_executions.create_index([("execution_id", 1), ("node_id", 1)])
    except Exception as e:
        logger.warning(f"workflow_executions index setup failed: {e}")


async def start_execution(
    workflow_id: str, version: int, graph_snapshot: Dict[str, Any], trigger_payload: Dict[str, Any],
    *, mode: str = "run", started_by: str = "system", actor: Optional[Dict[str, Any]] = None,
) -> str:
    """Creates the execution record synchronously and kicks off the walk as
    a background task — mirrors RASED's own trigger_incident() pattern
    (persist first, drive in the background, SSE is how a client watches)."""
    await _ensure_indexes()
    from ...core.database import db

    execution_id = str(uuid.uuid4())
    execution = WorkflowExecution(
        execution_id=execution_id, workflow_id=workflow_id, workflow_version=version,
        status="queued", trigger_type=trigger_payload.get("_trigger_type", "manual"),
        trigger_payload=trigger_payload, dry_run=(mode == "dry_run"), test_run=(mode == "test_run"),
        execution_graph_snapshot=graph_snapshot, started_by=started_by,
        metrics={"node_count": len(graph_snapshot.get("nodes", []))},
    )
    await db.workflow_executions.insert_one(execution.model_dump(mode="json"))
    asyncio.create_task(_drive(execution_id, actor))
    return execution_id


async def resume_execution(execution_id: str, actor: Optional[Dict[str, Any]] = None) -> None:
    from ...core.database import db
    await db.workflow_executions.update_one({"execution_id": execution_id}, {"$set": {"status": "running"}})
    asyncio.create_task(_drive(execution_id, actor))


async def cancel_execution(execution_id: str) -> Dict[str, Any]:
    from ...core.database import db
    result = await db.workflow_executions.update_one(
        {"execution_id": execution_id, "status": {"$in": ["queued", "running", "waiting", "paused"]}},
        {"$set": {"status": "cancelled", "finished_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        return {"error": "execution not found or already terminal"}
    return {"execution_id": execution_id, "status": "cancelled"}


async def _drive(execution_id: str, actor: Optional[Dict[str, Any]]) -> None:
    from ...core.database import db
    try:
        await db.workflow_executions.update_one({"execution_id": execution_id}, {"$set": {"status": "running"}})
        await _walk(execution_id, actor)
    except WorkflowPaused:
        pass
    except Exception as exc:
        logger.exception(f"workflow execution {execution_id} failed")
        await db.workflow_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {"status": "failed", "error": str(exc)[:1000], "finished_at": datetime.now(timezone.utc).isoformat()}},
        )


# ─────────────────────────── graph walk ───────────────────────────

async def _walk(execution_id: str, actor: Optional[Dict[str, Any]]) -> None:
    from ...core.database import db

    execution = await db.workflow_executions.find_one({"execution_id": execution_id}, {"_id": 0})
    if execution is None:
        return
    snapshot = execution.get("execution_graph_snapshot") or {}
    nodes = {n["node_id"]: n for n in snapshot.get("nodes", [])}
    edges = snapshot.get("edges", [])
    incoming: Dict[str, List[Dict]] = {nid: [] for nid in nodes}
    for e in edges:
        incoming.setdefault(e["target"], []).append(e)

    trigger_node_ids = {nid for nid, n in nodes.items() if n["type"].startswith("trigger_")}
    tracer = WorkflowTraceRecorder(execution_id)

    node_execs = await db.workflow_node_executions.find({"execution_id": execution_id}, {"_id": 0}).to_list(2000)
    terminal: Dict[str, Dict[str, Any]] = {ne["node_id"]: ne for ne in node_execs if ne["status"] in
                                            ("completed", "failed", "skipped", "cancelled")}

    node_outputs: Dict[str, Any] = {nid: ne.get("output", {}) for nid, ne in terminal.items()}
    context = {"trigger": execution.get("trigger_payload", {}), **{nid: {"output": out} for nid, out in node_outputs.items()}}

    remaining = set(nodes) - set(terminal)

    while remaining:
        ready: List[str] = []
        skipped: List[str] = []
        for node_id in list(remaining):
            state = _node_readiness(node_id, incoming.get(node_id, []), terminal, trigger_node_ids)
            if state == "ready":
                ready.append(node_id)
            elif state == "skip":
                skipped.append(node_id)

        for node_id in skipped:
            ne = WorkflowNodeExecution(
                node_execution_id=str(uuid.uuid4()), execution_id=execution_id, node_id=node_id,
                node_type=nodes[node_id]["type"], status="skipped",
                started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
            )
            await db.workflow_node_executions.insert_one(ne.model_dump(mode="json"))
            terminal[node_id] = ne.model_dump(mode="json")
            remaining.discard(node_id)
            await tracer.emit(node_id, nodes[node_id]["type"], "branch", f"Skipped (branch not taken)")

        if not ready:
            break  # nothing left is dispatchable this round — either done or genuinely blocked

        results = await asyncio.gather(
            *(_dispatch_node(execution_id, nodes[nid], context, actor, execution, tracer) for nid in ready),
            return_exceptions=True,
        )

        paused = False
        for node_id, result in zip(ready, results):
            remaining.discard(node_id)
            if isinstance(result, WorkflowPaused):
                paused = True
                continue
            if isinstance(result, Exception):
                logger.exception(f"node {node_id} dispatch raised")
                result = {"status": "failed", "output": {}, "error": str(result)[:500]}
            terminal[node_id] = {"node_id": node_id, "status": result["status"], "output": result.get("output", {})}
            node_outputs[node_id] = result.get("output", {})
            context[node_id] = {"output": result.get("output", {})}

        if paused:
            await db.workflow_executions.update_one({"execution_id": execution_id}, {"$set": {"status": "waiting"}})
            raise WorkflowPaused()

    await _finalize(execution_id, terminal, nodes)


async def _finalize(execution_id: str, terminal: Dict[str, Dict], nodes: Dict[str, Dict]) -> None:
    from ...core.database import db
    any_failed = any(t.get("status") == "failed" for t in terminal.values())
    all_accounted = len(terminal) >= len(nodes)
    status = "failed" if any_failed else ("completed" if all_accounted else "failed")
    now = datetime.now(timezone.utc)
    execution = await db.workflow_executions.find_one({"execution_id": execution_id}, {"_id": 0})
    started_at = execution.get("started_at") if execution else None
    duration_ms = None
    if started_at:
        try:
            started_dt = started_at if isinstance(started_at, datetime) else datetime.fromisoformat(str(started_at))
            duration_ms = int((now - started_dt).total_seconds() * 1000)
        except Exception:
            duration_ms = None
    await db.workflow_executions.update_one(
        {"execution_id": execution_id},
        {"$set": {"status": status, "finished_at": now.isoformat(),
                   "metrics.duration_ms": duration_ms}},
    )


def _node_readiness(node_id: str, incoming_edges: List[Dict], terminal: Dict[str, Dict], trigger_node_ids: Set[str]) -> str:
    if not incoming_edges:
        return "ready" if node_id in trigger_node_ids else "blocked"

    unconditional = [e for e in incoming_edges if not e.get("condition_branch")]
    conditional = [e for e in incoming_edges if e.get("condition_branch")]

    for e in unconditional:
        if e["source"] not in terminal:
            return "blocked"

    if conditional:
        pending = [e for e in conditional if e["source"] not in terminal]
        matched = [e for e in conditional if e["source"] in terminal and
                   (terminal[e["source"]].get("output") or {}).get("branch") == e["condition_branch"]]
        if matched:
            return "ready"
        if pending:
            return "blocked"
        return "skip"  # every conditional source resolved, none matched this node's branch

    return "ready"


# ─────────────────────────── per-node dispatch ───────────────────────────

async def _dispatch_node(
    execution_id: str, node: Dict[str, Any], context: Dict[str, Any], actor: Optional[Dict[str, Any]],
    execution: Dict[str, Any], tracer: WorkflowTraceRecorder,
) -> Dict[str, Any]:
    from ...core.database import db

    node_id, node_type = node["node_id"], node["type"]
    node_execution_id = str(uuid.uuid4())
    resolved_input = _resolve_inputs(node.get("data_mapping", {}), context)
    started = time.monotonic()

    ne = WorkflowNodeExecution(
        node_execution_id=node_execution_id, execution_id=execution_id, node_id=node_id,
        node_type=node_type, status="running", input=resolved_input,
    )
    await db.workflow_node_executions.insert_one(ne.model_dump(mode="json"))
    await tracer.emit(node_id, node_type, "start", f"{node_type} started")

    handler = _NODE_HANDLERS.get(node_type, _handle_passthrough)
    retry_cfg = node.get("config", {}).get("retry") or {}
    max_attempts = max(1, int(retry_cfg.get("max_attempts", 1)))
    timeout_seconds = node.get("config", {}).get("timeout_seconds")

    attempt = 0
    last_error = None
    output: Dict[str, Any] = {}
    status = "failed"
    while attempt < max_attempts:
        attempt += 1
        try:
            coro = handler(execution_id, node, resolved_input, context, actor, execution, node_execution_id)
            if timeout_seconds:
                output = await asyncio.wait_for(coro, timeout=float(timeout_seconds))
            else:
                output = await coro
            status = "completed"
            last_error = None
            break
        except _ApprovalRequested:
            await db.workflow_node_executions.update_one(
                {"node_execution_id": node_execution_id}, {"$set": {"status": "waiting_approval"}},
            )
            await tracer.emit(node_id, node_type, "approval", "Waiting for human approval")
            paused_exc = WorkflowPaused()
            raise paused_exc
        except asyncio.TimeoutError:
            last_error = f"node timed out after {timeout_seconds}s"
        except Exception as e:
            last_error = str(e)[:500]
        if attempt < max_attempts:
            await asyncio.sleep(min(retry_cfg.get("backoff_seconds", 1.0) * attempt, 10))

    duration_ms = int((time.monotonic() - started) * 1000)
    await db.workflow_node_executions.update_one(
        {"node_execution_id": node_execution_id},
        {"$set": {"status": status, "output": output, "error": last_error, "retries": attempt - 1,
                   "duration_ms": duration_ms, "finished_at": datetime.now(timezone.utc).isoformat()}},
    )
    await tracer.emit(node_id, node_type, "end" if status == "completed" else "error",
                       f"{node_type} {status}", detail={"error": last_error} if last_error else None,
                       duration_ms=duration_ms)
    return {"status": status, "output": output, "error": last_error}


class _ApprovalRequested(Exception):
    pass


def _resolve_inputs(data_mapping: Dict[str, str], context: Dict[str, Any]) -> Dict[str, Any]:
    resolved = {}
    for field, template in (data_mapping or {}).items():
        resolved[field] = resolve_template(template, context)
    return resolved


# ─────────────────────────── node type handlers ───────────────────────────

async def _handle_passthrough(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    return {"input": resolved_input}


async def _handle_trigger(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    return execution.get("trigger_payload", {})


async def _handle_agent(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    from ..agent_builder import agent_definition_service, react_engine

    agent_id = node.get("config", {}).get("agent_id")
    if not agent_id:
        raise ValueError("agent node has no config.agent_id")

    record = await agent_definition_service.get_agent(agent_id)
    if record is None:
        raise ValueError(f"agent '{agent_id}' not found")
    definition = record["definition"]

    if definition.get("is_rased_wrapper"):
        rased_class = definition.get("rased_agent_class")
        if rased_class == "ActionAgent":
            raise ValueError(
                "ActionAgent cannot be invoked directly from a workflow Agent node — its DESTRUCTIVE-tier "
                "approval gate depends on LangGraph's interrupt(), which only works inside RASED's own graph. "
                "Use an Action node bound to a rased_action tool instead; the workflow's own upstream "
                "Condition/RiskCheck/HumanApproval nodes are the workflow-level equivalent of ActionAgent's gate."
            )
        state = rased_bridge.load_shadow_state(execution) or rased_bridge.build_initial_shadow_state(
            execution_id, execution.get("trigger_payload", {}), execution.get("tenant_id"),
        )
        update = await rased_bridge.run_rased_agent(rased_class, state)
        new_state = state.model_copy(update=update) if update else state
        await _save_shadow_state(execution_id, new_state)
        return _project_rased_output(rased_class, update)

    result = await react_engine.run_agent(
        agent_id, resolved_input, triggered_by_kind="workflow_node", triggered_by_ref=node["node_id"], actor=actor,
    )
    return {"final_output": result.get("final_output", {}), "confidence": result.get("confidence"),
            "agent_execution_id": result.get("agent_execution_id"), "status": result.get("status")}


def _project_rased_output(rased_class: str, update: Dict[str, Any]) -> Dict[str, Any]:
    if rased_class == "RCAAgent":
        hyps = update.get("hypotheses", [])
        return {"hypotheses": [h.model_dump(mode="json") if hasattr(h, "model_dump") else h for h in hyps],
                "confidence": update.get("confidence")}
    if rased_class == "VerificationAgent":
        v = update.get("verification")
        return {"verification": v.model_dump(mode="json") if hasattr(v, "model_dump") else v, "status": update.get("status")}
    return {k: (v.model_dump(mode="json") if hasattr(v, "model_dump") else v) for k, v in update.items()}


async def _save_shadow_state(execution_id: str, state) -> None:
    from ...core.database import db
    await db.workflow_executions.update_one(
        {"execution_id": execution_id},
        {"$set": {f"variables.{rased_bridge._SHADOW_KEY}": rased_bridge.dump_shadow_state(state)}},
    )


async def _handle_data_node(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    from ..tool_binding_dispatch import dispatch_tool

    tool_id = node.get("config", {}).get("tool_id")
    if not tool_id:
        raise ValueError(f"{node['type']} node has no config.tool_id")
    result = await dispatch_tool(tool_id, resolved_input, actor=actor)

    if result.success and result.observation_kind == "observed_data":
        state = rased_bridge.load_shadow_state(execution) or rased_bridge.build_initial_shadow_state(
            execution_id, execution.get("trigger_payload", {}), execution.get("tenant_id"),
        )
        new_state = rased_bridge.append_evidence(
            state, source=node["type"].replace("data_", ""), query=f"tool:{tool_id}",
            summary=str(result.output)[:300], data=result.output,
        )
        await _save_shadow_state(execution_id, new_state)

    if not result.success:
        raise ValueError(result.error or "data tool call failed")
    return result.output


async def _handle_condition(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    passed = evaluate_condition(node.get("config", {}).get("condition"), context)
    return {"branch": "true" if passed else "false", "passed": passed}


async def _handle_switch(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    for case in node.get("config", {}).get("cases", []):
        if evaluate_condition(case.get("condition"), context):
            return {"branch": f"case:{case.get('value')}"}
    return {"branch": "default"}


async def _handle_loop(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    """Bounded sub-walk over an explicitly configured node list, not an
    open graph cycle. body_node_ids run in the order given, once per pass;
    condition/data-mapping resolution inside the body reads/writes the same
    `context` dict, so later passes see earlier passes' outputs."""
    from ...core.database import db

    body_ids: List[str] = node.get("config", {}).get("body_node_ids", [])
    max_iterations = min(int(node.get("config", {}).get("max_iterations", 3)), _MAX_LOOP_ITERATIONS_HARD_CAP)
    termination_condition = node.get("config", {}).get("termination_condition")
    snapshot = execution.get("execution_graph_snapshot") or {}
    body_nodes = {n["node_id"]: n for n in snapshot.get("nodes", []) if n["node_id"] in body_ids}
    tracer = WorkflowTraceRecorder(execution_id)

    passes = []
    for i in range(max_iterations):
        if termination_condition and evaluate_condition(termination_condition, context):
            break
        for body_node_id in body_ids:
            body_node = body_nodes.get(body_node_id)
            if body_node is None:
                continue
            result = await _dispatch_node(execution_id, body_node, context, actor, execution, tracer)
            context[body_node_id] = {"output": result.get("output", {})}
        passes.append(i)

    return {"iterations_run": len(passes)}


async def _handle_wait(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    seconds = min(float(node.get("config", {}).get("seconds", 5)), _MAX_WAIT_SECONDS_CAP)
    await asyncio.sleep(seconds)
    return {"waited_seconds": seconds}


async def _handle_action_via_tool(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    from ..tool_catalog_service import get_tool
    from ..tool_binding_dispatch import dispatch_tool

    tool_id = node.get("config", {}).get("tool_id")
    if not tool_id:
        raise ValueError(f"{node['type']} node has no config.tool_id — configure a Tool Catalog entry for this action")

    tool = await get_tool(tool_id)
    if tool is None:
        raise ValueError(f"tool '{tool_id}' not found")

    if tool.get("risk_tier") == "DESTRUCTIVE":
        from ...core.database import db
        approved = await db.workflow_approvals.find_one({"execution_id": execution_id, "status": "approved"})
        if not approved:
            raise ValueError(
                "DESTRUCTIVE-tier action blocked at execution time: no approved workflow_approvals record "
                "found for this execution. Publish-time validation should have required an upstream Human "
                "Approval node — this is the runtime re-check (defense in depth)."
            )

    is_simulated_mode = execution.get("dry_run") or execution.get("test_run")
    if is_simulated_mode and tool.get("risk_tier") != "SAFE":
        return {"execution_mode": "simulated", "note": f"{'dry run' if execution.get('dry_run') else 'test run'} — "
                "GUARDED/DESTRUCTIVE action forced to simulation, never touches production", "would_call": tool_id,
                "input": resolved_input}

    result = await dispatch_tool(tool_id, resolved_input, actor=actor)
    if not result.success:
        raise ValueError(result.error or "action failed")
    return result.model_dump()


async def _handle_run_workflow(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    from ...core.database import db
    from . import workflow_definition_service

    sub_workflow_id = node.get("config", {}).get("workflow_id")
    if not sub_workflow_id:
        raise ValueError("action_run_workflow node has no config.workflow_id")

    sub = await workflow_definition_service.get_workflow(sub_workflow_id)
    if sub is None or sub.get("version") is None:
        raise ValueError(f"sub-workflow '{sub_workflow_id}' has no published version")

    sub_execution_id = await start_execution(
        sub_workflow_id, sub["version"]["version"], {"nodes": sub["version"]["nodes"], "edges": sub["version"]["edges"]},
        resolved_input, mode="run", started_by=f"sub-workflow-of:{execution_id}", actor=actor,
    )

    waited = 0
    while waited < _MAX_SUBWORKFLOW_POLL_SECONDS:
        await asyncio.sleep(1)
        waited += 1
        sub_exec = await db.workflow_executions.find_one({"execution_id": sub_execution_id}, {"_id": 0})
        if sub_exec and sub_exec.get("status") in ("completed", "failed", "cancelled", "timed_out"):
            return {"sub_execution_id": sub_execution_id, "status": sub_exec.get("status"), "variables": sub_exec.get("variables", {})}
    return {"sub_execution_id": sub_execution_id, "status": "timed_out_waiting_for_subworkflow"}


async def _handle_human_approval(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    from . import approval_service

    await approval_service.request_approval(
        execution_id=execution_id, node_execution_id=node_execution_id,
        node_id=node["node_id"], workflow_id=execution["workflow_id"],
        title=node.get("config", {}).get("title", "Approval required"),
        risk_tier=node.get("config", {}).get("risk_tier", "GUARDED"),
        requested_permission=node.get("config", {}).get("required_permission", "remediation.approve_destructive"),
    )
    raise _ApprovalRequested()


async def _handle_risk_check(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    from ..tool_catalog_service import get_tool

    target_tool_id = node.get("config", {}).get("target_tool_id")
    tool = await get_tool(target_tool_id) if target_tool_id else None
    risk_tier = tool.get("risk_tier") if tool else node.get("config", {}).get("risk_tier", "SAFE")
    threshold = node.get("config", {}).get("block_at_or_above", "DESTRUCTIVE")
    order = {"SAFE": 0, "GUARDED": 1, "DESTRUCTIVE": 2}
    passed = order.get(risk_tier, 0) < order.get(threshold, 2)
    return {"risk_tier": risk_tier, "branch": "pass" if passed else "block", "passed": passed}


async def _handle_permission_check(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    from ..rbac_service import check_permission

    permission = node.get("config", {}).get("required_permission")
    if not permission:
        return {"branch": "pass", "passed": True}
    passed = bool(actor) and await check_permission(actor, permission)
    return {"branch": "pass" if passed else "block", "passed": passed, "checked_permission": permission}


async def _handle_policy_check(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    """Advisory only — RASED's PolicyAgent has no independently-verified
    policy corpus surface confirmed in this pass; rather than fabricate a
    pass/fail, this honestly reports unavailable and defaults to
    non-blocking. Use a Risk Check or Human Approval node for an actual
    enforced gate."""
    return {"available": False, "reason": "policy corpus lookup not wired for workflow-scoped checks", "branch": "pass"}


async def _handle_verification(execution_id, node, resolved_input, context, actor, execution, node_execution_id) -> Dict[str, Any]:
    state = rased_bridge.load_shadow_state(execution)
    if state is None:
        return {"available": False, "reason": "no shadow investigation state on this execution — "
                "Verification requires an upstream RASED-integrated Agent/Action node first"}
    update = await rased_bridge.run_rased_agent("VerificationAgent", state)
    if update:
        new_state = state.model_copy(update=update)
        await _save_shadow_state(execution_id, new_state)
    return _project_rased_output("VerificationAgent", update)


_NODE_HANDLERS = {
    "trigger_manual": _handle_trigger, "trigger_schedule": _handle_trigger, "trigger_alert": _handle_trigger,
    "trigger_incident": _handle_trigger, "trigger_api": _handle_trigger, "trigger_webhook": _handle_trigger,
    "trigger_threshold": _handle_trigger, "trigger_event": _handle_trigger,
    "agent": _handle_agent, "planner": _handle_agent, "ai_decision": _handle_agent,
    "synthesizer": _handle_agent, "judge": _handle_agent,
    "data_elasticsearch": _handle_data_node, "data_apm": _handle_data_node, "data_sql": _handle_data_node,
    "data_metrics": _handle_data_node, "data_logs": _handle_data_node, "data_http": _handle_data_node,
    "data_rag_search": _handle_data_node, "data_memory": _handle_data_node,
    "condition": _handle_condition, "switch": _handle_switch,
    "parallel": _handle_passthrough, "join": _handle_passthrough,
    "loop": _handle_loop, "wait": _handle_wait, "retry": _handle_passthrough, "timeout": _handle_passthrough,
    "action_restart_pod": _handle_action_via_tool, "action_scale_service": _handle_action_via_tool,
    "action_run_workflow": _handle_run_workflow, "action_create_ticket": _handle_action_via_tool,
    "action_send_email": _handle_action_via_tool, "action_send_teams": _handle_action_via_tool,
    "action_send_slack": _handle_action_via_tool, "action_create_incident": _handle_action_via_tool,
    "human_approval": _handle_human_approval, "risk_check": _handle_risk_check,
    "permission_check": _handle_permission_check, "policy_check": _handle_policy_check,
    "verification": _handle_verification, "health_check": _handle_data_node, "slo_check": _handle_data_node,
}

__all__ = ["start_execution", "resume_execution", "cancel_execution", "WorkflowPaused"]
