"""
FalconOps AI — Automation Templates
Curated, ready-to-import N8n workflow JSON files for common enterprise
observability integrations. Each template forwards events from a 3rd-party
source (AppDynamics, Elastic, PagerDuty, Splunk, Datadog) into FalconOps'
SOC ingestion engine for normalisation + AI triage.
"""
from datetime import datetime, timezone
import json
import logging
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..utils.auth import require_auth, require_admin
from ..core.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/automation-templates", tags=["AI Automation Templates"])


# ─────────────────────────────────────────────────────
# Helper — build a complete N8n workflow JSON for any source webhook
# ─────────────────────────────────────────────────────

def _n8n_workflow(*, name: str, source_label: str, webhook_path: str,
                  source_emoji: str, normalize_expr: Dict) -> Dict:
    """Build a working N8n workflow JSON: Webhook → Function (normalize) → HTTP
    POST to FalconOps SOC ingest endpoint."""
    return {
        "name": name,
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": webhook_path,
                    "responseMode": "lastNode",
                    "options": {},
                },
                "id": "webhook-node",
                "name": f"{source_emoji} {source_label} Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [240, 300],
                "webhookId": webhook_path,
            },
            {
                "parameters": {
                    "functionCode": (
                        "// Normalize " + source_label + " event into FalconOps SOC schema\n"
                        "const e = items[0].json;\n"
                        f"const service  = {normalize_expr['service']};\n"
                        f"const alert    = {normalize_expr['alert']};\n"
                        f"const severity = {normalize_expr['severity']};\n"
                        f"const host     = {normalize_expr['host']};\n"
                        "return [{json: {\n"
                        f"  source: '{source_label.lower().replace(' ', '-')}',\n"
                        "  service: service || 'unknown',\n"
                        "  alert: alert || 'Unknown alert',\n"
                        "  severity: (severity || 'warning').toLowerCase(),\n"
                        "  host: host || null,\n"
                        "  timestamp: new Date().toISOString(),\n"
                        "  raw_payload: e,\n"
                        "}}];"
                    ),
                },
                "id": "normalize-node",
                "name": "Normalize → FalconOps Schema",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [480, 300],
            },
            {
                "parameters": {
                    "url": "={{$env.FALCONOPS_URL}}/api/soc-engine/ingest",
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": "={{$json}}",
                    "options": {
                        "timeout": 10000,
                    },
                },
                "id": "ingest-node",
                "name": "POST to FalconOps SOC Ingest",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [720, 300],
            },
        ],
        "connections": {
            f"{source_emoji} {source_label} Webhook": {
                "main": [[{"node": "Normalize → FalconOps Schema", "type": "main", "index": 0}]]
            },
            "Normalize → FalconOps Schema": {
                "main": [[{"node": "POST to FalconOps SOC Ingest", "type": "main", "index": 0}]]
            },
        },
        "active": False,
        "settings": {"executionOrder": "v1"},
        "versionId": "1",
        "id": webhook_path,
        "meta": {
            "templateCredsSetupCompleted": False,
            "instanceId": "falconops-ai",
            "createdFor": "FalconOps AI Automation",
        },
        "tags": [{"name": "falconops"}, {"name": source_label.lower().replace(" ", "-")}],
    }


# ─────────────────────────────────────────────────────
# Templates registry
# ─────────────────────────────────────────────────────

