"""
Shared node contract for RASED's LangGraph agents.

Every node is `async def node(state: InvestigationState) -> dict` — a
partial state update, never a mutation of the input state, and it never
raises. guarded_node() enforces the "never raises" half of that contract at
the framework boundary: whatever an agent's own code does internally, a node
wrapped in this decorator degrades to an error record and a lowered
confidence score instead of crashing the graph.
"""
import logging
import time
from functools import wraps
from typing import Awaitable, Callable, Dict

from ....models.rased_schemas import InvestigationState
from ..graph.trace import TraceRecorder

logger = logging.getLogger(__name__)

NodeFn = Callable[[InvestigationState], Awaitable[Dict]]


def guarded_node(agent_name: str) -> Callable[[NodeFn], NodeFn]:
    def decorator(fn: NodeFn) -> NodeFn:
        @wraps(fn)
        async def wrapper(state: InvestigationState) -> Dict:
            trace = TraceRecorder(state.incident_id)
            started = time.perf_counter()
            await trace.emit(agent_name, "start", f"{agent_name} started")
            try:
                update = await fn(state)
            except Exception as exc:
                logger.exception(f"{agent_name} raised for incident {state.incident_id}")
                duration_ms = int((time.perf_counter() - started) * 1000)
                await trace.emit(agent_name, "error", f"{agent_name} failed: {exc}", duration_ms=duration_ms)
                return {
                    "error": f"{agent_name}: {exc}",
                    "confidence": max(0.0, state.confidence - 0.25),
                }
            duration_ms = int((time.perf_counter() - started) * 1000)
            await trace.emit(agent_name, "decision", f"{agent_name} completed", duration_ms=duration_ms)
            return update
        return wrapper
    return decorator


__all__ = ["guarded_node", "NodeFn"]
