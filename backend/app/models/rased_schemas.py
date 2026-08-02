"""
RASED (راصد) — shared Pydantic contracts.

Every downstream RASED module (adapters, agents, graph, routes) imports these
models rather than defining its own shape for the same concept. Two contracts
carry the most weight:

- Evidence.tier distinguishes what is knowable from an alert payload alone
  ("trigger") from what only surfaces after an adapter is queried ("deep").
  This is what makes hypothesis revision in Phase 2 a genuine change of mind
  driven by data, not a scripted reversal.
- InvestigationState.execution_mode is carried on every ActionResult so the
  audit trail is self-describing about whether an action actually touched
  anything, independent of how config.py is set at runtime.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Sources an adapter can be queried against. Kept as one shared Literal so
# Evidence, ToolResult, and ActionSpec.adapter all agree on the vocabulary.
Source = Literal["elk", "appdynamics", "solarwinds", "mq", "db", "cmdb", "changes"]

EvidenceTier = Literal["trigger", "deep"]

ExecutionMode = Literal["simulated", "live"]

RiskTier = Literal["SAFE", "GUARDED", "DESTRUCTIVE"]

Severity = Literal["critical", "high", "medium", "low", "info"]


class Alert(BaseModel):
    alert_id: str
    signature: str
    source: Source
    service: str
    host: Optional[str] = None
    severity: Severity
    title: str
    description: str
    tenant_id: Optional[str] = None
    observed_at: datetime
    raw: Dict[str, Any] = {}


class Evidence(BaseModel):
    evidence_id: str
    tier: EvidenceTier
    source: Source
    query: str
    summary: str
    data: Dict[str, Any]
    observed_at: datetime
    retrieved_at: datetime


class ToolResult(BaseModel):
    """Raw return shape of an adapter's query() call, before it is curated
    into an Evidence item."""
    source: Source
    query: str
    success: bool
    data: Any = None
    latency_ms: int
    error: Optional[str] = None
    retrieved_at: datetime


class BusinessImpact(BaseModel):
    incident_id: str
    affected_service: str
    business_capability: str
    transactions_at_risk: int
    revenue_at_risk: Optional[float] = None
    summary: str
    computed_at: datetime


class Hypothesis(BaseModel):
    hypothesis_id: str
    incident_id: str
    stage: Literal["initial", "revised"]
    statement: str
    root_cause_entity: Optional[str] = None
    confidence: float
    evidence_ids: List[str] = []
    superseded: bool = False
    changed_because: Optional[List[str]] = None
    revision_reason: Optional[str] = None
    generated_at: datetime


class PolicyCitation(BaseModel):
    document_id: str
    section: str


class PolicyDecision(BaseModel):
    incident_id: str
    severity_tier: Literal["P1", "P2", "P3", "P4"]
    escalation_target: str
    notification_template: str
    approval_required: bool
    maintenance_window_active: bool
    citations: List[PolicyCitation] = []
    justification: str
    decided_at: datetime


class ActionSpec(BaseModel):
    """Static registry entry. Risk tier is declared here, never inferred at
    runtime by an LLM."""
    tier: RiskTier
    adapter: str
    description: str = ""


class Action(BaseModel):
    action_id: str
    incident_id: str
    name: str
    spec: ActionSpec
    params: Dict[str, Any] = {}
    status: Literal["proposed", "approved", "rejected", "executed", "failed"]
    proposed_at: datetime


class ActionResult(BaseModel):
    action_id: str
    incident_id: str
    success: bool
    execution_mode: ExecutionMode
    output: Dict[str, Any] = {}
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    executed_at: datetime


class Approval(BaseModel):
    approval_id: str
    action_id: str
    incident_id: str
    status: Literal["pending", "approved", "rejected", "expired"]
    requested_at: datetime
    expires_at: datetime
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    reason: Optional[str] = None


class AuditEntry(BaseModel):
    entry_id: str
    incident_id: str
    tenant_id: Optional[str] = None
    actor: Literal["system", "agent", "human"]
    action: str
    detail: Dict[str, Any] = {}
    at: datetime


class TraceEvent(BaseModel):
    incident_id: str
    seq: int
    agent: str
    kind: Literal["start", "tool_call", "tool_result", "reasoning", "decision", "action", "error"]
    title: str
    detail: Dict[str, Any] = {}
    duration_ms: Optional[int] = None
    at: datetime


class InvestigationState(BaseModel):
    """LangGraph state object. Every node receives this and returns a
    partial update — never mutates it in place."""
    incident_id: str
    tenant_id: Optional[str] = None
    root_signature: Optional[str] = None
    status: Literal[
        "new", "investigating", "awaiting_approval", "suppressed", "resolved", "escalated"
    ] = "new"
    execution_mode: ExecutionMode

    alerts: List[Alert] = []
    evidence: List[Evidence] = []
    hypotheses: List[Hypothesis] = []
    business_impact: Optional[BusinessImpact] = None
    policy_decision: Optional[PolicyDecision] = None
    actions: List[Action] = []
    action_results: List[ActionResult] = []
    approvals: List[Approval] = []
    audit_log: List[AuditEntry] = []
    trace: List[TraceEvent] = []

    confidence: float = 0.0
    error: Optional[str] = None

    created_at: datetime
    updated_at: datetime


__all__ = [
    "Source",
    "EvidenceTier",
    "ExecutionMode",
    "RiskTier",
    "Severity",
    "Alert",
    "Evidence",
    "ToolResult",
    "BusinessImpact",
    "Hypothesis",
    "PolicyCitation",
    "PolicyDecision",
    "ActionSpec",
    "Action",
    "ActionResult",
    "Approval",
    "AuditEntry",
    "TraceEvent",
    "InvestigationState",
]
