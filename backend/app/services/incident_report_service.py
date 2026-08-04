"""
FalconOps AI — Incident report export (PDF/Markdown).

Reuses reportlab (already a dependency, already used by reports_service.py's
generate_report_pdf() for scheduled operational reports) with the same visual
branding (title/heading colors), but as its own builder function rather than
forcing an incident's shape (timeline, evidence, RCA, actions, verification)
into that function's KPI-table-oriented layout, which doesn't fit an
incident narrative well. Markdown export is new — nothing in this codebase
had one before.
"""
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def _load_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    from .core.database import db
    investigation = await db.rased_investigations.find_one({"incident_id": incident_id}, {"_id": 0})
    if investigation is None:
        return None
    verification = investigation.get("verification")
    case = await db.rased_cases.find_one({"incident_id": incident_id}, {"_id": 0})
    trace = await db.rased_trace.find({"incident_id": incident_id}, {"_id": 0}).sort("seq", 1).to_list(500)
    return {**investigation, "case": case, "trace": trace}


def _hypothesis_lines(investigation: Dict[str, Any]) -> list:
    lines = []
    for h in investigation.get("hypotheses") or []:
        status = "SUPERSEDED" if h.get("superseded") else "CURRENT"
        lines.append(f"[{status}] (confidence {h.get('confidence')}) {h.get('statement')}")
    return lines


def _timeline_lines(investigation: Dict[str, Any]) -> list:
    lines = []
    for event in investigation.get("trace") or []:
        at = (event.get("at") or "")[11:19] if event.get("at") else "?"
        lines.append(f"{at}  {event.get('agent')}: {event.get('title')}")
    return lines


async def generate_markdown_report(incident_id: str) -> Optional[str]:
    investigation = await _load_incident(incident_id)
    if investigation is None:
        return None

    verification = investigation.get("verification") or {}
    lines = [
        f"# Incident Report — {incident_id}",
        "",
        f"**Status:** {investigation.get('status')}  ",
        f"**Confidence:** {investigation.get('confidence')}  ",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Alerts",
    ]
    for a in investigation.get("alerts") or []:
        lines.append(f"- **[{a.get('severity')}]** {a.get('service')}: {a.get('title')} — {a.get('description')}")

    lines += ["", "## Timeline"]
    lines += [f"- {line}" for line in _timeline_lines(investigation)] or ["- No trace recorded."]

    lines += ["", "## Root Cause Hypotheses"]
    lines += [f"- {line}" for line in _hypothesis_lines(investigation)] or ["- None generated."]

    lines += ["", "## Evidence"]
    for e in investigation.get("evidence") or []:
        lines.append(f"- ({e.get('tier')}, {e.get('source')}) {e.get('summary')}")

    lines += ["", "## Actions Taken"]
    for a in investigation.get("actions") or []:
        lines.append(f"- **{a.get('name')}** ({a.get('spec', {}).get('tier')}) — status: {a.get('status')}")
    if not investigation.get("actions"):
        lines.append("- No actions taken.")

    lines += ["", "## Verification"]
    if verification.get("available"):
        lines.append(f"Recovery confirmed: **{verification.get('recovered')}**")
        lines.append("")
        lines.append("| Metric | Service | Before | After | Improvement |")
        lines.append("|---|---|---|---|---|")
        for m in verification.get("metrics") or []:
            lines.append(f"| {m.get('metric')} | {m.get('service')} | {m.get('before')}{m.get('unit')} | "
                         f"{m.get('after')}{m.get('unit')} | {m.get('improved_pct')}% |")
    else:
        lines.append(f"Not available — {verification.get('reason', 'no verification ran for this incident')}")

    case = investigation.get("case") or {}
    if case.get("brief_en"):
        lines += ["", "## Executive Summary", "", case["brief_en"]]

    return "\n".join(lines)


async def generate_pdf_report(incident_id: str) -> Optional[bytes]:
    investigation = await _load_incident(incident_id)
    if investigation is None:
        return None

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=22, spaceAfter=20,
                                  textColor=colors.HexColor("#D4AF37"))
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=13, spaceBefore=16,
                                    spaceAfter=8, textColor=colors.HexColor("#00F0FF"))

    elements = [
        Paragraph("FALCONOPS AI — INCIDENT REPORT", title_style),
        Paragraph(f"Incident: {incident_id}", styles["Heading2"]),
        Paragraph(f"Status: {investigation.get('status')} · Confidence: {investigation.get('confidence')}", styles["Normal"]),
        Spacer(1, 16),
    ]

    verification = investigation.get("verification") or {}
    if verification.get("available"):
        elements.append(Paragraph("VERIFICATION", heading_style))
        rows = [["Metric", "Service", "Before", "After", "Improvement"]]
        for m in verification.get("metrics") or []:
            rows.append([m.get("metric"), m.get("service"), f"{m.get('before')}{m.get('unit')}",
                         f"{m.get('after')}{m.get('unit')}", f"{m.get('improved_pct')}%"])
        table = Table(rows, colWidths=[1.4 * inch] * 5)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#D4AF37")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#333333")),
        ]))
        elements += [Paragraph(f"Recovery confirmed: {verification.get('recovered')}", styles["Normal"]), Spacer(1, 8), table, Spacer(1, 16)]

    elements.append(Paragraph("ROOT CAUSE HYPOTHESES", heading_style))
    for line in _hypothesis_lines(investigation) or ["No hypotheses generated."]:
        elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("TIMELINE", heading_style))
    for line in _timeline_lines(investigation) or ["No trace recorded."]:
        elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 16))

    case = investigation.get("case") or {}
    if case.get("brief_en"):
        elements.append(Paragraph("EXECUTIVE SUMMARY", heading_style))
        elements.append(Paragraph(case["brief_en"], styles["Normal"]))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}", styles["Normal"]))
    elements.append(Paragraph("FalconOps AI — AI Incident Commander", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


__all__ = ["generate_markdown_report", "generate_pdf_report"]
