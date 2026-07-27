"""
FalconOps AI — Multi-Agent AI Monitoring REST API
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..core.database import db
from ..services import ai_monitoring_service
from ..services.ai_monitoring_broadcaster import broadcaster
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/ai-monitoring", tags=["AI Monitoring"])


class EvaluateRequest(BaseModel):
    user_input: str = Field(..., description="Original user prompt / query")
    ai_output: str = Field(..., description="AI response to evaluate")
    context: Optional[str] = Field(None, description="Ground-truth context if available")
    latency_ms: float = Field(0)
    errored: bool = Field(False)
    error_message: Optional[str] = None
    model: str = ""
    provider: str = ""
    session_id: Optional[str] = None
    source: str = "manual"
    skip_llm_agents: bool = False


@router.post("/evaluate")
async def evaluate(req: EvaluateRequest, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Run all 10 AI monitoring agents on one LLM exchange (full LLM-judge coverage,
    unlike the sampled auto-instrumentation on real traffic). Persists + returns
    the full evaluation including a `verdict` of healthy/warning/critical."""
    event = await ai_monitoring_service.evaluate_exchange(
        user_input=req.user_input,
        ai_output=req.ai_output,
        context=req.context,
        latency_ms=req.latency_ms,
        errored=req.errored,
        error_message=req.error_message,
        model=req.model,
        provider=req.provider,
        session_id=req.session_id,
        user_id=user.get("id"),
        source=req.source,
        skip_llm_agents=req.skip_llm_agents,
    )
    return event


@router.get("/events")
async def list_events(
    user: dict = Depends(require_auth),
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None, description="healthy / warning / critical"),
    source: Optional[str] = None,
    hours: int = Query(24, ge=1, le=720),
) -> Dict[str, Any]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q: Dict[str, Any] = {"received_at": {"$gte": cutoff}}
    if status:
        q["verdict.system_status"] = status
    if source:
        q["source"] = source
    docs = await db.ai_monitoring_events.find(q, {"_id": 0}).sort("received_at", -1).limit(limit).to_list(length=limit)
    return {"events": docs, "count": len(docs)}


