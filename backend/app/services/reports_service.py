"""
FalconOps AI - Reports Service
Report generation, PDF/Excel export, and scheduled report delivery
"""
import os
import io
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from ..core.database import db
from .notification_service import send_alert_email, send_report_email_with_attachment

logger = logging.getLogger(__name__)

# Report scheduler state
report_scheduler_task = None
report_scheduler_running = False


async def generate_uptime_report(period_hours: int = 24, monitor_ids: Optional[List[str]] = None, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Generate uptime report data for the specified period"""
    since = (datetime.now(timezone.utc) - timedelta(hours=period_hours)).isoformat()

    query = {"enabled": True}
    if monitor_ids:
        query["id"] = {"$in": monitor_ids}
    if tenant_id:
        query["tenant_id"] = tenant_id
    monitors = await db.monitors.find(query, {"_id": 0}).to_list(500)

    monitor_stats = []
    total_uptime = 0
    total_checks = 0
    sla_compliant = 0

    for monitor in monitors:
        results = await db.monitor_results.find({
            "monitor_id": monitor["id"],
            "created_at": {"$gte": since}
        }, {"_id": 0}).to_list(5000)
        
        if results:
            up_count = sum(1 for r in results if r["status"] == "up")
            uptime_pct = round((up_count / len(results)) * 100, 2)
            latencies = [r["latency_ms"] for r in results if r.get("latency_ms")]
            avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0
            
            total_uptime += uptime_pct
            total_checks += 1
            
            if uptime_pct >= monitor.get("sla_uptime_percent", 99.9):
                sla_compliant += 1
            
            monitor_stats.append({
                "name": monitor["name"],
                "target": monitor["target"],
                "type": monitor["monitor_type"],
                "environment": monitor["environment"],
                "uptime_percent": uptime_pct,
                "avg_latency_ms": avg_latency,
                "total_checks": len(results),
                "sla_target": monitor.get("sla_uptime_percent", 99.9),
                "sla_met": uptime_pct >= monitor.get("sla_uptime_percent", 99.9)
            })
    
    incidents = await db.incidents.find({
        "created_at": {"$gte": since},
        **({"tenant_id": tenant_id} if tenant_id else {}),
    }, {"_id": 0}).sort("created_at", -1).to_list(20)

    alerts = await db.alerts.find({
        "created_at": {"$gte": since},
        **({"tenant_id": tenant_id} if tenant_id else {}),
    }, {"_id": 0}).to_list(1000)
    
    alert_summary = {
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a.get("severity") == "critical"),
        "warning": sum(1 for a in alerts if a.get("severity") == "warning"),
        "open": sum(1 for a in alerts if a.get("status") == "open"),
        "resolved": sum(1 for a in alerts if a.get("status") == "resolved")
    }
    
    return {
        "period_hours": period_hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_uptime": round(total_uptime / total_checks, 2) if total_checks > 0 else 100,
        "sla_compliance": round((sla_compliant / total_checks) * 100, 2) if total_checks > 0 else 100,
        "total_monitors": len(monitors),
        "sla_compliant_count": sla_compliant,
        "monitors": sorted(monitor_stats, key=lambda x: x["uptime_percent"]),
        "incidents": [{"title": i["title"], "severity": i["severity"], "status": i["status"]} for i in incidents[:10]],
        "alerts": alert_summary
    }


async def generate_ai_executive_summary(report_data: Dict[str, Any]) -> str:
    """Generate AI executive summary using Emergent LLM"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            return "AI summary unavailable - API key not configured"
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"exec-summary-{datetime.now(timezone.utc).timestamp()}",
            system_message="""You are an enterprise NOC executive report analyst. 
            Generate concise, actionable executive summaries from operational data.
            Focus on trends, risks, and recommendations. Keep it under 200 words.
            Write in a professional, executive-friendly tone."""
        ).with_model("openai", "gpt-5.2")
        
        prompt = f"""Generate an executive summary for this NOC operations report:

PERIOD: {report_data.get('period', {}).get('start_date', 'N/A')} to {report_data.get('period', {}).get('end_date', 'N/A')}

KEY METRICS:
- Total Incidents: {report_data.get('kpis', {}).get('total_incidents', 0)}
- Resolution Rate: {report_data.get('kpis', {}).get('resolution_rate', 0)}%
- Average MTTR: {report_data.get('kpis', {}).get('avg_mttr_minutes', 0)} minutes
- Open Incidents: {report_data.get('kpis', {}).get('open_incidents', 0)}
- Critical Incidents: {report_data.get('kpis', {}).get('critical_incidents', 0)}

SLA STATUS:
- Overall Availability: {report_data.get('sla_summary', {}).get('overall_availability', 0)}%
- SLA Compliance: {report_data.get('sla_summary', {}).get('sla_compliance', 0)}%
- Breaches: {report_data.get('sla_summary', {}).get('breach_count', 0)}

TOP INCIDENT CATEGORIES:
{json.dumps(report_data.get('category_breakdown', [])[:5], indent=2)}

Provide:
1. Overall health assessment (1 sentence)
2. Key observations (2-3 bullets)
3. Risk areas (if any)
4. Recommendations (1-2 actionable items)"""

        response = await chat.send_message(UserMessage(text=prompt))
        return response
        
    except Exception as e:
        logger.error(f"AI summary generation failed: {e}")
        return f"AI summary generation failed: {str(e)}"


