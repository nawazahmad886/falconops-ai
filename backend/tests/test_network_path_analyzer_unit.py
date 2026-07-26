"""
Unit tests for the AI Network Path Analyzer (backend/app/services/network_path_service.py).

Unlike the rest of backend/tests (HTTP integration tests against a live server), this
file mocks ping3/socket/ssl/httpx to deterministically exercise network-failure-shaped
edge cases (mid-path timeout, TTL-expired-every-hop, missing raw-socket permission,
etc.) that can't be reliably provoked against a real host. No running server or
CAP_NET_RAW capability is required to run these tests.

Async service functions are invoked via asyncio.run() from plain sync test functions
so no new pytest plugin (e.g. pytest-asyncio) is required.
"""
import asyncio
import socket
import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import ping3.errors
import pytest

from app.services import network_path_service as nps


def _ttl_expired(ip: str) -> ping3.errors.TimeToLiveExpired:
    """Build a TimeToLiveExpired instance without depending on ping3's exact __init__
    signature (varies across versions) -- bypass __init__ via __new__ and set the
    ip_header attribute directly, matching what _extract_responder_ip() reads."""
    exc = ping3.errors.TimeToLiveExpired.__new__(ping3.errors.TimeToLiveExpired)
    exc.ip_header = {"src_addr": ip}
    return exc


def _raise(exc):
    raise exc


# ──────────────────── _probe_once_sync / _extract_responder_ip ────────────────────

class TestProbeOnceSync:
    def test_destination_reply_returns_rtt_and_target_ip(self):
        with patch("ping3.ping", return_value=0.03):
            result = nps._probe_once_sync("8.8.8.8", ttl=10, timeout_s=1.0)

        assert result["is_destination_reply"] is True
        assert result["responder_ip"] == "8.8.8.8"
        assert result["rtt_ms"] == pytest.approx(30.0, abs=0.01)

    def test_ttl_expired_returns_router_ip_not_destination(self):
        with patch("ping3.ping", side_effect=_ttl_expired("172.16.0.1")):
            result = nps._probe_once_sync("8.8.8.8", ttl=2, timeout_s=1.0)

        assert result["is_destination_reply"] is False
        assert result["responder_ip"] == "172.16.0.1"
        assert result["rtt_ms"] is not None

    def test_silent_timeout_returns_none_fields(self):
        with patch("ping3.ping", return_value=None):
            result = nps._probe_once_sync("8.8.8.8", ttl=2, timeout_s=1.0)

        assert result == {"rtt_ms": None, "responder_ip": None, "is_destination_reply": False}

    def test_generic_ping_error_degrades_to_silent_timeout(self):
        with patch("ping3.ping", side_effect=ping3.errors.PingError()):
            result = nps._probe_once_sync("8.8.8.8", ttl=2, timeout_s=1.0)

        assert result["responder_ip"] is None
        assert result["rtt_ms"] is None

    def test_permission_error_propagates(self):
        with patch("ping3.ping", side_effect=PermissionError("Operation not permitted")):
            with pytest.raises(PermissionError):
                nps._probe_once_sync("8.8.8.8", ttl=2, timeout_s=1.0)


class TestExtractResponderIp:
    def test_reads_ip_header_src_addr_when_present(self):
        exc = _ttl_expired("192.0.2.7")
        assert nps._extract_responder_ip(exc) == "192.0.2.7"

    def test_falls_back_to_regex_when_no_ip_header(self):
        exc = ping3.errors.TimeToLiveExpired.__new__(ping3.errors.TimeToLiveExpired)
        # ip_header present but empty (attribute exists, no usable data) -- more
        # realistic than an entirely-missing attribute, and avoids depending on
        # whatever ping3's own __str__ does with a missing ip_header.
        exc.ip_header = None
        exc.args = ("Time exceeded from 198.51.100.9",)
        assert nps._extract_responder_ip(exc) == "198.51.100.9"

    def test_returns_none_when_no_ip_findable(self):
        exc = ping3.errors.TimeToLiveExpired.__new__(ping3.errors.TimeToLiveExpired)
        exc.ip_header = None
        exc.args = ("Time exceeded",)
        assert nps._extract_responder_ip(exc) is None


