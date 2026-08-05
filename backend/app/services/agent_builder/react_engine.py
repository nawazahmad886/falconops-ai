"""
ReAct engine — the autonomous tool-use loop for custom (non-RASED-wrapper)
agents.

Protocol is text-based (Thought / Action / Action Input / Observation),
not native function-calling: llm_provider_service.chat_completion() has no
tools= parameter and none of its 6 provider backends (ollama/openai/
anthropic/gemini/emergent/rule_based) support structured tool-calling
through this shared entry point (confirmed by reading the file — every
provider function is plain messages-in/text-out). A text protocol is the
only approach that works uniformly across all of them, including
rule_based, rather than silently degrading unsupported providers.

Every tool the model names is validated against the agent's own tools list
before dispatch — the model cannot invoke anything the agent wasn't
explicitly configured with, mirroring how RASED's ActionAgent validates a
proposed action against the static ACTIONS registry before it ever reaches
an executor. Every message list is redacted via RASED's own
sanitize_for_llm() immediately before the LLM call — the same boundary
RASED's own agents use, not a new/weaker one.
"""
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...models.agent_workflow_schemas import AgentExecution, ReactIteration
from ..rased.redaction import sanitize_for_llm

logger = logging.getLogger(__name__)

_THOUGHT_RE = re.compile(r"Thought:\s*(.*?)(?=\nAction:|\nFinal Answer:|\Z)", re.DOTALL)
_ACTION_RE = re.compile(r"Action:\s*(.+?)\s*\n")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(\{.*?\})\s*(?=\Z|\nThought:|\nObservation:)", re.DOTALL)
_FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)

MAX_MALFORMED_RETRIES = 1


def _build_scaffold(tools_desc: str) -> str:
    return (
        "\n\nYou operate in a strict ReAct loop. At every turn respond with EXACTLY one of the "
        "two forms below — nothing else, no extra prose:\n\n"
        "Thought: <your reasoning about what to do next>\n"
        "Action: <one tool_id from the list below>\n"
        "Action Input: <a single JSON object matching that tool's input schema>\n\n"
        "OR, once you have enough evidence:\n\n"
        "Thought: <your reasoning>\n"
        "Final Answer: <a single JSON object matching your required output schema>\n\n"
        "Rules:\n"
        "- Never invent data. If evidence is insufficient, say so in your Final Answer rather than guessing.\n"
        "- You may only use tools from this list — naming any other tool is invalid:\n"
        f"{tools_desc}\n"
        "- Do not fabricate an Observation yourself; it will be provided to you after each Action.\n"
    )


def _format_tools(tools: List[Dict[str, Any]]) -> str:
    if not tools:
        return "(no tools assigned — you may only produce a Final Answer from the input you were given)"
    lines = []
    for t in tools:
        lines.append(f"  - {t['tool_id']}: {t.get('description', '')} | input_schema={json.dumps(t.get('input_schema', {}))}")
    return "\n".join(lines)


def _parse_response(text: str) -> Dict[str, Any]:
    thought_match = _THOUGHT_RE.search(text)
    thought = thought_match.group(1).strip() if thought_match else ""

    final_match = _FINAL_RE.search(text)
    if final_match:
        raw = final_match.group(1).strip()
        try:
            start, end = raw.find("{"), raw.rfind("}")
            final_output = json.loads(raw[start:end + 1]) if start != -1 and end != -1 else {"text": raw}
        except (ValueError, json.JSONDecodeError):
            final_output = {"text": raw}
        return {"kind": "final", "thought": thought, "final_output": final_output}

    action_match = _ACTION_RE.search(text)
    input_match = _ACTION_INPUT_RE.search(text)
    if action_match:
        action = action_match.group(1).strip()
        action_input: Dict[str, Any] = {}
        if input_match:
            try:
                action_input = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                action_input = {}
        return {"kind": "action", "thought": thought, "action": action, "action_input": action_input}

    return {"kind": "malformed", "thought": thought}


