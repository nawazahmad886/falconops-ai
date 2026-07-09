"""
FalconOps AI - All Pydantic Models/Schemas
Centralized data models for the entire application
"""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Dict, Any


# ======================== AUTH MODELS ========================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    full_name: str
    organization: Optional[str] = None
    role: str = "user"
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ======================== ALERT MODELS ========================

class AlertCreate(BaseModel):
    source: str
    severity: str
    title: str
    description: str
    service: str
    host: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    tags: Optional[Dict[str, str]] = None
    raw_payload: Optional[Dict[str, Any]] = None

class AlertResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    source: str
    severity: str
    title: str
    description: str
    service: str
    host: Optional[str] = None
    status: str
    incident_id: Optional[str] = None
    created_at: str
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    acknowledged_by: Optional[str] = None

class SendAlertNotificationRequest(BaseModel):
    channel: str
    recipient: Optional[str] = None
    message: Optional[str] = None


# ======================== INCIDENT MODELS ========================

class IncidentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    severity: str
    status: str
    service: str
    alert_count: int
    alert_ids: List[str]
    ai_analysis: Optional[Dict[str, Any]] = None
    root_cause: Optional[str] = None
    suggested_actions: Optional[List[str]] = None
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    mttr_seconds: Optional[int] = None


# ======================== RUNBOOK MODELS ========================

class RunbookCreate(BaseModel):
    name: str
    description: str
    service: str
    trigger_conditions: Optional[Dict[str, Any]] = None
    steps: List[Dict[str, Any]]
    auto_execute: bool = False

class RunbookResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    description: str
    service: str
    steps: List[Dict[str, Any]]
    auto_execute: bool
    execution_count: int
    last_executed: Optional[str] = None
    created_at: str
    created_by: str
    category: Optional[str] = "general"
    schedule: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = []
    tenant_id: Optional[str] = None


# ======================== ANALYTICS MODELS ========================

class AnalyticsResponse(BaseModel):
    total_alerts: int
    open_alerts: int
    resolved_alerts: int
    total_incidents: int
    open_incidents: int
    avg_mttr_seconds: float
    alerts_by_severity: Dict[str, int]
    alerts_by_service: Dict[str, int]
    incidents_trend: List[Dict[str, Any]]
    sla_compliance: float

class AIAnalysisRequest(BaseModel):
    incident_id: str


# ======================== MONITORING MODELS ========================

class MonitorCreate(BaseModel):
    name: str
    target: str
    monitor_type: str
    interval_seconds: int = 60
    timeout_seconds: int = 5
    port: Optional[int] = None
    expected_status_code: Optional[int] = 200
    environment: str = "production"
    sla_uptime_percent: float = 99.9
    sla_max_latency_ms: float = 300
    tags: Optional[Dict[str, str]] = None
    enabled: bool = True
    notification_email: Optional[str] = None

class MonitorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    target: str
    monitor_type: str
    interval_seconds: int
    timeout_seconds: int
    port: Optional[int] = None
    expected_status_code: Optional[int] = None
    environment: str
    sla_uptime_percent: float
    sla_max_latency_ms: float
    tags: Optional[Dict[str, str]] = None
    enabled: bool
    notification_email: Optional[str] = None
    status: str
    last_check: Optional[str] = None
    last_latency_ms: Optional[float] = None
    uptime_percent_24h: Optional[float] = None
    created_at: str
    created_by: str

class MonitorResultCreate(BaseModel):
    monitor_id: str
    status: str
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    packet_loss: Optional[float] = None
    error_message: Optional[str] = None

class MonitorResultResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    monitor_id: str
    status: str
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    packet_loss: Optional[float] = None
    error_message: Optional[str] = None
    created_at: str

class MonitoringDashboardResponse(BaseModel):
    total_monitors: int
    monitors_up: int
    monitors_down: int
    monitors_degraded: int
    overall_uptime_percent: float
    avg_latency_ms: float
    sla_compliance_percent: float
    active_outages: int
    monitors_by_type: Dict[str, int]
    monitors_by_environment: Dict[str, int]
    recent_incidents: List[Dict[str, Any]]
    latency_trend: List[Dict[str, Any]]


# ======================== SCHEDULED REPORTS MODELS ========================

class ScheduledReportCreate(BaseModel):
    name: str
    frequency: str
    recipients: List[str]
    report_type: str = "executive"
    day_of_week: Optional[int] = 0
    hour: int = 8
    enabled: bool = True
    include_monitors: Optional[List[str]] = None
    include_pdf: bool = True
    include_ai_summary: bool = True

class ScheduledReportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    frequency: str
    recipients: List[str]
    report_type: str
    day_of_week: Optional[int] = None
    hour: int
    enabled: bool
    include_monitors: Optional[List[str]] = None
    include_pdf: bool = True
    include_ai_summary: bool = True
    last_sent: Optional[str] = None
    next_run: Optional[str] = None
    created_at: str
    created_by: str


# ======================== APM MODELS ========================

class APMServiceCreate(BaseModel):
    service_name: str
    service_type: str = "web"
    environment: str = "production"
    version: Optional[str] = None
    host: Optional[str] = None
    tags: Optional[Dict[str, str]] = None

class APMServiceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    service_name: str
    service_type: str
    environment: str
    version: Optional[str] = None
    host: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    api_key: str
    status: str = "active"
    last_seen: Optional[str] = None
    created_at: str

class APMMetricsBatch(BaseModel):
    service_id: str
    api_key: str
    timestamp: str
    metrics: List[Dict[str, Any]]

class APMTransactionCreate(BaseModel):
    service_id: str
    api_key: str
    transaction_id: str
    transaction_name: str
    transaction_type: str = "request"
    start_time: str
    end_time: str
    duration_ms: float
    status_code: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    db_time_ms: Optional[float] = None
    external_time_ms: Optional[float] = None
    code_time_ms: Optional[float] = None

class APMDependencyCall(BaseModel):
    service_id: str
    api_key: str
    transaction_id: Optional[str] = None
    dependency_name: str
    dependency_type: str
    target: str
    operation: str
    duration_ms: float
    success: bool = True
    error_message: Optional[str] = None
    timestamp: str

class APMErrorEvent(BaseModel):
    service_id: str
    api_key: str
    transaction_id: Optional[str] = None
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    severity: str = "error"
    endpoint: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str

class APMDashboardResponse(BaseModel):
    period: Dict[str, str]
    services: List[Dict[str, Any]]
    overall_metrics: Dict[str, Any]
    error_breakdown: List[Dict[str, Any]]
    slow_transactions: List[Dict[str, Any]]
    dependency_health: List[Dict[str, Any]]
    throughput_trend: List[Dict[str, Any]]


# ======================== TOPOLOGY MODELS ========================

class ServiceDependency(BaseModel):
    source_monitor_id: str
    target_monitor_id: str
    dependency_type: str = "depends_on"
    weight: float = 1.0
    description: Optional[str] = None

class ServiceDependencyCreate(BaseModel):
    source_monitor_id: str
    target_monitor_id: str
    dependency_type: str = "depends_on"
    description: Optional[str] = None

class TopologyNode(BaseModel):
    id: str
    name: str
    type: str
    target: str
    status: str
    health_score: float
    latency_ms: Optional[float] = None
    environment: Optional[str] = None
    dependencies: List[str] = []
    dependents: List[str] = []

class TopologyEdge(BaseModel):
    source: str
    target: str
    dependency_type: str
    status: str
    latency_impact: Optional[float] = None

class NetworkTopologyResponse(BaseModel):
    nodes: List[TopologyNode]
    edges: List[TopologyEdge]
    health_summary: Dict[str, Any]
    critical_paths: List[Dict[str, Any]]
    cascade_risks: List[Dict[str, Any]]


# ======================== TRACEROUTE MODELS ========================

class TracerouteHop(BaseModel):
    hop_number: int
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    latency_ms: Optional[float] = None
    status: str
    is_destination: bool = False
    location: Optional[str] = None

class TracerouteResponse(BaseModel):
    monitor_id: str
    target: str
    total_hops: int
    destination_reached: bool
    failure_hop: Optional[int] = None
    hops: List[TracerouteHop]
    analysis: Optional[Dict[str, Any]] = None
    executed_at: str


# ======================== SYNTHETIC MONITORING MODELS ========================

class SyntheticMonitorCreate(BaseModel):
    name: str
    target_url: str
    login_url: Optional[str] = None
    test_username: Optional[str] = None
    test_password: Optional[str] = None
    username_selector: str = 'input[type="email"], input[name="email"]'
    password_selector: str = 'input[type="password"]'
    submit_selector: str = 'button[type="submit"]'
    success_indicator: str = '/dashboard'
    check_interval_seconds: int = 300
    timeout_seconds: int = 30
    enabled: bool = True


# ======================== REPORT MODELS ========================

class ReportDateRange(BaseModel):
    start_date: str
    end_date: str

class ExecutiveReportResponse(BaseModel):
    period: Dict[str, str]
    kpis: Dict[str, Any]
    incident_trends: List[Dict[str, Any]]
    category_breakdown: List[Dict[str, Any]]
    team_performance: List[Dict[str, Any]]
    sla_summary: Dict[str, Any]
    ai_summary: Optional[str] = None
    generated_at: str
