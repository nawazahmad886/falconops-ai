"""
FalconOps AI — Vector Memory Service
Semantic memory for AI Copilot using sentence-transformers + MongoDB cosine similarity.

Embeds:
  - Past AI Copilot conversation messages (per-tenant scoped)
  - AI Insights from the Autonomous AI Pipeline (root cause + recommended action)

On every new chat message, the top-K most semantically similar memories are retrieved
and injected as RAG context so the agent recalls past incidents across sessions.

Storage: `vector_memory` collection (one doc per memory) with embeddings stored as
arrays. Cosine similarity computed in Python (NumPy) — fine for <10k entries.
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

import numpy as np

from ..core.database import db

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384

# Lazy-loaded model (only loaded when first embed is requested)
_model = None
_model_loading_lock = asyncio.Lock()


async def _get_model():
    """Lazy-load the embedding model on first use. Returns None if unavailable."""
    global _model
    if _model is not None:
        return _model
    async with _model_loading_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model %s ...", MODEL_NAME)
            # Load in a thread to avoid blocking the event loop
            _model = await asyncio.to_thread(SentenceTransformer, MODEL_NAME)
            logger.info("Vector memory model loaded (dim=%d)", _model.get_sentence_embedding_dimension())
            return _model
        except Exception as e:
            logger.warning("Vector memory unavailable (sentence-transformers not installed?): %s", e)
            return None


# ─────────────────────────────────────────────────────
#  Embed + store
# ─────────────────────────────────────────────────────

async def embed_text(text: str) -> Optional[List[float]]:
    """Generate L2-normalized 384-dim embedding. Returns None if model unavailable."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()[:2048]  # cap input size
    if not text:
        return None
    model = await _get_model()
    if model is None:
        return None
    try:
        vec = await asyncio.to_thread(
            model.encode, text, convert_to_numpy=True, normalize_embeddings=True
        )
        return vec.astype(float).tolist()
    except Exception as e:
        logger.warning("embed_text failed: %s", e)
        return None


async def remember(
    *,
    text: str,
    kind: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    source_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Optional[str]:
    """Persist a memory: text + embedding. Idempotent on (kind, source_id) per tenant."""
    embedding = await embed_text(text)
    if embedding is None:
        return None
    import uuid
    memory_id = str(uuid.uuid4())
    doc = {
        "id": memory_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_id": session_id,
        "kind": kind,  # 'chat_message' | 'ai_insight' | 'incident' | 'runbook'
        "source_id": source_id,
        "text": text[:4000],
        "embedding": embedding,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if source_id:
        # Don't put 'id' in $set + $setOnInsert (Mongo conflicts).
        # Use $set for the data + $setOnInsert just for id+created_at on first insert.
        set_fields = {k: v for k, v in doc.items() if k not in ("id", "created_at")}
        await db.vector_memory.update_one(
            {"kind": kind, "source_id": source_id, "tenant_id": tenant_id},
            {"$set": set_fields,
             "$setOnInsert": {"id": memory_id, "created_at": doc["created_at"]}},
            upsert=True,
        )
    else:
        await db.vector_memory.insert_one(doc)
    return memory_id


# ─────────────────────────────────────────────────────
#  Retrieve
# ─────────────────────────────────────────────────────

def _cosine(a: List[float], b: List[float]) -> float:
    av, bv = np.array(a), np.array(b)
    # Inputs are pre-normalized → cosine = dot product
    return float(np.dot(av, bv))


async def search(
    query_text: str,
    *,
    top_k: int = 5,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    kinds: Optional[List[str]] = None,
    min_score: float = 0.30,
    days: int = 90,
    exclude_session_id: Optional[str] = None,
) -> List[Dict]:
    """Return top-K most similar memories. Empty list if no model or no matches."""
    qvec = await embed_text(query_text)
    if qvec is None:
        return []

    # Pre-filter at the DB layer — only memories the user can see + recent
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q: Dict = {"created_at": {"$gte": cutoff}}
    if tenant_id is not None:
        q["tenant_id"] = tenant_id
    if user_id is not None:
        q["user_id"] = user_id
    if kinds:
        q["kind"] = {"$in": kinds}
    if exclude_session_id:
        q["session_id"] = {"$ne": exclude_session_id}

    candidates = await db.vector_memory.find(q, {"_id": 0}).limit(2000).to_list(length=2000)
    scored: List[Dict] = []
    for c in candidates:
        emb = c.get("embedding")
        if not emb:
            continue
        score = _cosine(qvec, emb)
        if score < min_score:
            continue
        scored.append({
            "id": c.get("id"),
            "kind": c.get("kind"),
            "source_id": c.get("source_id"),
            "session_id": c.get("session_id"),
            "text": c.get("text"),
            "metadata": c.get("metadata", {}),
            "score": round(score, 4),
            "created_at": c.get("created_at"),
        })
    scored.sort(key=lambda m: m["score"], reverse=True)
    return scored[:top_k]


# ─────────────────────────────────────────────────────
#  Maintenance
# ─────────────────────────────────────────────────────

async def stats(tenant_id: Optional[str] = None) -> Dict:
    q = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.vector_memory.count_documents(q)
    by_kind: Dict[str, int] = {}
    cursor = db.vector_memory.aggregate([
        {"$match": q},
        {"$group": {"_id": "$kind", "count": {"$sum": 1}}}
    ])
    async for r in cursor:
        by_kind[r["_id"] or "unknown"] = r["count"]
    model = _model is not None
    return {
        "total": total,
        "by_kind": by_kind,
        "model_loaded": model,
        "model_name": MODEL_NAME,
        "embedding_dim": EMBED_DIM,
    }


async def prune_old(days: int = 90) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    r = await db.vector_memory.delete_many({"created_at": {"$lt": cutoff}})
    return r.deleted_count


def format_for_prompt(memories: List[Dict]) -> str:
    """Return a compact RAG-context block to inject into the LLM prompt."""
    if not memories:
        return ""
    lines = ["Past similar conversations / incidents (use ONLY if relevant):"]
    for i, m in enumerate(memories, 1):
        kind = m.get("kind", "memory")
        score = m.get("score", 0)
        snippet = (m.get("text") or "")[:300].replace("\n", " ")
        lines.append(f"  [{i}] ({kind}, similarity {score:.2f}) {snippet}")
    return "\n".join(lines)
