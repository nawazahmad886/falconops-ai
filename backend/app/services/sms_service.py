"""
FalconOps AI - SMS Notification Service (Twilio)

Mirrors email_service.py / notification_service.py's precedent exactly: a
missing credential returns a clear {"ok": False, "error": ...} dict rather
than raising, so a caller (e.g. Problems console "notify owner") can send
on whichever channels are actually configured and report the rest as
unavailable instead of the whole notification failing.
"""
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def send_sms(to_phone: str, message: str) -> Dict[str, Any]:
    """Send a plain-text SMS via Twilio. Returns {"ok": bool, ...} — never raises."""
    if not to_phone:
        return {"ok": False, "error": "no phone number provided"}

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    if not (account_sid and auth_token and from_number):
        logger.warning("Twilio not configured (TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER) - skipping SMS")
        return {"ok": False, "error": "Twilio not configured"}

    try:
        import asyncio
        from twilio.rest import Client

        def _send() -> str:
            client = Client(account_sid, auth_token)
            msg = client.messages.create(to=to_phone, from_=from_number, body=message[:1600])
            return msg.sid

        message_sid = await asyncio.to_thread(_send)
        return {"ok": True, "message_sid": message_sid}
    except Exception as e:
        logger.error(f"Failed to send SMS to {to_phone}: {e}")
        return {"ok": False, "error": str(e)[:300]}


__all__ = ["send_sms"]
