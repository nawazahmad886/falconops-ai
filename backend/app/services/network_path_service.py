"""
FalconOps AI - Network Path Service
Real ICMP TTL-based traceroute (ping3) with per-hop packet-loss/jitter, reverse DNS,
GeoIP/ASN/ISP enrichment, plus real DNS/TCP/TLS timing to the destination and
loop/route-change/blocked-path detection.

Never fabricates data: any stage that can't run (no CAP_NET_RAW, DNS failure, TCP
refusal) degrades to None/False fields rather than raising or inventing numbers —
same philosophy as geo_ip_service.py.
"""
import asyncio
import logging
import re
import socket
import ssl
import time
from typing import Any, Dict, List, Optional

import ping3
import ping3.errors

from .geo_ip_service import get_geo_location, get_ip_intel

logger = logging.getLogger(__name__)

# ping3 raises typed exceptions (e.g. TimeToLiveExpired) instead of returning sentinel
# values — set once at module scope so it isn't silently reverted if some other module
# imports ping3 first and leaves it at the default (False).
ping3.EXCEPTIONS = True

MAX_HOPS = 30
PROBES_PER_HOP = 3
PROBE_TIMEOUT_S = 1.2
MAX_CONSECUTIVE_SILENT_HOPS = 6  # early-abort past this many all-silent hop rows
MIN_HOPS_BEFORE_EARLY_ABORT = 5
TCP_CONNECT_TIMEOUT_S = 5
DNS_TIMEOUT_S = 3
GEO_ENRICH_CONCURRENCY = 5

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


# ─────────────────────────────────────────────
#  ICMP probing (blocking calls run via asyncio.to_thread)
# ─────────────────────────────────────────────

def _extract_responder_ip(exc: "ping3.errors.TimeToLiveExpired") -> Optional[str]:
    """ping3's TimeToLiveExpired carries the replying router's IP on ip_header, but the
    exact shape can vary across versions — try the documented attribute first, then
    fall back to extracting an IPv4 from the exception's string form. Never raises."""
    try:
        hdr = getattr(exc, "ip_header", None)
        if isinstance(hdr, dict) and hdr.get("src_addr"):
            return hdr["src_addr"]
    except Exception:
        pass
    try:
        m = _IPV4_RE.search(str(exc))
        return m.group(0) if m else None
    except Exception:
        return None


def _probe_once_sync(target_ip: str, ttl: int, timeout_s: float) -> Dict[str, Any]:
    """One ICMP echo at the given TTL. Returns
    {"rtt_ms": Optional[float], "responder_ip": Optional[str], "is_destination_reply": bool}.
    Never raises except PermissionError, which the caller uses to detect a missing
    CAP_NET_RAW (raw ICMP socket) capability."""
    start = time.perf_counter()
    try:
        delay = ping3.ping(target_ip, ttl=ttl, timeout=timeout_s, unit="s")
    except ping3.errors.TimeToLiveExpired as e:
        rtt_ms = (time.perf_counter() - start) * 1000
        return {"rtt_ms": round(rtt_ms, 2), "responder_ip": _extract_responder_ip(e), "is_destination_reply": False}
    except PermissionError:
        raise
    except ping3.errors.PingError:
        return {"rtt_ms": None, "responder_ip": None, "is_destination_reply": False}
    except OSError:
        return {"rtt_ms": None, "responder_ip": None, "is_destination_reply": False}

    if not delay:
        return {"rtt_ms": None, "responder_ip": None, "is_destination_reply": False}
    return {"rtt_ms": round(delay * 1000, 2), "responder_ip": target_ip, "is_destination_reply": True}


