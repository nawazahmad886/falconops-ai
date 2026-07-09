"""
FalconOps AI - Client Portal Routes
Tokenized public share links for weekly reports with password + expiry + access log.
"""
import os
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services.client_portal_service import (
    create_share_link, verify_and_load, record_access,
    list_shares_for_report, revoke_share, get_share_logs,
    request_otp,
)

logger = logging.getLogger(__name__)

# Admin/auth routes (manage shares)
admin_router = APIRouter(prefix="/api/share", tags=["Client Portal (Admin)"])

# Public routes (no auth — token-gated)
public_router = APIRouter(prefix="/api/portal", tags=["Client Portal (Public)"])


# ============ MODELS ============

class CreateShareRequest(BaseModel):
    report_id: str
    expiry_days: int = 7
    password: Optional[str] = None
    require_otp: bool = False


class AccessRequest(BaseModel):
    password: Optional[str] = None
    email: Optional[str] = None
    otp: Optional[str] = None


class OtpRequest(BaseModel):
    email: str


# ============ ADMIN ROUTES ============

@admin_router.post("/create")
async def create_share(payload: CreateShareRequest, current_user: dict = Depends(require_auth)):
    """Create a new tokenized share link for a report."""
    token = await create_share_link(
        report_id=payload.report_id,
        created_by=current_user.get("email", current_user.get("id", "unknown")),
        expiry_days=payload.expiry_days,
        password=payload.password,
        require_otp=payload.require_otp,
    )
    return {
        "token": token,
        "report_id": payload.report_id,
        "expiry_days": payload.expiry_days,
        "password_protected": bool(payload.password),
        "require_otp": bool(payload.require_otp),
    }


@admin_router.get("/report/{report_id}")
async def list_report_shares(report_id: str, current_user: dict = Depends(require_auth)):
    return await list_shares_for_report(report_id)


@admin_router.post("/{token}/revoke")
async def revoke(token: str, current_user: dict = Depends(require_auth)):
    ok = await revoke_share(token)
    if not ok:
        raise HTTPException(status_code=404, detail="Share not found")
    return {"ok": True, "token": token}


@admin_router.get("/{token}/logs")
async def share_logs(token: str, limit: int = Query(50, le=200), current_user: dict = Depends(require_auth)):
    return await get_share_logs(token, limit)


# ============ PUBLIC ROUTES (token-gated) ============

def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@public_router.get("/{token}/meta")
async def portal_meta(token: str, request: Request):
    """Return minimal public metadata (whether link is valid, and whether password/OTP is required)."""
    result = await verify_and_load(token, password=None)
    if not result["ok"] and result["reason"] in ("password_required", "otp_required"):
        share = result.get("share", {})
        return {
            "valid": True,
            "password_protected": bool(share.get("password_protected")),
            "require_otp": bool(share.get("require_otp")),
        }
    if not result["ok"]:
        return {"valid": False, "reason": result["reason"]}
    report = result["report"]
    share = result["share"]
    return {
        "valid": True,
        "password_protected": False,
        "require_otp": bool(share.get("require_otp")),
        "expires_at": share["expires_at"],
        "report": {
            "report_id": report["report_id"],
            "period": report.get("period"),
            "total_alerts": report.get("total_alerts"),
            "critical_count": report.get("critical_count"),
            "warning_count": report.get("warning_count"),
            "created_at": report.get("created_at"),
        },
    }


@public_router.post("/{token}/request-otp")
async def portal_request_otp(token: str, payload: OtpRequest, request: Request):
    """Generate a 6-digit OTP and email it to the recipient for this share."""
    result = await request_otp(token, payload.email)
    if not result.get("ok"):
        if result.get("reason") == "invalid":
            raise HTTPException(status_code=404, detail="Invalid link")
        if result.get("reason") == "otp_not_enabled":
            raise HTTPException(status_code=400, detail="OTP not enabled for this share")
        raise HTTPException(status_code=400, detail=result.get("reason", "unknown"))
    await record_access(token, _client_ip(request), request.headers.get("user-agent", ""), "otp_requested", email=payload.email)
    return {"ok": True, "expires_in_minutes": result["expires_in_minutes"]}


@public_router.post("/{token}/view")
async def portal_view(token: str, payload: AccessRequest, request: Request):
    """Verify password + (optional) email+OTP, then return full report data."""
    result = await verify_and_load(token, password=payload.password, email=payload.email, otp=payload.otp)
    if not result["ok"]:
        if result["reason"] == "password_required":
            raise HTTPException(status_code=401, detail="Password required")
        if result["reason"] == "wrong_password":
            raise HTTPException(status_code=401, detail="Invalid password")
        if result["reason"] == "otp_required":
            raise HTTPException(status_code=401, detail="OTP required")
        if result["reason"] == "otp_invalid":
            raise HTTPException(status_code=401, detail="Invalid or expired OTP")
        if result["reason"] == "expired":
            raise HTTPException(status_code=410, detail="Link expired")
        if result["reason"] == "revoked":
            raise HTTPException(status_code=410, detail="Link revoked")
        raise HTTPException(status_code=404, detail="Invalid link")

    await record_access(
        token, _client_ip(request), request.headers.get("user-agent", ""),
        "view", email=payload.email,
    )

    report = result["report"]
    share = result["share"]
    return {
        "valid": True,
        "expires_at": share["expires_at"],
        "access_count": share.get("access_count", 0) + 1,
        "report": {
            "report_id": report["report_id"],
            "period": report.get("period"),
            "source": report.get("source"),
            "total_alerts": report.get("total_alerts"),
            "critical_count": report.get("critical_count"),
            "warning_count": report.get("warning_count"),
            "total_occurrences": report.get("total_occurrences"),
            "ai_summary": report.get("ai_summary"),
            "alerts": report.get("alerts", [])[:20],
            "sla_metrics": report.get("sla_metrics", {}),
            "branding": report.get("branding", {}),
            "has_pdf": report.get("has_pdf", False),
            "created_at": report.get("created_at"),
        },
    }


@public_router.post("/{token}/download/{fmt}")
async def portal_download(token: str, fmt: str, payload: AccessRequest, request: Request):
    """Download a report file (pdf/docx/excel). Password + OTP gating applied."""
    if fmt not in ("pdf", "docx", "excel"):
        raise HTTPException(status_code=400, detail="Invalid format")
    result = await verify_and_load(token, password=payload.password, email=payload.email, otp=payload.otp)
    if not result["ok"]:
        if result["reason"] in ("password_required", "wrong_password", "otp_required", "otp_invalid"):
            raise HTTPException(status_code=401, detail=result["reason"])
        raise HTTPException(status_code=404, detail=result["reason"])

    report = result["report"]
    path_key = "pdf_path" if fmt == "pdf" else ("docx_path" if fmt == "docx" else "excel_path")
    path = report.get(path_key)

    from ..services.storage_service import get_report_download, report_file_exists
    if not path or not report_file_exists(path):
        raise HTTPException(status_code=404, detail=f"{fmt.upper()} not available")

    await record_access(token, _client_ip(request), request.headers.get("user-agent", ""), f"download_{fmt}")

    media = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[fmt]
    ext = "xlsx" if fmt == "excel" else fmt
    resp = get_report_download(path, f"FalconOps_Report_{report['report_id']}.{ext}", media)
    if resp is None:
        raise HTTPException(status_code=500, detail="Download failed")
    return resp