async def run_agent(
    agent_id: str,
    input_payload: Dict[str, Any],
    *,
    triggered_by_kind: str = "manual_test",
    triggered_by_ref: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from . import agent_definition_service
    from ..tool_catalog_service import get_tool
    from ..tool_binding_dispatch import dispatch_tool
    from ..llm_provider_service import chat_completion

    record = await agent_definition_service.get_agent(agent_id)
    if record is None or record.get("version") is None:
        return {"error": f"agent '{agent_id}' has no available version"}

    definition = record["definition"]
    version = record["version"]

    execution = AgentExecution(
        agent_execution_id=str(uuid.uuid4()), agent_id=agent_id, agent_version=version["version"],
        triggered_by_kind=triggered_by_kind, triggered_by_ref=triggered_by_ref, input=input_payload,
    )

    if definition.get("is_rased_wrapper"):
        execution.status = "failed"
        execution.error = "RASED-wrapper agents are dispatched directly by the workflow engine, not the ReAct engine"
        await _persist(execution)
        return execution.model_dump(mode="json")

    guardrails = version.get("guardrails", {})
    environment = input_payload.get("environment")
    if environment and guardrails.get("allowed_environments") and environment not in guardrails["allowed_environments"]:
        execution.status = "guardrail_stopped"
        execution.guardrail_violations.append({"rule": "allowed_environments", "detail": f"'{environment}' not in {guardrails['allowed_environments']}", "at": datetime.now(timezone.utc)})
        execution.finished_at = datetime.now(timezone.utc)
        await _persist(execution)
        return execution.model_dump(mode="json")

    allowed_tool_ids = {t["tool_id"] for t in version.get("tools", [])}
    tools_meta = []
    for tool_ref in version.get("tools", []):
        tool = await get_tool(tool_ref["tool_id"])
        if tool:
            tools_meta.append(tool)

    system_template = (version.get("system_instructions") or {}).get("template", "")
    variables = {v["name"]: v.get("default") for v in (version.get("system_instructions") or {}).get("variables", [])}
    variables.update({k: v for k, v in input_payload.items() if isinstance(v, (str, int, float, bool))})
    for name, value in variables.items():
        system_template = system_template.replace(f"{{{{{name}}}}}", str(value))

    system_prompt = system_template + _build_scaffold(_format_tools(tools_meta))
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(input_payload, default=str)},
    ]

    max_iterations = guardrails.get("max_iterations", 6)
    max_seconds = guardrails.get("max_execution_seconds", 120)
    max_tokens_budget = guardrails.get("max_token_budget")
    started_wall = time.monotonic()
    total_tokens_in = 0
    total_tokens_out = 0
    saw_real_usage = False
    malformed_retries = 0

    for iteration_index in range(max_iterations):
        if time.monotonic() - started_wall > max_seconds:
            execution.status = "timed_out"
            execution.guardrail_violations.append({"rule": "max_execution_seconds", "detail": f"exceeded {max_seconds}s", "at": datetime.now(timezone.utc)})
            break

        iter_started = time.monotonic()
        llm_result = await chat_completion(
            sanitize_for_llm(messages), session_id=f"agent-{agent_id}-{execution.agent_execution_id}",
        )
        latency_ms = int((time.monotonic() - iter_started) * 1000)
        usage = llm_result.get("usage")
        if usage:
            saw_real_usage = True
            total_tokens_in += usage.get("input_tokens") or 0
            total_tokens_out += usage.get("output_tokens") or 0
            if max_tokens_budget and (total_tokens_in + total_tokens_out) > max_tokens_budget:
                execution.status = "guardrail_stopped"
                execution.guardrail_violations.append({"rule": "max_token_budget", "detail": f"exceeded {max_tokens_budget} tokens", "at": datetime.now(timezone.utc)})
                break

        raw_text = llm_result.get("response") or ""
        parsed = _parse_response(raw_text)
        messages.append({"role": "assistant", "content": raw_text})

        if parsed["kind"] == "malformed":
            malformed_retries += 1
            iteration = ReactIteration(
                iteration_index=iteration_index, thought=parsed.get("thought", ""),
                observation={"error": "malformed response — expected Thought/Action/Action Input or Thought/Final Answer"},
                observation_kind="tool_error",
                tokens_input=usage.get("input_tokens") if usage else None,
                tokens_output=usage.get("output_tokens") if usage else None, latency_ms=latency_ms,
            )
            execution.iterations.append(iteration)
            if malformed_retries > MAX_MALFORMED_RETRIES:
                execution.status = "guardrail_stopped"
                execution.guardrail_violations.append({"rule": "malformed_output", "detail": "model failed to produce a parseable response after retry", "at": datetime.now(timezone.utc)})
                break
            messages.append({"role": "user", "content": "Your last response didn't match the required Thought/Action/Action Input or Thought/Final Answer format. Respond again in that exact format."})
            continue

        if parsed["kind"] == "final":
            execution.iterations.append(ReactIteration(
                iteration_index=iteration_index, thought=parsed["thought"], observation_kind="ai_inference",
                tokens_input=usage.get("input_tokens") if usage else None,
                tokens_output=usage.get("output_tokens") if usage else None, latency_ms=latency_ms,
            ))
            execution.final_output = parsed["final_output"]
            execution.confidence = _extract_confidence(parsed["final_output"])
            execution.status = "completed"
            break

        # kind == "action"
        action_name = parsed["action"]
        action_input = parsed.get("action_input") or {}
        if action_name not in allowed_tool_ids:
            observation = {"error": f"tool '{action_name}' is not in this agent's allowed tools: {sorted(allowed_tool_ids)}"}
            observation_kind = "tool_error"
        else:
            dispatch_result = await dispatch_tool(action_name, action_input, actor=actor)
            observation = dispatch_result.model_dump()
            observation_kind = dispatch_result.observation_kind if dispatch_result.success else "tool_error"
            if dispatch_result.success:
                execution.evidence.append({
                    "kind": observation_kind, "source": action_name,
                    "content": dispatch_result.output, "citation": f"tool:{action_name}",
                })

        execution.iterations.append(ReactIteration(
            iteration_index=iteration_index, thought=parsed["thought"], action=action_name,
            action_input=action_input, observation=observation, observation_kind=observation_kind,
            tool_id=action_name if action_name in allowed_tool_ids else None,
            tokens_input=usage.get("input_tokens") if usage else None,
            tokens_output=usage.get("output_tokens") if usage else None, latency_ms=latency_ms,
        ))
        messages.append({"role": "user", "content": f"Observation: {json.dumps(observation, default=str)}"})
    else:
        execution.status = "guardrail_stopped"
        execution.guardrail_violations.append({"rule": "max_iterations", "detail": f"exceeded {max_iterations} iterations without a Final Answer", "at": datetime.now(timezone.utc)})

    execution.total_tokens_input = total_tokens_in if saw_real_usage else None
    execution.total_tokens_output = total_tokens_out if saw_real_usage else None
    execution.total_duration_ms = int((time.monotonic() - started_wall) * 1000)
    execution.finished_at = datetime.now(timezone.utc)
    if execution.status == "running":
        execution.status = "completed"

    await _persist(execution)
    return execution.model_dump(mode="json")


def _extract_confidence(final_output: Dict[str, Any]) -> Optional[float]:
    value = final_output.get("confidence") if isinstance(final_output, dict) else None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def _persist(execution: AgentExecution) -> None:
    from ...core.database import db
    try:
        await db.agent_executions.insert_one(execution.model_dump(mode="json"))
    except Exception as e:
        logger.warning(f"agent_executions persist failed for {execution.agent_execution_id}: {e}")


__all__ = ["run_agent"]
