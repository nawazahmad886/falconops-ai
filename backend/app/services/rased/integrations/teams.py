"""
TeamsAdapter — live and mock behind one interface. Mock is the default and
is what the demo runs on; see jira.py's module docstring for why live falls
back to a loud NotImplementedError rather than a silent no-op.
"""
import logging
import os
from typing import Any, Dict

from ..config import EXECUTION_MODE
from .base import IntegrationAdapter

logger = logging.getLogger(__name__)


class TeamsAdapter(IntegrationAdapter):
    def __init__(self):
        self.webhook_url = os.environ.get("RASED_TEAMS_WEBHOOK_URL")

    async def is_live(self) -> bool:
        return EXECUTION_MODE == "live" and bool(self.webhook_url)

    async def notify(self, state, brief: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        if await self.is_live():
            return await self._notify_live(state, brief)
        return await self._notify_mock(state, brief)

    async def _notify_mock(self, state, brief: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        logger.info(f"[MOCK TEAMS] incident {state.incident_id}: {brief['en']['what_is_happening']}")
        return {"mode": "mock", "delivered": True}

    async def _notify_live(self, state, brief: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        raise NotImplementedError(
            "RASED_EXECUTION_MODE=live is set and a Teams webhook URL is configured, but no live "
            "Teams client is implemented in this build — wire a real client here before relying on it."
        )


__all__ = ["TeamsAdapter"]