async def _probe_hop(target_ip: str, ttl: int) -> Dict[str, Any]:
    """Fires PROBES_PER_HOP probes concurrently (bounds hop time to ~PROBE_TIMEOUT_S
    instead of PROBES_PER_HOP * PROBE_TIMEOUT_S). PermissionError propagates to the
    caller so run_traceroute can short-circuit to a degraded response."""
    tasks = [asyncio.to_thread(_probe_once_sync, target_ip, ttl, PROBE_TIMEOUT_S) for _ in range(PROBES_PER_HOP)]
    results = await asyncio.gather(*tasks)

    rtts = [r["rtt_ms"] for r in results if r["rtt_ms"] is not None]
    responders = [r["responder_ip"] for r in results if r["responder_ip"]]
    responder_ip = responders[0] if responders else None
    reached = any(r["is_destination_reply"] for r in results)

    loss_pct = round((PROBES_PER_HOP - len(rtts)) / PROBES_PER_HOP * 100, 1)
    jitter = None
    if len(rtts) >= 2:
        diffs = [abs(rtts[i] - rtts[i - 1]) for i in range(1, len(rtts))]
        jitter = round(sum(diffs) / len(diffs), 2)

    return {
        "responder_ip": responder_ip,
        "rtt_samples_ms": rtts,
        "avg_rtt_ms": round(sum(rtts) / len(rtts), 2) if rtts else None,
        "packet_loss_pct": loss_pct,
        "jitter_ms": jitter,
        "reached_destination": reached,
    }


async def run_traceroute(target_ip: str) -> Dict[str, Any]:
    """TTL loop 1..MAX_HOPS. Returns
    {"probe_method": "icmp"|"unavailable", "hops": [...], "destination_reached": bool,
     "failure_hop": Optional[int]}. Never raises."""
    hops: List[Dict[str, Any]] = []
    silent_streak = 0
    destination_reached = False
    failure_hop = None

    for ttl in range(1, MAX_HOPS + 1):
        try:
            hop = await _probe_hop(target_ip, ttl)
        except PermissionError:
            logger.warning("ICMP raw socket unavailable (missing CAP_NET_RAW) — degrading to endpoint-only probe")
            return {"probe_method": "unavailable", "hops": [], "destination_reached": False, "failure_hop": None}

        hop["hop_number"] = ttl
        hops.append(hop)

        if hop["reached_destination"]:
            destination_reached = True
            break

        silent_streak = silent_streak + 1 if hop["responder_ip"] is None else 0
        if silent_streak >= MAX_CONSECUTIVE_SILENT_HOPS and ttl >= MIN_HOPS_BEFORE_EARLY_ABORT:
            failure_hop = ttl - silent_streak + 1
            break
    else:
        if not destination_reached:
            failure_hop = MAX_HOPS

    return {
        "probe_method": "icmp",
        "hops": hops,
        "destination_reached": destination_reached,
        "failure_hop": failure_hop,
    }


# ─────────────────────────────────────────────
#  Reverse DNS + GeoIP/ASN enrichment
# ─────────────────────────────────────────────

async def enrich_hops(hops: List[Dict[str, Any]]) -> None:
    """Mutates each hop dict in place: hostname (reverse DNS), location, asn, isp,
    org, is_proxy_or_vpn, is_hosting. Bounded concurrency to respect ip-api.com's
    45 req/min free tier. Best-effort — a hop with no responder_ip, or a failed
    lookup, just keeps its None fields."""
    sem = asyncio.Semaphore(GEO_ENRICH_CONCURRENCY)

    async def _one(hop: Dict[str, Any]) -> None:
        ip = hop.get("responder_ip")
        if not ip:
            return
        async with sem:
            try:
                rev = await asyncio.wait_for(asyncio.to_thread(socket.gethostbyaddr, ip), timeout=1.5)
                hop["hostname"] = rev[0]
            except Exception:
                hop["hostname"] = None
            hop["location"] = await get_geo_location(ip)
            intel = await get_ip_intel(ip)
            for key in ("asn", "isp", "org", "is_proxy_or_vpn", "is_hosting"):
                hop[key] = intel.get(key)

    await asyncio.gather(*[_one(h) for h in hops])


# ─────────────────────────────────────────────
#  DNS / TCP / TLS timing to the actual destination
# ─────────────────────────────────────────────

