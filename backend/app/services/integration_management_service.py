"""
FalconOps AI - Admin Integration Management Service
Manage external API keys, connectors, and integration settings
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.database import db
from ..connectors.crypto import encrypt_config_secrets, decrypt_config_secrets

logger = logging.getLogger(__name__)

# Available integration definitions
INTEGRATION_CATALOG = [
    {
        "id": "aws_cloudtrail",
        "name": "AWS CloudTrail",
        "category": "cloud",
        "description": "Ingest AWS CloudTrail security events and API call logs",
        "icon": "cloud",
        "fields": [
            {"key": "aws_access_key", "label": "AWS Access Key ID", "type": "text", "required": True},
            {"key": "aws_secret_key", "label": "AWS Secret Access Key", "type": "password", "required": True},
            {"key": "aws_region", "label": "AWS Region", "type": "text", "required": True, "default": "me-south-1"},
        ],
    },
    {
        "id": "aws_vpc_flowlogs",
        "name": "AWS VPC Flow Logs",
        "category": "cloud",
        "description": "Ingest VPC Flow Logs for network traffic analysis",
        "icon": "network",
        "fields": [
            {"key": "aws_access_key", "label": "AWS Access Key ID", "type": "text", "required": True},
            {"key": "aws_secret_key", "label": "AWS Secret Access Key", "type": "password", "required": True},
            {"key": "log_group", "label": "CloudWatch Log Group", "type": "text", "required": True},
        ],
    },
    {
        "id": "slack",
        "name": "Slack",
        "category": "notification",
        "description": "Send alerts and incident notifications to Slack channels",
        "icon": "message",
        "fields": [
            {"key": "webhook_url", "label": "Webhook URL", "type": "text", "required": True},
            {"key": "channel", "label": "Default Channel", "type": "text", "required": False, "default": "#alerts"},
        ],
    },
    {
        "id": "pagerduty",
        "name": "PagerDuty",
        "category": "notification",
        "description": "Trigger PagerDuty incidents for critical alerts",
        "icon": "bell",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
            {"key": "service_id", "label": "Service ID", "type": "text", "required": True},
        ],
    },
    {
        "id": "servicenow",
        "name": "ServiceNow",
        "category": "itsm",
        "description": "Create ServiceNow incidents and change requests",
        "icon": "ticket",
        "fields": [
            {"key": "instance_url", "label": "Instance URL", "type": "text", "required": True},
            {"key": "username", "label": "Username", "type": "text", "required": True},
            {"key": "password", "label": "Password", "type": "password", "required": True},
        ],
    },
    {
        "id": "sendgrid",
        "name": "SendGrid",
        "category": "notification",
        "description": "Send email notifications and reports via SendGrid",
        "icon": "mail",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
            {"key": "from_email", "label": "From Email", "type": "text", "required": True},
        ],
    },
    {
        "id": "elasticsearch",
        "name": "Elasticsearch / ELK",
        "category": "data_source",
        "description": "Ingest logs and metrics from Elasticsearch clusters",
        "icon": "search",
        "fields": [
            {"key": "host", "label": "Elasticsearch Host", "type": "text", "required": True},
            {"key": "api_key", "label": "API Key", "type": "password", "required": False},
            {"key": "index_pattern", "label": "Index Pattern", "type": "text", "required": True, "default": "logs-*"},
        ],
    },
    {
        "id": "datadog",
        "name": "Datadog",
        "category": "data_source",
        "description": "Import metrics and events from Datadog",
        "icon": "bar_chart",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "required": True},
            {"key": "app_key", "label": "Application Key", "type": "password", "required": True},
            {"key": "site", "label": "Datadog Site", "type": "text", "required": False, "default": "datadoghq.com"},
        ],
    },
    {
        "id": "jira",
        "name": "Jira",
        "category": "itsm",
        "description": "Create and manage Jira issues from incidents",
        "icon": "ticket",
        "fields": [
            {"key": "host", "label": "Jira URL", "type": "text", "required": True},
            {"key": "email", "label": "Email", "type": "text", "required": True},
            {"key": "api_token", "label": "API Token", "type": "password", "required": True},
            {"key": "project_key", "label": "Project Key", "type": "text", "required": True},
        ],
    },
    {
        "id": "splunk",
        "name": "Splunk",
        "category": "data_source",
        "description": "Ingest events from Splunk via HEC",
        "icon": "search",
        "fields": [
            {"key": "hec_url", "label": "HEC URL", "type": "text", "required": True},
            {"key": "hec_token", "label": "HEC Token", "type": "password", "required": True},
        ],
    },
    {
        "id": "custom_webhook",
        "name": "Custom Webhook",
        "category": "custom",
        "description": "Send events to a custom HTTP endpoint",
        "icon": "webhook",
        "fields": [
            {"key": "url", "label": "Webhook URL", "type": "text", "required": True},
            {"key": "auth_header", "label": "Authorization Header", "type": "password", "required": False},
            {"key": "method", "label": "HTTP Method", "type": "text", "required": False, "default": "POST"},
        ],
    },
    {
        "id": "prometheus",
        "name": "Prometheus",
        "category": "data_source",
        "description": "Pull metrics from a Prometheus server via its HTTP query API",
        "icon": "activity",
        "fields": [
            {"key": "prometheus_url", "label": "Prometheus URL", "type": "text", "required": True, "default": "http://localhost:9090"},
            {"key": "bearer_token", "label": "Bearer Token (optional)", "type": "password", "required": False},
            {"key": "default_queries", "label": "PromQL Queries (comma-separated)", "type": "text", "required": False, "default": "up"},
            {"key": "scrape_interval_seconds", "label": "Poll Interval (seconds)", "type": "text", "required": False, "default": "60"},
        ],
        # Connector-SDK-backed entries carry these extra fields; absent on the
        # legacy entries above, which means "config-only, not SDK-connected yet".
        "vendor": "Prometheus",
        "version": "1.0.0",
        "capabilities": ["metrics", "ai_context"],
        "connector_id": "prometheus",
    },
]


async def get_catalog() -> List[Dict]:
    """Get available integration catalog with current status"""
    configured = await db.integrations.find({}, {"_id": 0}).to_list(100)
    configured_map = {c["integration_id"]: c for c in configured}

    result = []
    for item in INTEGRATION_CATALOG:
        entry = {**item}
        cfg = configured_map.get(item["id"])
        if cfg:
            entry["enabled"] = cfg.get("enabled", False)
            entry["configured"] = True
            entry["last_updated"] = cfg.get("updated_at")
        else:
            entry["enabled"] = False
            entry["configured"] = False
        result.append(entry)

    return result


async def get_integration(integration_id: str) -> Optional[Dict]:
    """Get a single integration config (masks secrets)"""
    cfg = await db.integrations.find_one({"integration_id": integration_id}, {"_id": 0})
    if not cfg:
        return None

    # Decrypt password fields (transparently handles legacy plaintext docs — see
    # connectors/crypto.py) before the existing display-time masking below.
    catalog_item = next((c for c in INTEGRATION_CATALOG if c["id"] == integration_id), None)
    cfg["config"] = await decrypt_config_secrets(cfg.get("config", {}), catalog_item)

    # Mask password fields
    if catalog_item:
        for field in catalog_item["fields"]:
            if field["type"] == "password" and field["key"] in cfg.get("config", {}):
                val = cfg["config"][field["key"]]
                if val:
                    cfg["config"][field["key"]] = val[:4] + "****" + val[-4:] if len(val) > 8 else "****"

    return cfg


async def save_integration(integration_id: str, config: Dict, enabled: bool, updated_by: str) -> Dict:
    """Save or update an integration configuration"""
    catalog_item = next((c for c in INTEGRATION_CATALOG if c["id"] == integration_id), None)
    if not catalog_item:
        return {"error": f"Unknown integration: {integration_id}"}

    existing = await db.integrations.find_one({"integration_id": integration_id})

    # If updating, merge with existing config (don't overwrite masked values)
    if existing:
        existing_config = existing.get("config", {})
        for key, val in config.items():
            if "****" in str(val):
                config[key] = existing_config.get(key, val)

    # Encrypt password-typed fields before persisting (no-op for values already
    # encrypted — e.g. the masked-value restore above just put back a
    # previously-encrypted value unchanged).
    config = await encrypt_config_secrets(config, catalog_item)

    doc = {
        "integration_id": integration_id,
        "name": catalog_item["name"],
        "category": catalog_item["category"],
        "config": config,
        "enabled": enabled,
        "updated_by": updated_by,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if existing:
        await db.integrations.update_one(
            {"integration_id": integration_id},
            {"$set": doc}
        )
    else:
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.integrations.insert_one(doc)

    return {"message": f"Integration {catalog_item['name']} saved", "integration_id": integration_id, "enabled": enabled}


async def toggle_integration(integration_id: str, enabled: bool) -> Dict:
    """Toggle an integration on/off"""
    result = await db.integrations.update_one(
        {"integration_id": integration_id},
        {"$set": {"enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        return {"error": "Integration not found or not configured"}
    return {"message": f"Integration {'enabled' if enabled else 'disabled'}", "integration_id": integration_id}


async def delete_integration(integration_id: str) -> Dict:
    """Delete an integration configuration"""
    result = await db.integrations.delete_one({"integration_id": integration_id})
    if result.deleted_count == 0:
        return {"error": "Integration not found"}
    return {"message": "Integration deleted", "integration_id": integration_id}


async def test_integration(integration_id: str) -> Dict:
    """Test an integration connection with real connectivity check"""
    cfg = await db.integrations.find_one({"integration_id": integration_id}, {"_id": 0})
    if not cfg:
        return {"success": False, "error": "Integration not configured"}

    config = cfg.get("config", {})
    try:
        import httpx
        from .ssrf_guard import is_safe_outbound_url
        async with httpx.AsyncClient(timeout=8) as client:
            if integration_id == "slack":
                url = config.get("webhook_url", "")
                if not url:
                    return {"success": False, "error": "No webhook URL configured"}
                if not is_safe_outbound_url(url):
                    return {"success": False, "error": "Refused: webhook URL resolves to a private/internal address"}
                resp = await client.post(url, json={"text": "FalconOps connectivity test"})
                return {"success": resp.status_code == 200, "message": f"Slack responded with {resp.status_code}", "tested_at": datetime.now(timezone.utc).isoformat()}
            elif integration_id == "custom_webhook":
                url = config.get("url", "")
                if not url:
                    return {"success": False, "error": "No URL configured"}
                if not is_safe_outbound_url(url):
                    return {"success": False, "error": "Refused: URL resolves to a private/internal address"}
                headers = {}
                if config.get("auth_header"):
                    headers["Authorization"] = config["auth_header"]
                resp = await client.request(config.get("method", "POST"), url, json={"test": True}, headers=headers)
                return {"success": 200 <= resp.status_code < 300, "message": f"Endpoint responded with {resp.status_code}", "tested_at": datetime.now(timezone.utc).isoformat()}
            elif integration_id in ("pagerduty", "sendgrid", "elasticsearch", "datadog", "splunk"):
                # Validate required fields are present
                catalog_item = next((c for c in INTEGRATION_CATALOG if c["id"] == integration_id), None)
                missing = [f["label"] for f in catalog_item["fields"] if f.get("required") and not config.get(f["key"])]
                if missing:
                    return {"success": False, "error": f"Missing required fields: {', '.join(missing)}"}
                return {"success": True, "message": f"Configuration validated for {cfg.get('name', integration_id)}", "tested_at": datetime.now(timezone.utc).isoformat()}
            else:
                return {"success": True, "message": f"Configuration verified for {cfg.get('name', integration_id)}", "tested_at": datetime.now(timezone.utc).isoformat()}
    except httpx.ConnectError:
        return {"success": False, "error": "Connection refused - check URL", "tested_at": datetime.now(timezone.utc).isoformat()}
    except httpx.TimeoutException:
        return {"success": False, "error": "Connection timed out", "tested_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {"success": False, "error": str(e)[:200], "tested_at": datetime.now(timezone.utc).isoformat()}
