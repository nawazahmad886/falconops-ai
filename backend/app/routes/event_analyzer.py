"""
FalconOps AI - Event Analyzer Routes
AI-powered analysis of uploaded event/alert files
"""
import os
import io
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..core.database import db
from ..utils.auth import require_auth
from ..services.event_analyzer_service import EventAnalyzer
from ..services.event_report_service import generate_excel_report, generate_pdf_report

router = APIRouter(prefix="/api/events", tags=["Event Analyzer"])


# ======================== SCHEMAS ========================

class AnalysisResponse(BaseModel):
    """Analysis response"""
    success: bool
    analysis_id: Optional[str] = None
    message: Optional[str] = None


# ======================== FILE UPLOAD ENDPOINTS ========================

@router.post("/upload")
async def upload_events_file(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth)
):
    """
    Upload an Excel or CSV file containing events/alerts for analysis.
    
    Supported formats: .xlsx, .xls, .csv
    
    Expected columns (flexible naming):
    - timestamp: Event timestamp
    - service: Service/application name
    - alert: Alert name or description
    - severity: Alert severity (critical, warning, info)
    - host: Hostname or server name (optional)
    """
    # Validate file type
    filename = file.filename.lower()
    if not any(filename.endswith(ext) for ext in ['.xlsx', '.xls', '.csv']):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Supported formats: .xlsx, .xls, .csv"
        )
    
    # Check file size (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10MB"
        )
    
    # Parse file
    analyzer = EventAnalyzer()
    result = analyzer.parse_file(content, file.filename)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to parse file"))
    
    # Store upload record
    upload_id = str(uuid.uuid4())
    upload_record = {
        "id": upload_id,
        "filename": file.filename,
        "user_id": user.get("id"),
        "user_email": user.get("email"),
        "total_events": result.get("total_events"),
        "columns_detected": result.get("columns_detected"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "status": "parsed"
    }
    
    await db.event_uploads.insert_one(upload_record)
    
    # Store parsed events temporarily for analysis
    events_record = {
        "upload_id": upload_id,
        "events": analyzer.events,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.event_data.insert_one(events_record)
    
    return {
        "success": True,
        "upload_id": upload_id,
        "filename": file.filename,
        "total_events": result.get("total_events"),
        "columns_detected": result.get("columns_detected"),
        "sample_events": result.get("sample_events"),
        "message": f"Successfully parsed {result.get('total_events')} events"
    }


@router.post("/analyze/{upload_id}")
async def analyze_events(
    upload_id: str,
    user: dict = Depends(require_auth)
):
    """
    Perform AI-powered analysis on uploaded events.
    
    Returns:
    - Pattern detection results
    - Event clustering
    - AI root cause analysis
    - Recommended actions
    - Executive summary
    """
    # Get upload record
    upload = await db.event_uploads.find_one({"id": upload_id}, {"_id": 0})
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    # Get events data
    events_data = await db.event_data.find_one({"upload_id": upload_id}, {"_id": 0})
    if not events_data:
        raise HTTPException(status_code=404, detail="Events data not found")
    
    # Create analyzer and load events
    analyzer = EventAnalyzer()
    analyzer.events = events_data.get("events", [])
    
    if not analyzer.events:
        raise HTTPException(status_code=400, detail="No events to analyze")
    
    # Perform AI analysis
    analysis_result = await analyzer.ai_analyze()
    
    # Store analysis result
    analysis_record = {
        "id": analysis_result.get("analysis_id"),
        "upload_id": upload_id,
        "user_id": user.get("id"),
        "result": analysis_result,
        "analyzed_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.event_analyses.insert_one(analysis_record)
    
    # Update upload status
    await db.event_uploads.update_one(
        {"id": upload_id},
        {"$set": {"status": "analyzed", "analysis_id": analysis_result.get("analysis_id")}}
    )
    
    return analysis_result


@router.get("/analysis/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    user: dict = Depends(require_auth)
):
    """Get a specific analysis result"""
    analysis = await db.event_analyses.find_one({"id": analysis_id}, {"_id": 0})
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return analysis.get("result", {})


@router.get("/uploads")
async def list_uploads(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_auth)
):
    """List all uploaded event files"""
    # Admin sees all, others see only their uploads
    query = {} if user.get("role") == "admin" else {"user_id": user.get("id")}
    
    uploads = await db.event_uploads.find(
        query,
        {"_id": 0}
    ).sort("uploaded_at", -1).skip(skip).limit(limit).to_list(length=limit)
    
    total = await db.event_uploads.count_documents(query)
    
    return {
        "uploads": uploads,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/analyses")
async def list_analyses(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_auth)
):
    """List all analyses"""
    query = {} if user.get("role") == "admin" else {"user_id": user.get("id")}
    
    analyses = await db.event_analyses.find(
        query,
        {"_id": 0, "result.events_sample": 0}  # Exclude large data
    ).sort("analyzed_at", -1).skip(skip).limit(limit).to_list(length=limit)
    
    total = await db.event_analyses.count_documents(query)
    
    return {
        "analyses": analyses,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.delete("/upload/{upload_id}")
async def delete_upload(
    upload_id: str,
    user: dict = Depends(require_auth)
):
    """Delete an uploaded file and its analysis"""
    # Check ownership
    upload = await db.event_uploads.find_one({"id": upload_id}, {"_id": 0})
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    if user.get("role") != "admin" and upload.get("user_id") != user.get("id"):
        raise HTTPException(status_code=403, detail="Not authorized to delete this upload")
    
    # Delete related data
    await db.event_data.delete_many({"upload_id": upload_id})
    await db.event_analyses.delete_many({"upload_id": upload_id})
    await db.event_uploads.delete_one({"id": upload_id})
    
    return {"success": True, "message": "Upload and analysis deleted"}


@router.get("/report/{analysis_id}")
async def get_report_data(
    analysis_id: str,
    user: dict = Depends(require_auth)
):
    """
    Get analysis data formatted for report generation.
    Can be used with the existing reports module.
    """
    analysis = await db.event_analyses.find_one({"id": analysis_id}, {"_id": 0})
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    result = analysis.get("result", {})
    
    # Format for report generation
    report_data = {
        "report_type": "event_analysis",
        "analysis_id": analysis_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": result.get("summary", {}),
        "ai_analysis": result.get("ai_analysis", ""),
        "suggestions": result.get("suggestions", []),
        "patterns": result.get("patterns", {}),
        "clusters": result.get("clusters", [])[:10],
        "charts_data": {
            "severity_pie": [
                {"name": k, "value": v} 
                for k, v in result.get("patterns", {}).get("severity_distribution", {}).items()
            ],
            "alert_bar": result.get("patterns", {}).get("alert_frequency", [])[:10],
            "service_bar": result.get("patterns", {}).get("service_frequency", [])[:10]
        }
    }
    
    return report_data


# ======================== QUICK ANALYSIS (No file storage) ========================

@router.post("/quick-analyze")
async def quick_analyze(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth)
):
    """
    Quick analysis without storing the file.
    Uploads, analyzes, and returns results in one call.
    """
    # Validate file
    filename = file.filename.lower()
    if not any(filename.endswith(ext) for ext in ['.xlsx', '.xls', '.csv']):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Supported formats: .xlsx, .xls, .csv"
        )
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")
    
    # Parse and analyze
    analyzer = EventAnalyzer()
    parse_result = analyzer.parse_file(content, file.filename)
    
    if not parse_result.get("success"):
        raise HTTPException(status_code=400, detail=parse_result.get("error"))
    
    # Perform analysis
    analysis_result = await analyzer.ai_analyze()
    
    return {
        "filename": file.filename,
        "total_events": parse_result.get("total_events"),
        **analysis_result
    }


# ======================== SAMPLE DATA ENDPOINT ========================

@router.get("/sample-format")
async def get_sample_format():
    """Get sample file format for event uploads"""
    return {
        "description": "Expected file format for event analysis",
        "supported_formats": [".xlsx", ".xls", ".csv"],
        "max_file_size": "10MB",
        "required_columns": {
            "timestamp": "Event timestamp (flexible formats accepted)",
            "service": "Service or application name",
            "alert": "Alert name or description",
            "severity": "Alert severity (critical, warning, info)"
        },
        "optional_columns": {
            "host": "Hostname, server, or pod name",
            "component": "Sub-component or module",
            "message": "Additional details"
        },
        "sample_data": [
            {
                "timestamp": "2025-03-07 10:01:00",
                "service": "payment-api",
                "alert": "Database connection timeout",
                "severity": "critical",
                "host": "payment-pod-1"
            },
            {
                "timestamp": "2025-03-07 10:02:00",
                "service": "checkout-api",
                "alert": "API response latency high",
                "severity": "warning",
                "host": "checkout-pod-2"
            },
            {
                "timestamp": "2025-03-07 10:03:00",
                "service": "payment-api",
                "alert": "Database connection timeout",
                "severity": "critical",
                "host": "payment-pod-1"
            }
        ],
        "column_aliases": {
            "timestamp": ["time", "date", "datetime", "event_time", "created_at"],
            "service": ["service_name", "application", "app", "component", "source"],
            "alert": ["alert_name", "message", "event", "description", "title"],
            "severity": ["priority", "level", "status", "criticality"],
            "host": ["hostname", "server", "node", "instance", "pod"]
        }
    }



# ======================== EXPORT ENDPOINTS ========================

class ExportBranding(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    footer: Optional[str] = None


@router.get("/export/{analysis_id}/excel")
async def export_excel(
    analysis_id: str,
    user: dict = Depends(require_auth),
    company: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    footer: Optional[str] = Query(None),
):
    """Export analysis result as a multi-sheet Excel workbook"""
    analysis = await db.event_analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    result = analysis.get("result", {})
    events_data = await db.event_data.find_one(
        {"upload_id": analysis.get("upload_id")}, {"_id": 0}
    )
    events = events_data.get("events", []) if events_data else []

    branding = {}
    if company:
        branding["company"] = company
    if title:
        branding["title"] = title
    if footer:
        branding["footer"] = footer

    buf = generate_excel_report(result, events, branding or None)

    filename = f"FalconOps_Analysis_{analysis_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/{analysis_id}/pdf")
async def export_pdf(
    analysis_id: str,
    user: dict = Depends(require_auth),
    company: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    footer: Optional[str] = Query(None),
):
    """Export analysis result as a professional PDF report with charts"""
    analysis = await db.event_analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    result = analysis.get("result", {})
    events_data = await db.event_data.find_one(
        {"upload_id": analysis.get("upload_id")}, {"_id": 0}
    )
    events = events_data.get("events", []) if events_data else []

    branding = {}
    if company:
        branding["company"] = company
    if title:
        branding["title"] = title
    if footer:
        branding["footer"] = footer

    buf = generate_pdf_report(result, events, branding or None)

    filename = f"FalconOps_Analysis_{analysis_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/{analysis_id}/docx")
