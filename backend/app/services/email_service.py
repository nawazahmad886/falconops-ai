"""
FalconOps AI - Email Service (Resend)
Sends scheduled weekly report emails with PDF/DOCX/Excel attachments.
"""
import os
import base64
import asyncio
import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone

import resend
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Resend API key at import time
_API_KEY = os.environ.get("RESEND_API_KEY")
if _API_KEY:
    resend.api_key = _API_KEY
_DEFAULT_SENDER = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")


def _report_email_html(company: str, period: str, stats: Dict, ai_summary: str, portal_url: Optional[str] = None) -> str:
    """Render a polished HTML email body (inline CSS, tables for layout)."""
    risk = stats.get("risk_posture", "Low")
    risk_color = "#DC2626" if risk == "High" else "#F59E0B" if risk == "Medium" else "#10B981"
    summary_short = (ai_summary or "")[:900].replace("\n", "<br/>")
    portal_btn = ""
    if portal_url:
        portal_btn = f"""
        <tr><td align="center" style="padding:20px 0 6px;">
            <a href="{portal_url}" style="background:#00E0FF;color:#0B0E14;text-decoration:none;padding:12px 28px;border-radius:6px;font-weight:600;font-family:Helvetica,Arial,sans-serif;display:inline-block;">
                View Full Report
            </a>
        </td></tr>"""

    return f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F3F4F6;padding:24px 0;">
  <tr><td align="center">
    <table width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,0.08);">
      <tr><td style="background:#0B0E14;padding:24px 30px;color:#fff;">
        <div style="font-size:22px;font-weight:700;letter-spacing:0.5px;">
          <span style="color:#F5B841;">FALCON</span><span style="color:#fff;">OPS</span>
          <span style="color:#00E0FF;font-size:12px;margin-left:6px;">AI</span>
        </div>
        <div style="color:rgba(255,255,255,0.6);margin-top:4px;font-size:13px;">Weekly SOC &amp; AIOps Report</div>
      </td></tr>
      <tr><td style="padding:24px 30px;">
        <h2 style="margin:0 0 4px;color:#0B0E14;font-size:20px;">{company}</h2>
        <div style="color:#6B7280;font-size:13px;margin-bottom:20px;">Reporting Period: <b>{period}</b></div>

        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:22px;border-collapse:collapse;">
          <tr>
            <td style="padding:14px;background:#F9FAFB;border:1px solid #E5E7EB;text-align:center;border-radius:6px 0 0 6px;">
              <div style="font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;">Risk</div>
              <div style="font-size:20px;font-weight:700;color:{risk_color};margin-top:4px;">{risk}</div>
            </td>
            <td style="padding:14px;background:#F9FAFB;border:1px solid #E5E7EB;text-align:center;">
              <div style="font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;">Uptime</div>
              <div style="font-size:20px;font-weight:700;color:#0B0E14;margin-top:4px;">{stats.get("uptime_pct",0):.2f}%</div>
            </td>
            <td style="padding:14px;background:#F9FAFB;border:1px solid #E5E7EB;text-align:center;">
              <div style="font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;">MTTR</div>
              <div style="font-size:20px;font-weight:700;color:#0B0E14;margin-top:4px;">{stats.get("mttr_minutes",0)} min</div>
            </td>
            <td style="padding:14px;background:#F9FAFB;border:1px solid #E5E7EB;text-align:center;border-radius:0 6px 6px 0;">
              <div style="font-size:10px;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;">Critical Threats</div>
              <div style="font-size:20px;font-weight:700;color:#DC2626;margin-top:4px;">{stats.get("threats_critical",0)}</div>
            </td>
          </tr>
        </table>

        <h3 style="color:#00E0FF;font-size:14px;margin:0 0 8px;">Executive Summary</h3>
        <div style="color:#374151;font-size:13px;line-height:1.6;">{summary_short}</div>

        {portal_btn}

        <div style="margin-top:24px;padding-top:16px;border-top:1px solid #E5E7EB;color:#9CA3AF;font-size:11px;">
          Attachments include the full DOCX, Excel, and enterprise PDF. This is an automated report from FalconOps AI.
        </div>
      </td></tr>
      <tr><td style="background:#0B0E14;color:rgba(255,255,255,0.4);padding:12px 30px;font-size:10px;text-align:center;">
        Confidential &middot; Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>
"""


async def send_report_email(
    recipients: List[str],
    subject: str,
    html_body: str,
    attachments: Optional[List[Dict]] = None,
    sender: Optional[str] = None,
) -> Dict:
    """
    Send a Resend email with optional attachments.
    attachments: [{"filename": "report.pdf", "content": bytes or base64 str}]
    """
    if not resend.api_key:
        raise RuntimeError("RESEND_API_KEY not configured")

    params = {
        "from": sender or _DEFAULT_SENDER,
        "to": recipients,
        "subject": subject,
        "html": html_body,
    }
    if attachments:
        encoded = []
        for a in attachments:
            content = a.get("content")
            if isinstance(content, bytes):
                content_b64 = base64.b64encode(content).decode("ascii")
            elif isinstance(content, str):
                content_b64 = content
            else:
                continue
            encoded.append({"filename": a.get("filename", "attachment"), "content": content_b64})
        if encoded:
            params["attachments"] = encoded

    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        email_id = result.get("id") if isinstance(result, dict) else None
        logger.info(f"Resend email sent to {recipients} (id={email_id})")
        return {"ok": True, "id": email_id, "recipients": recipients}
    except Exception as e:
        logger.error(f"Resend send failed: {e}")
        return {"ok": False, "error": str(e), "recipients": recipients}


def get_sender_email() -> str:
    return _DEFAULT_SENDER


def set_sender_email(new_sender: str) -> None:
    global _DEFAULT_SENDER
    _DEFAULT_SENDER = new_sender


# ─────────────────────────────────────────────────────────────────────────────
# Generic email send (used by monetization routes — contact form, bundle link,
# alert emails). Mirrors send_report_email but without the report-specific
# default subject/body branding.
# ─────────────────────────────────────────────────────────────────────────────
async def send_email(
    recipients: List[str],
    subject: str,
    html_body: str,
    attachments: Optional[List[Dict]] = None,
    sender: Optional[str] = None,
) -> Dict:
    """Generic transactional email — alias to send_report_email.
    Returns {ok, id, recipients} on success or {ok: False, error, recipients} on failure.
    Never raises — returns a structured error dict instead so callers can decide what to do.
    """
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not configured — email not sent (recipients=%s)", recipients)
        return {"ok": False, "error": "RESEND_API_KEY not configured", "recipients": recipients}
    return await send_report_email(
        recipients=recipients,
        subject=subject,
        html_body=html_body,
        attachments=attachments,
        sender=sender,
    )