TEMPLATES: List[Dict] = [
    {
        "id": "n8n-appdynamics-to-falconops",
        "name": "AppDynamics → FalconOps",
        "category": "n8n",
        "source": "AppDynamics",
        "source_logo": "https://www.appdynamics.com/c/r/appdynamics/master/_jcr_content/header/logo.img.png/1666290048810.png",
        "description": "Forward AppDynamics events (BT slow, health rule violations, anomalies) into FalconOps SOC engine for AI triage, correlation, and unified incident response.",
        "tags": ["apm", "events", "alerting", "n8n"],
        "difficulty": "Easy (5 min)",
        "use_cases": [
            "Receive AppD health-rule violations as FalconOps incidents",
            "Trigger AI RCA + remediation playbooks automatically",
            "Unify AppD APM events with logs, traces, and security signals",
        ],
        "setup_steps": [
            "In N8n, click `Import from File` and paste this JSON",
            "Activate the workflow — N8n will give you a webhook URL `https://<n8n-host>/webhook/appdynamics`",
            "In AppDynamics → Alert & Respond → Actions → HTTP Request Templates, create a new template pointing at that webhook",
            "Bind the template to your AppD policies — events flow into FalconOps within seconds",
        ],
        "env_vars": ["FALCONOPS_URL — your FalconOps deployment URL"],
        "workflow": _n8n_workflow(
            name="AppDynamics → FalconOps",
            source_label="AppDynamics",
            webhook_path="appdynamics",
            source_emoji="🔭",
            normalize_expr={
                "service": "e.affectedEntity || e.application || e.businessTransaction",
                "alert": "e.healthRuleName || e.eventType || e.summary",
                "severity": "(e.severity || 'WARNING').toLowerCase().includes('critical') ? 'critical' : 'warning'",
                "host": "e.node || e.machineName || e.host",
            },
        ),
    },
    {
        "id": "n8n-elastic-to-falconops",
        "name": "Elastic / Kibana → FalconOps",
        "category": "n8n",
        "source": "Elastic",
        "source_logo": "https://upload.wikimedia.org/wikipedia/commons/f/f4/Elasticsearch_logo.svg",
        "description": "Pipe Elastic Watcher / Kibana alert payloads into FalconOps so security signals and APM anomalies share a single AI brain.",
        "tags": ["siem", "logs", "watcher", "kibana", "n8n"],
        "difficulty": "Easy (5 min)",
        "use_cases": [
            "Forward Kibana alert rule output (security, ML jobs, threshold) to FalconOps",
            "Correlate Elastic detection-rule hits with traces + monitors",
            "AI auto-triages noisy log alerts via Noise Reducer",
        ],
        "setup_steps": [
            "Import this JSON into N8n",
            "Activate the workflow to receive your webhook URL `https://<n8n-host>/webhook/elastic`",
            "In Kibana → Stack Management → Rules → Connectors, create a Webhook connector pointing at it (POST, application/json)",
            "Bind any Kibana / Elastic Security rule to that connector — payloads route via N8n → FalconOps",
        ],
        "env_vars": ["FALCONOPS_URL — your FalconOps deployment URL"],
        "workflow": _n8n_workflow(
            name="Elastic → FalconOps",
            source_label="Elastic",
            webhook_path="elastic",
            source_emoji="🪵",
            normalize_expr={
                "service": "e.kibana?.alert?.rule?.consumer || e.service?.name || e['service.name']",
                "alert": "e.kibana?.alert?.rule?.name || e.rule?.name || e.message || e['rule.name']",
                "severity": "(e.kibana?.alert?.severity || e['event.severity'] || 'medium').toString().toLowerCase()",
                "host": "e.host?.name || e['host.name'] || e.agent?.hostname",
            },
        ),
    },
    {
        "id": "n8n-pagerduty-to-falconops",
        "name": "PagerDuty → FalconOps",
        "category": "n8n",
        "source": "PagerDuty",
        "source_logo": "https://www.pagerduty.com/wp-content/uploads/2017/09/cropped-pagerduty-logo-green-1-32x32.png",
        "description": "Sync PagerDuty incidents into FalconOps for AI RCA + remediation suggestions, while keeping PagerDuty as the human-on-call surface.",
        "tags": ["incident-mgmt", "alerting", "n8n"],
        "difficulty": "Easy (3 min)",
        "use_cases": [
            "Automatic AI RCA on every PagerDuty incident",
            "Pull traces, metrics, logs around the incident time-window",
            "Push recommended actions back into the PagerDuty timeline",
        ],
        "setup_steps": [
            "Import this JSON into N8n + activate",
            "In PagerDuty → Services → your service → Extensions → Add `Generic Webhook V3`",
            "Point it at the N8n webhook URL `https://<n8n-host>/webhook/pagerduty`",
            "Trigger any PagerDuty incident — FalconOps will receive + auto-RCA it",
        ],
        "env_vars": ["FALCONOPS_URL — your FalconOps deployment URL"],
        "workflow": _n8n_workflow(
            name="PagerDuty → FalconOps",
            source_label="PagerDuty",
            webhook_path="pagerduty",
            source_emoji="🚨",
            normalize_expr={
                "service": "e.event?.data?.service?.summary || e.incident?.service?.summary",
                "alert": "e.event?.data?.summary || e.incident?.summary || e.incident?.title",
                "severity": "(e.event?.data?.urgency || e.incident?.urgency || 'high')",
                "host": "e.event?.data?.custom_details?.host || null",
            },
        ),
    },
    {
        "id": "n8n-splunk-to-falconops",
        "name": "Splunk → FalconOps",
        "category": "n8n",
        "source": "Splunk",
        "source_logo": "https://upload.wikimedia.org/wikipedia/commons/4/4f/Splunk_logo.svg",
        "description": "Stream Splunk saved-search alerts into FalconOps. Pairs with Splunk for storage + queries, but uses FalconOps' AI Copilot for triage and auto-remediation.",
        "tags": ["siem", "logs", "search", "n8n"],
        "difficulty": "Moderate (10 min)",
        "use_cases": [
            "Route high-severity Splunk saved-search alerts to FalconOps",
            "AI auto-correlation between Splunk events and FalconOps traces",
            "Enrich Splunk alerts with FalconOps' dependency topology",
        ],
        "setup_steps": [
            "Import this JSON into N8n + activate",
            "In Splunk → Settings → Alert actions → Webhook, enable the webhook alert action",
            "On your saved-search alerts, add the webhook action pointing at `https://<n8n-host>/webhook/splunk`",
            "Save — Splunk now forwards every triggered alert to FalconOps",
        ],
        "env_vars": ["FALCONOPS_URL — your FalconOps deployment URL"],
        "workflow": _n8n_workflow(
            name="Splunk → FalconOps",
            source_label="Splunk",
            webhook_path="splunk",
            source_emoji="🔍",
            normalize_expr={
                "service": "e.result?.host || e.result?.source || e.app",
                "alert": "e.search_name || e.result?.search_name || e.result?._raw?.slice?.(0, 200)",
                "severity": "(e.result?.severity || e.severity || 'warning')",
                "host": "e.result?.host || e.host",
            },
        ),
    },
    {
        "id": "n8n-datadog-to-falconops",
        "name": "Datadog → FalconOps",
        "category": "n8n",
        "source": "Datadog",
        "source_logo": "https://imgix.datadoghq.com/img/dd_logo_70x75.png",
        "description": "Forward Datadog monitor alerts into FalconOps for AI noise reduction, correlation, and unified action proposals.",
        "tags": ["apm", "monitors", "alerting", "n8n"],
        "difficulty": "Easy (5 min)",
        "use_cases": [
            "Merge Datadog alerts with on-prem metrics in one pane",
            "AI fingerprint + suppress duplicate Datadog noise",
            "Trigger FalconOps auto-remediation playbooks from Datadog alerts",
        ],
        "setup_steps": [
            "Import this JSON into N8n + activate",
            "In Datadog → Integrations → Webhooks, create a new webhook pointing at `https://<n8n-host>/webhook/datadog`",
            "In each monitor's notification body, include `@webhook-<name>` to route to FalconOps",
        ],
        "env_vars": ["FALCONOPS_URL — your FalconOps deployment URL"],
        "workflow": _n8n_workflow(
            name="Datadog → FalconOps",
            source_label="Datadog",
            webhook_path="datadog",
            source_emoji="🐶",
            normalize_expr={
                "service": "e.org?.name || e.snapshot || e.aggreg_key || e.service",
                "alert": "e.title || e.alert_title || e.event_title",
                "severity": "(e.priority || e.alert_type || 'warning').toString().toLowerCase()",
                "host": "e.host || e.hostname",
            },
        ),
    },
]


