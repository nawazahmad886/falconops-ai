"""
FalconOps AI — OneAgent ingest + management routes.

Receives telemetry from FalconOpsAI OneAgent (Go binary):
  POST /api/ingest/logs | /metrics | /traces | /heartbeat  (X-API-Key auth, gzip JSON)
Management (JWT auth):
  /api/oneagent/keys (admin CRUD), /api/oneagent/agents, downloads + install.sh
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from ..core.database import db
from ..utils.auth import require_admin, require_auth

logger = logging.getLogger(__name__)

ingest_router = APIRouter(prefix="/api/ingest", tags=["OneAgent Ingest"])
mgmt_router = APIRouter(prefix="/api/oneagent", tags=["OneAgent Management"])

ONEAGENT_DIR = os.environ.get(
    "ONEAGENT_DIR",
    str(Path(__file__).resolve().parents[2] / "static" / "agents" / "oneagent"))
MAX_BATCH = 2000
INGEST_RATE_LIMIT_PER_MIN = int(os.environ.get("ONEAGENT_INGEST_RATE_LIMIT_PER_MIN", "120"))


# ─────────────────────────────────────────────
#  API-key auth
# ─────────────────────────────────────────────

def _hash_key(raw_key: str) -> str:
    """API keys are high-entropy (32 random bytes) so a plain SHA-256 digest is
    sufficient — unlike passwords, no salt/slow-hash is needed, and a fast
    deterministic hash lets us look keys up directly by index."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# In-memory fallback bucket store: api_key_id -> [count, window]. Used only when
# Redis is unavailable; resets on process restart (acceptable for a best-effort limit).
_local_rate_buckets: Dict[str, list] = {}


async def _check_rate_limit(key_id: str) -> None:
    """Fixed-window rate limit (per API key) on ingest endpoints, so a leaked key
    can't be used for unbounded write amplification."""
    window = int(time.time() // 60)
    bucket_key = f"oneagent:ratelimit:{key_id}:{window}"
    try:
        from ..services.metrics_timeseries_service import metrics_timeseries_service
        r = await metrics_timeseries_service.get_redis()
    except Exception:
        r = None
    if r is not None:
        try:
            count = await r.incr(bucket_key)
            if count == 1:
                await r.expire(bucket_key, 60)
            if count > INGEST_RATE_LIMIT_PER_MIN:
                raise HTTPException(status_code=429, detail="rate limit exceeded, try again shortly")
            return
        except HTTPException:
            raise
        except Exception:
            pass  # fall through to in-memory best-effort limiting
    bucket = _local_rate_buckets.get(key_id)
    if bucket is None or bucket[1] != window:
        bucket = [0, window]
    bucket[0] += 1
    _local_rate_buckets[key_id] = bucket
    if bucket[0] > INGEST_RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="rate limit exceeded, try again shortly")


async def _verify_api_key(x_api_key: Optional[str] = Header(None)) -> Dict:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    key_hash = _hash_key(x_api_key)
    key_doc = await db.oneagent_api_keys.find_one({"key_hash": key_hash, "revoked": False}, {"_id": 0})
    if not key_doc:
        # Migrate legacy plaintext-stored keys (pre-hashing) transparently on first use.
        legacy_doc = await db.oneagent_api_keys.find_one({"key": x_api_key, "revoked": False}, {"_id": 0})
        if legacy_doc:
            await db.oneagent_api_keys.update_one(
                {"id": legacy_doc["id"]}, {"$set": {"key_hash": key_hash}, "$unset": {"key": ""}})
            key_doc = legacy_doc
    if not key_doc:
        raise HTTPException(status_code=403, detail="invalid or revoked API key")
    await _check_rate_limit(key_doc["id"])
    await db.oneagent_api_keys.update_one(
        {"id": key_doc["id"]},
        {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}, "$inc": {"requests": 1}})
    return key_doc


async def _read_batch(request: Request) -> Dict[str, Any]:
    raw = await request.body()
    if request.headers.get("content-encoding", "").lower() == "gzip":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid gzip body")
    try:
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    batch = payload.get("batch")
    if not isinstance(batch, list):
        raise HTTPException(status_code=400, detail="'batch' array required")
    if len(batch) > MAX_BATCH:
        raise HTTPException(status_code=413, detail=f"batch too large (max {MAX_BATCH})")
    return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────
#  Ingest endpoints
# ─────────────────────────────────────────────