# ──────────────────── run_traceroute ────────────────────

class TestRunTraceroute:
    def test_full_successful_trace_reaches_destination(self):
        target_ip = "8.8.8.8"

        def fake_ping(dest, ttl=None, timeout=None, unit=None):
            if ttl < 5:
                raise _ttl_expired(f"10.0.0.{ttl}")
            return 0.02  # seconds -> destination reply

        with patch("ping3.ping", side_effect=fake_ping):
            result = asyncio.run(nps.run_traceroute(target_ip))

        assert result["probe_method"] == "icmp"
        assert result["destination_reached"] is True
        assert len(result["hops"]) == 5
        assert result["hops"][-1]["reached_destination"] is True
        assert result["hops"][0]["responder_ip"] == "10.0.0.1"

    def test_mid_path_silent_timeout_hop_does_not_abort_trace(self):
        target_ip = "8.8.8.8"

        def fake_ping(dest, ttl=None, timeout=None, unit=None):
            if ttl == 3:
                return None  # silent timeout for every probe at this hop
            if ttl < 6:
                raise _ttl_expired(f"10.0.0.{ttl}")
            return 0.01

        with patch("ping3.ping", side_effect=fake_ping):
            result = asyncio.run(nps.run_traceroute(target_ip))

        assert result["destination_reached"] is True
        hop3 = next(h for h in result["hops"] if h["hop_number"] == 3)
        assert hop3["responder_ip"] is None
        assert hop3["packet_loss_pct"] == 100.0

    def test_ttl_expired_every_intermediate_hop_then_destination_replies(self):
        target_ip = "1.1.1.1"

        def fake_ping(dest, ttl=None, timeout=None, unit=None):
            if ttl < 8:
                raise _ttl_expired(f"192.168.1.{ttl}")
            return 0.015

        with patch("ping3.ping", side_effect=fake_ping):
            result = asyncio.run(nps.run_traceroute(target_ip))

        assert result["destination_reached"] is True
        assert len(result["hops"]) == 8
        for i, hop in enumerate(result["hops"][:-1], start=1):
            assert hop["responder_ip"] == f"192.168.1.{i}"

    def test_immediate_destination_reach_zero_intermediate_hops(self):
        with patch("ping3.ping", return_value=0.005):
            result = asyncio.run(nps.run_traceroute("127.0.0.1"))

        assert result["destination_reached"] is True
        assert len(result["hops"]) == 1
        assert result["hops"][0]["reached_destination"] is True

    def test_max_hops_exceeded_without_reaching_destination(self):
        with patch("ping3.ping", side_effect=lambda dest, ttl=None, timeout=None, unit=None: _raise(_ttl_expired(f"10.0.0.{ttl}")) if ttl <= 2 else None):
            result = asyncio.run(nps.run_traceroute("203.0.113.1"))

        assert result["destination_reached"] is False

    def test_consecutive_silent_hops_triggers_early_abort(self):
        with patch("ping3.ping", return_value=None):
            result = asyncio.run(nps.run_traceroute("203.0.113.1"))

        assert result["destination_reached"] is False
        assert len(result["hops"]) < nps.MAX_HOPS

    def test_permission_error_returns_degraded_probe_method_not_exception(self):
        with patch("ping3.ping", side_effect=PermissionError("Operation not permitted")):
            result = asyncio.run(nps.run_traceroute("8.8.8.8"))

        assert result["probe_method"] == "unavailable"
        assert result["hops"] == []
        assert result["destination_reached"] is False


def _raise(exc):
    raise exc


# ──────────────────── measure_endpoint ────────────────────

