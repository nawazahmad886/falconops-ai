"""
FalconOps AI — Multi-Agent AI Monitoring REST API
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Literal, Tuple

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..core.database import db
from ..services import ai_monitoring_service
from ..services.ai_monitoring_broadcaster import broadcaster
from ..utils.auth import require_auth

router = APIRouter(prefix="/api/ai-monitoring", tags=["AI Monitoring"])


def _tid(user: dict) -> Optional[str]:
    return (user or {}).get("tenant_id")


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
        tenant_id=_tid(user),
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
    tid = _tid(user)
    if tid:
        q["tenant_id"] = tid
    if status:
        q["verdict.system_status"] = status
    if source:
        q["source"] = source
    docs = await db.ai_monitoring_events.find(q, {"_id": 0}).sort("received_at", -1).limit(limit).to_list(length=limit)
    return {"events": docs, "count": len(docs)}


@router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    q: Dict[str, Any] = {"id": event_id}
    tid = _tid(user)
    if tid:
        q["tenant_id"] = tid
    doc = await db.ai_monitoring_events.find_one(q, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Event not found")
    return doc


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    comment: Optional[str] = Field(None, max_length=1000)


@router.post("/events/{event_id}/feedback")
async def submit_feedback(event_id: str, req: FeedbackRequest, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Real human signal on a specific AI output — the gap the automated LLM-judge
    quality/hallucination agents can't fill (see ai_monitoring_service.py's module
    docstring). Ties directly to event_id so bad-answer patterns can be mined from
    actual usage instead of only synthetic evaluation."""
    q: Dict[str, Any] = {"id": event_id}
    tid = _tid(user)
    if tid:
        q["tenant_id"] = tid
    feedback = {
        "rating": req.rating, "comment": req.comment,
        "user_id": user.get("id"), "user_email": user.get("email"),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.ai_monitoring_events.update_one(q, {"$set": {"feedback": feedback}})
    if result.matched_count == 0:
        raise HTTPException(404, "Event not found")
    return {"ok": True, "feedback": feedback}


@router.get("/dashboard")
async def dashboard(user: dict = Depends(require_auth),
                    hours: int = Query(24, ge=1, le=720)) -> Dict[str, Any]:
    """Aggregated dashboard stats for the AI Monitoring page."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    base: Dict[str, Any] = {"received_at": {"$gte": cutoff}}
    tid = _tid(user)
    if tid:
        base["tenant_id"] = tid
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
            # Mongo's $sum silently treats a missing/null estimated_cost_usd as 0 —
            # that would make total_cost_usd look complete when it's actually
            # undercounting calls to unpriced models. Count them separately so
            # the UI can say so instead of presenting a quietly-wrong total.
            "unpriced_count": {"$sum": {"$cond": [{"$eq": ["$estimated_cost_usd", None]}, 1, 0]}},
            "estimated_tokens_count": {"$sum": {"$cond": [{"$eq": ["$tokens_source", "estimated"]}, 1, 0]}},
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
            # Honesty flags for the UI: cost_usd above excludes calls to models with
            # no entry in the llm_pricing registry (llm_pricing_service.py), and
            # "total" may partly be char-count
            # estimates rather than provider-reported usage — surface both instead
            # of letting the totals look more precise than they are.
            "unpriced_events": summary.get("unpriced_count", 0),
            "estimated_token_events": summary.get("estimated_tokens_count", 0),
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
    base: Dict[str, Any] = {"received_at": {"$gte": cutoff}}
    tid = _tid(user)
    if tid:
        base["tenant_id"] = tid

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


def _percentiles(values: List[float]) -> Dict[str, float]:
    """p50/p90/p95/p99 + avg/max over a raw list of latency_ms samples."""
    arr = np.array(values, dtype=float)
    p50, p90, p95, p99 = np.percentile(arr, [50, 90, 95, 99])
    return {
        "p50": round(float(p50), 1), "p90": round(float(p90), 1),
        "p95": round(float(p95), 1), "p99": round(float(p99), 1),
        "avg": round(float(np.mean(arr)), 1), "max": round(float(np.max(arr)), 1),
    }


@router.get("/latency-stats")
async def latency_stats(
    user: dict = Depends(require_auth),
    hours: int = Query(24, ge=1, le=720),
    bucket_minutes: int = Query(15, ge=1, le=120),
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Real p50/p90/p95/p99 latency — computed from the same latency_ms already
    stored on every ai_monitoring_events doc (no new collection, no dual-write).
    Reuses /timeseries's exact bucketing pattern, swapping the $avg/$max
    accumulator for $push so percentiles can be computed in Python."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    base: Dict[str, Any] = {"received_at": {"$gte": cutoff}, "latency_ms": {"$gt": 0}}
    tid = _tid(user)
    if tid:
        base["tenant_id"] = tid
    if model:
        base["model"] = model
    if provider:
        base["provider"] = provider

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
        {"$group": {"_id": "$_bucket", "latencies": {"$push": "$latency_ms"}}},
        {"$sort": {"_id": 1}},
    ]

    points: List[Dict[str, Any]] = []
    all_latencies: List[float] = []
    async for row in db.ai_monitoring_events.aggregate(pipeline):
        vals = row.get("latencies") or []
        if not vals:
            continue
        all_latencies.extend(vals)
        stats = _percentiles(vals)
        ts = row["_id"]
        points.append({
            "ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "count": len(vals),
            **stats,
        })

    overall = _percentiles(all_latencies) if all_latencies else {
        "p50": None, "p90": None, "p95": None, "p99": None, "avg": None, "max": None,
    }
    overall["sample_size"] = len(all_latencies)

    return {
        "hours": hours,
        "bucket_minutes": bucket_minutes,
        "model": model,
        "provider": provider,
        "points": points,
        "overall": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# GPU Monitoring — reads db.metrics_timeseries, populated by OneAgent's "gpu"
# plugin via the existing schema-less POST /api/ingest/metrics (no ingestion
# changes needed — see oneagent/pkg/plugins/gpu/gpu.go).
# ═════════════════════════════════════════════════════════════════════════════

GPU_METRICS: Dict[str, str] = {
    "utilization_pct": "gpu.utilization.percent",
    "memory_pct": "gpu.memory.percent",
    "memory_used_mb": "gpu.memory.used_mb",
    "memory_total_mb": "gpu.memory.total_mb",
    "temperature_c": "gpu.temperature.c",
    "power_watts": "gpu.power.watts",
    "fan_pct": "gpu.fan.percent",
}
_GPU_GROUP_TAGS = ["host", "gpu_index", "gpu_name", "gpu_vendor"]


@router.get("/gpu")
async def gpu_summary(
    user: dict = Depends(require_auth),
    hours: int = Query(1, ge=1, le=168),
) -> Dict[str, Any]:
    """Per-GPU summary, merged across the 7 gpu.* metric names by (host, gpu_index).
    Honest empty state (never fabricated) when no OneAgent host has reported any
    gpu.* metric in the window — most hosts have no GPU at all."""
    from ..services.metrics_timeseries_service import metrics_timeseries_service

    start_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    tid = _tid(user)

    for key, metric_name in GPU_METRICS.items():
        rows = await metrics_timeseries_service.get_top_metrics(
            metric_name=metric_name, group_by=_GPU_GROUP_TAGS,
            aggregation="avg", limit=200, start_time=start_time, tenant_id=tid,
        )
        for r in rows:
            gpu_key = (r.get("host") or "unknown", r.get("gpu_index") or "0")
            entry = merged.setdefault(gpu_key, {
                "host": r.get("host"), "gpu_index": r.get("gpu_index"),
                "gpu_name": r.get("gpu_name"), "gpu_vendor": r.get("gpu_vendor"),
            })
            entry[key] = r.get("avg")
            entry["last_seen"] = r.get("last_timestamp")

    gpus = sorted(merged.values(), key=lambda g: (g.get("host") or "", g.get("gpu_index") or ""))
    return {
        "hours": hours,
        "gpu_count": len(gpus),
        "gpus": gpus,
        "detected": len(gpus) > 0,
        "not_available_reason": None if gpus else (
            "No GPU metrics reported yet — enable the 'gpu' plugin on a OneAgent "
            "host with nvidia-smi (NVIDIA) or rocm-smi (AMD) installed"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/gpu/timeseries")
async def gpu_timeseries(
    host: str,
    gpu_index: str,
    user: dict = Depends(require_auth),
    metric: str = Query("utilization_pct"),
    hours: int = Query(1, ge=1, le=168),
    bucket: str = Query("5m", pattern="^(1m|5m|15m|1h|6h|1d)$"),
) -> Dict[str, Any]:
    """Time series for one metric on one specific GPU (host + gpu_index).
    `bucket` uses metrics_timeseries_service.TIME_BUCKETS's exact keys, same as
    every other consumer of query_metrics()."""
    from ..services.metrics_timeseries_service import metrics_timeseries_service

    if metric not in GPU_METRICS:
        raise HTTPException(400, f"Unknown metric '{metric}'. Valid: {list(GPU_METRICS.keys())}")

    start_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    end_time = datetime.now(timezone.utc).isoformat()

    result = await metrics_timeseries_service.query_metrics(
        metric_name=GPU_METRICS[metric],
        start_time=start_time, end_time=end_time,
        tags={"host": host, "gpu_index": gpu_index},
        aggregation="avg", bucket=bucket, tenant_id=_tid(user),
    )
    return {"host": host, "gpu_index": gpu_index, "metric": metric, **result}


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
    match: Dict[str, Any] = {"received_at": {"$gte": cutoff}, "agents.agent": agent_id}
    tid = _tid(user)
    if tid:
        match["tenant_id"] = tid

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
    tid = _tid(user)
    if tid:
        q["tenant_id"] = tid
    docs = await db.ai_monitoring_quarantine.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"items": docs, "count": len(docs)}


@router.post("/quarantine/{event_id}")
async def quarantine_event(event_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Manually quarantine a flagged event so it sits in an admin-review queue."""
    event_q: Dict[str, Any] = {"id": event_id}
    tid = _tid(user)
    if tid:
        event_q["tenant_id"] = tid
    event = await db.ai_monitoring_events.find_one(event_q, {"_id": 0})
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
        "tenant_id": event.get("tenant_id"),
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
    release_q: Dict[str, Any] = {"event_id": event_id}
    tid = _tid(user)
    if tid:
        release_q["tenant_id"] = tid
    result = await db.ai_monitoring_quarantine.update_one(
        release_q,
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
    block_q: Dict[str, Any] = {"event_id": event_id}
    tid = _tid(user)
    if tid:
        block_q["tenant_id"] = tid
    result = await db.ai_monitoring_quarantine.update_one(
        block_q,
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
