"""
VerificationAgent — the graph's "verify" node, between execute and case.

The core rule this exists to enforce: execute_action() succeeding only means
the action ran without raising — it says nothing about whether the thing that
was actually broken recovered. Before this agent, ActionAgent set
status="resolved" purely on that basis (see agents/action.py line ~94). Now
resolution additionally requires a genuine before/after check, via
data/recovery.py — see that module for why RASED's otherwise-static scenario
data needed a distinct mechanism to make this real rather than theater.

If verification can't run at all (action wasn't successful, no scenario_id
inferable, no recovery profile defined for this scenario), status is left
exactly as execute_node set it, tagged verification.available=False — this
agent never invents a "verified" outcome it didn't actually check, and never
downgrades a status it had no basis to touch.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from ....models.rased_schemas import InvestigationState, Verification
from ..data.recovery import compute_recovery

logger = logging.getLogger(__name__)


class VerificationAgent:
    async def run(self, state: InvestigationState) -> dict:
        if state.status != "resolved" or not state.action_results:
            return {}
        if not state.action_results[-1].success:
            return {}

        scenario_id = self._infer_scenario_id(state)
        if not scenario_id:
            return {}

        result = await compute_recovery(scenario_id, state)
        if result is None:
            unavailable = Verification(
                incident_id=state.incident_id, available=False,
                reason="no recovery profile for this scenario",
                verified_at=datetime.now(timezone.utc),
            )
            return {"verification": unavailable}

        await self._persist(result)
        await self._emit_trace(state.incident_id, result)

        if result.recovered:
            return {"status": "resolved", "verification": result}
        return {"status": "escalated", "verification": result}

    @staticmethod
    def _infer_scenario_id(state: InvestigationState) -> Optional[str]:
        for alert in state.alerts:
            if "-alert-" in alert.alert_id:
                return alert.alert_id.split("-alert-")[0]
        return None

    async def _persist(self, result: Verification) -> None:
        from ....core.database import db
        try:
            await db.rased_verifications.insert_one(result.model_dump())
        except Exception as exc:
            logger.warning(f"rased verification persist failed for {result.incident_id}: {exc}")

    async def _emit_trace(self, incident_id: str, result: Verification) -> None:
        from ..graph.trace import TraceRecorder
        summary = ", ".join(
            f"{m.metric}: {m.before}{m.unit} -> {m.after}{m.unit} ({m.improved_pct:+.1f}%)"
            for m in result.metrics
        )
        title = "Recovery verified" if result.recovered else "Recovery NOT confirmed — reopening"
        try:
            await TraceRecorder(incident_id).emit(
                "verification", "verification", title,
                detail={"recovered": result.recovered, "metrics": [m.model_dump() for m in result.metrics], "summary": summary},
            )
        except Exception as exc:
            logger.warning(f"rased verification trace emit failed for {incident_id}: {exc}")


__all__ = ["VerificationAgent"]
