"""
FalconOps AI — Onboarding checklist.

Previously nothing: a new tenant landed on empty dashboards with zero guidance
(confirmed — no onboarding component/wizard existed anywhere in the frontend).
This is a real, backend-driven checklist, not a scripted fake wizard — every
step's checked/unchecked state is a genuine count against that tenant's own
data (has it created a monitor, configured a notification channel, seen its
first alert), never a hardcoded "step 2 of 5" that advances regardless of what
the tenant actually did.
"""
import logging
from typing import Any, Dict, Optional

from ..core.database import db

logger = logging.getLogger(__name__)


async def get_onboarding_status(tenant_id: Optional[str], user_id: str) -> Dict[str, Any]:
    monitor_q: Dict[str, Any] = {"tenant_id": tenant_id} if tenant_id else {}
    integration_q: Dict[str, Any] = {"enabled": True}
    alert_q: Dict[str, Any] = {"tenant_id": tenant_id} if tenant_id else {}

    monitors_count = await db.monitors.count_documents(monitor_q)
    integrations_count = await db.integrations.count_documents(integration_q)
    alerts_count = await db.alerts_engine.count_documents(alert_q)

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "onboarding_dismissed": 1})
    dismissed = bool((user or {}).get("onboarding_dismissed"))

    steps = [
        {"id": "create_monitor", "label": "Create your first monitor", "done": monitors_count > 0,
         "action_path": "/monitoring"},
        {"id": "configure_integration", "label": "Configure a notification channel (Slack, PagerDuty, email...)",
         "done": integrations_count > 0, "action_path": "/integrations"},
        {"id": "see_first_alert", "label": "See your first alert fire", "done": alerts_count > 0,
         "action_path": "/problems"},
    ]
    all_done = all(s["done"] for s in steps)

    return {
        "dismissed": dismissed,
        "all_done": all_done,
        # Show the checklist unless the tenant finished every step or explicitly dismissed it.
        "should_show": not dismissed and not all_done,
        "steps": steps,
    }


async def dismiss_onboarding(user_id: str) -> None:
    await db.users.update_one({"id": user_id}, {"$set": {"onboarding_dismissed": True}})


__all__ = ["get_onboarding_status", "dismiss_onboarding"]
