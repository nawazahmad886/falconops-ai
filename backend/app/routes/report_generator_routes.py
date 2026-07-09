"""
FalconOps AI - Report Generator Routes
Upload DOCX/JSON, auto-fetch from SOC, AI summary, DOCX/Excel/PDF export
Includes enterprise-grade PDF with charts, branding, SLA metrics
"""
import os
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..utils.auth import require_auth
from ..services.report_generator_service import (
    parse_docx, parse_csv_data, parse_excel, parse_csv_bytes, fetch_from_soc,
    generate_ai_summary, generate_docx_report, generate_excel_report,
    generate_pdf_report, fetch_sla_metrics, fetch_tenant_branding,
    store_report, get_reports, get_report,
)

router = APIRouter(prefix="/api/weekly-reports", tags=["Weekly Report Generator"])


class JSONReportRequest(BaseModel):
    alerts: List[dict]
    period: Optional[str] = ""
    include_pdf: Optional[bool] = True
    executive: Optional[bool] = True
    template_id: Optional[str] = None


class AutoFetchRequest(BaseModel):
    days: int = 7
    period: Optional[str] = ""
    include_pdf: Optional[bool] = True
    executive: Optional[bool] = True
    template_id: Optional[str] = None


async def _build_full_report(parsed, period, current_user, include_pdf=True, executive=True, template_id: Optional[str] = None):
    """Shared helper: SLA + branding + AI summary + exports"""
    days_for_sla = 7
    if period and period.isdigit():
        try:
            days_for_sla = int(period)
        except ValueError:
            pass
    sla = await fetch_sla_metrics(days_for_sla)
    branding = await fetch_tenant_branding(current_user.get("tenant_id"))
    ai_summary = await generate_ai_summary(parsed, sla=sla, executive=executive)
    docx_bytes = generate_docx_report(parsed, ai_summary, period or "")
    excel_bytes = generate_excel_report(parsed, ai_summary)

    # Load template sections if template_id provided
    template_sections = None
    if template_id:
        from ..core.database import db
        tmpl = await db.report_templates.find_one({"template_id": template_id}, {"_id": 0})
        if tmpl:
            template_sections = tmpl.get("sections")

    pdf_bytes = None
    if include_pdf:
        try:
            pdf_bytes = generate_pdf_report(parsed, ai_summary, sla, branding, period or "", template_sections=template_sections)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"PDF generation failed: {e}")
    report = await store_report(parsed, ai_summary, docx_bytes, excel_bytes, period or "",
                                pdf_bytes=pdf_bytes, sla=sla, branding=branding)
    return report, sla, branding, ai_summary


@router.post("/upload")
async def upload_report(file: UploadFile = File(...), current_user: dict = Depends(require_auth)):
    """Upload DOCX/XLSX/CSV file and parse alerts (parse-only, no generation)"""
    content = await file.read()
    fname = (file.filename or "").lower()
    if fname.endswith(".xlsx") or fname.endswith(".xls"):
        parsed = parse_excel(content)
    elif fname.endswith(".csv"):
        parsed = parse_csv_bytes(content)
    elif fname.endswith(".docx"):
        parsed = parse_docx(content)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use .docx, .xlsx, or .csv")
    return parsed


@router.post("/generate/upload")
async def generate_from_upload(
    file: UploadFile = File(...),
    include_pdf: bool = Query(True),
    executive: bool = Query(True),
    template_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_auth),
):
    """Upload DOCX/XLSX/CSV → parse → AI summary → generate DOCX + Excel + PDF exports"""
    content = await file.read()
    fname = (file.filename or "").lower()
    if fname.endswith(".xlsx") or fname.endswith(".xls"):
        parsed = parse_excel(content)
    elif fname.endswith(".csv"):
        parsed = parse_csv_bytes(content)
    elif fname.endswith(".docx"):
        parsed = parse_docx(content)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use .docx, .xlsx, or .csv")

    if not parsed.get("alerts"):
        raise HTTPException(
            status_code=400,
            detail="No alerts found in the file. Ensure the file has a header row and at least a 'rule_name' column.",
        )

    report, sla, branding, ai_summary = await _build_full_report(parsed, "", current_user, include_pdf, executive, template_id)
    return {
        "report_id": report["report_id"],
        "total_alerts": report["total_alerts"],
        "critical_count": report["critical_count"],
        "warning_count": report["warning_count"],
        "ai_summary": ai_summary,
        "alerts": parsed["alerts"][:20],
        "sla_metrics": sla,
        "branding": {k: v for k, v in branding.items() if k != "logo_url"},
        "has_pdf": report.get("has_pdf", False),
    }


