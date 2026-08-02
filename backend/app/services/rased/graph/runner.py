"""
Drives a compiled RASED graph from a fresh InvestigationState, or resumes
one paused on a DESTRUCTIVE-action approval interrupt.

Centralizes the two calls in this build that actually invoke
CompiledGraph.ainvoke() so the "unverified against a real langgraph install"
risk already flagged in checkpointer.py and workflow.py is contained here
rather than duplicated across every route that needs to run or resume an
investigation. resume_investigation()'s use of langgraph.types.Command is
the third and last place this build depends on LangGraph's human-in-the-loop
API surface specifically (after checkpointer.py's BaseCheckpointSaver and
agents/action.py's interrupt() call) — same caveat applies: authored without
a local interpreter available to confirm against langgraph==1.2.10.
"""
import logging
from typing import Any, Dict, Optional

from ....models.rased_schemas import InvestigationState
from .workflow import build_graph

logger = logging.getLogger(__name__)

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def _thread_config(incident_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": incident_id}}


def _coerce_state(raw_result: Any, fallback: Optional[InvestigationState]) -> InvestigationState:
    if isinstance(raw_result, InvestigationState):
        return raw_result
    if isinstance(raw_result, dict):
        try:
            return InvestigationState(**raw_result)
        except Exception as exc:
            logger.warning(f"rased graph result did not match InvestigationState shape: {exc}")
    if fallback is not None:
        return fallback
    raise RuntimeError("could not coerce langgraph result into InvestigationState")


async def run_investigation(initial_state: InvestigationState) -> InvestigationState:
    graph = get_graph()
    raw_result = await graph.ainvoke(initial_state.model_dump(), config=_thread_config(initial_state.incident_id))
    return _coerce_state(raw_result, initial_state)


async def resume_investigation(incident_id: str, resume_value: Dict[str, Any]) -> InvestigationState:
    from langgraph.types import Command
    graph = get_graph()
    raw_result = await graph.ainvoke(Command(resume=resume_value), config=_thread_config(incident_id))
    return _coerce_state(raw_result, None)


__all__ = ["get_graph", "run_investigation", "resume_investigation"]