class TestMeasureEndpoint:
    def test_dns_resolution_and_tcp_and_tls_all_succeed(self):
        fake_ssl_sock = MagicMock()
        fake_ctx = MagicMock()
        fake_ctx.wrap_socket.return_value = fake_ssl_sock

        with patch("socket.gethostbyname", return_value="93.184.216.34"), \
             patch("socket.create_connection", return_value=MagicMock()), \
             patch("ssl.create_default_context", return_value=fake_ctx):
            result = asyncio.run(nps.measure_endpoint("example.com", "93.184.216.34", None, "https"))

        assert result["tcp_reachable"] is True
        assert result["tcp_connect_ms"] is not None
        assert result["tls_handshake_ms"] is not None
        assert result["target_port"] == 443

    def test_tcp_connect_failure_degrades_gracefully(self):
        with patch("socket.gethostbyname", return_value="203.0.113.1"), \
             patch("socket.create_connection", side_effect=OSError("connection refused")):
            result = asyncio.run(nps.measure_endpoint("down.example.com", "203.0.113.1", None, "http"))

        assert result["tcp_reachable"] is False
        assert result["tcp_connect_ms"] is None
        assert result["target_port"] is None

    def test_tls_handshake_failure_keeps_tcp_reachable_true(self):
        fake_ctx = MagicMock()
        fake_ctx.wrap_socket.side_effect = ssl.SSLError("handshake failed")

        with patch("socket.gethostbyname", return_value="93.184.216.34"), \
             patch("socket.create_connection", return_value=MagicMock()), \
             patch("ssl.create_default_context", return_value=fake_ctx):
            result = asyncio.run(nps.measure_endpoint("badssl.example.com", "93.184.216.34", None, "https"))

        assert result["tcp_reachable"] is True
        assert result["tls_handshake_ms"] is None

    def test_dns_failure_still_attempts_tcp(self):
        with patch("socket.gethostbyname", side_effect=socket.gaierror("no such host")), \
             patch("socket.create_connection", return_value=MagicMock()):
            result = asyncio.run(nps.measure_endpoint("nowhere.invalid", "203.0.113.1", 8080, "http"))

        assert result["dns_resolution_ms"] is None
        assert result["target_port"] == 8080
        assert result["tcp_reachable"] is True


# ──────────────────── packet loss / jitter arithmetic ────────────────────

class TestProbeHopArithmetic:
    def test_packet_loss_and_jitter_from_synthetic_samples(self):
        # 2 replies (10ms, 15ms) + 1 silent timeout out of 3 probes
        calls = iter([
            {"rtt_ms": 10.0, "responder_ip": "10.0.0.1", "is_destination_reply": False},
            {"rtt_ms": 15.0, "responder_ip": "10.0.0.1", "is_destination_reply": False},
            {"rtt_ms": None, "responder_ip": None, "is_destination_reply": False},
        ])
        with patch.object(nps, "_probe_once_sync", side_effect=lambda *a, **k: next(calls)):
            result = asyncio.run(nps._probe_hop("10.0.0.1", 3))

        assert result["packet_loss_pct"] == pytest.approx(33.3, abs=0.1)
        assert result["jitter_ms"] == pytest.approx(5.0, abs=0.01)
        assert result["avg_rtt_ms"] == pytest.approx(12.5, abs=0.01)

    def test_single_sample_has_no_jitter(self):
        calls = iter([
            {"rtt_ms": 20.0, "responder_ip": "10.0.0.1", "is_destination_reply": False},
            {"rtt_ms": None, "responder_ip": None, "is_destination_reply": False},
            {"rtt_ms": None, "responder_ip": None, "is_destination_reply": False},
        ])
        with patch.object(nps, "_probe_once_sync", side_effect=lambda *a, **k: next(calls)):
            result = asyncio.run(nps._probe_hop("10.0.0.1", 1))

        assert result["jitter_ms"] is None


# ──────────────────── detection logic ────────────────────

class TestRoutingLoopDetection:
    def test_non_adjacent_repeat_is_flagged(self):
        loop = nps.detect_routing_loop(["1.1.1.1", "2.2.2.2", "1.1.1.1"])
        assert loop is not None
        assert loop["looped_ip"] == "1.1.1.1"
        assert loop["first_hop"] == 1
        assert loop["repeat_hop"] == 3

    def test_adjacent_repeat_is_not_flagged(self):
        assert nps.detect_routing_loop(["1.1.1.1", "1.1.1.1", "2.2.2.2"]) is None

    def test_no_repeats_returns_none(self):
        assert nps.detect_routing_loop(["1.1.1.1", "2.2.2.2", "3.3.3.3"]) is None

    def test_silent_hops_are_ignored(self):
        assert nps.detect_routing_loop([None, "1.1.1.1", None, "2.2.2.2"]) is None