# ─────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────

@router.get("/")
async def list_templates(user: dict = Depends(require_auth),
                         category: str = Query(None)):
    """Return curated list of importable automation templates."""
    out = [
        {k: v for k, v in t.items() if k != "workflow"}  # exclude heavy json
        for t in TEMPLATES
        if not category or t["category"] == category
    ]
    return {"templates": out, "total": len(out)}


@router.get("/{template_id}")
async def get_template(template_id: str, user: dict = Depends(require_auth)):
    """Return the full template incl. the N8n workflow JSON."""
    t = next((x for x in TEMPLATES if x["id"] == template_id), None)
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.get("/{template_id}/download")
async def download_template(template_id: str, request: Request,
                            user: dict = Depends(require_auth)):
    """Download the N8n workflow JSON ready for import.
    Substitutes ${{FALCONOPS_URL}} with the inbound origin so the workflow
    works out-of-the-box without manually setting an env var."""
    t = next((x for x in TEMPLATES if x["id"] == template_id), None)
    if not t:
        raise HTTPException(404, "Template not found")

    wf = json.loads(json.dumps(t["workflow"]))  # deep copy
    # Resolve falconops_url from the requesting Host
    origin = str(request.base_url).rstrip("/")
    resolved = origin
    try:
        for n in wf.get("nodes", []):
            url = (n.get("parameters") or {}).get("url")
            if isinstance(url, str) and "FALCONOPS_URL" in url:
                n["parameters"]["url"] = url.replace("{{$env.FALCONOPS_URL}}", resolved)
    except Exception as e:
        logger.warning("template URL substitution failed: %s", e)

    body = json.dumps(wf, indent=2)
    # Record usage
    try:
        await db.automation_template_downloads.insert_one({
            "template_id": template_id,
            "user_email": user.get("email"),
            "user_id": user.get("id"),
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "resolved_falconops_url": resolved,
        })
    except Exception:
        pass
    return PlainTextResponse(
        body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{template_id}.json"',
        },
    )


