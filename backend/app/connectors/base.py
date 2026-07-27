"""
FalconOps AI - Connector SDK: base contract

Every enterprise connector (Prometheus, AWS, and future IBM MQ/DataPower/
Datadog/etc.) implements `BaseConnector` plus whichever optional capability
mixins below it genuinely supports. There are no stub/NotImplementedError
methods for unsupported capabilities anywhere in this SDK — dispatch code
(the scheduler, API routes, the AI-tool bridge) always gates on
`isinstance(connector, XCapable)` rather than calling a method every
connector is forced to implement whether or not it makes sense for it.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ConnectorMetadata:
    id: str
    name: str
    vendor: str
    version: str
    category: str
    capabilities: List[str] = field(default_factory=list)


@dataclass
class HealthResult:
    status: str  # "healthy" | "degraded" | "unhealthy"
    message: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "checked_at": self.checked_at,
            "details": self.details,
        }


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: str
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    metric_type: str = "gauge"  # gauge | counter | histogram

    def to_ingest_dict(self) -> Dict[str, Any]:
        """Shape expected by metrics_timeseries_service.ingest_batch() — note the
        key is "type", not "metric_type" (verified against the real service)."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "unit": self.unit,
            "type": self.metric_type,
        }


@dataclass
class ConfidenceResult:
    """Never fabricated — derived from real sample count/coverage, or omitted."""
    score: float  # 0.0-1.0
    basis: str

    def to_dict(self) -> Dict[str, Any]:
        return {"score": self.score, "basis": self.basis}


class BaseConnector(ABC):
    """Required core contract. Deliberately small — identity, lifecycle, health
    only. Capability-specific behavior lives in the optional mixins below."""

    def __init__(self, config: Dict[str, Any], tenant_id: Optional[str] = None):
        self.config = config
        self.tenant_id = tenant_id

    @classmethod
    @abstractmethod
    def metadata(cls) -> ConnectorMetadata:
        """Static identity/version info — does not require a live connection."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish/validate the underlying client. Must never raise on missing
        or invalid config — record the failure internally and let
        test_connection()/health() report it, so callers can always safely call
        connect() then check health() rather than wrapping connect() in a
        connector-specific try/except."""

    @abstractmethod
    async def test_connection(self) -> HealthResult:
        """Real connectivity probe (never a hardcoded success). Backs
        POST /api/connectors/{id}/test and is called by the scheduler before
        each poll."""

    async def health(self) -> HealthResult:
        """Default: delegates to test_connection(). Override for a cheaper or
        cached check if a real connectivity probe is expensive."""
        return await self.test_connection()

    def capabilities(self) -> List[str]:
        """Derived via isinstance() against the mixins below — never a
        hand-maintained list that can drift out of sync with what a connector
        actually implements."""
        caps: List[str] = []
        if isinstance(self, MetricsCapable):
            caps.append("metrics")
        if isinstance(self, EventsCapable):
            caps.append("events")
        if isinstance(self, LogsCapable):
            caps.append("logs")
        if isinstance(self, TopologyCapable):
            caps.append("topology")
        if isinstance(self, InventoryCapable):
            caps.append("inventory")
        if isinstance(self, RemediationCapable):
            caps.append("remediation")
        if isinstance(self, AIContextCapable):
            caps.append("ai_context")
        return caps


class MetricsCapable(ABC):
    @abstractmethod
    async def fetch_metrics(self, since: Optional[str] = None) -> List[MetricPoint]:
        """Must return [] — never fabricated data — if not really connected."""


class EventsCapable(ABC):
    @abstractmethod
    async def fetch_events(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """Dicts compatible with soc_ingestion_service.normalize_event()'s input
        keys (source/service/severity/category/message/host/ip-or-source_ip/
        user/action; anything else collapses into metadata). Must return [] —
        never fabricated data — when not configured/reachable."""


class LogsCapable(ABC):
    @abstractmethod
    async def fetch_logs(self, since: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Must return [] — never fabricated data — when not configured/reachable."""


class TopologyCapable(ABC):
    @abstractmethod
    async def discover_topology(self) -> Dict[str, Any]:
        """{"nodes": [{"name","service_type","environment"?}],
        "edges": [{"source_name","target_name","connection_type"?}]} — the
        scheduler dedupes via topology_service.get_service_by_name() before
        create_service_node()/create_connection(), mirroring the existing
        auto_discover_from_traces() pattern."""


class InventoryCapable(ABC):
    @abstractmethod
    async def list_inventory(self) -> List[Dict[str, Any]]:
        """Must return [] — never fabricated data — when not configured/reachable."""


class RemediationCapable(ABC):
    @abstractmethod
    async def get_recommendations(self, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """[{"id","description","risk_level":"low"|"medium"|"high",
        "auto_eligible":bool,"params":[...]}] — same shape as
        remediation_service.ACTION_LIBRARY entries. NEVER executes anything;
        real remediation execution is a separate, still-open capability."""


class AIContextCapable(ABC):
    @abstractmethod
    async def get_ai_context(self, **params) -> Dict[str, Any]:
        """Same envelope ai_tools_service tool functions use:
        {"tool","params","count","data","summary"}, plus an optional
        "confidence": ConfidenceResult.to_dict()."""
