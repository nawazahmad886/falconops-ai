"""
RASED LangGraph spine: orchestrate -> retrieve -> analyze -> decide ->
execute -> verify -> case -> done.

verify (agents/verification.py) is what makes "resolved" mean the underlying
problem actually recovered, not just "the action didn't error" — see that
module's docstring. It runs unconditionally (like case_management) but only
has an effect when execute_node left status="resolved" with a successful
action result; everything else passes through unchanged.

Conditional edges route around outcomes that make the rest of the graph
unnecessary work: a suppressed storm (orchestrate) skips straight to done
without ever touching evidence retrieval or RCA — S5's "40+ alerts, zero
actions" acceptance property depends on this routing, not just on
ActionAgent declining to act.

analyze runs ImpactAgent and RCAAgent concurrently (they don't depend on
each other's output) via asyncio.gather, same concurrency stance as
TelemetryRetrievalAgent's adapter fan-out in Phase 1.

The approval gate is NOT a separate graph node — it's a LangGraph
interrupt() call inside ActionAgent._await_approval(), so DESTRUCTIVE
actions pause mid-node rather than requiring a dedicated routing edge. See
agents/action.py's module docstring for the replay-semantics caveat, and
graph/checkpointer.py's for why this file carries the same "unverified
against a real langgraph install" risk label.
"""
import asyncio

from langgraph.graph import END, StateGraph

from ....models.rased_schemas import InvestigationState
from ..agents.action import ActionAgent
from ..agents.base import guarded_node
from ..agents.case_mgmt import CaseManagementAgent
from ..agents.impact import ImpactAgent
from ..agents.orchestrator import OrchestratorAgent
from ..agents.policy import PolicyAgent
from ..agents.rca import RCAAgent
from ..agents.telemetry import TelemetryRetrievalAgent
from ..agents.verification import VerificationAgent
from .checkpointer import MongoCheckpointer

_orchestrator = OrchestratorAgent()
_telemetry = TelemetryRetrievalAgent()
_impact = ImpactAgent()
_rca = RCAAgent()
_policy = PolicyAgent()
_action = ActionAgent()
_verification = VerificationAgent()
_case_mgmt = CaseManagementAgent()


@guarded_node("orchestrator")
async def orchestrate_node(state: InvestigationState) -> dict:
    return await _orchestrator.run(state)


@guarded_node("telemetry_retrieval")
async def retrieve_node(state: InvestigationState) -> dict:
    return await _telemetry.run(state)


@guarded_node("analyze")
async def analyze_node(state: InvestigationState) -> dict:
    impact_update, rca_update = await asyncio.gather(_impact.run(state), _rca.run(state))
    return {**impact_update, **rca_update}


@guarded_node("policy")
async def decide_node(state: InvestigationState) -> dict:
    return await _policy.run(state)


@guarded_node("action")
async def execute_node(state: InvestigationState) -> dict:
    return await _action.run(state)


@guarded_node("verification")
async def verify_node(state: InvestigationState) -> dict:
    return await _verification.run(state)


@guarded_node("case_management")
async def case_node(state: InvestigationState) -> dict:
    return await _case_mgmt.run(state)


async def done_node(state: InvestigationState) -> dict:
    return {}


def _route_after_orchestrate(state: InvestigationState) -> str:
    if state.status == "suppressed":
        return "done"
    return "retrieve"


def build_graph(checkpointer=None):
    """checkpointer defaults to MongoCheckpointer(); tests pass a fake to
    avoid requiring Mongo."""
    graph = StateGraph(InvestigationState)
    graph.add_node("orchestrate", orchestrate_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("decide", decide_node)
    graph.add_node("execute", execute_node)
    graph.add_node("verify", verify_node)
    graph.add_node("case", case_node)
    graph.add_node("done", done_node)

    graph.set_entry_point("orchestrate")
    graph.add_conditional_edges(
        "orchestrate",
        _route_after_orchestrate,
        {"retrieve": "retrieve", "done": "done"},
    )
    graph.add_edge("retrieve", "analyze")
    graph.add_edge("analyze", "decide")
    graph.add_edge("decide", "execute")
    graph.add_edge("execute", "verify")
    graph.add_edge("verify", "case")
    graph.add_edge("case", "done")
    graph.add_edge("done", END)

    return graph.compile(checkpointer=checkpointer if checkpointer is not None else MongoCheckpointer())


__all__ = [
    "build_graph",
    "orchestrate_node",
    "retrieve_node",
    "analyze_node",
    "decide_node",
    "execute_node",
    "verify_node",
    "case_node",
    "done_node",
]
