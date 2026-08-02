"""
RASED generation sinks.

generate_scenario() never talks to Mongo directly — it writes everything
through a Sink. MongoSink persists to the real database; InMemorySink
collects the same data in plain Python structures. Pytest drives generation
through InMemorySink so scenario generation is verifiable with no FalconOps
stack running; the API route drives it through MongoSink.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ....models.rased_schemas import Alert, Evidence


class Sink(ABC):
    @abstractmethod
    async def clear_scenario(self, scenario_id: str) -> None:
        """Remove any previously generated data for this scenario_id before
        writing a fresh run — regeneration must not append duplicates."""
        raise NotImplementedError

    @abstractmethod
    async def write_alerts(self, scenario_id: str, alerts: List[Alert]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def write_evidence(self, scenario_id: str, evidence: List[Evidence]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def write_source_records(self, scenario_id: str, source: str, records: List[Dict[str, Any]]) -> None:
        raise NotImplementedError


class InMemorySink(Sink):
    """Everything keyed by scenario_id so a single sink instance can be
    reused across scenarios in a test session without cross-contamination."""

    def __init__(self) -> None:
        self.alerts: Dict[str, List[Alert]] = {}
        self.evidence: Dict[str, List[Evidence]] = {}
        self.source_records: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    async def clear_scenario(self, scenario_id: str) -> None:
        self.alerts.pop(scenario_id, None)
        self.evidence.pop(scenario_id, None)
        self.source_records.pop(scenario_id, None)

    async def write_alerts(self, scenario_id: str, alerts: List[Alert]) -> None:
        self.alerts.setdefault(scenario_id, []).extend(alerts)

    async def write_evidence(self, scenario_id: str, evidence: List[Evidence]) -> None:
        self.evidence.setdefault(scenario_id, []).extend(evidence)

    async def write_source_records(self, scenario_id: str, source: str, records: List[Dict[str, Any]]) -> None:
        self.source_records.setdefault(scenario_id, {}).setdefault(source, []).extend(records)


class MongoSink(Sink):
    """Writes generated data into the real database. Imports app.core.database
    lazily so importing this module never requires a live Motor client or
    running event loop — only actually using a MongoSink does."""

    def __init__(self) -> None:
        from ....core.database import db
        from .. import config
        self._db = db
        self._config = config

    async def clear_scenario(self, scenario_id: str) -> None:
        await self._db[self._config.ALERTS_COLLECTION].delete_many({"scenario_id": scenario_id})
        await self._db[self._config.EVIDENCE_COLLECTION].delete_many({"scenario_id": scenario_id})
        for collection_name in self._config.SOURCE_COLLECTIONS.values():
            await self._db[collection_name].delete_many({"scenario_id": scenario_id})

    async def write_alerts(self, scenario_id: str, alerts: List[Alert]) -> None:
        if not alerts:
            return
        docs = [{**alert.model_dump(), "scenario_id": scenario_id} for alert in alerts]
        await self._db[self._config.ALERTS_COLLECTION].insert_many(docs)

    async def write_evidence(self, scenario_id: str, evidence: List[Evidence]) -> None:
        if not evidence:
            return
        docs = [{**item.model_dump(), "scenario_id": scenario_id} for item in evidence]
        await self._db[self._config.EVIDENCE_COLLECTION].insert_many(docs)

    async def write_source_records(self, scenario_id: str, source: str, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        collection_name = self._config.SOURCE_COLLECTIONS[source]
        docs = [{**record, "scenario_id": scenario_id} for record in records]
        await self._db[collection_name].insert_many(docs)


__all__ = ["Sink", "InMemorySink", "MongoSink"]