def _connect_and_maybe_tls_sync(target_ip: str, port: int, hostname: str, want_tls: bool) -> Dict[str, Any]:
    """Blocking socket/ssl work, run via asyncio.to_thread. Mirrors the pattern
    already used in monitoring_service.perform_ssl_check."""
    result: Dict[str, Any] = {"tcp_connect_ms": None, "tls_handshake_ms": None, "tcp_reachable": False}
    sock = None
    try:
        t0 = time.perf_counter()
        sock = socket.create_connection((target_ip, port), timeout=TCP_CONNECT_TIMEOUT_S)
        result["tcp_connect_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        result["tcp_reachable"] = True

        if want_tls:
            t1 = time.perf_counter()
            ctx = ssl.create_default_context()
            try:
                ssock = ctx.wrap_socket(sock, server_hostname=hostname)
                result["tls_handshake_ms"] = round((time.perf_counter() - t1) * 1000, 2)
                ssock.close()
                sock = None
            except Exception:
                pass
    except Exception:
        pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    return result


async def measure_endpoint(hostname: str, target_ip: str, monitor_port: Optional[int], scheme_hint: str) -> Dict[str, Any]:
    """Real, independent-of-ICMP measurements. Every field defaults to None/False and
    degrades silently on failure — never raises."""
    result: Dict[str, Any] = {
        "dns_resolution_ms": None,
        "tcp_connect_ms": None,
        "tls_handshake_ms": None,
        "target_port": None,
        "tcp_reachable": False,
    }

    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(asyncio.to_thread(socket.gethostbyname, hostname), timeout=DNS_TIMEOUT_S)
        result["dns_resolution_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        pass

    candidates = [monitor_port] if monitor_port else ([443] if scheme_hint == "https" else [80, 443])
    for port in candidates:
        if not port:
            continue
        want_tls = port == 443 or scheme_hint == "https"
        conn = await asyncio.to_thread(_connect_and_maybe_tls_sync, target_ip, port, hostname, want_tls)
        if conn["tcp_reachable"]:
            result.update(conn)
            result["target_port"] = port
            break

    return result


# ─────────────────────────────────────────────
#  Detection logic
# ─────────────────────────────────────────────

def detect_routing_loop(hop_ips: List[Optional[str]]) -> Optional[Dict[str, Any]]:
    """Flags the same IP recurring at non-adjacent hop indices (adjacent repeats are
    normal, e.g. NAT hairpinning, and are not a loop)."""
    seen_at: Dict[str, int] = {}
    for idx, ip in enumerate(hop_ips):
        if not ip:
            continue
        if ip in seen_at and idx - seen_at[ip] > 1:
            return {"looped_ip": ip, "first_hop": seen_at[ip] + 1, "repeat_hop": idx + 1}
        seen_at[ip] = idx
    return None


def detect_route_change(current_ips: List[Optional[str]], previous_ips: Optional[List[Optional[str]]]) -> bool:
    """False when there's no previous run to compare against (first-ever trace)."""
    if previous_ips is None:
        return False
    return current_ips != previous_ips


def detect_blocked_likely(hops: List[Dict[str, Any]], destination_reached: bool, tcp_reachable: bool) -> bool:
    """Hops respond then everything silently times out, AND the direct TCP connect to
    the real service port also fails -- vs. plain packet loss / ICMP-only filtering
    (very common and benign), where TCP still succeeds."""
    if destination_reached or tcp_reachable:
        return False
    if not hops:
        return False
    tail = hops[-MAX_CONSECUTIVE_SILENT_HOPS:] if len(hops) > MAX_CONSECUTIVE_SILENT_HOPS else hops
    head = hops[: len(hops) - len(tail)]
    responded_then_stopped = any(h["responder_ip"] for h in head)
    trailing_all_silent = all(h["responder_ip"] is None for h in tail)
    return responded_then_stopped and trailing_all_silent