@router.get("/stats/usage")
async def usage_stats(user: dict = Depends(require_admin)):
    """Admin: show how many times each template has been downloaded."""
    pipeline = [
        {"$group": {"_id": "$template_id", "downloads": {"$sum": 1},
                    "last_downloaded": {"$max": "$downloaded_at"}}},
        {"$sort": {"downloads": -1}},
    ]
    out: List[Dict] = []
    async for r in db.automation_template_downloads.aggregate(pipeline):
        out.append({
            "template_id": r["_id"],
            "downloads": r["downloads"],
            "last_downloaded": r["last_downloaded"],
        })
    return {"usage": out}


# ─────────────────────────────────────────────────────────────────────────────
# N8n REST API — auto-import workflow directly into the operator's N8n instance
# ─────────────────────────────────────────────────────────────────────────────

class N8nConfig(BaseModel):
    base_url: str = Field(..., description="N8n instance base URL e.g. https://n8n.example.com")
    api_key: str = Field(..., description="N8n API key (Settings → n8n API → Create an API key)")
    activate_on_import: bool = Field(True)
    remediation_webhook_url: Optional[str] = Field(
        None, description="N8n webhook URL that receives remediation triggers from FalconOps (e.g. AI Log Analyzer)")
    auto_remediate: bool = Field(
        False, description="Auto-fire the remediation webhook for Critical/High log-analyzer verdicts")


