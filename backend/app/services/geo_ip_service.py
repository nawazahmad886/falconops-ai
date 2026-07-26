"""
FalconOps AI - IP Geolocation Service
Real IP -> city/country/ASN/ISP lookup via ip-api.com (free, keyless), giving
impossible-travel detection and network path analysis genuine geo/ASN data on real
traffic instead of an always-empty field. Private/loopback/reserved IPs are skipped
(they can't be geolocated). Results are cached in-memory per IP with a TTL to respect
ip-api.com's free-tier rate limit (45 req/min) and avoid adding real latency to every
lookup.
"""
import ipaddress
import logging
from datetime import datetime, timezone
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

GEO_API_URL = (
    "http://ip-api.com/json/{ip}"
    "?fields=status,message,city,country,as,asname,isp,org,proxy,hosting,mobile"
)
GEO_CACHE_TTL_SECONDS = 3600

_geo_cache: Dict[str, Dict] = {}  # ip -> {"data": dict, "cached_at": datetime}


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast)
    except ValueError:
        return False


async def _fetch_geo_data(ip: str) -> Dict[str, Any]:
    """Shared fetch+cache for get_geo_location and get_ip_intel. Returns {} for
    private/loopback/unresolvable IPs or on any lookup failure — never raises, never
    fabricates data."""
    if not ip or not _is_public_ip(ip):
        return {}

    cached = _geo_cache.get(ip)
    if cached and (datetime.now(timezone.utc) - cached["cached_at"]).total_seconds() < GEO_CACHE_TTL_SECONDS:
        return cached["data"]

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(GEO_API_URL.format(ip=ip))
            if resp.status_code != 200:
                return cached["data"] if cached else {}
            data = resp.json()
            if data.get("status") != "success":
                return cached["data"] if cached else {}
    except Exception as e:
        logger.debug(f"Geo lookup skipped for {ip}: {e}")
        return cached["data"] if cached else {}

    _geo_cache[ip] = {"data": data, "cached_at": datetime.now(timezone.utc)}
    return data


async def get_geo_location(ip: str) -> str:
    """Real geo lookup for a public IP, e.g. 'Riyadh, Saudi Arabia'. Returns '' for
    private/loopback/unresolvable IPs or on any lookup failure — never raises, never
    fabricates a location."""
    data = await _fetch_geo_data(ip)
    return ", ".join(p for p in (data.get("city", ""), data.get("country", "")) if p)


async def get_ip_intel(ip: str) -> Dict[str, Any]:
    """Real ASN/ISP/proxy/hosting lookup for a public IP, e.g.
    {"asn": "AS15169 Google LLC", "isp": "Google LLC", "org": "Google LLC",
     "is_proxy_or_vpn": False, "is_hosting": True, "is_mobile": False}.
    Returns {} for private/loopback/unresolvable IPs or on any lookup failure — never
    raises, never fabricates data."""
    data = await _fetch_geo_data(ip)
    if not data:
        return {}
    return {
        "asn": data.get("as") or None,
        "isp": data.get("isp") or None,
        "org": data.get("org") or None,
        "is_proxy_or_vpn": data.get("proxy"),
        "is_hosting": data.get("hosting"),
        "is_mobile": data.get("mobile"),
    }