@ingest_router.post("/logs")
async def ingest_logs(request: Request, key: Dict = Depends(_verify_api_key)) -> Dict:
    payload = await _read_batch(request)
    host = payload.get("host", "unknown")
    now = _now_iso()
    docs = []
    for item in payload["batch"]:
        level = str(item.get("level") or "INFO").upper()
        docs.append({
            "id": str(uuid.uuid4()),
            "timestamp": item.get("timestamp") or now,
            "severity": level.lower(),
            "level": level,
            "service": item.get("service") or "unknown",
            "message": str(item.get("message") or "")[:8000],
            "category": "oneagent",
            "host": item.get("tags", {}).get("host") or host,
            "source": item.get("source") or "oneagent",
            "tags": item.get("tags") or {},
            "created_at": now,
        })
    if docs:
        await db.logs.insert_many(docs)
    return {"status": "ok", "ingested": len(docs)}


@ingest_router.post("/metrics")
async def ingest_metrics(request: Request, key: Dict = Depends(_verify_api_key)) -> Dict:
    payload = await _read_batch(request)
    host = payload.get("host", "unknown")
    now = _now_iso()
    docs = []
    for item in payload["batch"]:
        name = item.get("name")
        value = item.get("value")
        if not name or not isinstance(value, (int, float)):
            continue
        tags = item.get("tags") or {}
        tags.setdefault("host", host)
        if item.get("service"):
            tags.setdefault("service", item["service"])
        docs.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "value": float(value),
            "timestamp": item.get("timestamp") or now,
            "tags": tags,
            "unit": item.get("unit") or "",
            "type": "gauge",
            "tenant_id": None,
            "processed_at": now,
            "source": "oneagent",
        })
    if docs:
        await db.metrics_timeseries.insert_many(docs)
    return {"status": "ok", "ingested": len(docs)}


@ingest_router.post("/traces")
async def ingest_traces(request: Request, key: Dict = Depends(_verify_api_key)) -> Dict:
    payload = await _read_batch(request)
    now = _now_iso()
    span_docs = []
    traces: Dict[str, Dict] = {}
    for item in payload["batch"]:
        trace_id = item.get("trace_id")
        if not trace_id:
            continue
        service = item.get("service") or "unknown"
        duration = float(item.get("duration_ms") or 0)
        is_err = str(item.get("status", "")).upper() == "ERROR"
        span_docs.append({
            "id": str(uuid.uuid4()),
            "trace_id": trace_id,
            "span_id": item.get("span_id"),
            "parent_span_id": item.get("parent_span_id") or None,
            "name": item.get("name") or "span",
            "service_name": service,
            "duration_ms": duration,
            "status": "ERROR" if is_err else "OK",
            "start_time": item.get("timestamp") or now,
            "attributes": item.get("attributes") or {},
            "received_at": now,
            "source": "oneagent",
        })
        t = traces.setdefault(trace_id, {"services": set(), "duration_ms": 0.0,
                                         "has_error": False, "root_span_name": None})
        t["services"].add(service)
        t["duration_ms"] = max(t["duration_ms"], duration)
        t["has_error"] = t["has_error"] or is_err
        if not item.get("parent_span_id"):
            t["root_span_name"] = item.get("name")
    if span_docs:
        await db.otel_spans.insert_many(span_docs)
    for trace_id, t in traces.items():
        await db.otel_traces.update_one(
            {"trace_id": trace_id},
            {"$set": {"received_at": now, "source": "oneagent"},
             "$addToSet": {"services": {"$each": sorted(t["services"])}},
             "$max": {"duration_ms": t["duration_ms"]},
             "$setOnInsert": {"trace_id": trace_id,
                              "root_span_name": t["root_span_name"] or "span",
                              "has_error": t["has_error"]}},
            upsert=True)
        if t["has_error"]:
            await db.otel_traces.update_one({"trace_id": trace_id}, {"$set": {"has_error": True}})
    return {"status": "ok", "ingested": len(span_docs), "traces": len(traces)}


@ingest_router.post("/netflows")
async def ingest_netflows(request: Request, key: Dict = Depends(_verify_api_key)) -> Dict:
    """Receives netflow plugin batches (see oneagent/pkg/plugins/netflow) — established
    TCP connections observed via /proc/net/tcp{,6}, attributed to a service where
    possible. Delegates enrichment (GeoIP/ASN, threat intel) and persistence to
    network_flow_service so this route stays a thin, consistent ingest shim like
    ingest_logs/ingest_metrics/ingest_traces above."""
    payload = await _read_batch(request)
    host = payload.get("host", "unknown")
    from ..services.network_flow_service import network_flow_service
    result = await network_flow_service.enrich_and_persist_batch(host, payload["batch"])
    return {"status": "ok", **result}


