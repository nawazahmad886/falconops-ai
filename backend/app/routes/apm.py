"""
FalconOps AI - APM Routes
Application Performance Monitoring endpoints
"""
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query

from ..core.database import db
from ..models.schemas import (
    APMServiceCreate, APMServiceResponse, APMMetricsBatch,
    APMTransactionCreate, APMDependencyCall, APMErrorEvent, APMDashboardResponse
)
from ..utils.auth import require_auth, require_write_access, get_current_user

router = APIRouter(prefix="/api/apm", tags=["APM"])


def _tid(user):
    return user.get("tenant_id") if user else None


# Helper function to validate APM API key
async def validate_apm_api_key(service_id: str, api_key: str) -> bool:
    """Validate that the API key matches the service"""
    service = await db.apm_services.find_one({"id": service_id, "api_key": api_key})
    return service is not None


@router.get("/dashboard", response_model=APMDashboardResponse)
async def get_apm_dashboard(
    hours: int = Query(24, ge=1, le=168),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get APM dashboard overview"""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    tid = _tid(current_user)
    tq = {"tenant_id": tid} if tid else {}
    
    services = await db.apm_services.find({"status": "active", **tq}, {"_id": 0, "api_key": 0}).to_list(100)
    
    transactions = await db.apm_transactions.find(
        {"start_time": {"$gte": since}, **tq}, {"_id": 0}
    ).to_list(10000)
    
    errors = await db.apm_errors.find(
        {"timestamp": {"$gte": since}, **tq}, {"_id": 0}
    ).to_list(1000)
    
    total_transactions = len(transactions)
    failed_transactions = sum(1 for t in transactions if not t.get("success", True))
    error_rate = round((failed_transactions / total_transactions) * 100, 2) if total_transactions > 0 else 0
    
    durations = [t.get("duration_ms", 0) for t in transactions if t.get("duration_ms")]
    avg_response_time = round(sum(durations) / len(durations), 2) if durations else 0
    p95_response_time = round(sorted(durations)[int(len(durations) * 0.95)] if len(durations) >= 20 else avg_response_time, 2)
    
    throughput = round(total_transactions / hours, 2) if hours > 0 else 0
    
    error_types = {}
    for err in errors:
        et = err.get("error_type", "Unknown")
        error_types[et] = error_types.get(et, 0) + 1
    error_breakdown = [{"error_type": k, "count": v} for k, v in sorted(error_types.items(), key=lambda x: -x[1])[:10]]
    
    slow_transactions = sorted(transactions, key=lambda x: -x.get("duration_ms", 0))[:10]
    slow_transactions = [
        {"transaction_name": t.get("transaction_name"), "duration_ms": t.get("duration_ms"), "service_id": t.get("service_id")}
        for t in slow_transactions
    ]
    
    service_metrics = []
    for svc in services:
        svc_transactions = [t for t in transactions if t.get("service_id") == svc["id"]]
        svc_errors = [e for e in errors if e.get("service_id") == svc["id"]]

        svc_durations = [t.get("duration_ms", 0) for t in svc_transactions if t.get("duration_ms")]
        svc_avg = round(sum(svc_durations) / len(svc_durations), 2) if svc_durations else 0
        svc_error_rate = round((len(svc_errors) / len(svc_transactions)) * 100, 2) if svc_transactions else 0
        svc_sorted = sorted(svc_durations)
        svc_p95 = round(svc_sorted[int(len(svc_sorted) * 0.95)], 2) if len(svc_sorted) >= 20 else svc_avg
        svc_p99 = round(svc_sorted[int(len(svc_sorted) * 0.99)], 2) if len(svc_sorted) >= 20 else svc_avg
        svc_rpm = round(len(svc_transactions) / (hours * 60), 2) if hours > 0 else 0
        if svc_error_rate >= 5 or svc_p95 >= 2000:
            svc_status = "critical"
        elif svc_error_rate >= 1 or svc_p95 >= 1000:
            svc_status = "degraded"
        else:
            svc_status = "healthy"

        service_metrics.append({
            "id": svc["id"],
            "service_name": svc["service_name"],
            "service_type": svc.get("service_type"),
            "environment": svc.get("environment"),
            "transaction_count": len(svc_transactions),
            "error_count": len(svc_errors),
            "avg_response_time_ms": svc_avg,
            "p95_response_time_ms": svc_p95,
            "p99_response_time_ms": svc_p99,
            "rpm": svc_rpm,
            "error_rate": svc_error_rate,
            "status": svc_status,
            "last_seen": svc.get("last_seen")
        })
    
    return APMDashboardResponse(
        period={"start": since, "end": datetime.now(timezone.utc).isoformat(), "hours": str(hours)},
        services=service_metrics,
        overall_metrics={
            "total_transactions": total_transactions,
            "error_rate": error_rate,
            "avg_response_time_ms": avg_response_time,
            "p95_response_time_ms": p95_response_time,
            "throughput_per_hour": throughput,
            "total_errors": len(errors)
        },
        error_breakdown=error_breakdown,
        slow_transactions=slow_transactions,
        dependency_health=[],
        throughput_trend=[]
    )


# Service Management

@router.get("/services", response_model=List[APMServiceResponse])
async def get_apm_services(
    environment: Optional[str] = Query(None),
    current_user: dict = Depends(require_auth)
):
    """Get all registered APM services"""
    query = {}
    if environment:
        query["environment"] = environment
    
    services = await db.apm_services.find(query, {"_id": 0}).to_list(100)
    return [APMServiceResponse(**s) for s in services]


@router.post("/services", response_model=APMServiceResponse)
async def register_apm_service(service: APMServiceCreate, current_user: dict = Depends(require_write_access)):
    """Register a new service for APM monitoring"""
    service_id = str(uuid.uuid4())
    api_key = f"fop_{secrets.token_hex(24)}"
    
    service_doc = {
        "id": service_id,
        "service_name": service.service_name,
        "service_type": service.service_type,
        "environment": service.environment,
        "version": service.version,
        "host": service.host,
        "tags": service.tags or {},
        "api_key": api_key,
        "status": "active",
        "last_seen": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["email"]
    }
    
    await db.apm_services.insert_one(service_doc)
    return APMServiceResponse(**service_doc)


@router.get("/services/{service_id}")
async def get_apm_service(service_id: str, current_user: dict = Depends(require_auth)):
    """Get single APM service details"""
    service = await db.apm_services.find_one({"id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.delete("/services/{service_id}")
async def delete_apm_service(service_id: str, current_user: dict = Depends(require_write_access)):
    """Delete an APM service"""
    result = await db.apm_services.delete_one({"id": service_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Clean up related data
    await db.apm_transactions.delete_many({"service_id": service_id})
    await db.apm_errors.delete_many({"service_id": service_id})
    await db.apm_metrics.delete_many({"service_id": service_id})
    
    return {"message": "Service and related data deleted"}


# Data Ingestion Endpoints (used by agents)

@router.post("/ingest/transactions")
async def ingest_transaction(transaction: APMTransactionCreate):
    """Ingest transaction data from APM agent"""
    if not await validate_apm_api_key(transaction.service_id, transaction.api_key):
        raise HTTPException(status_code=401, detail="Invalid service ID or API key")
    
    tx_doc = {
        "id": str(uuid.uuid4()),
        "service_id": transaction.service_id,
        "transaction_id": transaction.transaction_id,
        "transaction_name": transaction.transaction_name,
        "transaction_type": transaction.transaction_type,
        "start_time": transaction.start_time,
        "end_time": transaction.end_time,
        "duration_ms": transaction.duration_ms,
        "status_code": transaction.status_code,
        "success": transaction.success,
        "error_message": transaction.error_message,
        "error_type": transaction.error_type,
        "metadata": transaction.metadata,
        "db_time_ms": transaction.db_time_ms,
        "external_time_ms": transaction.external_time_ms,
        "code_time_ms": transaction.code_time_ms,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.apm_transactions.insert_one(tx_doc)
    
    await db.apm_services.update_one(
        {"id": transaction.service_id},
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Transaction ingested", "id": tx_doc["id"]}


@router.post("/ingest/metrics")
async def ingest_metrics(metrics_batch: APMMetricsBatch):
    """Ingest metrics batch from APM agent"""
    if not await validate_apm_api_key(metrics_batch.service_id, metrics_batch.api_key):
        raise HTTPException(status_code=401, detail="Invalid service ID or API key")
    
    for metric in metrics_batch.metrics:
        metric_doc = {
            "id": str(uuid.uuid4()),
            "service_id": metrics_batch.service_id,
            "timestamp": metrics_batch.timestamp,
            "metric_name": metric.get("name"),
            "metric_value": metric.get("value"),
            "metric_type": metric.get("type", "gauge"),
            "tags": metric.get("tags", {}),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.apm_metrics.insert_one(metric_doc)
    
    await db.apm_services.update_one(
        {"id": metrics_batch.service_id},
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": f"Ingested {len(metrics_batch.metrics)} metrics"}


@router.post("/ingest/dependencies")
async def ingest_dependency(dependency: APMDependencyCall):
    """Ingest dependency call data"""
    if not await validate_apm_api_key(dependency.service_id, dependency.api_key):
        raise HTTPException(status_code=401, detail="Invalid service ID or API key")
    
    dep_doc = {
        "id": str(uuid.uuid4()),
        "service_id": dependency.service_id,
        "transaction_id": dependency.transaction_id,
        "dependency_name": dependency.dependency_name,
        "dependency_type": dependency.dependency_type,
        "target": dependency.target,
        "operation": dependency.operation,
        "duration_ms": dependency.duration_ms,
        "success": dependency.success,
        "error_message": dependency.error_message,
        "timestamp": dependency.timestamp,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.apm_dependencies.insert_one(dep_doc)
    return {"message": "Dependency recorded", "id": dep_doc["id"]}


@router.post("/ingest/errors")
async def ingest_error(error: APMErrorEvent):
    """Ingest error event from APM agent"""
    if not await validate_apm_api_key(error.service_id, error.api_key):
        raise HTTPException(status_code=401, detail="Invalid service ID or API key")
    
    error_doc = {
        "id": str(uuid.uuid4()),
        "service_id": error.service_id,
        "transaction_id": error.transaction_id,
        "error_type": error.error_type,
        "error_message": error.error_message,
        "stack_trace": error.stack_trace,
        "severity": error.severity,
        "endpoint": error.endpoint,
        "user_id": error.user_id,
        "metadata": error.metadata,
        "timestamp": error.timestamp,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.apm_errors.insert_one(error_doc)
    return {"message": "Error recorded", "id": error_doc["id"]}


# Query Endpoints

@router.get("/services/{service_id}/transactions")
async def get_service_transactions(
    service_id: str,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, le=1000),
    current_user: dict = Depends(require_auth)
):
    """Get transactions for a service"""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    
    transactions = await db.apm_transactions.find(
        {"service_id": service_id, "start_time": {"$gte": since}}, {"_id": 0}
    ).sort("start_time", -1).limit(limit).to_list(limit)
    
    return transactions


@router.get("/services/{service_id}/errors")
async def get_service_errors(
    service_id: str,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, le=1000),
    current_user: dict = Depends(require_auth)
):
    """Get errors for a service"""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    
    errors = await db.apm_errors.find(
        {"service_id": service_id, "timestamp": {"$gte": since}}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    return errors


@router.get("/traces/{trace_id}")
async def get_trace_details(trace_id: str, current_user: dict = Depends(require_auth)):
    """Get detailed trace information including spans"""
    transaction = await db.apm_transactions.find_one(
        {"transaction_id": trace_id}, {"_id": 0}
    )
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    dependencies = await db.apm_dependencies.find(
        {"transaction_id": trace_id}, {"_id": 0}
    ).to_list(100)
    
    errors = await db.apm_errors.find(
        {"transaction_id": trace_id}, {"_id": 0}
    ).to_list(10)
    
    return {
        "transaction": transaction,
        "dependencies": dependencies,
        "errors": errors,
        "total_duration_ms": transaction.get("duration_ms"),
        "has_errors": len(errors) > 0
    }
