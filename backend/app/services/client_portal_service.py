"""
FalconOps AI - Client Portal Service
Tokenized shareable links for weekly reports with optional password + expiry + access log.
"""
import os
import secrets
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from ..core.database import db

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5


def _hash_pw(password: str) -> str:
    salt = "falconops-portal-v1"
    return hashlib.sha256(f"{salt}::{password}".encode()).hexdigest()


def _hash_otp(code: str) -> str:
    return hashlib.sha256(f"otp::{code}".encode()).hexdigest()


async def create_share_link(
    report_id: str,
    created_by: str,
    expiry_days: int = 7,
    password: Optional[str] = None,
    require_otp: bool = False,
) -> str:
    """Create a tokenized public link for a report. Returns the opaque token."""
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=max(1, min(expiry_days, 365)))).isoformat()
    doc = {
        "token": token,
        "report_id": report_id,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
        "expiry_days": expiry_days,
        "password_hash": _hash_pw(password) if password else None,
        "password_protected": bool(password),
        "require_otp": bool(require_otp),
        "revoked": False,
        "access_count": 0,
    }
    await db.report_shares.insert_one(doc)
    return token


async def verify_and_load(
    token: str,
    password: Optional[str] = None,
    email: Optional[str] = None,
    otp: Optional[str] = None,
) -> Dict:
    """Return {ok, report/reason}. Handles password + optional email+OTP gating."""
    share = await db.report_shares.find_one({"token": token}, {"_id": 0})
    if not share:
        return {"ok": False, "reason": "invalid"}
    if share.get("revoked"):
        return {"ok": False, "reason": "revoked"}
    try:
        exp = datetime.fromisoformat(share["expires_at"].replace("Z", "+00:00"))
    except Exception:
        return {"ok": False, "reason": "invalid"}
    if datetime.now(timezone.utc) > exp:
        return {"ok": False, "reason": "expired"}

    # Password gate
    if share.get("password_protected"):
        if not password:
            return {"ok": False, "reason": "password_required", "share": {"password_protected": True, "require_otp": share.get("require_otp", False)}}
        if _hash_pw(password) != share.get("password_hash"):
            return {"ok": False, "reason": "wrong_password"}

    # OTP gate
    if share.get("require_otp"):
        if not email:
            return {"ok": False, "reason": "otp_required", "share": {"require_otp": True}}
        if not otp:
            return {"ok": False, "reason": "otp_required", "share": {"require_otp": True, "email_in_flight": True}}
        # Verify OTP
        ok = await verify_otp(token, email, otp)
        if not ok:
            return {"ok": False, "reason": "otp_invalid"}

    report = await db.weekly_reports.find_one({"report_id": share["report_id"]}, {"_id": 0})
    if not report:
        return {"ok": False, "reason": "report_missing"}
    return {"ok": True, "share": share, "report": report}


async def record_access(token: str, ip: str, user_agent: str, action: str, email: Optional[str] = None) -> None:
    """Log a portal access event & increment counter."""
    await db.report_shares.update_one(
        {"token": token},
        {"$inc": {"access_count": 1}, "$set": {"last_accessed_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.report_share_logs.insert_one({
        "token": token,
        "ip": ip,
        "user_agent": (user_agent or "")[:300],
        "action": action,
        "email": (email or "")[:200] if email else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def list_shares_for_report(report_id: str) -> List[Dict]:
    rows = await db.report_shares.find(
        {"report_id": report_id}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(50)
    return rows


async def revoke_share(token: str) -> bool:
    res = await db.report_shares.update_one({"token": token}, {"$set": {"revoked": True}})
    return res.modified_count > 0


async def get_share_logs(token: str, limit: int = 50) -> List[Dict]:
    return await db.report_share_logs.find(
        {"token": token}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)


# ============ OTP ============

async def request_otp(token: str, email: str) -> Dict:
    """Generate a 6-digit OTP for this (token, email) pair and email it via Resend.
    Invalidates any prior active OTP for this pair.
    """
    share = await db.report_shares.find_one({"token": token}, {"_id": 0})
    if not share:
        return {"ok": False, "reason": "invalid"}
    if share.get("revoked") or not share.get("require_otp"):
        return {"ok": False, "reason": "otp_not_enabled"}

    # Invalidate prior OTPs
    await db.portal_otp_codes.update_many(
        {"token": token, "email": email.lower(), "used": False},
        {"$set": {"used": True, "invalidated_at": datetime.now(timezone.utc).isoformat()}},
    )

    code = f"{secrets.randbelow(1_000_000):06d}"
    doc = {
        "token": token,
        "email": email.lower(),
        "code_hash": _hash_otp(code),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat(),
        "attempts": 0,
        "used": False,
    }
    await db.portal_otp_codes.insert_one(doc)

    # Send email (best-effort)
    try:
        from .email_service import send_report_email
        html = f"""
        <html><body style="font-family:Helvetica,Arial,sans-serif;background:#F3F4F6;padding:24px;">
          <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;">
            <div style="background:#0B0E14;padding:20px;color:#fff;">
              <div style="font-size:18px;font-weight:700;">
                <span style="color:#F5B841;">FALCON</span><span>OPS</span>
                <span style="color:#00E0FF;font-size:11px;margin-left:4px;">AI</span>
              </div>
            </div>
            <div style="padding:24px;color:#111;">
              <h2 style="margin:0 0 8px;">Access Code</h2>
              <p style="color:#4B5563;margin:0 0 20px;font-size:14px;">
                Use this code to access the shared SOC report. It expires in {OTP_TTL_MINUTES} minutes.
              </p>
              <div style="text-align:center;font-size:40px;font-weight:700;letter-spacing:12px;
                          background:#F3F4F6;padding:20px;border-radius:8px;color:#0B0E14;">
                {code}
              </div>
              <p style="color:#9CA3AF;font-size:11px;margin-top:20px;text-align:center;">
                If you did not request this code, ignore this email. Never share this code.
              </p>
            </div>
          </div>
        </body></html>
        """
        await send_report_email(
            recipients=[email],
            subject="FalconOps AI — Your report access code",
            html_body=html,
        )
    except Exception as e:
        logger.error(f"OTP email send failed: {e}")

    return {"ok": True, "expires_in_minutes": OTP_TTL_MINUTES}


async def verify_otp(token: str, email: str, code: str) -> bool:
    """Check OTP validity. Marks code as used on success. Increments attempts on failure."""
    doc = await db.portal_otp_codes.find_one(
        {"token": token, "email": email.lower(), "used": False},
        sort=[("created_at", -1)],
    )
    if not doc:
        return False
    # Expired?
    try:
        exp = datetime.fromisoformat(doc["expires_at"].replace("Z", "+00:00"))
    except Exception:
        return False
    if datetime.now(timezone.utc) > exp:
        return False
    if doc.get("attempts", 0) >= OTP_MAX_ATTEMPTS:
        return False

    if _hash_otp(code) != doc["code_hash"]:
        await db.portal_otp_codes.update_one(
            {"_id": doc["_id"]} if "_id" in doc else {"token": token, "email": email.lower(), "code_hash": doc["code_hash"]},
            {"$inc": {"attempts": 1}},
        )
        return False

    # Success — mark used
    await db.portal_otp_codes.update_one(
        {"token": token, "email": email.lower(), "code_hash": doc["code_hash"]},
        {"$set": {"used": True, "verified_at": datetime.now(timezone.utc).isoformat()}},
    )
    return True
