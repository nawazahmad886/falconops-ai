"""
CaseManagementAgent — the graph's terminal "case" node. Builds the bilingual
executive brief, persists a case record to db.rased_cases, and dispatches
through the configured Jira/Teams integrations. Runs regardless of how the
investigation ended (resolved, escalated, suppressed, rejected approval) —
an escalated or suppressed outcome still needs a case record and, for
escalated, a human-visible notification.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ....models.rased_schemas import InvestigationState
from ..brief.bilingual import build_bilingual_brief
from ..integrations.jira import JiraAdapter
from ..integrations.teams import TeamsAdapter

logger = logging.getLogger(__name__)


class CaseManagementAgent:
    def __init__(self, jira: Optional[JiraAdapter] = None, teams: Optional[TeamsAdapter] = None):
        self.jira = jira or JiraAdapter()
        self.teams = teams or TeamsAdapter()

    async def run(self, state: InvestigationState) -> dict:
        brief = build_bilingual_brief(state)

        case_record: Dict[str, Any] = {
            "incident_id": state.incident_id,
            "status": state.status,
            "root_signature": state.root_signature,
            "confidence": state.confidence,
            "brief_en": brief["en"],
            "brief_ar": brief["ar"],
            "updated_at": datetime.now(timezone.utc),
        }

        try:
            ticket = await self.jira.create_or_update_case(state, brief)
            case_record["jira_ticket"] = ticket
        except Exception as exc:
            logger.warning(f"rased jira dispatch failed for {state.incident_id}: {exc}")

        try:
            await self.teams.notify(state, brief)
        except Exception as exc:
            logger.warning(f"rased teams dispatch failed for {state.incident_id}: {exc}")

        await self._persist(case_record)
        return {}

    async def _persist(self, case_record: Dict[str, Any]) -> None:
        from ....core.database import db
        try:
            await db.rased_cases.update_one(
                {"incident_id": case_record["incident_id"]}, {"$set": case_record}, upsert=True,
            )
        except Exception as exc:
            logger.warning(f"rased case persist failed: {exc}")


__all__ = ["CaseManagementAgent"]
