"""
FalconOps AI - Problems console: federation/normalization core

Reads db.alerts_engine + db.incidents_engine + db.soc_events + db.soc_incidents
(four independently-shaped collections — see the Problems console plan for the
full fragmentation history) and normalizes each row into one canonical
"Problem" shape at read time. Deliberately NOT a new canonical collection —
no dual-write, no migration. Real, honest limitation: true 100M-row federated
pagination across 4 heterogeneous Mongo collections (no Elasticsearch
anywhere in this stack) is not solved here — this fetches bounded per-source
candidate windows, merges, and paginates in Python.

Composite Problem ID scheme: "ae:{id}" / "ie:{id}" / "se:{event_id}" /
"si:{incident_id}" — the prefix says which collection + action functions to
route to; the per-source key name differs (alerts_engine/incidents_engine use
"id", soc_events uses "event_id", soc_incidents uses "incident_id").
"""
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..core.database import db

logger = logging.getLogger(__name__)


class ProblemSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ProblemStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


# ─────────────────────────────────────────────────────
#  Severity / status vocabulary mapping (per source prefix -> canonical)
# ─────────────────────────────────────────────────────

_SEVERITY_MAPS: Dict[str, Dict[str, str]] = {
    "ae": {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "info": "info", "warning": "high"},
    "ie": {"sev1": "critical", "sev2": "high", "sev3": "medium", "sev4": "low", "sev5": "info"},
    "se": {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "info": "info", "warning": "high"},
    "si": {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "info": "info", "warning": "high"},
}

_STATUS_MAPS: Dict[str, Dict[str, str]] = {
    "ae": {"triggered": "open", "acknowledged": "acknowledged", "resolved": "resolved", "closed": "closed"},
    "ie": {"active": "open", "investigating": "investigating", "identified": "identified",
           "monitoring": "monitoring", "acknowledged": "acknowledged", "resolved": "resolved", "closed": "closed"},
    "se": {"new": "open", "acknowledged": "acknowledged", "resolved": "resolved", "closed": "closed"},
    "si": {"open": "open", "acknowledged": "acknowledged", "resolved": "resolved", "closed": "closed"},
}


def _reverse_status(prefix: str, canonical: str) -> List[str]:
    return [raw for raw, canon in _STATUS_MAPS[prefix].items() if canon == canonical]


def _reverse_severity(prefix: str, canonical: str) -> List[str]:
    return [raw for raw, canon in _SEVERITY_MAPS[prefix].items() if canon == canonical]


def _duration_seconds(started_at: Optional[str]) -> Optional[float]:
    if not started_at:
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - started).total_seconds()
    except Exception:
        return None


# ─────────────────────────────────────────────────────
#  Row -> canonical Problem mapping
# ─────────────────────────────────────────────────────

def _map_alert_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": f"ae:{doc['id']}",
        "title": doc.get("title"),
        "severity": _SEVERITY_MAPS["ae"].get(doc.get("severity"), "info"),
        "status": _STATUS_MAPS["ae"].get(doc.get("status"), "open"),
        "source_collection": "alert_engine",
        "source_label": doc.get("source"),
        "affected_count": 1,
        "affected_entities": [doc.get("entity_name")] if doc.get("entity_name") else [],
        "root_cause": None,
        "confidence": None,
        "started_at": doc.get("created_at"),
        "last_updated": doc.get("updated_at") or doc.get("created_at"),
        "duration_seconds": _duration_seconds(doc.get("created_at")),
        "assigned_to": doc.get("assigned_to"),
        "assignment_group": doc.get("assignment_group"),
        "acknowledged_by": doc.get("acknowledged_by"),
        "resolved_by": doc.get("resolved_by"),
        "correlation_id": doc.get("incident_id"),
        "tags": doc.get("tags") or {},
    }


