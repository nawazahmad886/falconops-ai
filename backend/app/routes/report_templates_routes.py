"""
FalconOps AI - Report Template Builder Routes
Save named templates per-tenant. Each template is an ordered list of sections
(e.g. title, kpi_banner, exec_summary, sla_table, severity_chart, top_rules_chart,
 alert_table, custom_text).
When generating a weekly report with a template_id, PDF is rendered using only
the selected sections in the selected order.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..utils.auth import require_auth
from ..core.database import db

router = APIRouter(prefix="/api/report-templates", tags=["Report Templates"])


ALLOWED_SECTIONS = {
    "title", "header_logo", "kpi_banner", "exec_summary", "sla_table",
    "severity_chart", "sla_gauge_chart", "top_rules_chart", "alert_table",
    "custom_text", "page_break", "footer",
}


class Section(BaseModel):
    section_type: str                     # one of ALLOWED_SECTIONS
    title: Optional[str] = ""             # override title (for custom_text)
    content: Optional[str] = ""           # body text for custom_text
    config: Optional[dict] = Field(default_factory=dict)


class Template(BaseModel):
    name: str = "Default Weekly Template"
    description: Optional[str] = ""
    sections: List[Section] = Field(default_factory=list)


DEFAULT_SECTIONS = [
    {"section_type": "header_logo", "title": "", "content": "", "config": {}},
    {"section_type": "title", "title": "", "content": "", "config": {}},
    {"section_type": "kpi_banner", "title": "", "content": "", "config": {}},
    {"section_type": "exec_summary", "title": "", "content": "", "config": {}},
    {"section_type": "sla_table", "title": "", "content": "", "config": {}},
    {"section_type": "severity_chart", "title": "", "content": "", "config": {}},
    {"section_type": "sla_gauge_chart", "title": "", "content": "", "config": {}},
    {"section_type": "page_break", "title": "", "content": "", "config": {}},
    {"section_type": "top_rules_chart", "title": "", "content": "", "config": {}},
    {"section_type": "alert_table", "title": "", "content": "", "config": {}},
    {"section_type": "footer", "title": "", "content": "", "config": {}},
]


@router.get("/catalog")
async def list_section_types(current_user: dict = Depends(require_auth)):
    """Return the palette of section types for the builder UI."""
    return {
        "sections": [
            {"type": "header_logo", "label": "Header Logo", "category": "branding", "icon": "image"},
            {"type": "title", "label": "Report Title", "category": "header", "icon": "type"},
            {"type": "kpi_banner", "label": "KPI Banner (Risk · Uptime · MTTR · Threats)", "category": "metrics", "icon": "grid"},
            {"type": "exec_summary", "label": "AI Executive Summary", "category": "insight", "icon": "sparkles"},
            {"type": "sla_table", "label": "SLA & Operations Table", "category": "metrics", "icon": "table"},
            {"type": "severity_chart", "label": "Severity Bar Chart", "category": "chart", "icon": "bar-chart"},
            {"type": "sla_gauge_chart", "label": "SLA Donut Gauge", "category": "chart", "icon": "gauge"},
            {"type": "top_rules_chart", "label": "Top 10 Rules Chart", "category": "chart", "icon": "trending-up"},
            {"type": "alert_table", "label": "Alert Details Table (Top 20)", "category": "data", "icon": "alert-triangle"},
            {"type": "custom_text", "label": "Custom Text Block", "category": "content", "icon": "edit"},
            {"type": "page_break", "label": "Page Break", "category": "layout", "icon": "minus"},
            {"type": "footer", "label": "Footer", "category": "layout", "icon": "minus"},
        ],
        "default_sections": DEFAULT_SECTIONS,
    }


@router.get("/list")
async def list_templates(current_user: dict = Depends(require_auth)):
    tid = current_user.get("tenant_id")
    q = {"$or": [{"tenant_id": tid}, {"tenant_id": None}]} if tid else {}
    rows = await db.report_templates.find(q, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return rows


@router.post("/create")
async def create_template(payload: Template, current_user: dict = Depends(require_auth)):
    # Validate sections
    for s in payload.sections:
        if s.section_type not in ALLOWED_SECTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown section_type: {s.section_type}")

    template_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "template_id": template_id,
        "tenant_id": current_user.get("tenant_id"),
        "created_by": current_user.get("email", current_user.get("id")),
        "name": payload.name,
        "description": payload.description,
        "sections": [s.model_dump() for s in payload.sections],
        "created_at": now,
        "updated_at": now,
    }
    await db.report_templates.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/{template_id}")
async def get_template(template_id: str, current_user: dict = Depends(require_auth)):
    doc = await db.report_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    return doc


@router.put("/{template_id}")
async def update_template(template_id: str, payload: Template, current_user: dict = Depends(require_auth)):
    existing = await db.report_templates.find_one({"template_id": template_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    # Ownership check — tenant admins can update their tenant's templates
    if existing.get("tenant_id") and existing.get("tenant_id") != current_user.get("tenant_id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    for s in payload.sections:
        if s.section_type not in ALLOWED_SECTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown section_type: {s.section_type}")

    await db.report_templates.update_one(
        {"template_id": template_id},
        {"$set": {
            "name": payload.name,
            "description": payload.description,
            "sections": [s.model_dump() for s in payload.sections],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return await db.report_templates.find_one({"template_id": template_id}, {"_id": 0})


@router.delete("/{template_id}")
async def delete_template(template_id: str, current_user: dict = Depends(require_auth)):
    existing = await db.report_templates.find_one({"template_id": template_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    if existing.get("tenant_id") and existing.get("tenant_id") != current_user.get("tenant_id") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    await db.report_templates.delete_one({"template_id": template_id})
    return {"ok": True, "deleted": template_id}
