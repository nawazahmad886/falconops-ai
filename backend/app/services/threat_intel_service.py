"""
FalconOps AI - Threat Intelligence Feed Service
Real IOC feed sync from free, keyless sources (abuse.ch Feodo Tracker, Spamhaus DROP)
into db.threat_intel_iocs, used by security_service.py's malicious-IP check. Replaces the
previous KNOWN_MALICIOUS_IPS in-memory empty set (dead code — nothing ever populated it).

Network failures degrade honestly: on fetch failure we log and keep serving whatever was
last synced (or nothing, if never synced) — never raise into the caller, never fabricate
a match.
"""
import os
import ipaddress
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from ..core.database import db

logger = logging.getLogger(__name__)

FEODO_TRACKER_URL = "https://feodotracker.abuse.ch/downloads/ipblocklist.json"
SPAMHAUS_DROP_URL = "https://www.spamhaus.org/drop/drop.txt"
THREAT_INTEL_REFRESH_HOURS = int(os.environ.get("THREAT_INTEL_REFRESH_HOURS", "6"))

# In-memory CIDR cache — refreshed each sync; avoids a per-event DB scan for containment
# checks. Exact-IP matches still go straight to the DB (cheap indexed lookup).
_cidr_cache: List[Dict] = []
_cidr_cache_loaded = False


async def refresh_ioc_feed() -> Dict:
    """Fetch real IOC feeds and upsert into db.threat_intel_iocs. Never raises — on
    network failure, logs a warning and leaves existing data untouched."""
    ip_count = 0
    cidr_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(FEODO_TRACKER_URL)
            if resp.status_code == 200:
                entries = resp.json()
                for entry in entries:
                    ip = entry.get("ip_address")
                    if not ip:
                        continue
                    await db.threat_intel_iocs.update_one(
                        {"type": "ip", "value": ip},
                        {"$set": {
                            "type": "ip", "value": ip, "source": "abuse.ch Feodo Tracker",
                            "malware_family": entry.get("malware"), "confidence": entry.get("confidence_level"),
                            "first_seen": entry.get("first_seen_utc"), "synced_at": now_iso,
                        }},
                        upsert=True,
                    )
                    ip_count += 1
            else:
                logger.warning(f"Feodo Tracker fetch returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"Feodo Tracker IOC fetch failed (leaving existing data in place): {e}")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(SPAMHAUS_DROP_URL)
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith(";"):
                        continue
                    cidr = line.split(";")[0].strip()
                    if not cidr:
                        continue
                    try:
                        ipaddress.ip_network(cidr, strict=False)
                    except ValueError:
                        continue
                    await db.threat_intel_iocs.update_one(
                        {"type": "cidr", "value": cidr},
                        {"$set": {"type": "cidr", "value": cidr, "source": "Spamhaus DROP", "synced_at": now_iso}},
                        upsert=True,
                    )
                    cidr_count += 1
            else:
                logger.warning(f"Spamhaus DROP fetch returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"Spamhaus DROP IOC fetch failed (leaving existing data in place): {e}")

    if cidr_count:
        await _reload_cidr_cache()

    logger.info(f"Threat intel refresh: {ip_count} IP IOC(s), {cidr_count} CIDR IOC(s) synced")
    return {"ip_count": ip_count, "cidr_count": cidr_count, "synced_at": now_iso}


async def _reload_cidr_cache() -> None:
    global _cidr_cache, _cidr_cache_loaded
    rows = await db.threat_intel_iocs.find({"type": "cidr"}, {"_id": 0}).to_list(5000)
    cache = []
    for r in rows:
        try:
            cache.append({"network": ipaddress.ip_network(r["value"], strict=False), "doc": r})
        except ValueError:
            continue
    _cidr_cache = cache
    _cidr_cache_loaded = True


async def is_malicious_ip(ip: str) -> Optional[Dict]:
    """Real IOC lookup: exact-match against synced IPs, then CIDR containment against
    synced netblocks. Returns the matching IOC doc (source/malware_family) or None."""
    global _cidr_cache_loaded
    if not ip:
        return None

    exact = await db.threat_intel_iocs.find_one({"type": "ip", "value": ip}, {"_id": 0})
    if exact:
        return exact

    if not _cidr_cache_loaded:
        await _reload_cidr_cache()

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None

    for entry in _cidr_cache:
        if addr in entry["network"]:
            return entry["doc"]
    return None


async def threat_intel_refresh_scheduler():
    """Background loop mirroring autonomous_ops_orchestrator.sla_breach_scheduler's shape."""
    while True:
        try:
            await refresh_ioc_feed()
        except Exception as e:
            logger.error(f"Threat intel refresh scheduler error: {e}")
        await asyncio.sleep(THREAT_INTEL_REFRESH_HOURS * 3600)


async def get_ioc_stats() -> Dict:
    ip_count = await db.threat_intel_iocs.count_documents({"type": "ip"})
    cidr_count = await db.threat_intel_iocs.count_documents({"type": "cidr"})
    latest = await db.threat_intel_iocs.find_one({}, {"_id": 0, "synced_at": 1}, sort=[("synced_at", -1)])
    return {
        "ip_iocs": ip_count,
        "cidr_iocs": cidr_count,
        "last_synced_at": (latest or {}).get("synced_at"),
    }
