"""
FalconOps AI - Connector Dispatcher Service
Dispatches alerts, threats, and events to configured integrations (Slack, PagerDuty, SendGrid, Custom Webhook)
"""
import os
import json
import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "warning": "🟡", "info": "🔵"}
SEVERITY_COLOR = {"critical": "#dc2626", "high": "#ea580c", "warning": "#d97706", "info": "#2563eb"}


async def _get_enabled_integrations(categories: List[str] = None) -> List[Dict]:
    """Fetch all enabled integrations, optionally filtered by category"""
    query = {"enabled": True}
    if categories:
        query["category"] = {"$in": categories}
    return await db.integrations.find(query, {"_id": 0}).to_list(50)


async def _log_dispatch(integration_id: str, event_type: str, success: bool, detail: str = ""):
    """Log a dispatch attempt for audit"""
    await db.dispatch_logs.insert_one({
        "integration_id": integration_id,
        "event_type": event_type,
        "success": success,
        "detail": detail[:500],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ======================== SLACK ========================

async def _send_slack(config: Dict, payload: Dict) -> bool:
    """Send a message to Slack via webhook"""
    url = config.get("webhook_url")
    if not url:
        return False
    from .ssrf_guard import is_safe_outbound_url
    if not is_safe_outbound_url(url):
        logger.warning("Slack dispatch refused: webhook URL resolves to a private/internal address")
        return False
    try:
        sev = payload.get("severity", "info")
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{SEVERITY_EMOJI.get(sev, '📢')} FalconOps Alert: {payload.get('title', 'Alert')}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{sev.upper()}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{payload.get('type', 'alert')}"},
                    {"type": "mrkdwn", "text": f"*Source:*\n{payload.get('source', 'FalconOps')}"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{payload.get('timestamp', datetime.now(timezone.utc).isoformat())}"},
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": payload.get("message", "")}
            },
        ]
        if payload.get("host"):
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Host: `{payload['host']}` | IP: `{payload.get('source_ip', 'N/A')}`"}]
            })

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"blocks": blocks, "text": payload.get("message", "FalconOps Alert")})
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Slack dispatch failed: {e}")
        return False


# ======================== PAGERDUTY ========================

async def _send_pagerduty(config: Dict, payload: Dict) -> bool:
    """Create a PagerDuty incident via Events API v2"""
    routing_key = config.get("api_key")
    if not routing_key:
        return False
    try:
        sev_map = {"critical": "critical", "high": "error", "warning": "warning", "info": "info"}
        pd_payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": payload.get("message", "FalconOps Alert"),
                "severity": sev_map.get(payload.get("severity", "info"), "info"),
                "source": payload.get("source", "FalconOps AI"),
                "component": payload.get("host", ""),
                "group": payload.get("type", "alert"),
                "custom_details": {
                    "title": payload.get("title", ""),
                    "severity": payload.get("severity", ""),
                    "source_ip": payload.get("source_ip", ""),
                    "user": payload.get("user", ""),
                    "timestamp": payload.get("timestamp", ""),
                }
            },
            "dedup_key": payload.get("id", ""),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post("https://events.pagerduty.com/v2/enqueue", json=pd_payload)
            return resp.status_code in (200, 202)
    except Exception as e:
        logger.error(f"PagerDuty dispatch failed: {e}")
        return False


# ======================== SENDGRID ========================

