"""
FalconOps AI — AI Log Analyzer REST routes
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.database import db
from ..services import log_analyzer_service
from ..utils.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/log-analyzer", tags=["AI Log Analyzer"])

# Verdicts at these severities auto-enter the quarantine review queue
AUTO_QUARANTINE_SEVERITIES = {"High", "Critical"}

# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class AnalyzeIn(BaseModel):
    logs: str = Field(..., min_length=1, max_length=500_000,
                      description="Raw log text — any format, any length up to 500 KB")
    source: Optional[str] = Field(default="manual", max_length=80)
    use_cache: bool = True


class ExplainIn(BaseModel):
    error: str = Field(..., min_length=1, max_length=4000)
    context: Optional[str] = Field(default="", max_length=8000)


# ─────────────────────────────────────────────────────────────────────────────
# POST /analyze   — full pipeline + persist
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze(body: AnalyzeIn, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Clean → prioritize → chunk → LLM → cache → persist. Returns the verdict."""
    verdict = await log_analyzer_service.analyze_logs(
        body.logs, source=body.source or "manual",
        user_id=user.get("id"), use_cache=body.use_cache,
    )

    # Persist the analysis (skip the cached short-circuit duplicate)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user.get("id"),
        "user_email": user.get("email"),
        "source": body.source or "manual",
        "summary": verdict.get("summary"),
        "error_type": verdict.get("error_type"),
        "severity": verdict.get("severity"),
        "root_cause": verdict.get("root_cause"),
        "suggested_fix": verdict.get("suggested_fix"),
        "recurring_pattern": verdict.get("recurring_pattern"),
        "affected_components": verdict.get("affected_components", []),
        "key_lines": verdict.get("key_lines", []),
        "line_count": verdict.get("line_count", 0),
        "chunks": verdict.get("chunks", 0),
        "tokens_in": verdict.get("tokens_in", 0),
        "tokens_out": verdict.get("tokens_out", 0),
        "earliest_ts": verdict.get("earliest_ts"),
        "latest_ts": verdict.get("latest_ts"),
        "provider": verdict.get("provider"),
        "model": verdict.get("model"),
        "cached": verdict.get("cached", False),
        "pipeline_latency_ms": verdict.get("pipeline_latency_ms"),
        "raw_preview": (body.logs or "")[:1000],  # Keep a small preview only
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.log_analyses.insert_one(doc)
    doc.pop("_id", None)

    # ─── AUTO-QUARANTINE — feed Critical/High verdicts into the AI Observability
    # quarantine queue so analysts see them in a single unified inbox alongside
    # LLM-monitoring flags. The row is tagged source_type='log_analyzer' so the
    # UI can distinguish it. Existing quarantine list/release/block endpoints
    # work uniformly against these rows.
    if verdict.get("severity") in AUTO_QUARANTINE_SEVERITIES:
        try:
            qdoc = {
                "id": str(uuid.uuid4()),
                "event_id": doc["id"],           # references the log-analysis id
                "source_type": "log_analyzer",   # NEW discriminator
                "status": "pending",
                "verdict": (verdict.get("severity") or "").lower(),
                "model": verdict.get("model"),
                "source": body.source or "log_analyzer",
                "preview_input": (body.logs or "")[:300],
                "preview_output": (verdict.get("summary") or "")[:500],
                "flagged_agents": ["log_analyzer"],
                "error_type": verdict.get("error_type"),
                "root_cause": (verdict.get("root_cause") or "")[:600],
                "suggested_fix": (verdict.get("suggested_fix") or "")[:600],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": user.get("email") or user.get("id"),
                "auto_created": True,
            }
            await db.ai_monitoring_quarantine.insert_one(qdoc)
            doc["quarantined"] = True
            doc["quarantine_id"] = qdoc["id"]
        except Exception as e:
            logger.warning("auto-quarantine failed for analysis %s: %s", doc.get("id"), e)
            doc["quarantined"] = False
    else:
        doc["quarantined"] = False

    # ─── AUTO-REMEDIATE — if an admin enabled auto_remediate on the N8n config,
    # Critical/High verdicts fire the remediation webhook immediately.
    if verdict.get("severity") in AUTO_QUARANTINE_SEVERITIES:
        try:
            cfg = await _find_remediation_config(user.get("id"))
            if cfg and cfg.get("auto_remediate"):
                record = await _trigger_n8n_remediation(
                    doc, triggered_by=user.get("email") or "auto", auto=True, cfg=cfg)
                doc["remediation"] = record
        except Exception as e:
            logger.warning("auto-remediate failed for analysis %s: %s", doc.get("id"), e)

    return doc


# ─────────────────────────────────────────────────────────────────────────────
# N8n remediation
# ─────────────────────────────────────────────────────────────────────────────