def _validate_n8n_base_url(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        raise HTTPException(400, "base_url is required")
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(400, f"base_url must be a valid http(s) URL, got {raw!r}")
    return raw.rstrip("/")


@router.post("/n8n/config")
async def save_n8n_config(cfg: N8nConfig, user: dict = Depends(require_admin)):
    """Save a per-admin N8n instance + API key for one-click pushes.
    Stored encrypted-at-rest is out of scope here — the field is admin-only
    and only echoed back masked."""
    base = _validate_n8n_base_url(cfg.base_url)
    if not cfg.api_key or len(cfg.api_key) < 8:
        raise HTTPException(400, "api_key looks invalid")
    await db.n8n_configs.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "user_id": user["id"],
            "user_email": user.get("email"),
            "base_url": base,
            "api_key": cfg.api_key,
            "activate_on_import": cfg.activate_on_import,
            "remediation_webhook_url": (cfg.remediation_webhook_url or "").strip() or None,
            "auto_remediate": bool(cfg.auto_remediate),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "base_url": base, "api_key_masked": cfg.api_key[:4] + "…" + cfg.api_key[-4:]}


@router.get("/n8n/config")
async def get_n8n_config(user: dict = Depends(require_admin)):
    """Return saved N8n config (api_key masked)."""
    doc = await db.n8n_configs.find_one({"user_id": user["id"]}, {"_id": 0})
    if not doc:
        return {"configured": False}
    key = doc.get("api_key", "")
    return {
        "configured": True,
        "base_url": doc.get("base_url"),
        "api_key_masked": (key[:4] + "…" + key[-4:]) if len(key) >= 8 else "***",
        "activate_on_import": doc.get("activate_on_import", True),
        "remediation_webhook_url": doc.get("remediation_webhook_url"),
        "auto_remediate": doc.get("auto_remediate", False),
        "updated_at": doc.get("updated_at"),
    }


