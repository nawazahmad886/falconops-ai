"""
FalconOps AI - Logs Monitoring Routes
API endpoints for log ingestion, analysis, and AI-powered insights
"""
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel

from ..core.database import db
from ..utils.auth import require_auth, require_write_access, get_current_user
from ..services.log_analysis_service import (
    parse_log,
    classify_log_category,
    deduplicate_logs,
    correlate_logs,
    get_log_statistics,
    generate_sample_logs,
    LogAnomalyDetector,
)
from ..services.ai_copilot_service import (
    analyze_logs_with_ai,
    perform_ai_rca,
    ai_copilot,
)

router = APIRouter(prefix="/api/logs", tags=["Logs Monitoring"])

logger = logging.getLogger(__name__)

_indexes_ready = False

# Raw log lines are high-volume and low-value once old — same reasoning as
# metrics_timeseries_service.METRICS_RETENTION_DAYS. Configurable since real
# retention needs vary by deployment.
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "30"))


def _log_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=LOG_RETENTION_DAYS)


async def _ensure_indexes() -> None:
    """db.logs had zero indexes anywhere in the running app (the only real
    index-creation code lived in logs_service.py, which nothing imports) — every
    GET /api/logs / /analyze / /deduplicate / /correlate / /anomalies call was a
    full collection scan. Same lazy ensure-once-on-first-write pattern used by
    ai_monitoring_service/resource_explorer_service/metrics_timeseries_service.

    Also adds a real full-text index on "message" — the `search` param on
    GET /api/logs below used to be a non-anchored $regex (couldn't use any
    index, got slower linearly with collection size); now backed by Mongo's
    text index, real tokenized/relevance-ranked search. And a TTL index on
    expires_at (a real BSON Date field set at insert time — "timestamp" is
    stored as an ISO string throughout this file, which Mongo TTL can't act on)."""
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await db.logs.create_index([("timestamp", -1)], name="logs_ts")
        await db.logs.create_index([("tenant_id", 1), ("timestamp", -1)], name="logs_tenant_ts")
        await db.logs.create_index([("service", 1), ("timestamp", -1)], name="logs_service_ts")
        await db.logs.create_index([("message", "text")], name="logs_message_text")
        await db.logs.create_index("expires_at", name="logs_ttl", expireAfterSeconds=0)
        _indexes_ready = True
    except Exception:
        logger.warning("logs index creation skipped", exc_info=True)


def _tid(user):
    return user.get("tenant_id") if user else None


# ======================== MODELS ========================

class LogEntry(BaseModel):
    message: str
    level: Optional[str] = "INFO"
    service: Optional[str] = "unknown"
    host: Optional[str] = None
    timestamp: Optional[str] = None
    tags: Optional[dict] = None

class LogBatchIngest(BaseModel):
    logs: List[LogEntry]
    source: Optional[str] = "api"

class CopilotMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[dict] = None

class RCARequest(BaseModel):
    incident_id: Optional[str] = None
    logs: Optional[List[dict]] = None
    context: Optional[str] = None


# ======================== LOG INGESTION ========================

@router.post("/ingest")
async def ingest_log(log: LogEntry, current_user: Optional[dict] = Depends(get_current_user)):
    """Ingest a single log entry"""
    await _ensure_indexes()
    # Parse and enrich the log
    parsed = parse_log(log.message)
    
    log_doc = {
        "id": str(uuid.uuid4()),
        "timestamp": log.timestamp or datetime.now(timezone.utc).isoformat(),
        "message": log.message,
        "level": log.level or parsed.get("level", "INFO"),
        "severity": parsed.get("severity", "info"),
        "service": log.service or parsed.get("service", "unknown"),
        "host": log.host,
        "category": classify_log_category(log.message),
        "tags": log.tags or {},
        "source": "api",
        "parsed": parsed,
        "tenant_id": _tid(current_user),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": _log_expires_at(),
    }

    await db.logs.insert_one(log_doc)
    
    return {"id": log_doc["id"], "status": "ingested", "category": log_doc["category"]}


@router.post("/ingest/batch")
async def ingest_logs_batch(batch: LogBatchIngest, current_user: Optional[dict] = Depends(get_current_user)):
    """Ingest multiple log entries"""
    await _ensure_indexes()
    ingested = []
    
    for log in batch.logs:
        parsed = parse_log(log.message)
        
        log_doc = {
            "id": str(uuid.uuid4()),
            "timestamp": log.timestamp or datetime.now(timezone.utc).isoformat(),
            "message": log.message,
            "level": log.level or parsed.get("level", "INFO"),
            "severity": parsed.get("severity", "info"),
            "service": log.service or parsed.get("service", "unknown"),
            "host": log.host,
            "category": classify_log_category(log.message),
            "tags": log.tags or {},
            "source": batch.source,
            "parsed": parsed,
            "tenant_id": _tid(current_user),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": _log_expires_at(),
        }

        ingested.append(log_doc)
    
    if ingested:
        await db.logs.insert_many(ingested)
    
    return {
        "status": "success",
        "ingested_count": len(ingested),
        "log_ids": [l["id"] for l in ingested]
    }


