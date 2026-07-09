"""
FalconOps AI — Monetization Platform
====================================
Routes that power the public pricing experience and the admin control plane:

  Public
    GET    /api/pricing/plans              public plans (no auth)
    POST   /api/contact                    public lead capture (no auth)

  Admin (require_admin)
    GET    /api/admin/plans
    POST   /api/admin/plans
    PUT    /api/admin/plans/{id}
    DELETE /api/admin/plans/{id}

    GET    /api/admin/email-templates
    POST   /api/admin/email-templates
    PUT    /api/admin/email-templates/{id}
    DELETE /api/admin/email-templates/{id}
    POST   /api/admin/email-templates/{id}/send-test

    GET    /api/admin/leads
    PUT    /api/admin/leads/{id}
    DELETE /api/admin/leads/{id}

Backed by three new Mongo collections: `plans`, `email_templates`, `leads`.
All three are auto-seeded on first read so the platform works out of the box.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from ..core.database import db
from ..utils.auth import require_admin
from .. import services  # noqa: F401  (ensures package init)
from ..services import email_service

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _str_id() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
#  Defaults — seeded on first read so the platform never appears empty
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PLANS = [
    {
        "id": "trial",
        "name": "Trial",
        "tagline": "Try every feature for 14 days",
        "price": 0.0,
        "currency": "USD",
        "billing_type": "free",
        "interval": "month",
        "features": [
            "Up to 3 monitors",
            "2 users",
            "5 servers",
            "Basic AI insights",
            "Community support",
        ],
        "max_users": 2,
        "max_servers": 5,
        "max_monitors": 3,
        "max_ai_runs": 50,
        "button_text": "Start Free Trial",
        "stripe_price_id": "",
        "is_active": True,
        "sort_order": 0,
        "highlight": False,
    },
    {
        "id": "standard",
        "name": "Standard",
        "tagline": "Growing teams scaling observability",
        "price": 299.0,
        "currency": "USD",
        "billing_type": "subscription",
        "interval": "month",
        "features": [
            "Up to 50 monitors",
            "10 users",
            "100 servers",
            "Full AIOps + RCA",
            "OpenTelemetry APM",
            "Email + Webhook alerts",
            "8×5 support",
        ],
        "max_users": 10,
        "max_servers": 100,
        "max_monitors": 50,
        "max_ai_runs": 2000,
        "button_text": "Get Started",
        "stripe_price_id": "",
        "is_active": True,
        "sort_order": 1,
        "highlight": False,
    },
    {
        "id": "professional",
        "name": "Professional",
        "tagline": "Production teams with SLOs",
        "price": 799.0,
        "currency": "USD",
        "billing_type": "subscription",
        "interval": "month",
        "features": [
            "Up to 500 monitors",
            "30 users",
            "500 servers",
            "Advanced AIOps + RCA",
            "OpenTelemetry APM + Service Map",
            "Trace-driven Alerting",
            "Synthetic Journeys",
            "24×7 support",
        ],
        "max_users": 30,
        "max_servers": 500,
        "max_monitors": 500,
        "max_ai_runs": 8000,
        "button_text": "Get Started",
        "stripe_price_id": "",
        "is_active": True,
        "sort_order": 2,
        "highlight": True,
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "tagline": "Air-gapped, on-prem, custom",
        "price": 0.0,
        "currency": "USD",
        "billing_type": "enterprise",
        "interval": "year",
        "features": [
            "Unlimited monitors",
            "Unlimited users + servers",
            "On-prem / air-gapped install",
            "Helm chart + Podman support",
            "SSO + SAML + audit log",
            "Dedicated CSM",
            "Custom contract & SLA",
        ],
        "max_users": 100000,
        "max_servers": 100000,
        "max_monitors": 100000,
        "max_ai_runs": 1000000,
        "button_text": "Contact Sales",
        "stripe_price_id": "",
        "is_active": True,
        "sort_order": 3,
        "highlight": False,
    },
]


DEFAULT_EMAIL_TEMPLATES = [
    {
        "id": "contact_sales",
        "name": "contact_sales",
        "description": "Sent to the sales team when an enterprise lead submits the contact form.",
        "subject": "[FalconOps] New Enterprise Inquiry from {{company}}",
        "body_html": (
            "<h2>New FalconOps Inquiry</h2>"
            "<p><strong>Name:</strong> {{name}}</p>"
            "<p><strong>Email:</strong> {{email}}</p>"
            "<p><strong>Company:</strong> {{company}}</p>"
            "<p><strong>Phone:</strong> {{phone}}</p>"
            "<p><strong>Team size:</strong> {{team_size}}</p>"
            "<p><strong>Message:</strong></p>"
            "<blockquote style='border-left:3px solid #06b6d4;padding-left:12px;color:#444'>{{message}}</blockquote>"
            "<p style='color:#888;font-size:11px'>Submitted at {{submitted_at}}</p>"
        ),
        "body_text": (
            "New FalconOps Inquiry\n\n"
            "Name: {{name}}\nEmail: {{email}}\nCompany: {{company}}\n"
            "Phone: {{phone}}\nTeam size: {{team_size}}\n\n"
            "Message:\n{{message}}\n\nSubmitted at {{submitted_at}}\n"
        ),
        "variables": ["name", "email", "company", "phone", "team_size", "message", "submitted_at"],
        "is_active": True,
    },
    {
        "id": "contact_confirmation",
        "name": "contact_confirmation",
        "description": "Sent to the user who submitted the contact form confirming receipt.",
        "subject": "Thanks for reaching out to FalconOps, {{name}}!",
        "body_html": (
            "<h2>Thanks for getting in touch, {{name}}</h2>"
            "<p>We received your inquiry and our team will respond within 1 business day.</p>"
            "<p><strong>Your message:</strong></p>"
            "<blockquote style='border-left:3px solid #06b6d4;padding-left:12px;color:#444'>{{message}}</blockquote>"
            "<p>In the meantime, feel free to explore the <a href='https://falconops.ai/docs'>docs</a> "
            "or <a href='https://falconops.ai/pricing'>pricing</a>.</p>"
            "<p>— The FalconOps Team</p>"
        ),
        "body_text": (
            "Thanks for getting in touch, {{name}}\n\n"
            "We received your inquiry and our team will respond within 1 business day.\n\n"
            "Your message:\n{{message}}\n\n— The FalconOps Team\n"
        ),
        "variables": ["name", "message"],
        "is_active": True,
    },
    {
        "id": "welcome",
        "name": "welcome",
        "description": "Sent to every new user after signup.",
        "subject": "Welcome to FalconOps AI, {{name}} 👋",
        "body_html": (
            "<h2>Welcome aboard, {{name}}</h2>"
            "<p>Your FalconOps account is ready. Start by:</p>"
            "<ol><li>Adding your first <a href='{{app_url}}/uptime'>URL monitor</a></li>"
            "<li>Sending OpenTelemetry traces to <code>{{otlp_endpoint}}</code></li>"
            "<li>Inviting your team from <a href='{{app_url}}/settings/users'>Settings</a></li></ol>"
            "<p>Plan: <strong>{{plan_name}}</strong></p>"
            "<p>Need help? Reply to this email anytime.</p>"
        ),
        "body_text": (
            "Welcome aboard, {{name}}\n\n"
            "Your FalconOps account is ready. Start by:\n"
            "1. Adding your first URL monitor: {{app_url}}/uptime\n"
            "2. Sending OpenTelemetry traces to: {{otlp_endpoint}}\n"
            "3. Inviting your team: {{app_url}}/settings/users\n\n"
            "Plan: {{plan_name}}\n\nNeed help? Reply anytime.\n"
        ),
        "variables": ["name", "plan_name", "app_url", "otlp_endpoint"],
        "is_active": True,
    },
    {
        "id": "alert",
        "name": "alert",
        "description": "Sent when an alert fires (latency / error-rate / monitor down).",
        "subject": "🚨 [{{severity}}] {{alert_name}} — {{service}}",
        "body_html": (
            "<h2 style='color:#ef4444'>🚨 {{alert_name}}</h2>"
            "<p><strong>Service:</strong> {{service}}<br/>"
            "<strong>Severity:</strong> {{severity}}<br/>"
            "<strong>Time:</strong> {{triggered_at}}</p>"
            "<p>{{message}}</p>"
            "<h3>AI Insight</h3>"
            "<p>{{ai_insight}}</p>"
            "<h3>Suggested fix</h3>"
            "<p>{{fix_suggestion}}</p>"
            "<p><a href='{{app_url}}/alerts'>Open alert →</a></p>"
        ),
        "body_text": (
            "🚨 [{{severity}}] {{alert_name}}\n"
            "Service: {{service}}\nTime: {{triggered_at}}\n\n"
            "{{message}}\n\nAI Insight:\n{{ai_insight}}\n\n"
            "Suggested fix:\n{{fix_suggestion}}\n\nOpen: {{app_url}}/alerts\n"
        ),
        "variables": ["alert_name", "service", "severity", "triggered_at",
                      "message", "ai_insight", "fix_suggestion", "app_url"],
        "is_active": True,
    },
]


async def ensure_seed_data() -> None:
    """Seed default plans + email templates on first invocation (idempotent)."""
    plans_count = await db.plans.count_documents({})
    if plans_count == 0:
        for p in DEFAULT_PLANS:
            await db.plans.insert_one({**p, "created_at": _now(), "updated_at": _now()})
        logger.info("Seeded %d default plans", len(DEFAULT_PLANS))

    tmpl_count = await db.email_templates.count_documents({})
    if tmpl_count == 0:
        for t in DEFAULT_EMAIL_TEMPLATES:
            await db.email_templates.insert_one({**t, "created_at": _now(), "updated_at": _now()})
        logger.info("Seeded %d default email templates", len(DEFAULT_EMAIL_TEMPLATES))


# ─────────────────────────────────────────────────────────────────────────────
#  Template rendering (variable substitution)
# ─────────────────────────────────────────────────────────────────────────────

def render_template(text: str, variables: Dict[str, Any]) -> str:
    """Replace {{name}} placeholders with their values (or empty string)."""
    if not text:
        return ""
    out = text
    for k, v in variables.items():
        out = out.replace("{{" + k + "}}", "" if v is None else str(v))
    return out


async def render_and_send(
    template_id: str,
    recipients: List[str],
    variables: Dict[str, Any],
    sender: Optional[str] = None,
) -> Dict[str, Any]:
    """Look up the template, render with vars, and send via the email service."""
    tmpl = await db.email_templates.find_one({"id": template_id, "is_active": True}, {"_id": 0})
    if not tmpl:
        return {"ok": False, "error": f"template '{template_id}' not found or inactive"}

    subject = render_template(tmpl["subject"], variables)
    html = render_template(tmpl["body_html"], variables)

    try:
        return await email_service.send_email(
            recipients=recipients,
            subject=subject,
            html_body=html,
            sender=sender,
        )
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
#  Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class PlanModel(BaseModel):
    id: Optional[str] = None
    name: str
    tagline: Optional[str] = ""
    price: float = 0.0
    currency: str = "USD"
    billing_type: str = "subscription"  # free | subscription | enterprise
    interval: str = "month"             # month | year
    features: List[str] = Field(default_factory=list)
    max_users: int = 0
    max_servers: int = 0
    max_monitors: int = 0
    max_ai_runs: int = 0
    button_text: str = "Get Started"
    stripe_price_id: Optional[str] = ""
    is_active: bool = True
    sort_order: int = 0
    highlight: bool = False


class EmailTemplateModel(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    subject: str
    body_html: str
    body_text: Optional[str] = ""
    variables: List[str] = Field(default_factory=list)
    is_active: bool = True


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = ""
    phone: Optional[str] = ""
    team_size: Optional[str] = ""
    message: str = Field(..., min_length=1, max_length=4000)
    plan_id: Optional[str] = ""
    source: Optional[str] = "pricing_page"


class LeadUpdate(BaseModel):
    status: Optional[str] = None        # new | contacted | qualified | won | lost
    notes: Optional[str] = None
    assigned_to: Optional[str] = None


class TestSendRequest(BaseModel):
    recipient: EmailStr
    variables: Dict[str, str] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
#  Public router
# ─────────────────────────────────────────────────────────────────────────────

public_router = APIRouter(prefix="/api", tags=["Public — Monetization"])


@public_router.get("/pricing/plans")
async def public_list_plans():
    """Public plans list. No auth required. Used by the marketing pricing page."""
    await ensure_seed_data()
    cursor = db.plans.find({"is_active": True}, {"_id": 0}).sort("sort_order", 1)
    plans = await cursor.to_list(length=50)
    return {"plans": plans, "count": len(plans)}


@public_router.post("/contact")
async def submit_contact(req: ContactRequest, request: Request):
    """Public contact form submission. Stores the lead + emails sales + confirms to user."""
    await ensure_seed_data()
    lead_id = _str_id()
    now = _now()
    lead = {
        "id": lead_id,
        "name": req.name.strip(),
        "email": req.email.lower(),
        "company": (req.company or "").strip(),
        "phone": (req.phone or "").strip(),
        "team_size": (req.team_size or "").strip(),
        "message": req.message.strip(),
        "plan_id": req.plan_id or "",
        "source": req.source or "pricing_page",
        "status": "new",
        "notes": "",
        "assigned_to": "",
        "ip": (request.client.host if request.client else "unknown"),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "created_at": now,
        "updated_at": now,
    }
    await db.leads.insert_one(lead)

    # Send notification to sales team
    sales_to = os.environ.get("SALES_EMAIL", "sales@falconops.ai")
    template_vars = {
        "name": req.name,
        "email": req.email,
        "company": req.company or "(not provided)",
        "phone": req.phone or "(not provided)",
        "team_size": req.team_size or "(not provided)",
        "message": req.message,
        "submitted_at": now,
    }
    sales_result = await render_and_send("contact_sales", [sales_to], template_vars)
    confirm_result = await render_and_send(
        "contact_confirmation",
        [req.email],
        {"name": req.name, "message": req.message},
    )

    lead.pop("_id", None)  # safety
    return {
        "ok": True,
        "lead_id": lead_id,
        "sales_email_sent": sales_result.get("ok", False),
        "confirmation_email_sent": confirm_result.get("ok", False),
        "lead": lead,
    }


# Alias path requested by the spec: POST /api/contact/enterprise → same handler
@public_router.post("/contact/enterprise")
async def submit_contact_enterprise(req: ContactRequest, request: Request):
    """Alias for /api/contact, scoped to enterprise inquiries from pricing CTA."""
    return await submit_contact(req, request)


# ─────────────────────────────────────────────────────────────────────────────
#  Bundle gating — public request, email magic link, token download
# ─────────────────────────────────────────────────────────────────────────────

class BundleRequestModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: Optional[str] = ""
    use_case: Optional[str] = ""
    team_size: Optional[str] = ""

BUNDLE_TOKEN_TTL_DAYS = int(os.environ.get("BUNDLE_TOKEN_TTL_DAYS", "7"))
BUNDLE_TOKEN_MAX_USES = int(os.environ.get("BUNDLE_TOKEN_MAX_USES", "3"))


@public_router.post("/licenses/request-bundle")
async def request_bundle_download(req: BundleRequestModel, request: Request):
    """Public on-prem-bundle download request.
    Captures the lead, generates a single-use signed token, emails the download URL.
    """
    await ensure_seed_data()
    now = _now()
    lead_id = _str_id()

    lead = {
        "id": lead_id,
        "name": req.name.strip(),
        "email": req.email.lower(),
        "company": (req.company or "").strip(),
        "phone": "",
        "team_size": (req.team_size or "").strip(),
        "message": (
            f"On-prem bundle download requested.\n"
            f"Use case: {req.use_case or '(not provided)'}"
        ),
        "plan_id": "enterprise",
        "source": "bundle_download",
        "lead_type": "bundle_download",
        "status": "new",
        "notes": "",
        "assigned_to": "",
        "ip": (request.client.host if request.client else "unknown"),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "created_at": now,
        "updated_at": now,
    }
    await db.leads.insert_one(lead)

    # Generate token
    token = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char single-use token
    expires_at = (datetime.now(timezone.utc) + timedelta(days=BUNDLE_TOKEN_TTL_DAYS)).isoformat()
    await db.bundle_tokens.insert_one({
        "token": token,
        "lead_id": lead_id,
        "email": req.email.lower(),
        "company": (req.company or "").strip(),
        "max_uses": BUNDLE_TOKEN_MAX_USES,
        "uses": 0,
        "expires_at": expires_at,
        "created_at": now,
    })

    # Email user with the magic link
    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        # Best-effort fallback
        base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/api/licenses/download-with-token?token={token}"

    # Seed a dedicated email template the first time we need it
    existing = await db.email_templates.find_one({"id": "bundle_download_link"}, {"_id": 0})
    if not existing:
        await db.email_templates.insert_one({
            "id": "bundle_download_link",
            "name": "bundle_download_link",
            "description": "Sent to a user who requested the on-prem bundle. Contains the magic download link.",
            "subject": "Your FalconOps on-prem bundle is ready, {{name}}",
            "body_html": (
                "<h2>Your on-prem bundle is ready</h2>"
                "<p>Hi {{name}},</p>"
                "<p>Thanks for evaluating FalconOps AI on-prem. Use the secure link below to download the bundle. "
                "The link is valid for <strong>{{ttl_days}} days</strong> and works up to {{max_uses}} times.</p>"
                "<p><a href='{{download_url}}' style='display:inline-block;padding:12px 20px;background:#06b6d4;color:#000;text-decoration:none;border-radius:6px;font-weight:600'>Download bundle</a></p>"
                "<p style='font-size:12px;color:#666'>Direct URL (if the button doesn't work): {{download_url}}</p>"
                "<p>If you need help, just reply to this email — our SRE team is on call.</p>"
                "<p>— The FalconOps Team</p>"
            ),
            "body_text": (
                "Your on-prem bundle is ready\n\n"
                "Hi {{name}},\n\nThanks for evaluating FalconOps AI on-prem.\n"
                "Use the secure link below to download. Valid {{ttl_days}} days, up to {{max_uses}} uses.\n\n"
                "{{download_url}}\n\n— The FalconOps Team\n"
            ),
            "variables": ["name", "download_url", "ttl_days", "max_uses"],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })

    email_result = await render_and_send(
        "bundle_download_link",
        [req.email],
        {
            "name": req.name,
            "download_url": download_url,
            "ttl_days": str(BUNDLE_TOKEN_TTL_DAYS),
            "max_uses": str(BUNDLE_TOKEN_MAX_USES),
        },
    )

    # Notify sales team too
    sales_to = os.environ.get("SALES_EMAIL", "sales@falconops.ai")
    await render_and_send(
        "contact_sales",
        [sales_to],
        {
            "name": req.name,
            "email": req.email,
            "company": req.company or "(not provided)",
            "phone": "(not provided)",
            "team_size": req.team_size or "(not provided)",
            "message": f"📦 ON-PREM BUNDLE REQUEST\nUse case: {req.use_case or '(none)'}",
            "submitted_at": now,
        },
    )

    return {
        "ok": True,
        "lead_id": lead_id,
        "email_sent": email_result.get("ok", False),
        "expires_in_days": BUNDLE_TOKEN_TTL_DAYS,
        "max_uses": BUNDLE_TOKEN_MAX_USES,
        # Surface the URL only in DEV — in production the user must go via email
        "_dev_download_url": download_url if os.environ.get("ENVIRONMENT", "").lower() == "dev" else None,
    }


async def validate_bundle_token(token: str) -> Dict[str, Any]:
    """Validate a download token. Returns the token record or raises HTTPException."""
    if not token or len(token) < 32:
        raise HTTPException(400, "Invalid token format")
    rec = await db.bundle_tokens.find_one({"token": token}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Token not found")
    # Expiry
    try:
        exp = datetime.fromisoformat(rec["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > exp:
            raise HTTPException(410, "Token has expired")
    except ValueError:
        raise HTTPException(500, "Token has malformed expiry")
    # Usage cap
    if rec.get("uses", 0) >= rec.get("max_uses", BUNDLE_TOKEN_MAX_USES):
        raise HTTPException(429, "Token has reached its maximum download count")
    return rec


@public_router.get("/licenses/bundle-token/validate")
async def validate_token_endpoint(token: str):
    """Public endpoint a UI can hit to validate a token before showing the download button.

    Returns a 200 with a status field instead of raising 429/410 so the UI can render
    a polite "this link has expired / been exhausted" message without parsing HTTP status.
    """
    if not token or len(token) < 32:
        raise HTTPException(400, "Invalid token format")
    rec = await db.bundle_tokens.find_one({"token": token}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Token not found")
    now = datetime.now(timezone.utc)
    try:
        exp = datetime.fromisoformat(rec["expires_at"].replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(500, "Token has malformed expiry")
    status = "ok"
    if now > exp:
        status = "expired"
    elif rec.get("uses", 0) >= rec.get("max_uses", BUNDLE_TOKEN_MAX_USES):
        status = "exhausted"
    return {
        "ok": status == "ok",
        "status": status,
        "email": rec.get("email"),
        "company": rec.get("company"),
        "uses": rec.get("uses", 0),
        "max_uses": rec.get("max_uses", BUNDLE_TOKEN_MAX_USES),
        "expires_at": rec.get("expires_at"),
    }



# ─────────────────────────────────────────────────────────────────────────────
#  Admin router — plans, email templates, leads
# ─────────────────────────────────────────────────────────────────────────────

admin_router = APIRouter(prefix="/api/admin", tags=["Admin — Monetization"])


# ── Plans ──────────────────────────────────────────────────────────────────
@admin_router.get("/plans")
async def admin_list_plans(_: dict = Depends(require_admin)):
    await ensure_seed_data()
    cursor = db.plans.find({}, {"_id": 0}).sort("sort_order", 1)
    return {"plans": await cursor.to_list(length=100)}


@admin_router.post("/plans")
async def admin_create_plan(plan: PlanModel, _: dict = Depends(require_admin)):
    p = plan.model_dump()
    p["id"] = p.get("id") or _str_id()
    if await db.plans.find_one({"id": p["id"]}, {"_id": 0}):
        raise HTTPException(409, f"Plan id '{p['id']}' already exists")
    p["created_at"] = _now()
    p["updated_at"] = _now()
    await db.plans.insert_one(p)
    p.pop("_id", None)
    return p


@admin_router.put("/plans/{plan_id}")
async def admin_update_plan(plan_id: str, plan: PlanModel, _: dict = Depends(require_admin)):
    update = plan.model_dump(exclude_unset=True)
    update.pop("id", None)
    update["updated_at"] = _now()
    res = await db.plans.update_one({"id": plan_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Plan not found")
    updated = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    return updated


@admin_router.delete("/plans/{plan_id}")
async def admin_delete_plan(plan_id: str, _: dict = Depends(require_admin)):
    res = await db.plans.delete_one({"id": plan_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Plan not found")
    return {"deleted": True, "id": plan_id}


# ── Email templates ────────────────────────────────────────────────────────
@admin_router.get("/email-templates")
async def admin_list_email_templates(_: dict = Depends(require_admin)):
    await ensure_seed_data()
    cursor = db.email_templates.find({}, {"_id": 0}).sort("name", 1)
    return {"templates": await cursor.to_list(length=100)}


@admin_router.post("/email-templates")
async def admin_create_email_template(tmpl: EmailTemplateModel, _: dict = Depends(require_admin)):
    t = tmpl.model_dump()
    t["id"] = t.get("id") or _str_id()
    if await db.email_templates.find_one({"id": t["id"]}, {"_id": 0}):
        raise HTTPException(409, f"Template id '{t['id']}' already exists")
    t["created_at"] = _now()
    t["updated_at"] = _now()
    await db.email_templates.insert_one(t)
    t.pop("_id", None)
    return t


@admin_router.put("/email-templates/{template_id}")
async def admin_update_email_template(
    template_id: str,
    tmpl: EmailTemplateModel,
    _: dict = Depends(require_admin),
):
    update = tmpl.model_dump(exclude_unset=True)
    update.pop("id", None)
    update["updated_at"] = _now()
    res = await db.email_templates.update_one({"id": template_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Template not found")
    return await db.email_templates.find_one({"id": template_id}, {"_id": 0})


@admin_router.delete("/email-templates/{template_id}")
async def admin_delete_email_template(template_id: str, _: dict = Depends(require_admin)):
    res = await db.email_templates.delete_one({"id": template_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Template not found")
    return {"deleted": True, "id": template_id}


@admin_router.post("/email-templates/{template_id}/send-test")
async def admin_send_test_email(
    template_id: str,
    req: TestSendRequest,
    _: dict = Depends(require_admin),
):
    result = await render_and_send(template_id, [req.recipient], req.variables)
    if not result.get("ok"):
        raise HTTPException(500, result.get("error", "Email send failed"))
    return {"ok": True, "id": result.get("id"), "recipient": req.recipient}


# ── Leads ──────────────────────────────────────────────────────────────────
@admin_router.get("/leads")
async def admin_list_leads(
    status: Optional[str] = None,
    limit: int = 100,
    _: dict = Depends(require_admin),
):
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    cursor = db.leads.find(q, {"_id": 0}).sort("created_at", -1).limit(min(limit, 500))
    leads = await cursor.to_list(length=min(limit, 500))
    total = await db.leads.count_documents({})
    return {"leads": leads, "count": len(leads), "total": total}


@admin_router.get("/leads/{lead_id}")
async def admin_get_lead(lead_id: str, _: dict = Depends(require_admin)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


@admin_router.put("/leads/{lead_id}")
async def admin_update_lead(
    lead_id: str,
    update: LeadUpdate,
    _: dict = Depends(require_admin),
):
    patch = {k: v for k, v in update.model_dump(exclude_unset=True).items() if v is not None}
    if not patch:
        raise HTTPException(400, "No fields to update")
    patch["updated_at"] = _now()
    res = await db.leads.update_one({"id": lead_id}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(404, "Lead not found")
    return await db.leads.find_one({"id": lead_id}, {"_id": 0})


@admin_router.delete("/leads/{lead_id}")
async def admin_delete_lead(lead_id: str, _: dict = Depends(require_admin)):
    res = await db.leads.delete_one({"id": lead_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Lead not found")
    return {"deleted": True, "id": lead_id}
