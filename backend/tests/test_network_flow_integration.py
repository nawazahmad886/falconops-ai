"""
Integration tests for POST /api/ingest/netflows and the /api/network query routes.
Matches the existing oneagent ingest test convention (test_oneagent.py): HTTP against
a live server, X-API-Key auth for ingest, JWT auth for queries.

Deliberately does NOT try to trigger a real malicious-IP threat end-to-end -- there's
no HTTP-exposed way to seed backend/app/services/threat_intel_service.py's
threat_intel_iocs collection (it's only populated by the hourly Feodo/Spamhaus sync),
and depending on a real published IOC IP being current would make this test flaky.
That detection path (ioc_match -> _check_netflow_malicious_ip -> _store_threat) is
covered deterministically with mocks in test_network_flow_unit.py instead. This file
covers the HTTP contract: auth, shape, and that ordinary (non-malicious) flows persist.
"""
import os
import uuid

import pytest
import requests

from tests.conftest import BASE_URL, admin_credentials


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=admin_credentials(), timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def netflow_key(admin_headers):
    r = requests.post(f"{BASE_URL}/api/oneagent/keys", headers=admin_headers,
                       json={"name": f"netflow-test-{uuid.uuid4().hex[:8]}"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    yield data
    requests.delete(f"{BASE_URL}/api/oneagent/keys/{data['id']}", headers=admin_headers, timeout=30)


def _sample_batch(host_suffix: str):
    return {
        "host": f"netflow-test-host-{host_suffix}",
        "batch": [{
            "local_ip": "10.55.0.5", "local_port": 8080,
            "remote_ip": "10.55.0.9", "remote_port": 54321,
            "state": "ESTABLISHED", "pid": 4242, "process_name": "checkout",
            "service": "checkout",
        }],
    }


class TestNetflowIngestAuth:
    def test_no_key_rejected(self):
        r = requests.post(f"{BASE_URL}/api/ingest/netflows", json={"batch": []}, timeout=30)
        assert r.status_code == 401

    def test_invalid_key_rejected(self):
        r = requests.post(f"{BASE_URL}/api/ingest/netflows",
                          headers={"X-API-Key": "fops_invalid_xxx"}, json={"batch": []}, timeout=30)
        assert r.status_code == 403

    def test_missing_batch_field_rejected(self, netflow_key):
        r = requests.post(f"{BASE_URL}/api/ingest/netflows",
                          headers={"X-API-Key": netflow_key["key"], "Content-Type": "application/json"},
                          json={"host": "x"}, timeout=30)
        assert r.status_code == 400


class TestNetflowIngest:
    def test_ordinary_flow_batch_ingests(self, netflow_key):
        payload = _sample_batch(uuid.uuid4().hex[:8])
        r = requests.post(f"{BASE_URL}/api/ingest/netflows",
                          headers={"X-API-Key": netflow_key["key"], "Content-Type": "application/json"},
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert body["ingested"] == 1
        assert "threats_detected" in body

    def test_flow_with_missing_ip_fields_is_skipped_not_errored(self, netflow_key):
        payload = {"host": "netflow-test-incomplete", "batch": [{"local_port": 80}]}
        r = requests.post(f"{BASE_URL}/api/ingest/netflows",
                          headers={"X-API-Key": netflow_key["key"], "Content-Type": "application/json"},
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["ingested"] == 0


class TestNetworkQueryRoutes:
    def test_flows_summary_shape(self, admin_headers, netflow_key):
        suffix = uuid.uuid4().hex[:8]
        payload = _sample_batch(suffix)
        ir = requests.post(f"{BASE_URL}/api/ingest/netflows",
                           headers={"X-API-Key": netflow_key["key"], "Content-Type": "application/json"},
                           json=payload, timeout=30)
        assert ir.status_code == 200, ir.text

        r = requests.get(f"{BASE_URL}/api/network/flows/summary",
                         params={"hours": 1, "host": f"netflow-test-host-{suffix}"},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for field in ("window_hours", "total_flows", "distinct_remote_ips",
                      "threat_flagged_flows", "top_talkers", "top_services"):
            assert field in data, f"missing field: {field}"
        assert data["total_flows"] >= 1

    def test_dependencies_shape(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/network/dependencies", params={"hours": 24},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "edges" in data and "edge_count" in data
        assert isinstance(data["edges"], list)

    def test_active_threats_shape(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/network/threats/active", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "threats" in data and "count" in data
        assert isinstance(data["threats"], list)
        for t in data["threats"]:
            assert t.get("detection_source") == "netflow"