async def generate_executive_report_data(start_date: str, end_date: str, include_ai_summary: bool = True, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Generate executive report data"""
    start_dt = datetime.fromisoformat(start_date + "T00:00:00+00:00")
    end_dt = datetime.fromisoformat(end_date + "T23:59:59+00:00")
    tenant_filter = {"tenant_id": tenant_id} if tenant_id else {}

    incidents = await db.incidents.find({
        "created_at": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()},
        **tenant_filter,
    }, {"_id": 0}).to_list(10000)

    alerts = await db.alerts.find({
        "created_at": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()},
        **tenant_filter,
    }, {"_id": 0}).to_list(10000)

    monitors = await db.monitors.find({"enabled": True, **tenant_filter}, {"_id": 0}).to_list(500)
    # monitor_results docs carry no tenant_id of their own (confirmed — only
    # monitor_id) — scope via the already-tenant-filtered monitor id set instead.
    monitor_ids = [m["id"] for m in monitors]
    monitor_results_query = {"created_at": {"$gte": start_dt.isoformat()}}
    if tenant_id:
        monitor_results_query["monitor_id"] = {"$in": monitor_ids}
    monitor_results = await db.monitor_results.find(
        monitor_results_query, {"_id": 0}
    ).to_list(50000)
    
    total_incidents = len(incidents)
    resolved_incidents = sum(1 for i in incidents if i.get("status") == "resolved")
    critical_incidents = sum(1 for i in incidents if i.get("severity") == "critical")
    mttr_values = [i.get("mttr_seconds", 0) for i in incidents if i.get("mttr_seconds")]
    avg_mttr_minutes = round(sum(mttr_values) / len(mttr_values) / 60, 1) if mttr_values else 0
    resolution_rate = round((resolved_incidents / total_incidents * 100), 1) if total_incidents > 0 else 100
    
    up_count = sum(1 for r in monitor_results if r.get("status") == "up")
    overall_availability = round(up_count / len(monitor_results) * 100, 2) if monitor_results else 100
    sla_breaches = sum(1 for m in monitors if m.get("status") in ["down", "timeout"])
    sla_compliance = round((len(monitors) - sla_breaches) / len(monitors) * 100, 1) if monitors else 100
    
    category_counts = {}
    for alert in alerts:
        cat = alert.get("service", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1
    category_breakdown = [
        {"category": k, "count": v, "percentage": round(v / len(alerts) * 100, 1) if alerts else 0}
        for k, v in sorted(category_counts.items(), key=lambda x: -x[1])
    ][:10]
    
    report_data = {
        "period": {"start_date": start_date, "end_date": end_date},
        "kpis": {
            "total_incidents": total_incidents,
            "resolved_incidents": resolved_incidents,
            "open_incidents": total_incidents - resolved_incidents,
            "critical_incidents": critical_incidents,
            "resolution_rate": resolution_rate,
            "avg_mttr_minutes": avg_mttr_minutes,
            "total_alerts": len(alerts)
        },
        "sla_summary": {
            "overall_availability": overall_availability,
            "sla_compliance": sla_compliance,
            "total_monitors": len(monitors),
            "breach_count": sla_breaches
        },
        "category_breakdown": category_breakdown,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if include_ai_summary:
        report_data["ai_summary"] = await generate_ai_executive_summary(report_data)
    
    return report_data


async def generate_sla_report_data(start_date: str, end_date: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Generate SLA report data"""
    start_dt = datetime.fromisoformat(start_date + "T00:00:00+00:00")
    end_dt = datetime.fromisoformat(end_date + "T23:59:59+00:00")

    monitors = await db.monitors.find({**({"tenant_id": tenant_id} if tenant_id else {})}, {"_id": 0}).to_list(500)
    # monitor_results carries no tenant_id of its own — without scoping this query
    # to this tenant's monitor ids too, the overall_availability aggregate below
    # (which sums across every key in monitor_sla, not just this tenant's monitors)
    # would silently include other tenants' check results.
    results_query = {"created_at": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}}
    if tenant_id:
        results_query["monitor_id"] = {"$in": [m["id"] for m in monitors]}
    results = await db.monitor_results.find(results_query, {"_id": 0}).to_list(100000)
    
    monitor_sla = {}
    for result in results:
        mid = result.get("monitor_id")
        if mid not in monitor_sla:
            monitor_sla[mid] = {"up": 0, "down": 0, "total": 0, "latencies": []}
        monitor_sla[mid]["total"] += 1
        if result.get("status") == "up":
            monitor_sla[mid]["up"] += 1
        else:
            monitor_sla[mid]["down"] += 1
        if result.get("latency_ms"):
            monitor_sla[mid]["latencies"].append(result["latency_ms"])
    
    service_sla = []
    for monitor in monitors:
        mid = monitor.get("id")
        stats = monitor_sla.get(mid, {"up": 0, "down": 0, "total": 1, "latencies": []})
        availability = round(stats["up"] / stats["total"] * 100, 2) if stats["total"] > 0 else 100
        sla_target = monitor.get("sla_uptime_percent", 99.9)
        
        service_sla.append({
            "service_name": monitor.get("name"),
            "availability_percent": availability,
            "sla_target": sla_target,
            "sla_met": availability >= sla_target
        })
    
    total_up = sum(s["up"] for s in monitor_sla.values())
    total_checks = sum(s["total"] for s in monitor_sla.values())
    overall_availability = round(total_up / total_checks * 100, 2) if total_checks > 0 else 100
    
    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "overall_availability": overall_availability,
            "total_services": len(monitors),
            "services_meeting_sla": sum(1 for s in service_sla if s["sla_met"])
        },
        "service_breakdown": sorted(service_sla, key=lambda x: x["availability_percent"]),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


