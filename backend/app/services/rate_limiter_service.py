"""
FalconOps AI - Rate Limiter
Real per-key rate limiting via Redis INCR+EXPIRE (fixed window), correct across multiple
app instances/replicas — reuses the same Redis connection already established by
metrics_timeseries_service.py rather than opening a second pool. Falls back to an
in-process in-memory limiter if Redis is unavailable: real protection on a single
instance, though (honestly) not correct across replicas in that degraded mode — same
graceful-degrade philosophy already used elsewhere in this codebase (e.g. kafka_pipeline.py's
MongoDB fallback).
"""
import time
import logging
from collections import defaultdict
from typing import Dict, List

logger = logging.getLogger(__name__)

_memory_hits: Dict[str, List[float]] = defaultdict(list)


async def _get_redis():
    try:
        from .metrics_timeseries_service import metrics_timeseries_service
        return await metrics_timeseries_service.get_redis()
    except Exception:
        return None


async def is_rate_limited(key: str, max_requests: int, window_seconds: int) -> bool:
    """Returns True if `key` has exceeded max_requests within window_seconds (a fixed
    window starting at the first hit) — the caller should reject the request."""
    r = await _get_redis()
    if r is not None:
        try:
            redis_key = f"falcon:ratelimit:{key}"
            count = await r.incr(redis_key)
            if count == 1:
                await r.expire(redis_key, window_seconds)
            return count > max_requests
        except Exception as e:
            logger.debug(f"Redis rate limit check failed, falling back to in-memory: {e}")

    now = time.monotonic()
    cutoff = now - window_seconds
    hits = [t for t in _memory_hits[key] if t > cutoff]
    hits.append(now)
    _memory_hits[key] = hits
    return len(hits) > max_requests
