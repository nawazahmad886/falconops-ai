"""
FalconOps AI — Noise Reduction Layer
Dedupe + suppress repeat alerts. Target: 70–80% reduction in alert volume.

Strategy:
- Group by (service, alert, fingerprint) within a sliding window
- Suppress duplicates within the window; emit "rolled_up" summary instead
- Maintain `noise_buckets` collection: bucket_key → {first_seen, last_seen, count, suppressed_count}
"""
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

from ..core.database import db

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_MIN = 10  # default suppression window


def _fingerprint(event: Dict) -> str:
    """Stable hash of (service, alert, host) so similar events collapse."""
    parts = [
        str(event.get("service", "")).strip().lower(),
        str(event.get("alert") or event.get("alert_description") or "").strip().lower(),
        str(event.get("host", "")).strip().lower(),
    ]
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


async def reduce(events: List[Dict], window_min: int = DEFAULT_WINDOW_MIN) -> Dict:
    """Process a batch of events; dedupe + return {kept, suppressed, buckets}."""
    if not events:
        return {"kept": [], "suppressed": [], "buckets": [], "reduction_pct": 0.0}

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_min)
    cutoff_iso = cutoff.isoformat()
    seen: Dict[str, Dict] = {}
    kept: List[Dict] = []
    suppressed: List[Dict] = []

    for ev in events:
        fp = _fingerprint(ev)
        bucket = await db.noise_buckets.find_one({"fingerprint": fp}, {"_id": 0})
        if bucket and bucket.get("last_seen", "") > cutoff_iso:
            # Within suppression window — collapse
            suppressed.append({**ev, "fingerprint": fp})
            await db.noise_buckets.update_one(
                {"fingerprint": fp},
                {"$set": {"last_seen": datetime.now(timezone.utc).isoformat()},
                 "$inc": {"count": 1, "suppressed_count": 1}},
            )
        else:
            kept.append({**ev, "fingerprint": fp})
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.noise_buckets.update_one(
                {"fingerprint": fp},
                {"$set": {"last_seen": now_iso, "service": ev.get("service"),
                          "alert": ev.get("alert") or ev.get("alert_description"),
                          "host": ev.get("host")},
                 "$setOnInsert": {"first_seen": now_iso, "fingerprint": fp},
                 "$inc": {"count": 1}},
                upsert=True,
            )
        seen[fp] = ev

    total = len(events)
    reduction_pct = round((len(suppressed) / total) * 100, 1) if total else 0.0
    return {
        "kept": kept,
        "suppressed": suppressed,
        "kept_count": len(kept),
        "suppressed_count": len(suppressed),
        "reduction_pct": reduction_pct,
        "window_min": window_min,
    }


async def get_top_noisy_buckets(limit: int = 20) -> List[Dict]:
    """For the AI Insight Panel: which (service, alert) pairs are noisiest?"""
    cursor = db.noise_buckets.find({}, {"_id": 0}).sort("suppressed_count", -1).limit(limit)
    out = []
    async for b in cursor:
        out.append(b)
    return out


async def cleanup_old_buckets(days: int = 7) -> int:
    """Maintenance: drop buckets older than N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    r = await db.noise_buckets.delete_many({"last_seen": {"$lt": cutoff}})
    return r.deleted_count
