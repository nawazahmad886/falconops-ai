"""
AI Operations — Agent Builder + Agentic Workflow Builder shared Pydantic contracts.

Layered on top of RASED (backend/app/services/rased/), not a replacement for
it. Two split-collection patterns repeat here, both mirroring how RASED
itself separates mutable/current state from immutable/historical state
(rased_investigations vs rased_trace):

- agent_definitions / agent_versions: the header doc is a mutable pointer
  (current_published_version, latest_draft_version); each version is an
  immutable snapshot. Publish = freeze a version + move the pointer.
  Rollback = move the pointer only, no data mutation. Same split for
  workflow_definitions / workflow_versions.
- ToolBinding.kind is a closed enum, not a free string — this is the actual
  enforcement point for "no unrestricted shell execution": there is no
  binding kind that maps to an arbitrary command, and tool_binding_dispatch's
  dispatch table has no default/fallback branch for an unrecognized kind.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .rased_schemas import RiskTier

# ─────────────────────────── Tool Catalog ───────────────────────────

ToolBindingKind = Literal[
    "rased_action",           # ref = RASED ACTIONS registry key (registry.py)
    "rased_adapter_readonly",  # ref = RASED adapter module name under rased/adapters/ (read-only query())
    "troubleshooting_command",  # ref = troubleshooting_service.COMMAND_CATALOG id
    "http_integration",       # ref = integration_id in db.integrations
    "k8s_read",                # ref = "list_pods" (only real read op exposed)
    "k8s_restart_pod",         # ref = unused; always dispatches to rased restart_pod executor
    "rag_search",               # ref = "incidents" | "logs"
    "memory_search",            # ref = vector_memory_service kind filter, e.g. "agent_ltm"
]

ToolCategory = Literal[
    "Observability", "Database", "Network", "Kubernetes", "Cloud",
    "Security", "ITSM", "Notification", "Custom API", "Knowledge",
]


class ToolBinding(BaseModel):
    kind: ToolBindingKind
    ref: str
    static_params: Dict[str, Any] = {}


class ToolCatalogEntry(BaseModel):
    tool_id: str
    name: str
    description: str = ""
    category: ToolCategory
    version: int = 1
    status: Literal["active", "disabled"] = "active"
    binding: ToolBinding
    input_schema: Dict[str, Any] = {"type": "object", "properties": {}}
    output_schema: Dict[str, Any] = {"type": "object", "properties": {}}
    risk_tier: RiskTier = "SAFE"
    required_permission: Optional[str] = None
    timeout_seconds: int = 30
    created_by: str = "system"
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolDispatchResult(BaseModel):
    success: bool
    output: Dict[str, Any] = {}
    error: Optional[str] = None
    execution_mode: Literal["simulated", "live", "read"] = "read"
    observation_kind: Literal["observed_data", "retrieved_knowledge"] = "observed_data"
    duration_ms: int = 0


# ─────────────────────────── Agent Builder ───────────────────────────

class PromptVariable(BaseModel):
    name: str
    type: Literal["string", "number", "boolean"] = "string"
    default: Optional[Any] = None
    required: bool = False


class SystemInstructions(BaseModel):
    template: str = ""
    variables: List[PromptVariable] = []


class ModelConfig(BaseModel):
    provider: str = "openai"   # matches AdminControlConsole.js's picklist ids
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 1500
    timeout_seconds: int = 60
    retry_max_attempts: int = 2
    retry_backoff_seconds: float = 1.5


class KnowledgeConfig(BaseModel):
    enabled: bool = False
    source: Literal["rag_incidents", "rag_logs", "none"] = "none"
    retrieval_limit: int = 3
    similarity_threshold: float = 0.0
    citation_required: bool = True


class MemoryConfig(BaseModel):
    stm_enabled: bool = True
    stm_retention_turns: int = 10
    ltm_enabled: bool = False
    ltm_retention_days: int = 30
    incident_memory_enabled: bool = False


class ApprovalRule(BaseModel):
    condition: str = ""  # human-readable label only; enforcement is by tool risk_tier, not this string
    approval_permission: str = "remediation.approve_destructive"


class AgentGuardrails(BaseModel):
    allowed_tools: List[str] = []
    denied_tools: List[str] = []
    max_execution_seconds: int = 120
    max_iterations: int = 6
    max_token_budget: Optional[int] = None
    allowed_environments: List[str] = ["development", "staging", "production"]
    required_approval_rules: List[ApprovalRule] = []
    confidence_threshold: float = 0.0


class AgentToolRef(BaseModel):
    tool_id: str
    tool_version: int = 1


class AgentVersion(BaseModel):
    version_id: str
    agent_id: str
    version: int
    state: Literal["draft", "published", "archived"] = "draft"
    system_instructions: SystemInstructions = SystemInstructions()
    llm_config: ModelConfig = Field(default_factory=ModelConfig)
    tools: List[AgentToolRef] = []
    knowledge_config: KnowledgeConfig = KnowledgeConfig()
    memory_config: MemoryConfig = MemoryConfig()
    input_schema: Dict[str, Any] = {"type": "object", "properties": {}}
    output_schema: Dict[str, Any] = {"type": "object", "properties": {}}
    guardrails: AgentGuardrails = AgentGuardrails()
    permissions_required: List[str] = ["agent.read"]
    changelog: str = ""
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None


class AgentDefinition(BaseModel):
    agent_id: str
    name: str
    description: str = ""
    category: str = "custom"
    icon: str = "Bot"
    owner_email: str = "system"
    status: Literal["draft", "published", "archived"] = "draft"
    current_published_version: Optional[int] = None
    latest_draft_version: int = 1
    is_rased_wrapper: bool = False
    rased_agent_class: Optional[str] = None
    tags: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


ObservationKind = Literal["observed_data", "retrieved_knowledge", "ai_inference", "tool_error"]


class ReactIteration(BaseModel):
    iteration_index: int
    thought: str = ""
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    observation_kind: Optional[ObservationKind] = None
    tool_id: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    latency_ms: int = 0
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceItem(BaseModel):
    kind: ObservationKind
    source: str
    content: Dict[str, Any] = {}
    citation: Optional[str] = None


class AgentExecution(BaseModel):
    agent_execution_id: str
    agent_id: str
    agent_version: int
    triggered_by_kind: Literal["manual_test", "workflow_node", "api"] = "manual_test"
    triggered_by_ref: Optional[str] = None
    status: Literal["running", "completed", "failed", "timed_out", "guardrail_stopped"] = "running"
    input: Dict[str, Any] = {}
    iterations: List[ReactIteration] = []
    final_output: Dict[str, Any] = {}
    confidence: Optional[float] = None
    evidence: List[EvidenceItem] = []
    guardrail_violations: List[Dict[str, Any]] = []
    total_tokens_input: Optional[int] = None
    total_tokens_output: Optional[int] = None
    total_cost_estimate: Optional[float] = None
    total_duration_ms: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


# ─────────────────────────── Workflow Builder ───────────────────────────

WorkflowNodeType = Literal[
    # Triggers
    "trigger_manual", "trigger_schedule", "trigger_alert", "trigger_incident",
    "trigger_api", "trigger_webhook", "trigger_threshold", "trigger_event",
    # AI
    "agent", "planner", "ai_decision", "synthesizer", "judge",
    # Data
    "data_elasticsearch", "data_apm", "data_sql", "data_metrics", "data_logs",
    "data_http", "data_rag_search", "data_memory",
    # Control
    "condition", "switch", "parallel", "join", "loop", "wait", "retry", "timeout",
    # Action
    "action_restart_pod", "action_scale_service", "action_run_workflow",
    "action_create_ticket", "action_send_email", "action_send_teams",
    "action_send_slack", "action_create_incident",
    # Governance
    "human_approval", "risk_check", "permission_check", "policy_check",
    # Validation
    "verification", "health_check", "slo_check",
]

WorkflowNodeCategory = Literal[
    "trigger", "ai", "data", "control", "action", "governance", "validation",
]

_NODE_CATEGORY: Dict[str, WorkflowNodeCategory] = {}
for _t in (
    "trigger_manual", "trigger_schedule", "trigger_alert", "trigger_incident",
    "trigger_api", "trigger_webhook", "trigger_threshold", "trigger_event",
):
    _NODE_CATEGORY[_t] = "trigger"
for _t in ("agent", "planner", "ai_decision", "synthesizer", "judge"):
    _NODE_CATEGORY[_t] = "ai"
for _t in (
    "data_elasticsearch", "data_apm", "data_sql", "data_metrics", "data_logs",
    "data_http", "data_rag_search", "data_memory",
):
    _NODE_CATEGORY[_t] = "data"
for _t in ("condition", "switch", "parallel", "join", "loop", "wait", "retry", "timeout"):
    _NODE_CATEGORY[_t] = "control"
for _t in (
    "action_restart_pod", "action_scale_service", "action_run_workflow",
    "action_create_ticket", "action_send_email", "action_send_teams",
    "action_send_slack", "action_create_incident",
):
    _NODE_CATEGORY[_t] = "action"
for _t in ("human_approval", "risk_check", "permission_check", "policy_check"):
    _NODE_CATEGORY[_t] = "governance"
for _t in ("verification", "health_check", "slo_check"):
    _NODE_CATEGORY[_t] = "validation"


class WorkflowNode(BaseModel):
    node_id: str
    type: WorkflowNodeType
    position: Dict[str, float] = {"x": 0.0, "y": 0.0}
    config: Dict[str, Any] = {}
    data_mapping: Dict[str, str] = {}   # {input_field: "{{source_node.output.path}}"}
    label: Optional[str] = None


class WorkflowEdge(BaseModel):
    edge_id: str
    source: str
    source_handle: Optional[str] = None
    target: str
    target_handle: Optional[str] = None
    label: Optional[str] = None
    condition_branch: Optional[str] = None   # "true" | "false" | "case:<value>" | None


class WorkflowVariable(BaseModel):
    name: str
    type: Literal["string", "number", "boolean", "object"] = "string"
    default: Optional[Any] = None


class WorkflowTriggerConfig(BaseModel):
    type: Literal[
        "manual", "schedule", "alert", "incident", "api", "webhook", "threshold", "event",
    ] = "manual"
    config: Dict[str, Any] = {}


class WorkflowVersion(BaseModel):
    version_id: str
    workflow_id: str
    version: int
    state: Literal["draft", "published", "archived"] = "draft"
    nodes: List[WorkflowNode] = []
    edges: List[WorkflowEdge] = []
    variables: List[WorkflowVariable] = []
    trigger_config: WorkflowTriggerConfig = WorkflowTriggerConfig()
    changelog: str = ""
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None


class WorkflowDefinition(BaseModel):
    workflow_id: str
    name: str
    description: str = ""
    status: Literal["draft", "published", "paused", "disabled", "archived"] = "draft"
    current_published_version: Optional[int] = None
    latest_draft_version: int = 1
    tags: List[str] = []
    category: str = "custom"
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


ExecutionStatus = Literal[
    "queued", "running", "waiting", "paused", "completed", "failed", "cancelled", "timed_out",
]

NodeExecutionStatus = Literal[
    "queued", "running", "completed", "failed", "skipped", "waiting_approval", "cancelled",
]


class WorkflowExecutionMetrics(BaseModel):
    duration_ms: Optional[int] = None
    node_count: int = 0
    agent_tokens_input_total: Optional[int] = None
    agent_tokens_output_total: Optional[int] = None
    agent_cost_estimate_total: Optional[float] = None
    retries_total: int = 0
    approval_wait_ms_total: int = 0


class WorkflowExecution(BaseModel):
    execution_id: str
    workflow_id: str
    workflow_version: int
    status: ExecutionStatus = "queued"
    trigger_type: str = "manual"
    trigger_payload: Dict[str, Any] = {}
    dry_run: bool = False
    test_run: bool = False
    execution_graph_snapshot: Dict[str, Any] = {}   # {"nodes": [...], "edges": [...]}
    variables: Dict[str, Any] = {}
    current_node_ids: List[str] = []
    incident_id: Optional[str] = None
    metrics: WorkflowExecutionMetrics = WorkflowExecutionMetrics()
    started_by: str = "system"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


class WorkflowNodeExecution(BaseModel):
    node_execution_id: str
    execution_id: str
    node_id: str
    node_type: str
    iteration_index: int = 0
    status: NodeExecutionStatus = "queued"
    input: Dict[str, Any] = {}
    output: Dict[str, Any] = {}
    error: Optional[str] = None
    agent_execution_id: Optional[str] = None
    rased_incident_id: Optional[str] = None
    approval_id: Optional[str] = None
    retries: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class WorkflowApproval(BaseModel):
    approval_id: str
    execution_id: str
    node_execution_id: str
    workflow_id: str
    requested_permission: str = "remediation.approve_destructive"
    title: str = ""
    risk_tier: RiskTier = "GUARDED"
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    reason: Optional[str] = None


class WorkflowTemplate(BaseModel):
    template_id: str
    name: str
    description: str = ""
    category: str = "custom"
    is_built_in: bool = False
    graph_snapshot: Dict[str, Any] = {}   # {"nodes", "edges", "variables", "trigger_config"}
    tags: List[str] = []
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationFinding(BaseModel):
    severity: Literal["error", "warning"]
    node_id: Optional[str] = None
    rule: str
    message: str


__all__ = [
    "ToolBindingKind", "ToolCategory", "ToolBinding", "ToolCatalogEntry", "ToolDispatchResult",
    "PromptVariable", "SystemInstructions", "ModelConfig", "KnowledgeConfig", "MemoryConfig",
    "ApprovalRule", "AgentGuardrails", "AgentToolRef", "AgentVersion", "AgentDefinition",
    "ObservationKind", "ReactIteration", "EvidenceItem", "AgentExecution",
    "WorkflowNodeType", "WorkflowNodeCategory", "WorkflowNode", "WorkflowEdge", "WorkflowVariable",
    "WorkflowTriggerConfig", "WorkflowVersion", "WorkflowDefinition", "ExecutionStatus",
    "NodeExecutionStatus", "WorkflowExecutionMetrics", "WorkflowExecution", "WorkflowNodeExecution",
    "WorkflowApproval", "WorkflowTemplate", "ValidationFinding",
]
