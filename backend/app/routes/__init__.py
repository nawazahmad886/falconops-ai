# FalconOps AI - Routes Package
from .auth import router as auth_router
from .alerts import router as alerts_router
from .incidents import router as incidents_router
from .monitors import router as monitors_router
from .topology import router as topology_router
from .reports import router as reports_router
from .analytics import router as analytics_router
from .runbooks import router as runbooks_router
from .apm import router as apm_router
from .servers import router as servers_router
from .correlation import router as correlation_router
from .tenants import router as tenants_router
from .logs import router as logs_router
from .licenses import router as licenses_router
from .event_analyzer import router as event_analyzer_router
from .alert_ingestion import router as alert_ingestion_router
from .health_rules import router as health_rules_router
from .metrics import router as metrics_router
from .metrics_observability import router as metrics_observability_router
from .alert_engine_routes import router as alert_engine_router
from .incident_engine_routes import router as incident_engine_router
from .capacity_routes import router as capacity_router
from .seed_data import router as seed_data_router
from .anomaly_detection_routes import router as anomaly_detection_router
from .smart_correlation_routes import router as smart_correlation_router
from .impact_analysis_routes import router as impact_analysis_router
from .agent_routes import router as agent_router
from .core_aiops import router as core_aiops_router
from .report_schedules import router as report_schedules_router
from .db_monitoring import router as db_monitoring_router
from .alert_respond import router as alert_respond_router
from .synthetic_monitoring import router as synthetic_monitoring_router
from .self_monitor import router as self_monitor_router
from .security_routes import router as security_router
from .ueba_routes import router as ueba_router
from .attack_sim_routes import router as attack_sim_router
from .integration_management_routes import router as integration_mgmt_router
from .remediation_routes import router as remediation_router
from .impact_routes import router as impact_router
from .dispatch_routes import router as dispatch_router
from .rbac_routes import router as rbac_router
from .soc_live_feed_routes import router as soc_live_feed_router
from .aws_connector_routes import router as aws_connector_router
from .connector_routes import router as connector_sdk_router
from .problems_routes import router as problems_router
from .resource_explorer_routes import router as resource_explorer_router
from .kafka_pipeline_routes import router as kafka_pipeline_router
from .query_analyzer_routes import router as query_analyzer_router
from .uptime_monitor_routes import router as uptime_monitor_router
from .billing_routes import router as billing_router
from .check_node_routes import router as check_node_router
from .sla_routes import router as sla_router
from .detection_routes import router as detection_router
from .ai_agents_routes import router as ai_agents_router
from .correlation_routes import router as correlation_v2_router
from .k8s_healing_routes import router as k8s_healing_router
from .soc_engine_routes import router as soc_engine_router
from .report_generator_routes import router as report_generator_router
from .custom_dashboard_routes import router as custom_dashboard_router
from .scheduled_reports_routes import router as scheduled_reports_enterprise_router
from .client_portal_routes import admin_router as client_portal_admin_router, public_router as client_portal_public_router
from .report_templates_routes import router as report_templates_router
from .ai_copilot_chat_routes import router as ai_copilot_chat_router
from .admin_control_routes import router as admin_control_router
from .ai_engine_routes import router as ai_engine_router
from .otlp_routes import otlp_router, trace_router, trace_alerts_router
from .monetization_routes import public_router as monetization_public_router, admin_router as monetization_admin_router
from .aiops_diagnose_routes import router as aiops_diagnose_router
from .automation_templates_routes import router as automation_templates_router
from .aws_deploy_routes import router as aws_deploy_router
from .ai_monitoring_routes import router as ai_monitoring_router
from .log_analyzer_routes import router as log_analyzer_router
from .ai_intelligence_routes import router as ai_intelligence_router
from .oneagent_routes import ingest_router as oneagent_ingest_router, mgmt_router as oneagent_mgmt_router
from .mitre_routes import router as mitre_router
from .vulnerability_routes import router as vulnerability_router
from .compliance_routes import router as compliance_router
from .security_agents_routes import router as security_agents_router
from .executive_routes import router as executive_router
from .agent_eval_routes import router as agent_eval_router
from .ops_agents_routes import router as ops_agents_router
from .network_flow_routes import router as network_flow_router
from .agentic_workflow_routes import router as agentic_workflow_router
from .knowledge_graph_routes import router as knowledge_graph_router
from .rased_routes import router as rased_router
from .rased_incident_routes import router as rased_incident_router
from .rased_demo_routes import router as rased_demo_router
from .control_center_routes import router as control_center_router
from .backup_routes import router as backup_router
from .onboarding_routes import router as onboarding_router
from .incident_commander_routes import router as incident_commander_router, audit_router as incident_commander_audit_router
from .troubleshooting_routes import router as troubleshooting_router

# Export all routers
all_routers = [
    auth_router,
    alerts_router,
    incidents_router,
    monitors_router,
    topology_router,
    reports_router,
    analytics_router,
    runbooks_router,
    apm_router,
    servers_router,
    correlation_router,
    tenants_router,
    logs_router,
    licenses_router,
    event_analyzer_router,
    alert_ingestion_router,
    health_rules_router,
    metrics_router,
    metrics_observability_router,
    alert_engine_router,
    incident_engine_router,
    capacity_router,
    seed_data_router,
    anomaly_detection_router,
    smart_correlation_router,
    impact_analysis_router,
    agent_router,
    core_aiops_router,
    report_schedules_router,
    db_monitoring_router,
    alert_respond_router,
    synthetic_monitoring_router,
    self_monitor_router,
    security_router,
    ueba_router,
    attack_sim_router,
    integration_mgmt_router,
    remediation_router,
    impact_router,
    dispatch_router,
    rbac_router,
    soc_live_feed_router,
    aws_connector_router,
    connector_sdk_router,
    problems_router,
    resource_explorer_router,
    kafka_pipeline_router,
    query_analyzer_router,
    uptime_monitor_router,
    billing_router,
    check_node_router,
    sla_router,
    detection_router,
    ai_agents_router,
    correlation_v2_router,
    k8s_healing_router,
    soc_engine_router,
    report_generator_router,
    custom_dashboard_router,
    scheduled_reports_enterprise_router,
    client_portal_admin_router,
    client_portal_public_router,
    report_templates_router,
    ai_copilot_chat_router,
    admin_control_router,
    ai_engine_router,
    otlp_router,
    trace_alerts_router,
    trace_router,
    monetization_public_router,
    monetization_admin_router,
    aiops_diagnose_router,
    automation_templates_router,
    aws_deploy_router,
    ai_monitoring_router,
    log_analyzer_router,
    ai_intelligence_router,
    oneagent_ingest_router,
    oneagent_mgmt_router,
    mitre_router,
    vulnerability_router,
    compliance_router,
    security_agents_router,
    executive_router,
    agent_eval_router,
    ops_agents_router,
    network_flow_router,
    agentic_workflow_router,
    knowledge_graph_router,
    rased_router,
    rased_incident_router,
    rased_demo_router,
    control_center_router,
    backup_router,
    onboarding_router,
    incident_commander_router,
    incident_commander_audit_router,
    troubleshooting_router,
]