def _map_incident_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    affected = doc.get("affected_services") or []
    return {
        "id": f"ie:{doc['id']}",
        "title": doc.get("title"),
        "severity": _SEVERITY_MAPS["ie"].get(doc.get("severity"), "info"),
        "status": _STATUS_MAPS["ie"].get(doc.get("status"), "open"),
        "source_collection": "incident_engine",
        "source_label": doc.get("source"),
        "affected_count": len(affected) or doc.get("alert_count") or 1,
        "affected_entities": affected or (doc.get("affected_hosts") or []),
        "root_cause": doc.get("root_cause"),
        "confidence": doc.get("correlation_confidence") if doc.get("correlation_type") else None,
        "started_at": doc.get("created_at"),
        "last_updated": doc.get("updated_at") or doc.get("created_at"),
        "duration_seconds": _duration_seconds(doc.get("created_at")),
        "assigned_to": doc.get("assigned_to"),
        "assignment_group": doc.get("assignment_group"),
        "acknowledged_by": doc.get("acknowledged_by"),
        "resolved_by": doc.get("resolved_by"),
        "correlation_id": doc.get("id"),
        "tags": {},
        "sla_breach_at": doc.get("sla_breach_at"),
        "is_sla_breached": doc.get("is_sla_breached"),
    }


def _map_soc_event_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": f"se:{doc['event_id']}",
        "title": doc.get("message"),
        "severity": _SEVERITY_MAPS["se"].get(doc.get("severity"), "info"),
        "status": _STATUS_MAPS["se"].get(doc.get("status"), "open"),
        "source_collection": "soc_event",
        "source_label": doc.get("source"),
        "affected_count": 1,
        "affected_entities": [doc.get("service")] if doc.get("service") else [],
        "root_cause": None,
        "confidence": None,
        "started_at": doc.get("timestamp"),
        "last_updated": doc.get("timestamp"),
        "duration_seconds": _duration_seconds(doc.get("timestamp")),
        "assigned_to": doc.get("assigned_to"),
        "assignment_group": doc.get("assignment_group"),
        "acknowledged_by": doc.get("acknowledged_by"),
        "resolved_by": doc.get("resolved_by"),
        "correlation_id": doc.get("incident_id"),
        "tags": doc.get("metadata") or {},
    }


def _map_soc_incident_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    raw_confidence = doc.get("confidence")
    return {
        "id": f"si:{doc['incident_id']}",
        "title": doc.get("title"),
        "severity": _SEVERITY_MAPS["si"].get(doc.get("severity"), "info"),
        "status": _STATUS_MAPS["si"].get(doc.get("status"), "open"),
        "source_collection": "soc_incident",
        "source_label": doc.get("source"),
        "affected_count": doc.get("event_count") or 1,
        "affected_entities": [doc.get("service")] if doc.get("service") else [],
        "root_cause": None,
        "confidence": (raw_confidence / 100) if raw_confidence is not None else None,
        "started_at": doc.get("created_at"),
        "last_updated": doc.get("created_at"),
        "duration_seconds": _duration_seconds(doc.get("created_at")),
        "assigned_to": doc.get("assigned_to"),
        "assignment_group": doc.get("assignment_group"),
        "acknowledged_by": doc.get("acknowledged_by"),
        "resolved_by": doc.get("resolved_by"),
        "correlation_id": doc.get("incident_id"),
        "tags": {},
    }


def _col_alerts_engine():
    return db.alerts_engine


def _col_incidents_engine():
    return db.incidents_engine


def _col_soc_events():
    return db.soc_events


def _col_soc_incidents():
    return db.soc_incidents


_SOURCES: Dict[str, Dict[str, Any]] = {
    "ae": {"collection": _col_alerts_engine, "key": "id", "map": _map_alert_row},
    "ie": {"collection": _col_incidents_engine, "key": "id", "map": _map_incident_row},
    "se": {"collection": _col_soc_events, "key": "event_id", "map": _map_soc_event_row},
    "si": {"collection": _col_soc_incidents, "key": "incident_id", "map": _map_soc_incident_row},
}

_LABEL_TO_PREFIX = {
    "alert_engine": "ae", "incident_engine": "ie", "soc_event": "se", "soc_incident": "si",
}

_SERVICE_FIELD = {"ae": "entity_name", "ie": "affected_services", "se": "service", "si": "service"}


def split_problem_id(problem_id: str) -> Tuple[str, str]:
    if ":" not in problem_id:
        raise ValueError(f"invalid problem id: {problem_id}")
    prefix, raw_id = problem_id.split(":", 1)
    if prefix not in _SOURCES:
        raise ValueError(f"unknown problem id prefix: {prefix}")
    return prefix, raw_id


# ─────────────────────────────────────────────────────
#  Indexes (lazy, idempotent — copied idiom from network_flow_service.py)
# ─────────────────────────────────────────────────────