# ======================== LOG RETRIEVAL ========================

@router.get("")
async def get_logs(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    service: Optional[str] = Query(None, description="Filter by service"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in message"),
    hours: int = Query(24, description="Time range in hours"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get logs with filters"""
    await _ensure_indexes()
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = {"timestamp": {"$gte": time_threshold.isoformat()}}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid

    if severity:
        query["severity"] = severity
    if service:
        query["service"] = service
    if category:
        query["category"] = category

    # Real full-text search via the "message" text index (tokenized, stemmed,
    # relevance-ranked) instead of a non-anchored $regex scan, which could never
    # use an index and got slower linearly with collection size. Quote the query
    # for an exact-phrase match (Mongo's $text supports this natively).
    use_text_search = bool(search)
    if use_text_search:
        query["$text"] = {"$search": search}

    total = await db.logs.count_documents(query)
    if use_text_search:
        cursor = db.logs.find(query, {"_id": 0, "score": {"$meta": "textScore"}}) \
            .sort([("score", {"$meta": "textScore"}), ("timestamp", -1)])
    else:
        cursor = db.logs.find(query, {"_id": 0}).sort("timestamp", -1)
    logs = await cursor.skip(offset).limit(limit).to_list(limit)

    return {
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/statistics")
async def logs_statistics(
    hours: int = Query(24, description="Time range in hours"),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get comprehensive log statistics"""
    stats = await get_log_statistics(hours)
    return stats


@router.get("/services")
async def get_log_services(
    hours: int = Query(24, description="Time range in hours"),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get list of services that have logs"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    pipeline = [
        {"$match": {"timestamp": {"$gte": time_threshold.isoformat()}}},
        {"$group": {"_id": "$service", "count": {"$sum": 1}, "errors": {"$sum": {"$cond": [{"$in": ["$severity", ["critical", "error"]]}, 1, 0]}}}},
        {"$sort": {"count": -1}},
        {"$limit": 50}
    ]
    
    result = await db.logs.aggregate(pipeline).to_list(50)
    
    return [{"service": r["_id"], "log_count": r["count"], "error_count": r["errors"]} for r in result]


# ======================== LOG ANALYSIS ========================

@router.post("/analyze")
async def analyze_logs_endpoint(
    hours: int = Query(1, description="Analyze logs from last N hours"),
    service: Optional[str] = Query(None, description="Filter by service"),
    context: Optional[str] = Query(None, description="Additional context"),
    current_user: dict = Depends(require_auth)
):
    """AI-powered log analysis"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = {"timestamp": {"$gte": time_threshold.isoformat()}}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    if service:
        query["service"] = service
    
    logs = await db.logs.find(query, {"_id": 0}).sort("timestamp", -1).limit(500).to_list(500)
    
    if not logs:
        return {"message": "No logs found for analysis", "logs_count": 0}
    
    analysis = await analyze_logs_with_ai(logs, context or "")
    
    # Store analysis result
    analysis_doc = {
        "id": str(uuid.uuid4()),
        "type": "log_analysis",
        "logs_analyzed": len(logs),
        "service_filter": service,
        "hours": hours,
        "analysis": analysis,
        "tenant_id": tid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.get("email")
    }
    await db.ai_analyses.insert_one(analysis_doc)
    
    return analysis


@router.post("/deduplicate")
async def deduplicate_logs_endpoint(
    hours: int = Query(1, description="Deduplicate logs from last N hours"),
    service: Optional[str] = Query(None, description="Filter by service"),
    current_user: dict = Depends(require_auth)
):
    """Deduplicate logs and return summary"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = {"timestamp": {"$gte": time_threshold.isoformat()}}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    if service:
        query["service"] = service
    
    logs = await db.logs.find(query, {"_id": 0}).limit(5000).to_list(5000)
    
    result = await deduplicate_logs(logs)
    
    return result


@router.post("/correlate")
async def correlate_logs_endpoint(
    hours: int = Query(1, description="Correlate logs from last N hours"),
    time_window: int = Query(5, description="Correlation time window in minutes"),
    current_user: dict = Depends(require_auth)
):
    """Correlate logs into event groups"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = {"timestamp": {"$gte": time_threshold.isoformat()}}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    logs = await db.logs.find(query, {"_id": 0}).limit(5000).to_list(5000)
    
    correlations = await correlate_logs(logs, time_window)
    
    return {
        "total_logs": len(logs),
        "correlated_events": len(correlations),
        "events": correlations
    }


# ======================== ANOMALY DETECTION ========================

@router.get("/anomalies")
async def detect_anomalies(
    hours: int = Query(1, description="Detect anomalies in last N hours"),
    current_user: dict = Depends(require_auth)
):
    """Detect anomalies in recent logs"""
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    query = {"timestamp": {"$gte": time_threshold.isoformat()}}
    tid = _tid(current_user)
    if tid:
        query["tenant_id"] = tid
    logs = await db.logs.find(query, {"_id": 0}).limit(5000).to_list(5000)
    
    detector = LogAnomalyDetector(history_hours=24)
    anomalies = await detector.detect_anomalies(logs)
    
    return {
        "logs_analyzed": len(logs),
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies
    }


# ======================== AI RCA ========================

@router.post("/rca")
async def perform_rca(
    request: RCARequest,
    current_user: dict = Depends(require_auth)
):
    """Perform AI-powered Root Cause Analysis"""
    incident_data = None
    related_logs = request.logs or []
    
    # If incident_id provided, fetch incident
    if request.incident_id:
        incident_data = await db.incidents.find_one({"id": request.incident_id}, {"_id": 0})
        
        if not incident_data:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Get related logs if not provided
        if not related_logs:
            service = incident_data.get("service")
            if service:
                time_threshold = datetime.now(timezone.utc) - timedelta(hours=1)
                related_logs = await db.logs.find({
                    "service": service,
                    "timestamp": {"$gte": time_threshold.isoformat()}
                }, {"_id": 0}).limit(100).to_list(100)
    
    if not incident_data and not related_logs:
        raise HTTPException(status_code=400, detail="Provide incident_id or logs for RCA")
    
    rca_result = await perform_ai_rca(incident_data or {}, related_logs)
    
    # Store RCA result
    rca_doc = {
        "id": str(uuid.uuid4()),
        "type": "rca",
        "incident_id": request.incident_id,
        "result": rca_result,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.get("email")
    }
    await db.ai_analyses.insert_one(rca_doc)
    
    # Update incident with RCA if applicable
    if request.incident_id and rca_result.get("root_cause"):
        await db.incidents.update_one(
            {"id": request.incident_id},
            {"$set": {
                "ai_analysis": rca_result,
                "root_cause": rca_result.get("root_cause"),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    
    return rca_result


# ======================== AI COPILOT ========================

@router.post("/copilot/chat")
async def copilot_chat(
    request: CopilotMessage,
    current_user: dict = Depends(require_auth)
):
    """Chat with AI Copilot"""
    session_id = request.session_id or f"user-{current_user.get('id', 'anon')}-{uuid.uuid4().hex[:8]}"
    
    # Add user info to context
    context = request.context or {}
    context["user_email"] = current_user.get("email")
    context["user_role"] = current_user.get("role")
    
    response = await ai_copilot.chat(session_id, request.message, context)
    
    return response


@router.get("/copilot/history/{session_id}")
async def get_copilot_history(
    session_id: str,
    current_user: dict = Depends(require_auth)
):
    """Get chat history for a session"""
    history = await ai_copilot.get_history(session_id)
    return {"session_id": session_id, "history": history}


@router.delete("/copilot/session/{session_id}")
async def clear_copilot_session(
    session_id: str,
    current_user: dict = Depends(require_auth)
):
    """Clear a copilot session"""
    ai_copilot.clear_session(session_id)
    return {"message": "Session cleared", "session_id": session_id}


# ======================== DEMO DATA ========================

@router.post("/simulate")
async def simulate_logs(
    count: int = Query(100, le=1000, description="Number of logs to generate"),
    current_user: dict = Depends(require_write_access)
):
    """Generate sample logs for demo"""
    sample_logs = await generate_sample_logs(count)
    
    await db.logs.insert_many(sample_logs)
    
    return {
        "message": f"Generated {len(sample_logs)} sample logs",
        "log_count": len(sample_logs),
        "services": list(set(l["service"] for l in sample_logs))
    }


@router.delete("/clear")
async def clear_logs(
    hours: int = Query(None, description="Clear logs older than N hours (None = all)"),
    current_user: dict = Depends(require_write_access)
):
    """Clear logs (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if hours:
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.logs.delete_many({"timestamp": {"$lt": time_threshold.isoformat()}})
    else:
        result = await db.logs.delete_many({})
    
    return {"message": f"Cleared {result.deleted_count} logs"}