async def generate_incident_report_data(start_date: str, end_date: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Generate incident analytics report data"""
    start_dt = datetime.fromisoformat(start_date + "T00:00:00+00:00")
    end_dt = datetime.fromisoformat(end_date + "T23:59:59+00:00")

    incidents = await db.incidents.find({
        "created_at": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()},
        **({"tenant_id": tenant_id} if tenant_id else {}),
    }, {"_id": 0}).to_list(10000)
    
    total = len(incidents)
    resolved = sum(1 for i in incidents if i.get("status") == "resolved")
    critical = sum(1 for i in incidents if i.get("severity") == "critical")
    
    mttr_values = [i.get("mttr_seconds", 0) for i in incidents if i.get("mttr_seconds")]
    avg_mttr = round(sum(mttr_values) / len(mttr_values) / 60, 1) if mttr_values else 0
    
    return {
        "period": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "total_incidents": total,
            "resolved_incidents": resolved,
            "open_incidents": total - resolved,
            "critical_incidents": critical,
            "resolution_rate": round(resolved / total * 100, 1) if total > 0 else 100
        },
        "mttr_stats": {"average_minutes": avg_mttr},
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


async def generate_report_pdf(report_type: str, report_data: Dict[str, Any], period_label: str) -> bytes:
    """Generate PDF report"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import inch
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=30, textColor=colors.HexColor('#D4AF37'))
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14, spaceBefore=20, spaceAfter=10, textColor=colors.HexColor('#00F0FF'))
    
    elements = []
    
    elements.append(Paragraph("FALCONOPS AI", title_style))
    elements.append(Paragraph(f"{period_label.upper()} {report_type.upper()} REPORT", styles['Heading2']))
    elements.append(Paragraph(f"Period: {report_data.get('period', {}).get('start_date', 'N/A')} to {report_data.get('period', {}).get('end_date', 'N/A')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    if "kpis" in report_data:
        elements.append(Paragraph("KEY PERFORMANCE INDICATORS", heading_style))
        kpi_data = [["Metric", "Value"]]
        for key, value in report_data["kpis"].items():
            kpi_data.append([key.replace("_", " ").title(), str(value)])
        kpi_table = Table(kpi_data, colWidths=[3*inch, 2*inch])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#D4AF37')),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#333333'))
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 20))
    
    if "sla_summary" in report_data or "summary" in report_data:
        elements.append(Paragraph("SLA & AVAILABILITY", heading_style))
        summary = report_data.get("sla_summary", report_data.get("summary", {}))
        sla_data = [["Metric", "Value"]]
        for key, value in summary.items():
            sla_data.append([key.replace("_", " ").title(), str(value)])
        sla_table = Table(sla_data, colWidths=[3*inch, 2*inch])
        sla_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#D4AF37')),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#333333'))
        ]))
        elements.append(sla_table)
        elements.append(Spacer(1, 20))
    
    if report_data.get("ai_summary"):
        elements.append(Paragraph("AI EXECUTIVE SUMMARY", heading_style))
        elements.append(Paragraph(report_data["ai_summary"], styles['Normal']))
        elements.append(Spacer(1, 20))
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(f"Generated: {report_data.get('generated_at', datetime.now(timezone.utc).isoformat())}", styles['Normal']))
    elements.append(Paragraph("FalconOps AI - Enterprise AIOps Platform", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


async def send_scheduled_report(report_config: Dict[str, Any]) -> bool:
    """Send a scheduled report to recipients with optional PDF attachment"""
    try:
        report_type = report_config.get("report_type", "uptime_summary")
        frequency = report_config.get("frequency", "daily")
        recipients = report_config.get("recipients", [])
        include_pdf = report_config.get("include_pdf", True)
        include_ai_summary = report_config.get("include_ai_summary", True)
        
        period_days = {"daily": 1, "weekly": 7, "monthly": 30}.get(frequency, 1)
        period_hours = period_days * 24
        period_label = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}.get(frequency, "")
        
        end_date = datetime.now(timezone.utc).isoformat()[:10]
        start_date = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()[:10]
        
        if report_type in ["executive", "executive_summary"]:
            report_data = await generate_executive_report_data(start_date, end_date, include_ai_summary)
        elif report_type == "sla":
            report_data = await generate_sla_report_data(start_date, end_date)
        elif report_type == "incidents":
            report_data = await generate_incident_report_data(start_date, end_date)
        else:
            report_data = await generate_uptime_report(period_hours=period_hours, monitor_ids=report_config.get("include_monitors"))
            report_type = "uptime_summary"
        
        pdf_buffer = None
        if include_pdf:
            pdf_buffer = await generate_report_pdf(report_type, report_data, period_label)
        
        # Build simple email HTML
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background: #050505; color: #fff; padding: 20px;">
            <h1 style="color: #D4AF37;">FalconOps AI - {period_label} {report_type.title()} Report</h1>
            <p>Please find your scheduled report attached.</p>
            <p>Period: {start_date} to {end_date}</p>
            <p>Generated: {report_data.get('generated_at', '')}</p>
        </body>
        </html>
        """
        
        subject = f"📊 FalconApps {period_label} {report_type.title()} Report - {datetime.now().strftime('%b %d, %Y')}"
        
        if pdf_buffer:
            await send_report_email_with_attachment(
                recipients=recipients,
                subject=subject,
                html_content=html_content,
                pdf_data=pdf_buffer,
                filename=f"falconops_{report_type}_{frequency}_report_{datetime.now().strftime('%Y%m%d')}.pdf"
            )
        
        await db.scheduled_reports.update_one(
            {"id": report_config["id"]},
            {"$set": {"last_sent": datetime.now(timezone.utc).isoformat()}}
        )
        
        logger.info(f"Scheduled report '{report_config['name']}' sent to {len(recipients)} recipients")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send scheduled report: {e}")
        return False


async def report_scheduler():
    """Background scheduler for scheduled reports"""
    global report_scheduler_running
    report_scheduler_running = True
    
    while report_scheduler_running:
        try:
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            current_day = now.weekday()
            
            reports = await db.scheduled_reports.find({"enabled": True}, {"_id": 0}).to_list(100)
            
            for report in reports:
                should_run = False
                
                if report["frequency"] == "daily" and report["hour"] == current_hour:
                    last_sent = report.get("last_sent")
                    if not last_sent or last_sent[:10] != now.isoformat()[:10]:
                        should_run = True
                        
                elif report["frequency"] == "weekly" and report["hour"] == current_hour:
                    if report.get("day_of_week", 0) == current_day:
                        last_sent = report.get("last_sent")
                        if not last_sent or (now - datetime.fromisoformat(last_sent.replace("Z", "+00:00"))).days >= 6:
                            should_run = True
                            
                elif report["frequency"] == "monthly" and report["hour"] == current_hour:
                    if now.day == 1:
                        last_sent = report.get("last_sent")
                        if not last_sent or (now - datetime.fromisoformat(last_sent.replace("Z", "+00:00"))).days >= 27:
                            should_run = True
                
                if should_run:
                    logger.info(f"Running scheduled report: {report['name']}")
                    await send_scheduled_report(report)
                    
        except Exception as e:
            logger.error(f"Report scheduler error: {e}")
        
        await asyncio.sleep(3600)


def start_report_scheduler():
    """Start the report scheduler"""
    global report_scheduler_task
    if report_scheduler_task is None or report_scheduler_task.done():
        report_scheduler_task = asyncio.create_task(report_scheduler())
        logger.info("Report scheduler started")


def stop_report_scheduler():
    """Stop the report scheduler"""
    global report_scheduler_running, report_scheduler_task
    report_scheduler_running = False
    if report_scheduler_task:
        report_scheduler_task.cancel()
        logger.info("Report scheduler stopped")