@router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    doc = await db.ai_monitoring_events.find_one({"id": event_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Event not found")
    return doc


@router.get("/dashboard")
async def dashboard(user: dict = Depends(require_auth),
                    hours: int = Query(24, ge=1, le=720)) -> Dict[str, Any]:
    """Aggregated dashboard stats for the AI Monitoring page."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    base = {"received_at": {"$gte": cutoff}}
    total = await db.ai_monitoring_events.count_documents(base)
    healthy = await db.ai_monitoring_events.count_documents({**base, "verdict.system_status": "healthy"})
    warning = await db.ai_monitoring_events.count_documents({**base, "verdict.system_status": "warning"})
    critical = await db.ai_monitoring_events.count_documents({**base, "verdict.system_status": "critical"})

    # Aggregated stats
    agg = await db.ai_monitoring_events.aggregate([
        {"$match": base},
        {"$group": {
            "_id": None,
            "total_tokens": {"$sum": "$tokens_total"},
            "total_cost_usd": {"$sum": "$estimated_cost_usd"},
            "avg_latency_ms": {"$avg": "$latency_ms"},
            "max_latency_ms": {"$max": "$latency_ms"},
            "errored_count": {"$sum": {"$cond": ["$errored", 1, 0]}},
        }},
    ]).to_list(length=1)
    summary = agg[0] if agg else {}
    summary.pop("_id", None)

    # By-agent flag counts
    by_agent_pipeline = [
        {"$match": base},
        {"$unwind": "$verdict.priority_issues"},
        {"$project": {"issue": "$verdict.priority_issues"}},
    ]
    by_agent: Dict[str, int] = {}
    async for doc in db.ai_monitoring_events.aggregate(by_agent_pipeline):
        issue = doc.get("issue", "")
        for k in ("hallucination", "injection", "cost", "performance", "quality"):
            if k in issue:
                by_agent[k] = by_agent.get(k, 0) + 1
                break

    # Top recent critical events
    recent_critical = await db.ai_monitoring_events.find(
        {**base, "verdict.system_status": "critical"}, {"_id": 0}
    ).sort("received_at", -1).limit(10).to_list(length=10)

    # By-model summary
    by_model_cur = db.ai_monitoring_events.aggregate([
        {"$match": base},
        {"$group": {
            "_id": "$model",
            "count": {"$sum": 1},
            "tokens": {"$sum": "$tokens_total"},
            "cost_usd": {"$sum": "$estimated_cost_usd"},
            "avg_latency_ms": {"$avg": "$latency_ms"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 8},
    ])
    by_model: List[Dict[str, Any]] = []
    async for r in by_model_cur:
        by_model.append({
            "model": r["_id"] or "(unset)",
            "count": r["count"],
            "tokens": r["tokens"],
            "cost_usd": round(r["cost_usd"], 4),
            "avg_latency_ms": round(r["avg_latency_ms"] or 0, 1),
        })

    return {
        "hours": hours,
        "totals": {
            "events": total,
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
        },
        "tokens": {
            "total": summary.get("total_tokens", 0),
            "cost_usd": round(summary.get("total_cost_usd") or 0, 4),
        },
        "performance": {
            "avg_latency_ms": round(summary.get("avg_latency_ms") or 0, 1),
            "max_latency_ms": round(summary.get("max_latency_ms") or 0, 1),
            "errored_count": summary.get("errored_count", 0),
        },
        "by_agent": by_agent,
        "by_model": by_model,
        "recent_critical": recent_critical,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health")
async def monitoring_health(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    total = await db.ai_monitoring_events.count_documents({})
    last = await db.ai_monitoring_events.find_one({}, {"_id": 0}, sort=[("received_at", -1)])
    policies = await db.ai_monitoring_policies.count_documents({"enabled": True})
    quarantine = await db.ai_monitoring_quarantine.count_documents({"status": "pending"})
    return {
        "events_total": total,
        "last_event_at": last.get("received_at") if last else None,
        "active_policies": policies,
        "pending_quarantine": quarantine,
        "live_subscribers": broadcaster.client_count,
        "agents": [
            {"id": "hallucination", "kind": "llm",         "description": "Detects fabricated / unsupported claims"},
            {"id": "injection",     "kind": "regex+llm",   "description": "Detects prompt-injection / jailbreak"},
            {"id": "cost",          "kind": "statistical", "description": "Token & cost anomalies (z-score)"},
            {"id": "performance",   "kind": "statistical", "description": "Latency & error anomalies (p95)"},
            {"id": "quality",       "kind": "llm",         "description": "Scores response usefulness 1-10"},
            {"id": "root_cause",    "kind": "llm",         "description": "Explains WHY when >= 1 agent flags"},
            {"id": "pii_leak",      "kind": "regex+luhn",  "description": "Outbound PII / secret leak guard"},
            {"id": "toxicity",      "kind": "llm",         "description": "Toxicity, hate, sexual, violence, bias scoring"},
            {"id": "policy",        "kind": "llm+rules",   "description": "Admin-defined custom policy compliance"},
            {"id": "drift",         "kind": "statistical", "description": "Response-length / token-ratio drift vs baseline"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Phase 35 — AI Observability v2: timeseries, drilldown, policies, quarantine
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/timeseries")
async def timeseries(
    user: dict = Depends(require_auth),
    hours: int = Query(24, ge=1, le=720),
    bucket_minutes: int = Query(15, ge=1, le=120),
) -> Dict[str, Any]:
    """Bucketed timeseries (per ``bucket_minutes``) of events / cost / verdict mix.
    Powers the Overview tab sparklines."""
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff = cutoff_dt.isoformat()
    base = {"received_at": {"$gte": cutoff}}

    # We store received_at as ISO string -> convert to date in pipeline
    pipeline = [
        {"$match": base},
        {"$addFields": {
            "_ts": {"$dateFromString": {"dateString": "$received_at"}},
        }},
        {"$addFields": {
            "_bucket": {
                "$toDate": {
                    "$subtract": [
                        {"$toLong": "$_ts"},
                        {"$mod": [{"$toLong": "$_ts"}, bucket_minutes * 60 * 1000]},
                    ]
                }
            }
        }},
        {"$group": {
            "_id": "$_bucket",
            "events": {"$sum": 1},
            "tokens": {"$sum": "$tokens_total"},
            "cost_usd": {"$sum": "$estimated_cost_usd"},
            "avg_latency_ms": {"$avg": "$latency_ms"},
            "max_latency_ms": {"$max": "$latency_ms"},
            "critical": {"$sum": {"$cond": [{"$eq": ["$verdict.system_status", "critical"]}, 1, 0]}},
            "warning":  {"$sum": {"$cond": [{"$eq": ["$verdict.system_status", "warning"]}, 1, 0]}},
            "healthy":  {"$sum": {"$cond": [{"$eq": ["$verdict.system_status", "healthy"]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]
    points: List[Dict[str, Any]] = []
    async for row in db.ai_monitoring_events.aggregate(pipeline):
        ts = row.pop("_id")
        points.append({
            "ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "events": row.get("events", 0),
            "tokens": row.get("tokens", 0),
            "cost_usd": round(row.get("cost_usd") or 0, 4),
            "avg_latency_ms": round(row.get("avg_latency_ms") or 0, 1),
            "max_latency_ms": round(row.get("max_latency_ms") or 0, 1),
            "critical": row.get("critical", 0),
            "warning":  row.get("warning", 0),
            "healthy":  row.get("healthy", 0),
        })

    return {
        "hours": hours,
        "bucket_minutes": bucket_minutes,
        "points": points,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


_AGENT_FLAG_FIELDS = {
    "hallucination": "hallucination_detected",
    "injection":     "is_attack",
    "cost":          "anomaly_detected",
    "performance":   "performance_issue",
    "quality":       None,
    "pii_leak":      "leak_detected",
    "toxicity":      "toxic",
    "policy":        "violated",
    "drift":         "drift_detected",
}


@router.get("/agents/{agent_id}")
async def agent_drilldown(
    agent_id: str,
    user: dict = Depends(require_auth),
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Per-agent drilldown: count, flagged count, severity mix, recent flagged events."""
    if agent_id not in _AGENT_FLAG_FIELDS:
        raise HTTPException(404, f"Unknown agent_id '{agent_id}'")

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    match = {"received_at": {"$gte": cutoff}, "agents.agent": agent_id}

    total = await db.ai_monitoring_events.count_documents(match)

    flag_field = _AGENT_FLAG_FIELDS[agent_id]
    if flag_field:
        flagged_q: Dict[str, Any] = {**match, "agents": {"$elemMatch": {"agent": agent_id, flag_field: True}}}
    else:
        # quality has no boolean — flagged when quality_score <= 4
        flagged_q = {**match, "agents": {"$elemMatch": {"agent": agent_id, "quality_score": {"$lte": 4}}}}

    flagged = await db.ai_monitoring_events.count_documents(flagged_q)

    # Severity mix from the embedded agent block
    sev_pipeline = [
        {"$match": match},
        {"$unwind": "$agents"},
        {"$match": {"agents.agent": agent_id}},
        {"$group": {"_id": "$agents.severity", "count": {"$sum": 1}}},
    ]
    sev_mix: Dict[str, int] = {}
    async for r in db.ai_monitoring_events.aggregate(sev_pipeline):
        sev_mix[(r.get("_id") or "low")] = r.get("count", 0)

    recent = await db.ai_monitoring_events.find(
        flagged_q, {"_id": 0}
    ).sort("received_at", -1).limit(limit).to_list(length=limit)

    return {
        "agent_id": agent_id,
        "hours": hours,
        "total_evaluations": total,
        "flagged_count": flagged,
        "flagged_rate": round((flagged / total) if total else 0, 4),
        "severity_mix": sev_mix,
        "recent_flagged": recent,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Policies CRUD ──────────────────────────────────────────────────────────

class PolicyIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    rule: str = Field(..., min_length=4, max_length=2000)
    severity: Literal["low", "medium", "high"] = Field("medium")
    enabled: bool = True
    tags: Optional[List[str]] = None


@router.get("/policies")
async def list_policies(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    docs = await db.ai_monitoring_policies.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    return {"policies": docs, "count": len(docs)}


@router.post("/policies")
async def create_policy(p: PolicyIn, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(403, "Admin role required to create policies")
    doc = {
        "id": str(uuid.uuid4()),
        "name": p.name.strip(),
        "rule": p.rule.strip(),
        "severity": p.severity,
        "enabled": bool(p.enabled),
        "tags": [t.strip() for t in (p.tags or []) if t.strip()][:10],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("email") or user.get("id"),
    }
    await db.ai_monitoring_policies.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, p: PolicyIn, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(403, "Admin role required")
    updates = {
        "name": p.name.strip(),
        "rule": p.rule.strip(),
        "severity": p.severity,
        "enabled": bool(p.enabled),
        "tags": [t.strip() for t in (p.tags or []) if t.strip()][:10],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user.get("email") or user.get("id"),
    }
    result = await db.ai_monitoring_policies.update_one({"id": policy_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Policy not found")
    doc = await db.ai_monitoring_policies.find_one({"id": policy_id}, {"_id": 0})
    return doc


@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(403, "Admin role required")
    result = await db.ai_monitoring_policies.delete_one({"id": policy_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Policy not found")
    return {"ok": True, "deleted_id": policy_id}


# ─── Quarantine queue ────────────────────────────────────────────────────────

@router.get("/quarantine")
async def list_quarantine(
    user: dict = Depends(require_auth),
    status: str = Query("pending", description="pending|released|blocked|all"),
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    q: Dict[str, Any] = {} if status == "all" else {"status": status}
    docs = await db.ai_monitoring_quarantine.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"items": docs, "count": len(docs)}


@router.post("/quarantine/{event_id}")
async def quarantine_event(event_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Manually quarantine a flagged event so it sits in an admin-review queue."""
    event = await db.ai_monitoring_events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(404, "Event not found")
    if user.get("role") not in ("admin", "owner", "analyst"):
        raise HTTPException(403, "Insufficient role to quarantine")
    existing = await db.ai_monitoring_quarantine.find_one({"event_id": event_id})
    if existing:
        existing.pop("_id", None)
        return {"already_quarantined": True, "item": existing}
    doc = {
        "id": str(uuid.uuid4()),
        "event_id": event_id,
        "status": "pending",
        "verdict": event.get("verdict", {}).get("system_status"),
        "model": event.get("model"),
        "source": event.get("source"),
        "preview_input": (event.get("user_input") or "")[:300],
        "preview_output": (event.get("ai_output") or "")[:500],
        "flagged_agents": [a.get("agent") for a in event.get("agents", []) if a],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("email") or user.get("id"),
    }
    await db.ai_monitoring_quarantine.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/quarantine/{event_id}/release")
async def release_quarantine(event_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(403, "Admin role required to release")
    result = await db.ai_monitoring_quarantine.update_one(
        {"event_id": event_id},
        {"$set": {
            "status": "released",
            "released_at": datetime.now(timezone.utc).isoformat(),
            "released_by": user.get("email") or user.get("id"),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Quarantine item not found")
    return {"ok": True, "event_id": event_id, "status": "released"}


@router.post("/quarantine/{event_id}/block")
async def block_quarantine(event_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(403, "Admin role required to block")
    result = await db.ai_monitoring_quarantine.update_one(
        {"event_id": event_id},
        {"$set": {
            "status": "blocked",
            "blocked_at": datetime.now(timezone.utc).isoformat(),
            "blocked_by": user.get("email") or user.get("id"),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Quarantine item not found")
    return {"ok": True, "event_id": event_id, "status": "blocked"}


# ─── Live WebSocket feed ─────────────────────────────────────────────────────
# Auth + hello-message hooks assigned onto the shared BroadcastManager singleton
# at import time (they need _AGENT_FLAG_FIELDS, which lives in this module).

async def _live_authenticate(ws: WebSocket) -> bool:
    """Lightweight token gate — pass `?token=<jwt>` to authenticate."""
    token = ws.query_params.get("token") or ""
    if not token:
        await ws.send_json({"type": "error", "error": "missing token"})
        await ws.close()
        return False
    try:
        import jwt
        from ..core.config import JWT_SECRET, JWT_ALGORITHM
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        await ws.send_json({"type": "error", "error": "invalid token"})
        await ws.close()
        return False
    return True


async def _live_hello(ws: WebSocket) -> Dict[str, Any]:
    return {
        "type": "ai_monitoring.hello",
        "subscribers": broadcaster.client_count,
        "agents": list(_AGENT_FLAG_FIELDS.keys()) + ["root_cause"],
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


broadcaster.authenticate = _live_authenticate
broadcaster.on_connect = _live_hello


@router.websocket("/live")
async def live_feed(ws: WebSocket):
    """WebSocket: every new AI monitoring event broadcasts here."""
    if not await broadcaster.connect(ws):
        return
    try:
        while True:
            # Keep the socket alive — we don't actually need client messages
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await broadcaster.disconnect(ws)
