"""
Integration tests for the AI Network Path Analyzer: POST /api/topology/{monitor_id}/traceroute.

Matches the repo's existing HTTP-integration-test convention (requests + a live server)
rather than the mocked-unit style in test_network_path_analyzer_unit.py. These tests
assert response SHAPE, not real-network specifics, since the environment running this
suite likely lacks CAP_NET_RAW (see docker-compose.yml's `cap_add: [NET_RAW]` on the
backend service) — the endpoint must degrade to a 200 with probe_method:"unavailable"
in that case, never a 500.
"""
import time
import uuid

import pytest
import requests

from tests.conftest import BASE_URL, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, admin_credentials


# ──────────────────── Fixtures ────────────────────

@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=admin_credentials(), timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def traceable_monitor(admin_headers):
    """A real monitor pointing at a well-known, always-resolvable host, so the
    endpoint's DNS-resolution step succeeds regardless of environment."""
    body = {
        "name": f"network-path-test-{uuid.uuid4().hex[:8]}",
        "target": "https://1.1.1.1",
        "monitor_type": "http",
        "interval_seconds": 300,
        "timeout_seconds": 5,
    }
    r = requests.post(f"{BASE_URL}/api/monitors", json=body, headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ──────────────────── Response shape ────────────────────

class TestTracerouteResponseShape:
    def test_returns_new_optional_fields_without_breaking_existing_shape(self, admin_headers, traceable_monitor):
        r = requests.post(
            f"{BASE_URL}/api/topology/{traceable_monitor['id']}/traceroute",
            headers=admin_headers, timeout=90,
        )
        assert r.status_code == 200, r.text
        data = r.json()

        # Original fields (pre-existing contract) must still be present.
        for field in ("monitor_id", "target", "total_hops", "destination_reached",
                      "hops", "analysis", "executed_at"):
            assert field in data, f"missing original field: {field}"

        # New fields are present (possibly null) -- additive, never removed.
        for field in ("probe_method", "dns_resolution_ms", "tcp_connect_ms", "tls_handshake_ms",
                      "target_port", "tcp_reachable", "avg_packet_loss_pct", "avg_jitter_ms",
                      "routing_loop_detected", "route_changed", "blocked_likely"):
            assert field in data, f"missing new field: {field}"

        assert data["probe_method"] in ("icmp", "unavailable")

        if data["probe_method"] == "icmp":
            for hop in data["hops"]:
                for field in ("packet_loss_pct", "jitter_ms", "asn", "isp", "is_proxy_or_vpn", "is_hosting"):
                    assert field in hop, f"missing hop field: {field}"

    def test_degrades_without_raising_when_icmp_unavailable_or_succeeds(self, admin_headers, traceable_monitor):
        """Whichever mode this environment is in (CAP_NET_RAW present or not), the
        endpoint must return 200 -- never a 500 -- and the fields must be internally
        consistent for that mode."""
        r = requests.post(
            f"{BASE_URL}/api/topology/{traceable_monitor['id']}/traceroute",
            headers=admin_headers, timeout=90,
        )
        assert r.status_code == 200, r.text
        data = r.json()

        if data["probe_method"] == "unavailable":
            assert data["hops"] == []
            assert data["analysis"].get("status") == "degraded"
        else:
            assert data["probe_method"] == "icmp"


class TestTracerouteErrorHandling:
    def test_unknown_monitor_404(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/topology/nonexistent-monitor-id-xyz/traceroute",
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 404

    def test_requires_authentication(self, traceable_monitor):
        r = requests.post(
            f"{BASE_URL}/api/topology/{traceable_monitor['id']}/traceroute", timeout=30,
        )
        assert r.status_code in (401, 403)


class TestTracerouteRateLimit:
    def test_rate_limited_after_repeated_calls(self, admin_headers, traceable_monitor):
        url = f"{BASE_URL}/api/topology/{traceable_monitor['id']}/traceroute"
        statuses = []
        for _ in range(8):
            r = requests.post(url, headers=admin_headers, timeout=90)
            statuses.append(r.status_code)
            if r.status_code == 429:
                break
        assert 429 in statuses, f"expected a 429 among repeated calls, got {statuses}"


# ──────────────────── Cross-tenant isolation ────────────────────

class TestTracerouteTenantIsolation:
    """Regression test for the tenant-scoping fix: perform_traceroute's monitor
    lookup previously had no tenant_id filter (unlike get_network_topology in the
    same file), which -- now that the endpoint does real ICMP/TCP/TLS probing --
    would let any authenticated user trace another tenant's internal targets."""

    @pytest.fixture(scope="class")
    def two_tenant_users(self, admin_headers):
        suffix = uuid.uuid4().hex[:8]
        tenants = {}
        for label in ("a", "b"):
            r = requests.post(
                f"{BASE_URL}/api/tenants",
                json={"name": f"nettest-tenant-{label}-{suffix}"},
                headers=admin_headers, timeout=30,
            )
            assert r.status_code == 200, r.text
            tenant = r.json()

            email = f"nettest-{label}-{suffix}@example.com"
            password = "TestPass123!"
            ur = requests.post(
                f"{BASE_URL}/api/tenants/{tenant['id']}/users",
                json={"email": email, "full_name": f"Net Test {label.upper()}",
                      "password": password, "role": "user"},
                headers=admin_headers, timeout=30,
            )
            assert ur.status_code == 200, ur.text

            lr = requests.post(f"{BASE_URL}/api/auth/login",
                               json={"email": email, "password": password}, timeout=30)
            assert lr.status_code == 200, lr.text
            token = lr.json()["access_token"]
            tenants[label] = {"tenant": tenant, "headers": {"Authorization": f"Bearer {token}"}}
        return tenants

    def test_tenant_a_monitor_not_traceable_by_tenant_b_user(self, two_tenant_users):
        a_headers = two_tenant_users["a"]["headers"]
        b_headers = two_tenant_users["b"]["headers"]

        mr = requests.post(
            f"{BASE_URL}/api/monitors",
            json={"name": f"tenant-a-monitor-{uuid.uuid4().hex[:8]}", "target": "https://1.1.1.1",
                  "monitor_type": "http", "interval_seconds": 300, "timeout_seconds": 5},
            headers=a_headers, timeout=30,
        )
        assert mr.status_code == 200, mr.text
        monitor_id = mr.json()["id"]

        # Tenant A can trace its own monitor.
        own = requests.post(f"{BASE_URL}/api/topology/{monitor_id}/traceroute", headers=a_headers, timeout=90)
        assert own.status_code == 200, own.text

        # Tenant B must not be able to see or trace it.
        other = requests.post(f"{BASE_URL}/api/topology/{monitor_id}/traceroute", headers=b_headers, timeout=30)
        assert other.status_code == 404, other.text