async def _send_sendgrid(config: Dict, payload: Dict) -> bool:
    """Send an alert email via SendGrid API"""
    api_key = config.get("api_key")
    from_email = config.get("from_email", "alerts@falconops.ai")
    if not api_key:
        return False
    try:
        sev = payload.get("severity", "info")
        color = SEVERITY_COLOR.get(sev, "#2563eb")
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0a0a;color:#fff;border:1px solid #222;border-radius:8px;">
            <div style="background:{color};padding:16px;text-align:center;border-radius:8px 8px 0 0;">
                <h2 style="margin:0;color:#fff;">FalconOps Alert - {sev.upper()}</h2>
            </div>
            <div style="padding:20px;">
                <h3 style="color:#fff;">{payload.get('title', 'Alert')}</h3>
                <p style="color:#aaa;">{payload.get('message', '')}</p>
                <table style="width:100%;color:#ccc;font-size:14px;margin-top:16px;">
                    <tr><td style="color:#888;padding:4px 0;">Type:</td><td>{payload.get('type', 'alert')}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Host:</td><td>{payload.get('host', 'N/A')}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Source IP:</td><td>{payload.get('source_ip', 'N/A')}</td></tr>
                    <tr><td style="color:#888;padding:4px 0;">Time:</td><td>{payload.get('timestamp', '')}</td></tr>
                </table>
            </div>
            <div style="padding:12px 20px;border-top:1px solid #222;text-align:center;color:#666;font-size:12px;">
                FalconOps AI Platform
            </div>
        </div>
        """
        sg_payload = {
            "personalizations": [{"to": [{"email": from_email}], "subject": f"[{sev.upper()}] {payload.get('title', 'FalconOps Alert')}"}],
            "from": {"email": from_email, "name": "FalconOps AI"},
            "content": [{"type": "text/html", "value": html}],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=sg_payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            return resp.status_code in (200, 202)
    except Exception as e:
        logger.error(f"SendGrid dispatch failed: {e}")
        return False


# ======================== CUSTOM WEBHOOK ========================

async def _send_custom_webhook(config: Dict, payload: Dict) -> bool:
    """Forward event to a custom HTTP endpoint"""
    url = config.get("url")
    if not url:
        return False
    from .ssrf_guard import is_safe_outbound_url
    if not is_safe_outbound_url(url):
        logger.warning("Custom webhook dispatch refused: URL resolves to a private/internal address")
        return False
    try:
        method = config.get("method", "POST").upper()
        headers = {"Content-Type": "application/json"}
        auth_header = config.get("auth_header")
        if auth_header:
            headers["Authorization"] = auth_header

        async with httpx.AsyncClient(timeout=15) as client:
            if method == "POST":
                resp = await client.post(url, json=payload, headers=headers)
            else:
                resp = await client.request(method, url, json=payload, headers=headers)
            return 200 <= resp.status_code < 300
    except Exception as e:
        logger.error(f"Custom webhook dispatch failed: {e}")
        return False


# ======================== DISPATCHER ========================

CONNECTOR_MAP = {
    "slack": _send_slack,
    "pagerduty": _send_pagerduty,
    "sendgrid": _send_sendgrid,
    "custom_webhook": _send_custom_webhook,
}


async def dispatch_event(event_type: str, payload: Dict, min_severity: str = "warning") -> Dict:
    """
    Dispatch an event to all enabled notification integrations.
    event_type: 'threat', 'violation', 'incident', 'remediation'
    """
    sev_order = {"info": 0, "warning": 1, "high": 2, "critical": 3}
    event_sev = sev_order.get(payload.get("severity", "info"), 0)
    min_sev = sev_order.get(min_severity, 1)

    if event_sev < min_sev:
        return {"dispatched": 0, "skipped": "below_severity_threshold"}

    integrations = await _get_enabled_integrations(categories=["notification", "custom"])
    results = {"dispatched": 0, "failed": 0, "details": []}

    for integ in integrations:
        iid = integ.get("integration_id")
        connector_fn = CONNECTOR_MAP.get(iid)
        if not connector_fn:
            continue

        config = integ.get("config", {})
        success = await connector_fn(config, payload)
        await _log_dispatch(iid, event_type, success, payload.get("message", "")[:200])

        if success:
            results["dispatched"] += 1
        else:
            results["failed"] += 1
        results["details"].append({"integration": iid, "success": success})

    return results


async def dispatch_threat(threat: Dict) -> Dict:
    """Dispatch a security threat to all notification channels"""
    payload = {
        "id": threat.get("id", ""),
        "type": threat.get("type", "threat"),
        "title": f"Security Threat: {threat.get('type', 'unknown').replace('_', ' ').title()}",
        "message": threat.get("message", ""),
        "severity": threat.get("severity", "high"),
        "source_ip": threat.get("source_ip", ""),
        "user": threat.get("user", ""),
        "host": threat.get("host", ""),
        "timestamp": threat.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "source": "FalconOps Security Engine",
        "mitre_technique": threat.get("mitre_technique", ""),
    }
    return await dispatch_event("threat", payload)


async def dispatch_violation(violation: Dict) -> Dict:
    """Dispatch a health rule violation to all notification channels"""
    payload = {
        "id": violation.get("id", ""),
        "type": "health_rule_violation",
        "title": f"Health Rule Violation: {violation.get('rule_name', 'Unknown')}",
        "message": f"Metric {violation.get('metric', '')} breached threshold on {violation.get('source_name', '')}. Value: {violation.get('value', 'N/A')}",
        "severity": violation.get("severity", "warning"),
        "host": violation.get("source_name", ""),
        "timestamp": violation.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "source": "FalconOps Health Rules",
    }
    return await dispatch_event("violation", payload)


async def get_dispatch_logs(limit: int = 50) -> List[Dict]:
    """Get recent dispatch logs"""
    return await db.dispatch_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