_indexes_ready = False


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await db.alerts_engine.create_index([("tenant_id", 1), ("status", 1), ("severity", 1), ("created_at", -1)])
        await db.alerts_engine.create_index("incident_id")
        await db.alerts_engine.create_index("assigned_to")
        await db.incidents_engine.create_index([("tenant_id", 1), ("status", 1), ("severity", 1), ("created_at", -1)])
        await db.incidents_engine.create_index("assigned_to")
        await db.soc_events.create_index([("service", 1), ("severity", 1), ("timestamp", -1), ("correlated", 1)])
        await db.soc_events.create_index("assigned_to")
        await db.soc_incidents.create_index([("status", 1), ("created_at", -1)])
        await db.soc_incidents.create_index("assigned_to")
        await db.problem_suppressions.create_index("problem_id", unique=True)
    except Exception as e:
        logger.warning(f"Problems console index creation skipped/partial: {e}")
    _indexes_ready = True


# ─────────────────────────────────────────────────────
#  Query construction (shared by count + fetch, so eligibility/filter logic
#  lives in exactly one place)
# ─────────────────────────────────────────────────────

def _build_source_query(
    prefix: str,
    *,
    status_canonical: Optional[str],
    severity_canonical: Optional[str],
    service: Optional[str],
    assigned_to: Optional[str],
    start_time: Optional[str],
    end_time: Optional[str],
    tenant_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """None return means "structurally no rows can match" (e.g. filtering by a
    canonical status this source has no raw value for) — callers must skip the
    source entirely rather than run an empty-ish query."""
    query: Dict[str, Any] = {}

    # Eligibility predicate — "should this row appear as a Problem at all"
    if prefix == "ae":
        query["incident_id"] = None
        if tenant_id:
            query["tenant_id"] = tenant_id
    elif prefix == "ie":
        if tenant_id:
            query["tenant_id"] = tenant_id
    elif prefix == "se":
        query["correlated"] = False
    # si: no extra eligibility predicate — every soc_incidents row is already correlated

    if status_canonical:
        raw = _reverse_status(prefix, status_canonical)
        if not raw:
            return None
        query["status"] = raw[0] if len(raw) == 1 else {"$in": raw}

    if severity_canonical:
        raw = _reverse_severity(prefix, severity_canonical)
        if not raw:
            return None
        query["severity"] = raw[0] if len(raw) == 1 else {"$in": raw}

    if service:
        field = _SERVICE_FIELD[prefix]
        query[field] = {"$regex": re.escape(service), "$options": "i"}

    if assigned_to:
        query["assigned_to"] = assigned_to

    time_field = "timestamp" if prefix == "se" else "created_at"
    if start_time or end_time:
        time_query: Dict[str, str] = {}
        if start_time:
            time_query["$gte"] = start_time
        if end_time:
            time_query["$lte"] = end_time
        query[time_field] = time_query

    return query


async def _fetch_source(prefix: str, *, fetch_limit: int, **filters) -> List[Dict[str, Any]]:
    query = _build_source_query(prefix, **filters)
    if query is None:
        return []
    cfg = _SOURCES[prefix]
    time_field = "timestamp" if prefix == "se" else "created_at"
    rows = await cfg["collection"]().find(query, {"_id": 0}).sort(time_field, -1).limit(fetch_limit).to_list(fetch_limit)
    return [cfg["map"](r) for r in rows]


async def _count_source(prefix: str, **filters) -> int:
    query = _build_source_query(prefix, **filters)
    if query is None:
        return 0
    return await _SOURCES[prefix]["collection"]().count_documents(query)


# ─────────────────────────────────────────────────────
#  Suppression
# ─────────────────────────────────────────────────────

async def suppress_problem(problem_id: str, reason: str, suppressed_by: str, expires_at: Optional[str] = None) -> Dict[str, Any]:
    await db.problem_suppressions.update_one(
        {"problem_id": problem_id},
        {"$set": {
            "reason": reason, "suppressed_by": suppressed_by,
            "suppressed_at": datetime.now(timezone.utc).isoformat(), "expires_at": expires_at,
        }},
        upsert=True,
    )
    return {"problem_id": problem_id, "suppressed": True}


async def unsuppress_problem(problem_id: str) -> Dict[str, Any]:
    result = await db.problem_suppressions.delete_one({"problem_id": problem_id})
    return {"problem_id": problem_id, "suppressed": False, "existed": result.deleted_count > 0}


async def _get_suppressed_ids(problem_ids: List[str]) -> set:
    if not problem_ids:
        return set()
    now_iso = datetime.now(timezone.utc).isoformat()
    docs = await db.problem_suppressions.find(
        {"problem_id": {"$in": problem_ids}, "$or": [{"expires_at": None}, {"expires_at": {"$gt": now_iso}}]},
        {"_id": 0, "problem_id": 1},
    ).to_list(len(problem_ids))
    return {d["problem_id"] for d in docs}


# ─────────────────────────────────────────────────────
#  List / detail / statistics / timeline / search
# ─────────────────────────────────────────────────────

async def list_problems(
    *,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    service: Optional[str] = None,
    assigned_to: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    sort_by: str = "started_at",
    sort_order: str = "desc",
    include_suppressed: bool = False,
    limit: int = 50,
    offset: int = 0,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Federated, paginated Problem list. `total` is a real per-source
    count_documents() sum (cheap, index-backed) computed BEFORE suppression
    filtering — if include_suppressed=false and some matching rows are
    suppressed, the returned page can be shorter than `limit` rather than
    backfilled (documented tradeoff, not silently patched)."""
    await _ensure_indexes()
    limit = min(max(limit, 1), 500)
    fetch_limit = min(offset + limit, 2000)

    if source is not None and source not in _LABEL_TO_PREFIX:
        raise ValueError(f"unknown source: {source}")
    prefixes = [_LABEL_TO_PREFIX[source]] if source else list(_SOURCES.keys())

    filters = dict(
        status_canonical=status, severity_canonical=severity, service=service,
        assigned_to=assigned_to, start_time=start_time, end_time=end_time, tenant_id=tenant_id,
    )

    sources_queried: Dict[str, int] = {}
    all_rows: List[Dict[str, Any]] = []
    total = 0
    for prefix in prefixes:
        total += await _count_source(prefix, **filters)
        rows = await _fetch_source(prefix, fetch_limit=fetch_limit, **filters)
        sources_queried[prefix] = len(rows)
        all_rows.extend(rows)

    if not include_suppressed and all_rows:
        suppressed_ids = await _get_suppressed_ids([r["id"] for r in all_rows])
        for r in all_rows:
            r["suppressed"] = r["id"] in suppressed_ids
        all_rows = [r for r in all_rows if not r["suppressed"]]
    else:
        for r in all_rows:
            r["suppressed"] = False

    if sort_by == "severity":
        rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_rows.sort(key=lambda r: rank.get(r["severity"], 5), reverse=(sort_order == "asc"))
    else:
        all_rows.sort(key=lambda r: r.get("started_at") or "", reverse=(sort_order != "asc"))

    page = all_rows[offset:offset + limit]

    return {
        "problems": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "sources_queried": sources_queried,
    }


async def _enrich_problem(prefix: str, raw_id: str, problem: Dict[str, Any]) -> Dict[str, Any]:
    """On-demand only — never computed per grid row. Each block honestly reports
    why it's unavailable rather than fabricating a value."""
    enrichment: Dict[str, Any] = {}
    service_hint = (problem.get("affected_entities") or [None])[0]

    try:
        from .intelligence_agents_service import incident_analysis
        enrichment["ai_analysis"] = await incident_analysis(
            query=f"Why is {problem.get('title') or service_hint or 'this'} failing?",
            service=service_hint,
        )
    except Exception as e:
        enrichment["ai_analysis"] = None
        enrichment["ai_analysis_not_available_reason"] = str(e)[:200]

    try:
        from .impact_analysis_engine import impact_analysis_engine
        if prefix == "ie":
            enrichment["impact"] = await impact_analysis_engine.analyze_incident_impact(raw_id)
        elif service_hint:
            enrichment["impact"] = await impact_analysis_engine.get_blast_radius(service_hint)
        else:
            enrichment["impact"] = None
            enrichment["impact_not_available_reason"] = "no affected service known for this problem"
    except Exception as e:
        enrichment["impact"] = None
        enrichment["impact_not_available_reason"] = str(e)[:200]

    if prefix == "ie":
        try:
            from .autonomous_ops_orchestrator import get_recommendation
            enrichment["recommendation"] = await get_recommendation(raw_id)
        except Exception as e:
            enrichment["recommendation"] = None
            enrichment["recommendation_not_available_reason"] = str(e)[:200]
        try:
            from .rca_chain_service import run_rca_chain
            enrichment["rca_chain"] = await run_rca_chain(raw_id)
        except Exception as e:
            enrichment["rca_chain"] = None
            enrichment["rca_chain_not_available_reason"] = str(e)[:200]
    else:
        enrichment["recommendation"] = None
        enrichment["recommendation_not_available_reason"] = "recommendations are only generated for correlated incidents (ie: problems) in Phase 1"
        enrichment["rca_chain"] = None
        enrichment["rca_chain_not_available_reason"] = "RCA chain is only available for correlated incidents (ie: problems) in Phase 1"

    return enrichment


async def get_problem(problem_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    prefix, raw_id = split_problem_id(problem_id)
    cfg = _SOURCES[prefix]
    doc = await cfg["collection"]().find_one({cfg["key"]: raw_id}, {"_id": 0})
    if not doc:
        return None
    if tenant_id and prefix in ("ae", "ie") and doc.get("tenant_id") not in (None, tenant_id):
        return None

    problem = cfg["map"](doc)
    suppressed_ids = await _get_suppressed_ids([problem["id"]])
    problem["suppressed"] = problem["id"] in suppressed_ids
    problem["enrichment"] = await _enrich_problem(prefix, raw_id, problem)
    return problem


async def get_statistics(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Every field here is a real per-source Mongo aggregation, summed in Python
    (no single cross-collection aggregation exists in Mongo). mttd_minutes and
    availability_pct are intentionally omitted, not null-filled — no source
    captures real data for either."""
    await _ensure_indexes()
    today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")

    by_status: Dict[str, int] = defaultdict(int)
    by_severity: Dict[str, int] = defaultdict(int)
    total = 0
    ai_correlated_count = 0
    resolved_today = 0
    resolution_minutes_sum = 0.0
    resolution_count = 0
    sla_total = 0
    sla_breached = 0

    no_filter = dict(status_canonical=None, severity_canonical=None, service=None,
                      assigned_to=None, start_time=None, end_time=None, tenant_id=tenant_id)

    for prefix, cfg in _SOURCES.items():
        base_query = _build_source_query(prefix, **no_filter)
        if base_query is None:
            continue
        col = cfg["collection"]()
        time_field = "timestamp" if prefix == "se" else "created_at"

        source_total = await col.count_documents(base_query)
        total += source_total
        if prefix in ("ie", "si"):
            ai_correlated_count += source_total

        async for row in col.aggregate([{"$match": base_query}, {"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
            by_status[_STATUS_MAPS[prefix].get(row["_id"], "open")] += row["count"]

        async for row in col.aggregate([{"$match": base_query}, {"$group": {"_id": "$severity", "count": {"$sum": 1}}}]):
            by_severity[_SEVERITY_MAPS[prefix].get(row["_id"], "info")] += row["count"]

        resolved_today += await col.count_documents({**base_query, "resolved_at": {"$gte": today_start}})

        mttr_pipeline = [
            {"$match": {**base_query, "resolved_at": {"$ne": None}}},
            {"$project": {"resolution_time": {"$divide": [
                {"$subtract": [{"$toDate": "$resolved_at"}, {"$toDate": f"${time_field}"}]}, 60000,
            ]}}},
            {"$group": {"_id": None, "total_minutes": {"$sum": "$resolution_time"}, "count": {"$sum": 1}}},
        ]
        async for row in col.aggregate(mttr_pipeline):
            resolution_minutes_sum += row["total_minutes"]
            resolution_count += row["count"]

        if prefix == "ie":
            sla_total += await col.count_documents({**base_query, "sla_breach_at": {"$ne": None}})
            sla_breached += await col.count_documents({**base_query, "is_sla_breached": True})

    return {
        "total": total,
        "by_status": dict(by_status),
        "by_severity": dict(by_severity),
        "resolved_today": resolved_today,
        "ai_correlated_count": ai_correlated_count,
        "mttr_minutes": round(resolution_minutes_sum / resolution_count, 2) if resolution_count else None,
        "sla_compliance_pct": round(100 * (sla_total - sla_breached) / sla_total, 1) if sla_total else None,
        "sla_computed_over": sla_total,
    }


async def get_timeline(hours: int = 24, bucket_minutes: int = 60, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Bucketed per-severity counts, computed in Python (timestamps are ISO
    strings across all 4 sources, requiring per-collection $toDate conversion
    for a Mongo-side bucketing anyway — one Python pass is simpler and
    consistent with the read-time-federation architecture)."""
    await _ensure_indexes()
    hours = min(max(hours, 1), 720)
    bucket_minutes = max(5, bucket_minutes)
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    num_buckets = int((hours * 60) / bucket_minutes) + 1

    buckets: Dict[str, Dict[str, int]] = {
        (start + timedelta(minutes=i * bucket_minutes)).strftime("%Y-%m-%dT%H:%M:00"): defaultdict(int)
        for i in range(num_buckets)
    }

    no_service_filter = dict(status_canonical=None, severity_canonical=None, service=None,
                              assigned_to=None, start_time=start.isoformat(), end_time=None, tenant_id=tenant_id)

    for prefix, cfg in _SOURCES.items():
        base_query = _build_source_query(prefix, **no_service_filter)
        if base_query is None:
            continue
        time_field = "timestamp" if prefix == "se" else "created_at"
        docs = await cfg["collection"]().find(base_query, {"_id": 0, time_field: 1, "severity": 1}).limit(20000).to_list(20000)
        for doc in docs:
            ts_raw = doc.get(time_field)
            if not ts_raw:
                continue
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except Exception:
                continue
            bucket_idx = max(0, min(int((ts - start).total_seconds() / (bucket_minutes * 60)), num_buckets - 1))
            bucket_key = (start + timedelta(minutes=bucket_idx * bucket_minutes)).strftime("%Y-%m-%dT%H:%M:00")
            severity = _SEVERITY_MAPS[prefix].get(doc.get("severity"), "info")
            buckets.setdefault(bucket_key, defaultdict(int))[severity] += 1

    timeline = [{"bucket": k, **v} for k, v in sorted(buckets.items())]
    return {"hours": hours, "bucket_minutes": bucket_minutes, "buckets": timeline}


_SEARCH_FIELDS = {"ae": ["title", "entity_name"], "ie": ["title"], "se": ["message", "service"], "si": ["title", "service"]}


async def search_problems(q: str, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Case-insensitive substring match across a few text-ish fields per
    source — NOT full-text-at-scale (no Elasticsearch anywhere in this stack)."""
    pattern = re.escape(q.strip())
    if not pattern:
        return []

    no_filter = dict(status_canonical=None, severity_canonical=None, service=None,
                      assigned_to=None, start_time=None, end_time=None, tenant_id=tenant_id)

    results: List[Dict[str, Any]] = []
    for prefix, cfg in _SOURCES.items():
        base = _build_source_query(prefix, **no_filter) or {}
        or_query = [{f: {"$regex": pattern, "$options": "i"}} for f in _SEARCH_FIELDS[prefix]]
        query = {**base, "$or": or_query}
        docs = await cfg["collection"]().find(query, {"_id": 0}).limit(20).to_list(20)
        results.extend(cfg["map"](d) for d in docs)
    return results


# ─────────────────────────────────────────────────────
#  Actions — dispatch to the matching per-source lifecycle function
# ─────────────────────────────────────────────────────

async def acknowledge_problem(problem_id: str, user_email: str) -> Optional[Dict[str, Any]]:
    prefix, raw_id = split_problem_id(problem_id)
    if prefix == "ae":
        from .alert_engine import alert_engine
        result = await alert_engine.acknowledge_alert(raw_id, user_id=user_email, user_email=user_email)
    elif prefix == "ie":
        from .incident_engine import incident_engine
        result = await incident_engine.update_status(raw_id, "acknowledged", user=user_email, notes="Acknowledged via Problems console")
        if result:
            now = datetime.now(timezone.utc).isoformat()
            await db.incidents_engine.update_one({"id": raw_id}, {"$set": {"acknowledged_at": now, "acknowledged_by": user_email}})
            result["acknowledged_at"] = now
            result["acknowledged_by"] = user_email
    elif prefix == "se":
        from .soc_ingestion_service import acknowledge_event
        result = await acknowledge_event(raw_id, user_email)
    else:
        from .soc_ingestion_service import acknowledge_soc_incident
        result = await acknowledge_soc_incident(raw_id, user_email)
    return _SOURCES[prefix]["map"](result) if result else None


async def resolve_problem(problem_id: str, user_email: str, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
    prefix, raw_id = split_problem_id(problem_id)
    if prefix == "ae":
        from .alert_engine import alert_engine
        result = await alert_engine.resolve_alert(raw_id, user_id=user_email, user_email=user_email, resolution_notes=notes)
    elif prefix == "ie":
        from .incident_engine import incident_engine
        result = await incident_engine.update_status(raw_id, "resolved", user=user_email, notes=notes)
    elif prefix == "se":
        from .soc_ingestion_service import resolve_event
        result = await resolve_event(raw_id, user_email)
    else:
        from .soc_ingestion_service import resolve_soc_incident
        result = await resolve_soc_incident(raw_id, user_email)
    return _SOURCES[prefix]["map"](result) if result else None


async def close_problem(problem_id: str, user_email: str) -> Optional[Dict[str, Any]]:
    prefix, raw_id = split_problem_id(problem_id)
    if prefix == "ae":
        from .alert_engine import alert_engine
        result = await alert_engine.close_alert(raw_id, user_id=user_email, user_email=user_email)
    elif prefix == "ie":
        from .incident_engine import incident_engine
        result = await incident_engine.update_status(raw_id, "closed", user=user_email)
    elif prefix == "se":
        from .soc_ingestion_service import close_event
        result = await close_event(raw_id, user_email)
    else:
        from .soc_ingestion_service import close_soc_incident
        result = await close_soc_incident(raw_id, user_email)
    return _SOURCES[prefix]["map"](result) if result else None


async def assign_problem(
    problem_id: str, assigned_to: Optional[str], assignment_group: Optional[str], user_email: str
) -> Optional[Dict[str, Any]]:
    prefix, raw_id = split_problem_id(problem_id)
    if prefix == "ae":
        from .alert_engine import alert_engine
        result = await alert_engine.assign_alert(raw_id, assigned_to, assignment_group, user_email)
    elif prefix == "ie":
        from .incident_engine import incident_engine
        result = await incident_engine.assign_incident(raw_id, assigned_to, assignment_group, user_email)
    elif prefix == "se":
        from .soc_ingestion_service import assign_event
        result = await assign_event(raw_id, assigned_to, assignment_group)
    else:
        from .soc_ingestion_service import assign_soc_incident
        result = await assign_soc_incident(raw_id, assigned_to, assignment_group)
    return _SOURCES[prefix]["map"](result) if result else None


async def escalate_problem(problem_id: str) -> Dict[str, Any]:
    prefix, raw_id = split_problem_id(problem_id)
    if prefix != "ae":
        raise ValueError("Escalate is only supported for alert-sourced Problems in Phase 1")
    from .alert_engine import alert_engine
    result = await alert_engine.escalate_alert(raw_id)
    if not result:
        raise LookupError("Problem not found")
    return _SOURCES["ae"]["map"](result)


# ─────────────────────────────────────────────────────
#  Export
# ─────────────────────────────────────────────────────

EXPORT_ROW_CEILING = 20000


async def export_rows(
    *,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    service: Optional[str] = None,
    assigned_to: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    include_suppressed: bool = False,
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    result = await list_problems(
        status=status, severity=severity, source=source, service=service, assigned_to=assigned_to,
        start_time=start_time, end_time=end_time, include_suppressed=include_suppressed,
        limit=EXPORT_ROW_CEILING, offset=0, tenant_id=tenant_id,
    )
    return result["problems"]


# ─────────────────────────────────────────────────────
#  AI fix suggestion (on-demand, cached — not part of _enrich_problem)
# ─────────────────────────────────────────────────────

FIX_SUGGESTION_COLLECTION = "problem_fix_suggestions"


async def get_cached_fix_suggestion(problem_id: str) -> Optional[Dict[str, Any]]:
    return await db[FIX_SUGGESTION_COLLECTION].find_one({"problem_id": problem_id}, {"_id": 0})


async def generate_fix_suggestion(problem_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """On-demand, cached — call only from an explicit Generate/Regenerate
    action, never from the list/grid view. Complements rather than
    duplicates _enrich_problem's existing ai_analysis (root-cause) and
    ie-only recommendation blocks: this always runs for any problem type
    (ae/ie/se/si), and is scoped specifically to "what should the engineer
    actually do next" — it cites the already-computed root-cause summary as
    input rather than re-deriving it, so it's one extra LLM call, not two
    redundant ones."""
    problem = await get_problem(problem_id, tenant_id=tenant_id)
    if problem is None:
        raise LookupError("Problem not found")

    ai_analysis = (problem.get("enrichment") or {}).get("ai_analysis") or {}
    root_cause_summary = ai_analysis.get("summary") or problem.get("root_cause") or "unknown root cause"
    service_hint = (problem.get("affected_entities") or [None])[0]

    facts = (
        f"Title: {problem.get('title')}\n"
        f"Severity: {problem.get('severity')}\n"
        f"Status: {problem.get('status')}\n"
        f"Affected: {service_hint or 'unknown service/host'}\n"
        f"Duration (seconds): {problem.get('duration_seconds')}\n"
        f"Root cause analysis so far: {root_cause_summary}\n"
    )
    messages = [
        {"role": "system", "content": (
            "You are a senior site-reliability engineer writing a fix suggestion for "
            "another on-call engineer. Given the facts below (already gathered — do not "
            "ask for more information), write: one sentence summarizing what's wrong, then "
            "2-4 concrete, specific next steps in priority order. Be specific (name likely "
            "commands/checks), not generic advice like 'investigate further'. Plain text, "
            "no markdown headers."
        )},
        {"role": "user", "content": facts},
    ]

    fix_suggestion = None
    try:
        from .llm_provider_service import chat_completion
        result = await chat_completion(messages, session_id=f"problem-fix-{problem_id}")
        fix_suggestion = (result or {}).get("response", "").strip() or None
    except Exception as e:
        logger.warning(f"Fix-suggestion LLM call failed for {problem_id}: {e}")

    if not fix_suggestion:
        fix_suggestion = (
            "AI fix suggestion unavailable (no LLM provider configured, or the call failed). "
            "Fall back to the Recommended Remediation / AI Root Cause Analysis panels above, "
            "or the remediation action library, to choose a next step manually."
        )

    doc = {
        "problem_id": problem_id,
        "summary": f"{problem.get('title')} — {root_cause_summary}",
        "fix_suggestion": fix_suggestion,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db[FIX_SUGGESTION_COLLECTION].update_one({"problem_id": problem_id}, {"$set": doc}, upsert=True)
    return doc


# ─────────────────────────────────────────────────────
#  Notify owner (email / SMS)
# ─────────────────────────────────────────────────────

NOTIFICATION_COLLECTION = "problem_notifications"


async def notify_problem_owner(
    problem_id: str,
    channels: List[str],
    message: Optional[str],
    triggered_by: str,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    problem = await get_problem(problem_id, tenant_id=tenant_id)
    if problem is None:
        raise LookupError("Problem not found")

    owner_email = problem.get("assigned_to")
    if not owner_email:
        raise ValueError("This problem has no assigned owner to notify")

    owner = await db.users.find_one({"email": owner_email}, {"_id": 0})
    service_hint = (problem.get("affected_entities") or [None])[0]
    results: Dict[str, Any] = {}

    if "email" in channels:
        from .notification_service import send_alert_email
        sent = await send_alert_email(
            recipient=owner_email,
            subject=f"[{(problem.get('severity') or 'warning').upper()}] {problem.get('title')} — assigned to you",
            alert_data={
                "severity": problem.get("severity"),
                "title": problem.get("title"),
                "monitor_name": problem.get("source_label"),
                "target": service_hint or "N/A",
                "status": problem.get("status"),
                "description": message or problem.get("root_cause") or "No additional details",
            },
        )
        results["email"] = {"ok": True, "recipient": owner_email} if sent else {"ok": False, "error": "SendGrid not configured or send failed"}

    if "sms" in channels:
        if not owner:
            results["sms"] = {"ok": False, "error": f"no user record found for {owner_email}"}
        elif not owner.get("phone"):
            results["sms"] = {"ok": False, "error": "owner has no phone number on file (set via PATCH /api/auth/me)"}
        else:
            from .sms_service import send_sms
            sms_text = message or f"[{problem.get('severity')}] {problem.get('title')} assigned to you. Status: {problem.get('status')}."
            results["sms"] = await send_sms(owner["phone"], sms_text)

    record = {
        "problem_id": problem_id,
        "owner_email": owner_email,
        "channels": channels,
        "message": message,
        "results": results,
        "triggered_by": triggered_by,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    await db[NOTIFICATION_COLLECTION].insert_one(record)
    record.pop("_id", None)
    return record