@ingest_router.post("/heartbeat")
async def ingest_heartbeat(request: Request, key: Dict = Depends(_verify_api_key)) -> Dict:
    raw = await request.body()
    if request.headers.get("content-encoding", "").lower() == "gzip":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid gzip body")
    try:
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    host = payload.get("host") or "unknown"
    now = _now_iso()
    await db.oneagent_agents.update_one(
        {"host": host},
        {"$set": {
            "host": host,
            "environment": payload.get("environment"),
            "agent_version": payload.get("agent_version"),
            "services": payload.get("services") or [],
            "api_key_id": key["id"],
            "api_key_name": key.get("name"),
            "last_seen": now,
        }, "$setOnInsert": {"id": str(uuid.uuid4()), "first_seen": now}},
        upsert=True)
    return {"status": "ok"}


# ─────────────────────────────────────────────
#  Management: API keys + agent inventory
# ─────────────────────────────────────────────

class KeyCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


@mgmt_router.post("/keys")
async def create_key(body: KeyCreateIn, admin: dict = Depends(require_admin)) -> Dict:
    key = "fops_" + secrets.token_urlsafe(32)
    key_preview = (key[:9] + "…" + key[-4:]) if len(key) > 13 else "…"
    doc = {
        "id": str(uuid.uuid4()),
        "key_hash": _hash_key(key),
        "key_preview": key_preview,
        "name": body.name,
        "created_by": admin.get("email"),
        "created_at": _now_iso(),
        "revoked": False,
        "requests": 0,
        "last_used_at": None,
    }
    await db.oneagent_api_keys.insert_one({**doc})
    response = {k: v for k, v in doc.items() if k != "key_hash"}
    response["key"] = key  # full key returned ONCE at creation, never persisted
    return response


@mgmt_router.get("/keys")
async def list_keys(admin: dict = Depends(require_admin)) -> Dict:
    rows = await db.oneagent_api_keys.find({}, {"_id": 0, "key_hash": 0, "key": 0}).sort("created_at", -1).to_list(100)
    return {"keys": rows}


@mgmt_router.delete("/keys/{key_id}")
async def revoke_key(key_id: str, admin: dict = Depends(require_admin)) -> Dict:
    r = await db.oneagent_api_keys.update_one({"id": key_id}, {"$set": {"revoked": True}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="key not found")
    return {"status": "revoked"}


@mgmt_router.get("/agents")
async def list_agents(user: dict = Depends(require_auth)) -> Dict:
    rows = await db.oneagent_agents.find({}, {"_id": 0}).sort("last_seen", -1).to_list(200)
    return {"agents": rows, "count": len(rows)}


# ─────────────────────────────────────────────
#  Downloads (public — the installer runs before any auth exists)
# ─────────────────────────────────────────────

@mgmt_router.get("/install.sh")
async def install_script() -> FileResponse:
    bundled = Path(ONEAGENT_DIR) / "install.sh"
    path = bundled if bundled.exists() else Path("/app/oneagent/deploy/install.sh")
    if not path.exists():
        raise HTTPException(status_code=404, detail="install.sh not found on this deployment")
    return FileResponse(str(path), media_type="text/x-shellscript", filename="install.sh")


@mgmt_router.get("/download/binary")
async def download_binary(arch: str = Query("amd64", pattern="^(amd64|arm64)$")) -> FileResponse:
    path = Path(ONEAGENT_DIR) / f"falconops-oneagent-linux-{arch}"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"binary for {arch} not found on this deployment")
    return FileResponse(str(path), media_type="application/octet-stream",
                        filename=f"falconops-oneagent-linux-{arch}")


@mgmt_router.get("/download/source")
async def download_source() -> FileResponse:
    path = Path(ONEAGENT_DIR) / "falconops-oneagent-src.tar.gz"
    if not path.exists():
        raise HTTPException(status_code=404, detail="source bundle not found on this deployment")
    return FileResponse(str(path), media_type="application/gzip",
                        filename="falconops-oneagent-src.tar.gz")