@router.post("/n8n/test")
async def test_n8n_connection(cfg: Optional[N8nConfig] = None,
                              user: dict = Depends(require_admin)):
    """Smoke-test the operator's N8n instance: `GET /api/v1/workflows?limit=1`.
    If `cfg` body provided, use it (un-saved test); otherwise use stored config."""
    if cfg:
        base = _validate_n8n_base_url(cfg.base_url)
        key = cfg.api_key
    else:
        stored = await db.n8n_configs.find_one({"user_id": user["id"]}, {"_id": 0})
        if not stored:
            raise HTTPException(400, "No N8n config saved — POST one to /n8n/config first or pass body")
        base, key = stored["base_url"], stored["api_key"]

    url = f"{base}/api/v1/workflows?limit=1"
    headers = {"X-N8N-API-KEY": key, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
        if r.status_code in (401, 403):
            return {"ok": False, "status": r.status_code, "error": "Auth failed — check API key", "url": url}
        if r.status_code >= 400:
            return {"ok": False, "status": r.status_code, "error": (r.text or "")[:200], "url": url}
        data = r.json()
        return {
            "ok": True, "status": r.status_code,
            "base_url": base,
            "workflows_seen": len(data.get("data", []) if isinstance(data, dict) else (data or [])),
        }
    except httpx.RequestError as e:
        return {"ok": False, "error": f"Network error: {type(e).__name__}: {str(e)[:200]}", "url": url}


def _prepare_workflow_payload(template: dict, origin: str) -> dict:
    """Deep-copy the template, substitute the FALCONOPS_URL placeholder in all
    node URL parameters, and trim the dict to only the keys the N8n create-workflow
    endpoint accepts."""
    wf = json.loads(json.dumps(template["workflow"]))
    for node in wf.get("nodes", []):
        url = (node.get("parameters") or {}).get("url")
        if isinstance(url, str) and "FALCONOPS_URL" in url:
            node["parameters"]["url"] = url.replace("{{$env.FALCONOPS_URL}}", origin)
    return {k: v for k, v in wf.items()
            if k in ("name", "nodes", "connections", "settings", "tags")}, wf


async def _n8n_create_workflow(base: str, headers: dict, payload: dict) -> "httpx.Response":
    """POST the workflow to N8n. On 4xx, retry once without the 'tags' field
    (older N8n versions reject it). Raises HTTPException on network errors."""
    create_url = f"{base}/api/v1/workflows"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.post(create_url, json=payload, headers=headers)
    except httpx.RequestError as e:
        raise HTTPException(502, f"Network error reaching N8n: {type(e).__name__}: {str(e)[:200]}")

    if r.status_code >= 400 and "tags" in payload:
        retry_payload = {k: v for k, v in payload.items() if k != "tags"}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                r = await client.post(create_url, json=retry_payload, headers=headers)
        except httpx.RequestError as e:
            raise HTTPException(502, f"Network error on retry: {str(e)[:200]}")
    return r


async def _n8n_activate_workflow(base: str, headers: dict, workflow_id: str) -> bool:
    """Activate a workflow. N8n REST shape varies across versions —
    try POST .../activate first, then PATCH active=true. Returns True on success."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            ar = await client.post(f"{base}/api/v1/workflows/{workflow_id}/activate", headers=headers)
        if ar.status_code < 400:
            return True
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            ar2 = await client.patch(
                f"{base}/api/v1/workflows/{workflow_id}",
                headers=headers, json={"active": True},
            )
        return ar2.status_code < 400
    except httpx.RequestError:
        return False


def _extract_webhook_url(base: str, original_wf: dict) -> Optional[str]:
    """Look for a webhook node in the workflow and return its public URL."""
    path = next(
        (n["parameters"].get("path") for n in original_wf.get("nodes", [])
         if n.get("type") == "n8n-nodes-base.webhook"),
        None,
    )
    return f"{base}/webhook/{path}" if path else None


@router.post("/{template_id}/push-to-n8n")
async def push_to_n8n(template_id: str, request: Request, user: dict = Depends(require_admin)):
    """Auto-import a FalconOps template into the operator's N8n instance via
    `POST {base_url}/api/v1/workflows`. Substitutes `FALCONOPS_URL` with the
    inbound origin so the workflow works immediately.

    Refactored from cyclomatic-complexity 25 → ~6 by extracting the 4 distinct
    responsibilities into `_prepare_workflow_payload`, `_n8n_create_workflow`,
    `_n8n_activate_workflow`, and `_extract_webhook_url`.
    """
    stored = await db.n8n_configs.find_one({"user_id": user["id"]}, {"_id": 0})
    if not stored:
        raise HTTPException(400, "No N8n config saved — go to N8n Settings tab first.")

    template = next((x for x in TEMPLATES if x["id"] == template_id), None)
    if not template:
        raise HTTPException(404, "Template not found")

    origin = str(request.base_url).rstrip("/")
    wf_payload, original_wf = _prepare_workflow_payload(template, origin)

    base = stored["base_url"]
    headers = {
        "X-N8N-API-KEY": stored["api_key"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    r = await _n8n_create_workflow(base, headers, wf_payload)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"N8n rejected the import: {(r.text or '')[:400]}")

    created = r.json() or {}
    workflow_id = created.get("id") or (created.get("data") or {}).get("id")

    activated = False
    if stored.get("activate_on_import", True) and workflow_id:
        activated = await _n8n_activate_workflow(base, headers, workflow_id)

    await db.automation_template_downloads.insert_one({
        "template_id": template_id,
        "user_email": user.get("email"),
        "user_id": user.get("id"),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "delivery": "n8n_api",
        "n8n_workflow_id": workflow_id,
        "activated": activated,
    })

    webhook_url = _extract_webhook_url(base, original_wf)
    return {
        "ok": True,
        "workflow_id": workflow_id,
        "activated": activated,
        "n8n_base_url": base,
        "webhook_url": webhook_url,
        "next_step": (
            f"Point your source tool's webhook at:  {webhook_url}"
            if webhook_url else "Open N8n to find the webhook URL for this workflow."
        ),
    }

