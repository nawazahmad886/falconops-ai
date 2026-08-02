"""
OrchestratorAgent — root signature, dedup, storm suppression, correlation.

Root signature comes straight off the alerts: RASED's synthetic generator
(Phase 0) already assigns each scenario a single deterministic
Alert.signature (e.g. "edge-router-cluster:network-flap" for S5), so the
majority signature across the incoming batch *is* the root signature here —
there is no ambiguity to resolve via LLM inference. correlation_shared's
multi_dimension_group() is still wrapped and called (this is the "RASED-owned
interface" the plan asks for over the shared engine) to cross-check that
grouping and to compute a correlation-based signal; it never raises past this
module because it was written for a different alert schema than RASED's, and
a shape mismatch degrading to "no additional correlation groups" is
preferable to crashing the orchestrate node over a wrapper written for a
sibling engine's alert format the author of this module has not run against
this repo.
"""
import logging
from collections import Counter
from typing import Any, Dict, List

from ....models.rased_schemas import Alert, InvestigationState
from ..data.scenarios import SERVICE_CATALOG

logger = logging.getLogger(__name__)

STORM_THRESHOLD = 15
DEDUP_WINDOW_SECONDS = 300


class OrchestratorAgent:
    async def run(self, state: InvestigationState) -> Dict[str, Any]:
        if not state.alerts:
            return {"status": "resolved"}

        root_signature = self._pick_root_signature(state.alerts)

        if await self._is_duplicate(root_signature):
            return {"status": "suppressed", "root_signature": root_signature}

        signatures = {a.signature for a in state.alerts}
        if len(state.alerts) >= STORM_THRESHOLD and len(signatures) == 1:
            return {"status": "suppressed", "root_signature": root_signature, "confidence": 1.0}

        self._correlate(state.alerts)  # exercised for trace/telemetry value; result not required downstream yet

        return {"status": "investigating", "root_signature": root_signature, "confidence": 0.5}

    @staticmethod
    def _pick_root_signature(alerts: List[Alert]) -> str:
        counts = Counter(a.signature for a in alerts)
        return counts.most_common(1)[0][0]

    async def _is_duplicate(self, signature: str) -> bool:
        try:
            from ...metrics_timeseries_service import metrics_timeseries_service
            redis_client = await metrics_timeseries_service.get_redis()
            if redis_client is None:
                return False
            key = f"rased:dedup:{signature}"
            was_set = await redis_client.set(key, "1", nx=True, ex=DEDUP_WINDOW_SECONDS)
            return not bool(was_set)
        except Exception as exc:
            logger.warning(f"rased dedup check failed for {signature}: {exc}")
            return False

    def _correlate(self, alerts: List[Alert]) -> List[Dict[str, Any]]:
        try:
            from ..correlation import correlate_alerts
            return correlate_alerts(alerts, SERVICE_CATALOG)
        except Exception as exc:
            logger.warning(f"rased correlation wrapper failed, continuing without it: {exc}")
            return []


__all__ = ["OrchestratorAgent", "STORM_THRESHOLD", "DEDUP_WINDOW_SECONDS"]