@router.post("/generate/json")
async def generate_from_json(req: JSONReportRequest, current_user: dict = Depends(require_auth)):
    """Generate report from JSON alert data"""
    parsed = parse_csv_data(req.alerts)
    report, sla, branding, ai_summary = await _build_full_report(parsed, req.period or "", current_user, req.include_pdf, req.executive, req.template_id)
    return {
        "report_id": report["report_id"],
        "total_alerts": report["total_alerts"],
        "critical_count": report["critical_count"],
        "warning_count": report["warning_count"],
        "ai_summary": ai_summary,
        "alerts": parsed["alerts"][:20],
        "sla_metrics": sla,
        "branding": {k: v for k, v in branding.items() if k != "logo_url"},
        "has_pdf": report.get("has_pdf", False),
    }


@router.post("/generate/auto")
async def generate_auto(req: AutoFetchRequest, current_user: dict = Depends(require_auth)):
    """Auto-fetch from SOC engine + SLA + branding + AI summary + DOCX/Excel/PDF export"""
    parsed = await fetch_from_soc(req.days)
    report, sla, branding, ai_summary = await _build_full_report(parsed, req.period or str(req.days), current_user, req.include_pdf, req.executive, req.template_id)
    return {
        "report_id": report["report_id"],
        "total_alerts": report["total_alerts"],
        "critical_count": report["critical_count"],
        "warning_count": report["warning_count"],
        "total_occurrences": report["total_occurrences"],
        "ai_summary": ai_summary,
        "alerts": parsed["alerts"][:20],
        "sla_metrics": sla,
        "branding": {k: v for k, v in branding.items() if k != "logo_url"},
        "has_pdf": report.get("has_pdf", False),
    }


@router.get("/list")
async def list_reports(limit: int = Query(10, le=50), current_user: dict = Depends(require_auth)):
    return await get_reports(limit)


@router.get("/{report_id}")
async def get_single_report(report_id: str, current_user: dict = Depends(require_auth)):
    report = await get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/download/docx")
async def download_docx(report_id: str, current_user: dict = Depends(require_auth)):
    from ..services.storage_service import get_report_download, report_file_exists
    report = await get_report(report_id)
    if not report or not report_file_exists(report.get("docx_path", "")):
        raise HTTPException(status_code=404, detail="Report file not found")
    resp = get_report_download(
        report["docx_path"], f"FalconOps_Report_{report_id}.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    if resp is None:
        raise HTTPException(status_code=500, detail="Download failed")
    return resp


@router.get("/{report_id}/download/excel")
async def download_excel(report_id: str, current_user: dict = Depends(require_auth)):
    from ..services.storage_service import get_report_download, report_file_exists
    report = await get_report(report_id)
    if not report or not report_file_exists(report.get("excel_path", "")):
        raise HTTPException(status_code=404, detail="Report file not found")
    resp = get_report_download(
        report["excel_path"], f"FalconOps_Report_{report_id}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if resp is None:
        raise HTTPException(status_code=500, detail="Download failed")
    return resp


@router.get("/{report_id}/download/pdf")
async def download_pdf(report_id: str, current_user: dict = Depends(require_auth)):
    """Enterprise PDF download"""
    from ..services.storage_service import get_report_download, report_file_exists
    report = await get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    pdf_path = report.get("pdf_path")
    if not pdf_path or not report_file_exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not generated for this report")
    resp = get_report_download(pdf_path, f"FalconOps_Report_{report_id}.pdf", "application/pdf")
    if resp is None:
        raise HTTPException(status_code=500, detail="Download failed")
    return resp
