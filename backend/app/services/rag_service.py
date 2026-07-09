"""
FalconOps AI — Lightweight RAG (ChromaDB embedded)
Indexes: recent error/warning logs + incident history (incl. past AI analyses).
Embeddings reuse the sentence-transformers model from vector_memory_service —
no external API calls, fully on-prem compatible.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.database import db
from . import vector_memory_service

logger = logging.getLogger(__name__)

CHROMA_PATH = os.environ.get(
    "CHROMA_PATH",
    str(Path(__file__).resolve().parents[2] / "data" / "chroma"))
INCIDENTS_COLLECTION = "falcon_incident_history"
LOGS_COLLECTION = "falcon_recent_logs"

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import chromadb
        os.makedirs(CHROMA_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        return _client
    except Exception as e:
        logger.warning("ChromaDB unavailable: %s", e)
        return None


def _collection(name: str):
    client = _get_client()
    if client is None:
        return None
    # embedding_function=None → we always pass embeddings explicitly (no onnx download)
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


async def _embed(text: str) -> Optional[List[float]]:
    return await vector_memory_service.embed_text(text)


# ─────────────────────────────────────────────
#  Indexing
# ─────────────────────────────────────────────

async def index_incident_history(limit: int = 200) -> int:
    """Upsert incidents (+ their AI root cause) and past intelligence analyses."""
    col = _collection(INCIDENTS_COLLECTION)
    if col is None:
        return 0
    indexed = 0
    incidents = await db.incidents.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for inc in incidents:
        rc = (inc.get("ai_analysis") or {}).get("root_cause", "")
        text = f"[{inc.get('severity')}] {inc.get('title', '')} | service={inc.get('service', '')} | root_cause: {rc}"[:1500]
        emb = await _embed(text)
        if emb is None:
            continue
        col.upsert(ids=[f"incident:{inc.get('id')}"], embeddings=[emb], documents=[text],
                   metadatas=[{"kind": "incident", "service": inc.get("service") or "",
                               "severity": inc.get("severity") or "", "status": inc.get("status") or "",
                               "created_at": inc.get("created_at") or ""}])
        indexed += 1
    analyses = await db.ai_intelligence_analyses.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for a in analyses:
        text = f"Q: {a.get('query', '')} | RCA: {a.get('summary', '')} | actions: {', '.join(a.get('recommended_actions', [])[:3])}"[:1500]
        emb = await _embed(text)
        if emb is None:
            continue
        col.upsert(ids=[f"analysis:{a.get('id')}"], embeddings=[emb], documents=[text],
                   metadatas=[{"kind": "past_analysis", "service": a.get("service") or "",
                               "confidence": float(a.get("confidence") or 0),
                               "created_at": a.get("created_at") or ""}])
        indexed += 1
    return indexed


async def index_recent_logs(hours: int = 24, limit: int = 300) -> int:
    """Embed recent ERROR/WARN logs only (keeps the store small)."""
    col = _collection(LOGS_COLLECTION)
    if col is None:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q = {"timestamp": {"$gte": cutoff}, "level": {"$in": ["ERROR", "CRITICAL", "FATAL", "WARN", "WARNING"]}}
    rows = await db.logs.find(q, {"_id": 0, "embedding": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    indexed = 0
    for r in rows:
        text = f"[{r.get('level')}] {r.get('service', '')}: {(r.get('message') or '')[:400]}"
        emb = await _embed(text)
        if emb is None:
            continue
        col.upsert(ids=[f"log:{r.get('id')}"], embeddings=[emb], documents=[text],
                   metadatas=[{"kind": "log", "service": r.get("service") or "",
                               "level": r.get("level") or "", "timestamp": r.get("timestamp") or ""}])
        indexed += 1
    return indexed


async def reindex_all() -> Dict[str, int]:
    inc = await index_incident_history()
    lg = await index_recent_logs()
    return {"incidents_indexed": inc, "logs_indexed": lg}


# ─────────────────────────────────────────────
#  Retrieval
# ─────────────────────────────────────────────

async def _query(collection_name: str, query_text: str, top_k: int, where: Optional[Dict] = None) -> List[Dict]:
    col = _collection(collection_name)
    if col is None or col.count() == 0:
        return []
    emb = await _embed(query_text)
    if emb is None:
        return []
    kwargs: Dict[str, Any] = {"query_embeddings": [emb], "n_results": min(top_k, col.count())}
    if where:
        kwargs["where"] = where
    try:
        res = col.query(**kwargs)
    except Exception as e:
        logger.warning("Chroma query failed: %s", e)
        return []
    out = []
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    ids = (res.get("ids") or [[]])[0]
    for i, doc in enumerate(docs):
        sim = round(1.0 - (dists[i] if i < len(dists) else 1.0), 4)
        out.append({"id": ids[i] if i < len(ids) else None, "text": doc,
                    "metadata": metas[i] if i < len(metas) else {}, "similarity": sim})
    return [m for m in out if m["similarity"] >= 0.25]


async def find_similar_incidents(query_text: str, top_k: int = 3, service: Optional[str] = None) -> List[Dict]:
    where = {"service": service} if service else None
    results = await _query(INCIDENTS_COLLECTION, query_text, top_k, where)
    if not results and service:
        results = await _query(INCIDENTS_COLLECTION, query_text, top_k)
    return results


async def find_similar_logs(query_text: str, top_k: int = 5, service: Optional[str] = None) -> List[Dict]:
    where = {"service": service} if service else None
    results = await _query(LOGS_COLLECTION, query_text, top_k, where)
    if not results and service:
        results = await _query(LOGS_COLLECTION, query_text, top_k)
    return results


async def rag_stats() -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"available": False, "reason": "chromadb not installed / failed to init"}
    inc_col = _collection(INCIDENTS_COLLECTION)
    log_col = _collection(LOGS_COLLECTION)
    return {
        "available": True,
        "store": "chromadb (embedded)",
        "path": CHROMA_PATH,
        "incident_history_count": inc_col.count() if inc_col else 0,
        "recent_logs_count": log_col.count() if log_col else 0,
        "embedding_model": vector_memory_service.MODEL_NAME,
    }
