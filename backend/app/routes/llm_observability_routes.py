"""
FalconOps AI — LLM Observability API.

Purpose-built request/model/provider/token/cost/cache/latency/prompt
analytics for the platform's own LLM usage — distinct from
/api/ai-monitoring/* (the 9-agent AI-safety/compliance monitoring system).
Both read the same db.ai_monitoring_events collection; this file adds the
groupings/aggregations that dataset didn't have an endpoint for yet
(by-provider breakdown, cache analytics, cost projection, top-expensive/
slow prompt tables) rather than duplicating what /api/ai-monitoring/dashboard
already computes correctly.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.database import db
from ..utils.auth import require_auth, require_admin

router = APIRouter(prefix="/api/llm-observability", tags=["LLM Observability"])


def _cutoff(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _percentiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
    arr = np.array(values)
    return {"p50": round(float(np.percentile(arr, 50)), 1), "p90": round(float(np.percentile(arr, 90)), 1),
            "p95": round(float(np.percentile(arr, 95)), 1), "p99": round(float(np.percentile(arr, 99)), 1)}


async def _events(hours: int, extra_query: Optional[Dict[str, Any]] = None, projection: Optional[Dict] = None,
                   limit: int = 5000) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"received_at": {"$gte": _cutoff(hours)}}
    if extra_query:
        query.update(extra_query)
    return await db.ai_monitoring_events.find(query, projection or {"_id": 0}).limit(limit).to_list(limit)


# ─────────────────────────────────────────────
#  Overview
# ─────────────────────────────────────────────

@router.get("/overview")
async def get_overview(hours: int = Query(24, ge=1, le=8760), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await _events(hours, projection={
        "_id": 0, "errored": 1, "latency_ms": 1, "tokens_input": 1, "tokens_output": 1, "tokens_total": 1,
        "estimated_cost_usd": 1, "cached_tokens": 1, "received_at": 1,
    })
    total = len(events)
    if total == 0:
        return {"hours": hours, "total_requests": 0, "message": "No LLM requests recorded in this window"}

    errored = sum(1 for e in events if e.get("errored"))
    latencies = [e["latency_ms"] for e in events if e.get("latency_ms") is not None]
    costs = [e["estimated_cost_usd"] for e in events if e.get("estimated_cost_usd") is not None]
    tokens_in = sum(e.get("tokens_input") or 0 for e in events)
    tokens_out = sum(e.get("tokens_output") or 0 for e in events)
    cached = [e for e in events if e.get("cached_tokens")]

    # Previous-period comparison (same window length, immediately prior) for % change cards.
    prev_cutoff_start = (datetime.now(timezone.utc) - timedelta(hours=2 * hours)).isoformat()
    prev_events = await db.ai_monitoring_events.find(
        {"received_at": {"$gte": prev_cutoff_start, "$lt": _cutoff(hours)}}, {"_id": 0, "estimated_cost_usd": 1},
    ).to_list(5000)
    prev_total = len(prev_events)
    pct_change = round(100 * (total - prev_total) / prev_total, 1) if prev_total else None

    return {
        "hours": hours,
        "total_requests": total,
        "requests_pct_change_vs_previous": pct_change,
        "successful_requests": total - errored,
        "failed_requests": errored,
        "error_rate_pct": round(100 * errored / total, 2),
        "total_tokens": tokens_in + tokens_out,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "total_cost_usd": round(sum(costs), 4) if costs else None,
        "unpriced_request_count": total - len(costs),
        "latency": _percentiles(latencies),
        "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "cache_hit_rate_pct": round(100 * len(cached) / total, 1) if total else None,
    }


# ─────────────────────────────────────────────
#  Requests log
# ─────────────────────────────────────────────

@router.get("/requests")
async def list_requests(hours: int = Query(24, ge=1, le=8760), model: Optional[str] = None,
                         provider: Optional[str] = None, errored_only: bool = False,
                         limit: int = Query(50, le=500), offset: int = 0,
                         user: dict = Depends(require_auth)) -> Dict[str, Any]:
    query: Dict[str, Any] = {"received_at": {"$gte": _cutoff(hours)}}
    if model:
        query["model"] = model
    if provider:
        query["provider"] = provider
    if errored_only:
        query["errored"] = True
    total = await db.ai_monitoring_events.count_documents(query)
    rows = await db.ai_monitoring_events.find(
        query, {"_id": 0, "user_input": 0, "ai_output": 0, "agents": 0},  # summaries only, not full I/O — use /requests/{id} for that
    ).sort("received_at", -1).skip(offset).limit(limit).to_list(limit)
    return {"requests": rows, "total": total, "offset": offset, "limit": limit}


@router.get("/requests/{event_id}")
async def get_request_detail(event_id: str, user: dict = Depends(require_auth)) -> Dict[str, Any]:
    doc = await db.ai_monitoring_events.find_one({"id": event_id}, {"_id": 0})
    if doc is None:
        raise HTTPException(status_code=404, detail="request not found")
    return doc


# ─────────────────────────────────────────────
#  Models / Providers
# ─────────────────────────────────────────────

def _group_by(events: List[Dict], key: str) -> Dict[str, Any]:
    groups: Dict[str, Dict[str, Any]] = {}
    for e in events:
        k = e.get(key) or "unknown"
        g = groups.setdefault(k, {"count": 0, "errored": 0, "tokens": 0, "cost": 0.0, "latencies": [], "cached": 0})
        g["count"] += 1
        g["errored"] += 1 if e.get("errored") else 0
        g["tokens"] += e.get("tokens_total") or 0
        if e.get("estimated_cost_usd") is not None:
            g["cost"] += e["estimated_cost_usd"]
        if e.get("latency_ms") is not None:
            g["latencies"].append(e["latency_ms"])
        if e.get("cached_tokens"):
            g["cached"] += 1
    return groups


@router.get("/models")
async def get_models(hours: int = Query(24, ge=1, le=8760), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await _events(hours, projection={"_id": 0, "model": 1, "provider": 1, "errored": 1, "tokens_total": 1,
                                                "estimated_cost_usd": 1, "latency_ms": 1, "cached_tokens": 1})
    groups = _group_by(events, "model")
    providers_by_model = {e.get("model"): e.get("provider") for e in events}
    rows = []
    for model, g in groups.items():
        pct = _percentiles(g["latencies"])
        rows.append({
            "model": model, "provider": providers_by_model.get(model), "requests": g["count"],
            "success_pct": round(100 * (g["count"] - g["errored"]) / g["count"], 1),
            "error_pct": round(100 * g["errored"] / g["count"], 1),
            "p50_ms": pct["p50"], "p95_ms": pct["p95"], "p99_ms": pct["p99"],
            "tokens": g["tokens"], "cost_usd": round(g["cost"], 4) if g["cost"] else None,
            "cost_per_request_usd": round(g["cost"] / g["count"], 6) if g["cost"] else None,
            "cache_hit_pct": round(100 * g["cached"] / g["count"], 1),
        })
    rows.sort(key=lambda r: r["requests"], reverse=True)
    return {"models": rows}


@router.get("/providers")
async def get_providers(hours: int = Query(24, ge=1, le=8760), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """The one breakdown genuinely missing from the existing AI Monitoring
    dashboard (confirmed by research — model breakdown exists, provider
    breakdown doesn't, anywhere in the app until this endpoint)."""
    events = await _events(hours, projection={"_id": 0, "provider": 1, "errored": 1, "tokens_total": 1,
                                                 "estimated_cost_usd": 1, "latency_ms": 1})
    groups = _group_by(events, "provider")
    rows = []
    for provider, g in groups.items():
        pct = _percentiles(g["latencies"])
        rows.append({
            "provider": provider, "requests": g["count"],
            "error_rate_pct": round(100 * g["errored"] / g["count"], 1),
            "p95_ms": pct["p95"], "tokens": g["tokens"],
            "cost_usd": round(g["cost"], 4) if g["cost"] else None,
            "cost_per_request_usd": round(g["cost"] / g["count"], 6) if g["cost"] else None,
        })
    rows.sort(key=lambda r: r["requests"], reverse=True)
    return {"providers": rows}


# ─────────────────────────────────────────────
#  Tokens / Cost / Cache / Latency time series
# ─────────────────────────────────────────────

def _bucket_key(iso_ts: str, bucket_minutes: int) -> str:
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    epoch_min = int(dt.timestamp() // 60)
    bucketed = (epoch_min // bucket_minutes) * bucket_minutes
    return datetime.fromtimestamp(bucketed * 60, tz=timezone.utc).isoformat()


def _bucket_minutes_for(hours: int) -> int:
    if hours <= 1:
        return 1
    if hours <= 6:
        return 5
    if hours <= 24:
        return 15
    if hours <= 168:
        return 60
    return 24 * 60


@router.get("/tokens")
async def get_tokens_timeseries(hours: int = Query(24, ge=1, le=8760), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await _events(hours, projection={"_id": 0, "received_at": 1, "tokens_input": 1, "tokens_output": 1, "model": 1})
    bucket_min = _bucket_minutes_for(hours)
    buckets: Dict[str, Dict[str, Any]] = {}
    for e in events:
        key = _bucket_key(e["received_at"], bucket_min)
        b = buckets.setdefault(key, {"prompt_tokens": 0, "completion_tokens": 0})
        b["prompt_tokens"] += e.get("tokens_input") or 0
        b["completion_tokens"] += e.get("tokens_output") or 0
    points = [{"timestamp": k, "prompt_tokens": v["prompt_tokens"], "completion_tokens": v["completion_tokens"],
               "total_tokens": v["prompt_tokens"] + v["completion_tokens"]} for k, v in sorted(buckets.items())]
    return {"hours": hours, "bucket_minutes": bucket_min, "points": points}


@router.get("/cost")
async def get_cost(hours: int = Query(24, ge=1, le=8760), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await _events(hours, projection={"_id": 0, "received_at": 1, "estimated_cost_usd": 1, "model": 1, "provider": 1})
    bucket_min = _bucket_minutes_for(hours)
    buckets: Dict[str, float] = {}
    priced = [e for e in events if e.get("estimated_cost_usd") is not None]
    for e in priced:
        key = _bucket_key(e["received_at"], bucket_min)
        buckets[key] = buckets.get(key, 0.0) + e["estimated_cost_usd"]
    points = [{"timestamp": k, "cost_usd": round(v, 6)} for k, v in sorted(buckets.items())]
    total_cost = sum(buckets.values())
    return {
        "hours": hours, "bucket_minutes": bucket_min, "points": points,
        "total_cost_usd": round(total_cost, 4), "priced_request_count": len(priced),
        "unpriced_request_count": len(events) - len(priced),
        "by_model": {k: round(v["cost"], 4) for k, v in _group_by(events, "model").items() if v["cost"]},
        "by_provider": {k: round(v["cost"], 4) for k, v in _group_by(events, "provider").items() if v["cost"]},
    }


@router.get("/cost/projection")
async def get_cost_projection(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Naive linear projection from the last 24h's real spend — clearly
    labeled as an estimate, not a forecast model. If there's no cost data
    yet, returns unavailable rather than projecting from nothing."""
    events = await _events(24, projection={"_id": 0, "estimated_cost_usd": 1})
    priced = [e["estimated_cost_usd"] for e in events if e.get("estimated_cost_usd") is not None]
    if not priced:
        return {"available": False, "reason": "no priced LLM requests in the last 24h to project from"}
    daily_cost = sum(priced)
    days_in_month = 30
    return {
        "available": True, "is_estimate": True,
        "last_24h_cost_usd": round(daily_cost, 4),
        "projected_monthly_cost_usd": round(daily_cost * days_in_month, 2),
        "method": "linear extrapolation of the last 24h's real spend across a 30-day month",
    }


@router.get("/cache")
async def get_cache(hours: int = Query(24, ge=1, le=8760), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await _events(hours, projection={"_id": 0, "cached_tokens": 1, "tokens_input": 1, "cache_savings_usd": 1,
                                                 "model": 1, "provider": 1, "received_at": 1})
    total = len(events)
    cached_events = [e for e in events if e.get("cached_tokens")]
    if total == 0:
        return {"available": False, "reason": "no LLM requests in this window"}

    cache_savings = [e["cache_savings_usd"] for e in cached_events if e.get("cache_savings_usd") is not None]
    bucket_min = _bucket_minutes_for(hours)
    buckets: Dict[str, Dict[str, int]] = {}
    for e in events:
        key = _bucket_key(e["received_at"], bucket_min)
        b = buckets.setdefault(key, {"total": 0, "cached": 0})
        b["total"] += 1
        if e.get("cached_tokens"):
            b["cached"] += 1
    hit_rate_series = [{"timestamp": k, "cache_hit_rate_pct": round(100 * v["cached"] / v["total"], 1)}
                        for k, v in sorted(buckets.items())]

    return {
        "hours": hours,
        "cache_hit_rate_pct": round(100 * len(cached_events) / total, 1),
        "avg_cache_read_tokens": round(statistics.mean([e["cached_tokens"] for e in cached_events]), 1) if cached_events else None,
        "total_cache_savings_usd": round(sum(cache_savings), 4) if cache_savings else None,
        "cache_savings_unavailable_reason": None if cache_savings else "no cache-read pricing configured for the models seen, or no cache hits recorded",
        "hit_rate_series": hit_rate_series,
        "by_model": {k: round(100 * v["cached"] / v["count"], 1) for k, v in _group_by(events, "model").items()},
    }


@router.get("/latency")
async def get_latency(hours: int = Query(24, ge=1, le=8760), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await _events(hours, projection={"_id": 0, "latency_ms": 1, "model": 1, "provider": 1, "received_at": 1})
    latencies = [e["latency_ms"] for e in events if e.get("latency_ms") is not None]
    if not latencies:
        return {"available": False, "reason": "no LLM requests with latency recorded in this window"}

    bucket_min = _bucket_minutes_for(hours)
    buckets: Dict[str, List[float]] = {}
    for e in events:
        if e.get("latency_ms") is None:
            continue
        key = _bucket_key(e["received_at"], bucket_min)
        buckets.setdefault(key, []).append(e["latency_ms"])
    series = [{"timestamp": k, "avg_ms": round(statistics.mean(v), 1), **_percentiles(v)} for k, v in sorted(buckets.items())]

    by_model = _group_by(events, "model")
    slowest_models = sorted(
        ({"model": m, "p95_ms": _percentiles(g["latencies"])["p95"]} for m, g in by_model.items() if g["latencies"]),
        key=lambda r: r["p95_ms"], reverse=True,
    )

    return {"hours": hours, "overall": _percentiles(latencies), "avg_ms": round(statistics.mean(latencies), 1),
            "max_ms": round(max(latencies), 1), "series": series, "slowest_models": slowest_models[:10]}


# ─────────────────────────────────────────────
#  Prompt analytics (top expensive / slowest)
# ─────────────────────────────────────────────

@router.get("/prompts/expensive")
async def top_expensive_prompts(hours: int = Query(24, ge=1, le=8760), limit: int = Query(10, le=100),
                                 user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await db.ai_monitoring_events.find(
        {"received_at": {"$gte": _cutoff(hours)}, "estimated_cost_usd": {"$ne": None}},
        {"_id": 0, "id": 1, "received_at": 1, "trace_id": 1, "model": 1, "provider": 1, "tokens_input": 1,
         "tokens_output": 1, "tokens_total": 1, "estimated_cost_usd": 1, "prompt_hash": 1, "source": 1,
         "user_input": 1},
    ).sort("estimated_cost_usd", -1).limit(limit).to_list(limit)
    for e in events:
        e["prompt_preview"] = (e.pop("user_input", "") or "")[:200]
    return {"prompts": events}


@router.get("/prompts/slow")
async def top_slow_prompts(hours: int = Query(24, ge=1, le=8760), limit: int = Query(10, le=100),
                            user: dict = Depends(require_auth)) -> Dict[str, Any]:
    events = await db.ai_monitoring_events.find(
        {"received_at": {"$gte": _cutoff(hours)}, "latency_ms": {"$gt": 0}},
        {"_id": 0, "id": 1, "received_at": 1, "trace_id": 1, "model": 1, "provider": 1, "latency_ms": 1,
         "tokens_total": 1, "status": 1, "errored": 1, "user_input": 1},
    ).sort("latency_ms", -1).limit(limit).to_list(limit)
    for e in events:
        e["prompt_preview"] = (e.pop("user_input", "") or "")[:200]
    return {"prompts": events}


# ─────────────────────────────────────────────
#  Pricing registry (admin CRUD)
# ─────────────────────────────────────────────

@router.get("/pricing")
async def list_pricing(user: dict = Depends(require_auth)) -> Dict[str, Any]:
    from ..services.llm_pricing_service import list_rates
    return {"rates": await list_rates()}


class SetPricingPayload(BaseModel):
    input_price_per_1k: float
    output_price_per_1k: float
    cache_read_price_per_1k: Optional[float] = None
    currency: str = "USD"


@router.put("/pricing/{provider}/{model}")
async def set_pricing(provider: str, model: str, body: SetPricingPayload, admin: dict = Depends(require_admin)) -> Dict[str, Any]:
    from ..services.llm_pricing_service import set_rate
    return await set_rate(
        provider, model, input_price_per_1k=body.input_price_per_1k, output_price_per_1k=body.output_price_per_1k,
        cache_read_price_per_1k=body.cache_read_price_per_1k, currency=body.currency,
        updated_by=admin.get("email", "unknown"),
    )


@router.delete("/pricing/{provider}/{model}")
async def delete_pricing(provider: str, model: str, admin: dict = Depends(require_admin)) -> Dict[str, Any]:
    from ..services.llm_pricing_service import delete_rate
    result = await delete_rate(provider, model)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ─────────────────────────────────────────────
#  Dependencies (LLM nodes in FalconGraph)
# ─────────────────────────────────────────────

@router.get("/dependencies")
async def get_llm_dependencies(hours: int = Query(24, ge=1, le=8760), user: dict = Depends(require_auth)) -> Dict[str, Any]:
    """Thin wrapper over the same service_dependencies edges
    trace_persistence_service.persist_normalized_spans() already builds for
    every LLM call span — filtered to llm:* nodes. Real edges only exist
    where a caller supplied parent trace context (disclosed limitation —
    most current callers don't yet); a standalone LLM span still shows as a
    node with no inbound edge rather than being hidden."""
    cutoff = _cutoff(hours)
    edges = await db.service_dependencies.find(
        {"$or": [{"service": {"$regex": "^llm:"}}, {"depends_on": {"$regex": "^llm:"}}], "last_seen": {"$gte": cutoff}},
        {"_id": 0},
    ).to_list(500)
    llm_services = {e["service"] for e in edges} | {e["depends_on"] for e in edges}
    llm_only_nodes = [s for s in llm_services if s.startswith("llm:")]
    return {"edges": edges, "llm_nodes": llm_only_nodes, "edge_count": len(edges)}


__all__ = ["router"]
