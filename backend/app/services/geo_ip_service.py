"""
FalconOps AI - IP Geolocation Service
Real IP -> city/country lookup via ip-api.com (free, keyless), giving impossible-travel
detection genuine geo data on real login traffic instead of an always-empty field.
Private/loopback/reserved IPs are skipped (they can't be geolocated). Results are cached
in-memory per IP with a TTL to respect ip-api.com's free-tier rate limit (45 req/min) and
avoid adding real latency to every login.
"""
import ipaddress
import logging
from datetime import datetime, timezone
from typing import Dict

import httpx

logger = logging.getLogger(__name__)

GEO_API_URL = "http://ip-api.com/json/{ip}?fields=status,message,city,country"
GEO_CACHE_TTL_SECONDS = 3600

_geo_cache: Dict[str, Dict] = {}  # ip -> {"geo": str, "cached_at": datetime}


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast)
    except ValueError:
        return False


async def get_geo_location(ip: str) -> str:
    """Real geo lookup for a public IP, e.g. 'Riyadh, Saudi Arabia'. Returns '' for
    private/loopback/unresolvable IPs or on any lookup failure — never raises, never
    fabricates a location."""
    if not ip or not _is_public_ip(ip):
        return ""

    cached = _geo_cache.get(ip)
    if cached and (datetime.now(timezone.utc) - cached["cached_at"]).total_seconds() < GEO_CACHE_TTL_SECONDS:
        return cached["geo"]

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(GEO_API_URL.format(ip=ip))
            if resp.status_code != 200:
                return cached["geo"] if cached else ""
            data = resp.json()
            if data.get("status") != "success":
                return cached["geo"] if cached else ""
            geo = ", ".join(p for p in (data.get("city", ""), data.get("country", "")) if p)
    except Exception as e:
        logger.debug(f"Geo lookup skipped for {ip}: {e}")
        return cached["geo"] if cached else ""

    _geo_cache[ip] = {"geo": geo, "cached_at": datetime.now(timezone.utc)}
    return geo