async def export_docx_weekly(
    analysis_id: str,
    user: dict = Depends(require_auth),
    company: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    period: Optional[str] = Query(None, description="Custom period label, e.g. '12 Apr – 18 Apr 2026'"),
):
    """Export analysis as a Fasah-format Weekly Report DOCX."""
    from ..services.fasah_report_service import generate_fasah_weekly_report

    analysis = await db.event_analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    result = analysis.get("result", {})
    events_data = await db.event_data.find_one(
        {"upload_id": analysis.get("upload_id")}, {"_id": 0}
    )
    events = events_data.get("events", []) if events_data else []

    docx_bytes = generate_fasah_weekly_report(
        analysis=result,
        events=events,
        period=period,
        company_name=company or "Fasah",
        report_title=title or "Weekly AIOps Report",
    )

    filename = (
        f"Weekly_Report_{(company or 'Fasah').replace(' ', '_')}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.docx"
    )
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ======================== HEALTH RULE ALERT ANALYTICS ========================

import hashlib


def _fingerprint(rule_name: str, metric: str, source_id: str = "") -> str:
    """Generate a unique fingerprint for a violation type."""
    raw = f"{rule_name}|{metric}|{source_id}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@router.get("/health-rule-analytics")
async def get_health_rule_analytics(
    user: dict = Depends(require_auth)
):
    """
    Aggregate all health-rule violations into analytics:
    - Per-rule breakdown (distinct alerts, critical/warning counts)
    - Fingerprinted alert identifiers
    - Overall summary with resolution rate
    """
    # Fetch all violations
    violations = await db["db.health_violations"].find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).to_list(5000)

    # Fetch all health rules
    rules = await db.health_rules.find(
        {}, {"_id": 0, "id": 1, "name": 1, "metric": 1, "component_type": 1,
             "severity": 1, "operator": 1, "threshold": 1, "enabled": 1,
             "violations_count": 1, "alerts_triggered": 1}
    ).to_list(200)

    rules_map = {r["id"]: r for r in rules}

    # Aggregate per-rule
    rule_stats = {}
    for v in violations:
        rule_id = v.get("rule_id", "unknown")
        rule_name = v.get("rule_name", "Unknown Rule")
        metric = v.get("metric", "unknown")
        severity = v.get("severity", "info")
        state = v.get("state", "active")
        source_id = v.get("source_id", "")
        source_name = v.get("source_name", "")

        fp = _fingerprint(rule_name, metric, source_id)

        if rule_id not in rule_stats:
            rule_info = rules_map.get(rule_id, {})
            rule_stats[rule_id] = {
                "rule_id": rule_id,
                "rule_name": rule_name,
                "metric": metric,
                "component_type": rule_info.get("component_type", v.get("source_type", "")),
                "operator": v.get("operator", ""),
                "threshold": v.get("threshold", 0),
                "rule_severity": rule_info.get("severity", severity),
                "enabled": rule_info.get("enabled", True),
                "total_violations": 0,
                "active_count": 0,
                "resolved_count": 0,
                "critical_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "sources": {},
                "fingerprints": [],
                "first_seen": v.get("timestamp"),
                "last_seen": v.get("timestamp"),
            }

        s = rule_stats[rule_id]
        s["total_violations"] += 1
        if state in ("active", "critical", "warning"):
            s["active_count"] += 1
        elif state == "resolved":
            s["resolved_count"] += 1
        if severity == "critical":
            s["critical_count"] += 1
        elif severity == "warning":
            s["warning_count"] += 1
        else:
            s["info_count"] += 1

        # Track distinct sources
        if source_id and source_id not in s["sources"]:
            s["sources"][source_id] = source_name

        # Track fingerprints
        fp_entry = {
            "fingerprint": fp,
            "source_id": source_id,
            "source_name": source_name,
            "severity": severity,
            "state": state,
            "value": v.get("actual_value"),
            "timestamp": v.get("timestamp"),
        }
        s["fingerprints"].append(fp_entry)

        # Update time range
        ts = v.get("timestamp", "")
        if ts and (not s["first_seen"] or ts < s["first_seen"]):
            s["first_seen"] = ts
        if ts and (not s["last_seen"] or ts > s["last_seen"]):
            s["last_seen"] = ts

    # Build per-rule result list
    rule_analytics = []
    for rid, s in rule_stats.items():
        s["distinct_sources"] = len(s["sources"])
        s["sources"] = list(s["sources"].values())[:10]
        s["fingerprints"] = s["fingerprints"][:20]  # Limit
        s["resolution_rate"] = (
            round(s["resolved_count"] / s["total_violations"] * 100, 1)
            if s["total_violations"] > 0 else 0
        )
        rule_analytics.append(s)

    rule_analytics.sort(key=lambda x: x["total_violations"], reverse=True)

    # Build chart data: severity stacked per rule
    chart_data = []
    for ra in rule_analytics[:15]:
        chart_data.append({
            "rule_name": ra["rule_name"][:30],
            "critical": ra["critical_count"],
            "warning": ra["warning_count"],
            "info": ra["info_count"],
            "total": ra["total_violations"],
        })

    # Overall summary
    total_violations = len(violations)
    active_violations = sum(1 for v in violations if v.get("state") in ("active", "critical", "warning"))
    resolved_violations = sum(1 for v in violations if v.get("state") == "resolved")
    total_critical = sum(1 for v in violations if v.get("severity") == "critical")
    total_warning = sum(1 for v in violations if v.get("severity") == "warning")

    summary = {
        "total_violations": total_violations,
        "active_violations": active_violations,
        "resolved_violations": resolved_violations,
        "total_critical": total_critical,
        "total_warning": total_warning,
        "total_info": total_violations - total_critical - total_warning,
        "resolution_rate": round(resolved_violations / total_violations * 100, 1) if total_violations > 0 else 0,
        "distinct_rules_triggered": len(rule_analytics),
        "total_rules_configured": len(rules),
        "rules_with_active_violations": sum(1 for ra in rule_analytics if ra["active_count"] > 0),
    }

    return {
        "summary": summary,
        "rule_analytics": rule_analytics,
        "chart_data": chart_data,
        "severity_distribution": {
            "critical": total_critical,
            "warning": total_warning,
            "info": total_violations - total_critical - total_warning,
        },
    }
