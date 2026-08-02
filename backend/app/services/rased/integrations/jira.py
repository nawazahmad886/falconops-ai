"""
JiraAdapter — live and mock behind one interface. Mock is the default and is
what the demo runs on. Live requires config.EXECUTION_MODE == "live" (see
config.py's single env-var gate) AND a configured base URL/token; a
misconfigured or premature "live" attempt falls back to raising rather than
silently doing nothing or silently mocking — a case going missing because
Jira access was assumed-but-not-actually-granted is worse than a loud
failure the caller (case_mgmt.py) already catches and logs.
"""
import logging
import os
from typing import Any, Dict

from ..config import EXECUTION_MODE
from .base import IntegrationAdapter

logger = logging.getLogger(__name__)


class JiraAdapter(IntegrationAdapter):
    def __init__(self):
        self.base_url = os.environ.get("RASED_JIRA_BASE_URL")
        self.token = os.environ.get("RASED_JIRA_API_TOKEN")

    async def is_live(self) -> bool:
        return EXECUTION_MODE == "live" and bool(self.base_url) and bool(self.token)

    async def create_or_update_case(self, state, brief: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        if await self.is_live():
            return await self._create_live(state, brief)
        return await self._create_mock(state, brief)

    async def _create_mock(self, state, brief: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        key = f"RASED-{state.incident_id[:8].upper()}"
        return {
            "mode": "mock",
            "ticket_key": key,
            "url": f"https://mock-jira.internal/browse/{key}",
            "summary": brief["en"]["what_is_happening"],
        }

    async def _create_live(self, state, brief: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        raise NotImplementedError(
            "RASED_EXECUTION_MODE=live is set and Jira base URL/token are configured, but no live "
            "Jira client is implemented in this build — wire a real client here before relying on it."
        )


__all__ = ["JiraAdapter"]
