"""
RASED adapter interface.

Every external system RASED touches sits behind an Adapter. Swapping a mock
implementation for a live one is a config/adapter-class change — agent code
that calls query() never changes. In Phase 0, every adapter is a
MongoSeededAdapter: it reads back synthetic telemetry a scenario generator
already seeded into its own collection. Live variants (Phase 4 onward) are
new Adapter subclasses selected by config, not a branch inside this one.
"""
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List

from ....models.rased_schemas import Source, ToolResult


class Adapter(ABC):
    source: Source

    @abstractmethod
    async def query(self, params: Dict[str, Any]) -> ToolResult:
        """Never raises. A failed query returns ToolResult(success=False,
        error=...) — the caller degrades the investigation and lowers
        confidence, it never crashes the run."""
        raise NotImplementedError


class MongoSeededAdapter(Adapter):
    collection_name: str

    async def query(self, params: Dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        query_filter = self._build_filter(params)
        try:
            docs = await self._fetch(query_filter)
            return ToolResult(
                source=self.source,
                query=self._describe_query(params),
                success=True,
                data=docs,
                latency_ms=self._elapsed_ms(started),
                retrieved_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            return ToolResult(
                source=self.source,
                query=self._describe_query(params),
                success=False,
                data=None,
                error=str(exc),
                latency_ms=self._elapsed_ms(started),
                retrieved_at=datetime.now(timezone.utc),
            )

    async def _fetch(self, query_filter: Dict[str, Any]) -> List[dict]:
        from ....core.database import db
        cursor = db[self.collection_name].find(query_filter, {"_id": 0})
        return await cursor.to_list(length=500)

    def _build_filter(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query_filter: Dict[str, Any] = {}
        if params.get("scenario_id"):
            query_filter["scenario_id"] = params["scenario_id"]
        if params.get("incident_id"):
            query_filter["incident_id"] = params["incident_id"]
        if params.get("service"):
            query_filter["service"] = params["service"]
        return query_filter

    def _describe_query(self, params: Dict[str, Any]) -> str:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
        return f"db.{self.collection_name}.find({{{parts}}})"

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