class TestRouteChangeDetection:
    def test_first_ever_run_is_not_a_change(self):
        assert nps.detect_route_change(["1.1.1.1", "2.2.2.2"], None) is False

    def test_identical_sequence_is_not_a_change(self):
        ips = ["1.1.1.1", "2.2.2.2", "3.3.3.3"]
        assert nps.detect_route_change(list(ips), list(ips)) is False

    def test_differing_sequence_is_a_change(self):
        assert nps.detect_route_change(["1.1.1.1", "9.9.9.9"], ["1.1.1.1", "2.2.2.2"]) is True


class TestBlockedLikelyDetection:
    def _hop(self, responder_ip):
        return {"responder_ip": responder_ip}

    def test_blocked_when_hops_stop_and_tcp_also_fails(self):
        hops = [self._hop("10.0.0.1"), self._hop("10.0.0.2")] + [self._hop(None)] * nps.MAX_CONSECUTIVE_SILENT_HOPS
        assert nps.detect_blocked_likely(hops, destination_reached=False, tcp_reachable=False) is True

    def test_not_blocked_when_tcp_still_reachable(self):
        hops = [self._hop("10.0.0.1"), self._hop("10.0.0.2")] + [self._hop(None)] * nps.MAX_CONSECUTIVE_SILENT_HOPS
        assert nps.detect_blocked_likely(hops, destination_reached=False, tcp_reachable=True) is False

    def test_not_blocked_when_destination_reached(self):
        hops = [self._hop("10.0.0.1")]
        assert nps.detect_blocked_likely(hops, destination_reached=True, tcp_reachable=False) is False

    def test_not_blocked_when_nothing_ever_responded(self):
        hops = [self._hop(None)] * nps.MAX_CONSECUTIVE_SILENT_HOPS
        assert nps.detect_blocked_likely(hops, destination_reached=False, tcp_reachable=False) is False


# ──────────────────── ASN / proxy / hosting enrichment ────────────────────

class TestEnrichHops:
    def test_asn_proxy_hosting_enrichment_from_mocked_geo_response(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "status": "success", "city": "Mountain View", "country": "United States",
            "as": "AS15169 Google LLC", "asname": "GOOGLE", "isp": "Google LLC",
            "org": "Google LLC", "proxy": False, "hosting": True, "mobile": False,
        }
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=fake_response)
        mock_client_cm = MagicMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cm.__aexit__ = AsyncMock(return_value=False)

        hops = [{"hop_number": 1, "responder_ip": "8.8.8.8"}]
        with patch("httpx.AsyncClient", return_value=mock_client_cm), \
             patch("socket.gethostbyaddr", side_effect=socket.herror("no reverse dns")):
            asyncio.run(nps.enrich_hops(hops))

        assert hops[0]["asn"] == "AS15169 Google LLC"
        assert hops[0]["isp"] == "Google LLC"
        assert hops[0]["is_hosting"] is True
        assert hops[0]["is_proxy_or_vpn"] is False
        assert hops[0]["location"] == "Mountain View, United States"

    def test_private_ip_never_triggers_http_call(self):
        mock_client = AsyncMock()
        hops = [{"hop_number": 1, "responder_ip": "10.0.0.1"}]
        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("socket.gethostbyaddr", side_effect=socket.herror("no reverse dns")):
            asyncio.run(nps.enrich_hops(hops))

        mock_client.get.assert_not_called()
        assert hops[0].get("asn") is None

    def test_silent_hop_is_skipped(self):
        mock_client = AsyncMock()
        hops = [{"hop_number": 1, "responder_ip": None}]
        with patch("httpx.AsyncClient", return_value=mock_client):
            asyncio.run(nps.enrich_hops(hops))

        mock_client.get.assert_not_called()