async def _find_remediation_config(user_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Prefer the requester's own N8n config; fall back to any admin config
    that has a remediation webhook set (single-webhook-per-org is the norm)."""
    if user_id:
        own = await db.n8n_configs.find_one(
            {"user_id": user_id, "remediation_webhook_url": {"$nin": [None, ""]}}, {"_id": 0})
        if own:
            return own
    return await db.n8n_configs.find_one(
        {"remediation_webhook_url": {"$nin": [None, ""]}}, {"_id": 0})


async def _trigger_n8n_remediation(analysis: Dict[str, Any], *, triggered_by: str,
                                   auto: bool, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """POST the analysis verdict to the configured N8n remediation webhook and
    record the outcome on the analysis document."""
    webhook = cfg["remediation_webhook_url"]
    payload = {
        "event": "falconops.log_analyzer.remediate",
        "auto_triggered": auto,
        "triggered_by": triggered_by,
        "analysis": {k: analysis.get(k) for k in (
            "id", "severity", "error_type", "summary", "root_cause", "suggested_fix",
            "affected_components", "key_lines", "source", "earliest_ts", "latest_ts", "created_at")},
    }
    record: Dict[str, Any] = {
        "triggered_by": triggered_by,
        "auto": auto,
        "webhook_url": webhook,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.post(webhook, json=payload)
        record["webhook_status"] = r.status_code
        record["status"] = "sent" if r.status_code < 400 else "failed"
        if r.status_code >= 400:
            record["error"] = (r.text or "")[:300]
    except httpx.RequestError as e:
        record["status"] = "failed"
        record["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    await db.log_analyses.update_one({"id": analysis["id"]}, {"$set": {"remediation": record}})
    return record


@router.post("/analysis/{analysis_id}/remediate")
async def remediate(analysis_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """One-click 'Remediate via N8n': fires the configured N8n webhook with the
    verdict payload so an N8n workflow can execute the remediation runbook."""
    analysis = await db.log_analyses.find_one({"id": analysis_id}, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="analysis not found")
    cfg = await _find_remediation_config(user.get("id"))
    if not cfg:
        raise HTTPException(
            status_code=400,
            detail="No N8n remediation webhook configured. Set one in Automation → N8n Settings "
                   "(remediation_webhook_url) first.")
    record = await _trigger_n8n_remediation(
        analysis, triggered_by=user.get("email") or user.get("id") or "unknown",
        auto=False, cfg=cfg)
    if record["status"] != "sent":
        raise HTTPException(status_code=502, detail=f"N8n webhook failed: {record.get('error') or record.get('webhook_status')}")
    return {"status": "sent", "remediation": record}


# ─────────────────────────────────────────────────────────────────────────────
# GET /history   — recent analyses for the current user
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/history")
async def history(
    user: dict = Depends(require_auth),
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None, description="Filter by severity"),
) -> Dict[str, Any]:
    q: Dict[str, Any] = {"user_id": user.get("id")}
    if severity and severity in ("Low", "Medium", "High", "Critical"):
        q["severity"] = severity
    docs = await db.log_analyses.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"items": docs, "count": len(docs)}


# ─────────────────────────────────────────────────────────────────────────────
# GET /analysis/{id}   — fetch one
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    doc = await db.log_analyses.find_one(
        {"id": analysis_id, "user_id": user.get("id")}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Analysis not found")
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /analysis/{id}
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    result = await db.log_analyses.delete_one(
        {"id": analysis_id, "user_id": user.get("id")}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Analysis not found")
    return {"ok": True, "deleted_id": analysis_id}


# ─────────────────────────────────────────────────────────────────────────────
# POST /explain   — "Explain this error" feature
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/explain")
async def explain(body: ExplainIn, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    result = await log_analyzer_service.explain_error(body.error, context=body.context or "")
    # Light persistence for analytics
    try:
        await db.log_analyzer_explanations.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user.get("id"),
            "error": body.error[:500],
            "explanation": (result.get("explanation") or "")[:1500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass
    return result


# ─────────────────────────────────────────────────────────────────────────────
# GET /patterns   — top recurring patterns across recent analyses
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/patterns")
async def patterns(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Group recurring error_types from the user's recent history."""
    pipeline = [
        {"$match": {"user_id": user.get("id")}},
        {"$group": {
            "_id": "$error_type",
            "count": {"$sum": 1},
            "severities": {"$addToSet": "$severity"},
            "last_seen": {"$max": "$created_at"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 15},
    ]
    out: List[Dict[str, Any]] = []
    async for r in db.log_analyses.aggregate(pipeline):
        out.append({
            "error_type": r.get("_id") or "Unknown",
            "occurrences": r.get("count", 0),
            "severities": sorted(r.get("severities", []) or []),
            "last_seen": r.get("last_seen"),
        })
    return {"patterns": out, "count": len(out)}


# ─────────────────────────────────────────────────────────────────────────────
# GET /stats   — quick KPI snapshot for the tab header
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def stats(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    q = {"user_id": user.get("id")}
    total = await db.log_analyses.count_documents(q)
    crit  = await db.log_analyses.count_documents({**q, "severity": "Critical"})
    high  = await db.log_analyses.count_documents({**q, "severity": "High"})
    last = await db.log_analyses.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    return {
        "total_analyses": total,
        "critical_count": crit,
        "high_count": high,
        "last_analysis_at": last.get("created_at") if last else None,
        "last_severity": last.get("severity") if last else None,
    }
