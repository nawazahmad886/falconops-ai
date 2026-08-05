"""
Concurrent telemetry retrieval across all seven adapters, plus the
pre-tiered Evidence catalog a scenario shipped with.

RASED's synthetic scenarios ship two things per Phase 0: raw per-source
telemetry documents (what the seven adapters read) and a curated, tier-
tagged Evidence list (what Phase 2's RCA agent reasons over). This agent
fetches both — the adapters concurrently, for genuine timing/failure
behavior and trace visibility, and the Evidence catalog directly, since
deriving tiered, citable evidence from raw telemetry via an LLM at retrieval
time is exactly what Part A's constraints (every evidence item citable,
deterministic output) argue against for a demo-grade synthetic system.

scenario_id is recovered from Alert.alert_id's "{scenario_id}-alert-N"
convention (Phase 0's generator always builds ids that way) rather than
being a field on the locked Alert/InvestigationState contracts.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ....models.rased_schemas import Evidence, InvestigationState, ToolResult
from ..adapters import ADAPTERS
from ..config import EVIDENCE_COLLECTION

logger = logging.getLogger(__name__)

ADAPTER_TIMEOUT_SECONDS = 5.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TelemetryRetrievalAgent:
    async def run(self, state: InvestigationState) -> dict:
        scenario_id = self._infer_scenario_id(state)
        params: Dict = {"scenario_id": scenario_id} if scenario_id else {}
        # Additive: existing MongoSeededAdapter._build_filter already reads
        # params.get("service") if present (it just never received one before
        # this change) — synthetic adapters are unaffected when these are
        # absent; live adapters (e.g. OneAgentLiveAdapter) use them to scope
        # a real query instead of a scenario_id.
        if state.alerts:
            if state.alerts[0].service:
                params["service"] = state.alerts[0].service
            if state.alerts[0].host:
                params["host"] = state.alerts[0].host

        tool_results = await self._query_all_adapters(params)
        evidence = await self._load_evidence(scenario_id) if scenario_id else []

        failed = [r for r in tool_results if not r.success]
        confidence = state.confidence
        if failed:
            confidence = max(0.0, confidence - 0.1 * len(failed))

        return {
            "evidence": state.evidence + evidence,
            "confidence": confidence,
        }

    @staticmethod
    def _infer_scenario_id(state: InvestigationState) -> Optional[str]:
        for alert in state.alerts:
            if "-alert-" in alert.alert_id:
                return alert.alert_id.split("-alert-")[0]
        return None

    async def _query_all_adapters(self, params: Dict) -> List[ToolResult]:
        async def _bounded(adapter):
            try:
                return await asyncio.wait_for(adapter.query(params), timeout=ADAPTER_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                return ToolResult(
                    source=adapter.source,
                    query=str(params),
                    success=False,
                    data=None,
                    error="timeout",
                    latency_ms=int(ADAPTER_TIMEOUT_SECONDS * 1000),
                    retrieved_at=_now(),
                )

        adapters = list(ADAPTERS.values())
        results = await asyncio.gather(*(_bounded(a) for a in adapters), return_exceptions=True)

        out: List[ToolResult] = []
        for adapter, result in zip(adapters, results):
            if isinstance(result, Exception):
                # Adapter.query() already contracts to never raise; this branch
                # only matters if a future adapter breaks that contract, and it
                # still must not take the retrieval node down.
                out.append(ToolResult(
                    source=adapter.source, query=str(params), success=False,
                    data=None, error=str(result), latency_ms=0, retrieved_at=_now(),
                ))
            else:
                out.append(result)
        return out

    async def _load_evidence(self, scenario_id: str) -> List[Evidence]:
        from ....core.database import db
        try:
            docs = await db[EVIDENCE_COLLECTION].find(
                {"scenario_id": scenario_id}, {"_id": 0, "scenario_id": 0}
            ).to_list(length=100)
            return [Evidence(**doc) for doc in docs]
        except Exception as exc:
            logger.warning(f"failed to load evidence for scenario {scenario_id}: {exc}")
            return []


__all__ = ["TelemetryRetrievalAgent", "ADAPTER_TIMEOUT_SECONDS"]
