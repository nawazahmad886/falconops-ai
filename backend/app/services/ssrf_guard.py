"""
FalconOps AI - SSRF Guard
Real check for outbound webhook/integration/runbook URLs the platform is asked to fetch,
so a stored or user-supplied URL can't be pointed at an internal service or a cloud
metadata endpoint (e.g. http://169.254.169.254/). Resolves the hostname and rejects
private/loopback/link-local/reserved targets.

Caveat: this validates at check time, not connection time, so it does not fully close a
DNS-rebinding attack (attacker-controlled DNS that resolves differently between this
check and the actual request). It blocks the overwhelmingly common real case — typo'd
internal URLs, localhost, private subnets, and cloud metadata IPs — which is what
webhook/integration test endpoints and runbook HTTP steps realistically face.
"""
import socket
import logging
import ipaddress
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}


def is_safe_outbound_url(url: str) -> bool:
    """Returns True only if the URL is http(s) and its host resolves to a public,
    non-reserved IP. Never raises — any resolution failure is treated as unsafe."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        if host.lower() in _BLOCKED_HOSTNAMES:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            resolved = socket.gethostbyname(host)
            ip = ipaddress.ip_address(resolved)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
        return True
    except Exception as e:
        logger.warning(f"SSRF guard: could not validate URL (treating as unsafe): {e}")
        return False
