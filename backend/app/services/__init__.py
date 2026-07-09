# FalconOps AI - Services Package
from .websocket_manager import ws_manager, get_ws_manager, ConnectionManager
from .notification_service import send_alert_email, send_teams_notification, send_report_email_with_attachment
from .monitoring_service import (
    perform_ping_check,
    perform_http_check,
    perform_tcp_check,
    perform_ssl_check,
    perform_dns_check,
    run_monitor_check,
    check_sla_breach,
    process_monitor_results,
    start_monitoring_scheduler,
    stop_monitoring_scheduler,
    is_monitoring_running
)
from .reports_service import (
    generate_uptime_report,
    generate_executive_report_data,
    generate_sla_report_data,
    generate_incident_report_data,
    generate_report_pdf,
    generate_ai_executive_summary,
    send_scheduled_report,
    start_report_scheduler,
    stop_report_scheduler
)
from .ai_crew_service import get_aiops_crew, get_aiops_service, AIOpsService
