"""Tests for FalconOpsAI OneAgent backend routes (ingest + management + downloads)."""
import os
import io
import gzip
import json
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://health-rules-engine.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}
VIEWER = {"email": "test@falconapps.com", "password": "testpass123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def viewer_token():
    return _login(VIEWER)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def created_key(admin_headers):
    r = requests.post(f"{BASE_URL}/api/oneagent/keys", headers=admin_headers,
                      json={"name": "test-key-2"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["key"].startswith("fops_")
    assert "id" in data
    yield data
    # cleanup
    requests.delete(f"{BASE_URL}/api/oneagent/keys/{data['id']}", headers=admin_headers, timeout=30)


# ─── Key management ──────────────────────────────────────────────
class TestKeys:
    def test_create_key_admin(self, created_key):
        assert created_key["key"].startswith("fops_")
        assert created_key["name"] == "test-key-2"
        assert created_key["revoked"] is False

    def test_list_keys_no_full_key(self, admin_headers, created_key):
        r = requests.get(f"{BASE_URL}/api/oneagent/keys", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        keys = r.json()["keys"]
        assert len(keys) > 0
        for k in keys:
            assert "key" not in k, "Full key must NOT be in list response"
            assert "key_preview" in k

    def test_non_admin_cannot_create(self, viewer_token):
        r = requests.post(f"{BASE_URL}/api/oneagent/keys",
                          headers={"Authorization": f"Bearer {viewer_token}", "Content-Type": "application/json"},
                          json={"name": "viewer-key"}, timeout=30)
        assert r.status_code == 403

    def test_revoke_and_reject(self, admin_headers):
        # create fresh key
        r = requests.post(f"{BASE_URL}/api/oneagent/keys", headers=admin_headers,
                          json={"name": "revoke-me"}, timeout=30)
        k = r.json()
        # revoke
        r2 = requests.delete(f"{BASE_URL}/api/oneagent/keys/{k['id']}", headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        # revoked key rejected on ingest
        r3 = requests.post(f"{BASE_URL}/api/ingest/logs",
                           headers={"X-API-Key": k["key"], "Content-Type": "application/json"},
                           json={"host": "h", "batch": [{"message": "x"}]}, timeout=30)
        assert r3.status_code == 403


# ─── Ingest auth ─────────────────────────────────────────────────
class TestIngestAuth:
    def test_no_key(self):
        r = requests.post(f"{BASE_URL}/api/ingest/logs", json={"batch": []}, timeout=30)
        assert r.status_code == 401

    def test_invalid_key(self):
        r = requests.post(f"{BASE_URL}/api/ingest/logs",
                          headers={"X-API-Key": "fops_invalid_xxx"},
                          json={"batch": []}, timeout=30)
        assert r.status_code == 403


# ─── Ingest data ─────────────────────────────────────────────────
class TestIngest:
    def test_logs_plain(self, created_key):
        payload = {"host": "qa-host", "batch": [
            {"service": "qa-svc", "timestamp": "2026-07-07T15:00:00Z", "level": "error",
             "message": "QA test error", "tags": {"host": "qa-host"}}
        ]}
        r = requests.post(f"{BASE_URL}/api/ingest/logs",
                          headers={"X-API-Key": created_key["key"], "Content-Type": "application/json"},
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["ingested"] == 1

    def test_logs_gzip(self, created_key):
        payload = {"host": "qa-host", "batch": [
            {"service": "qa-svc", "timestamp": "2026-07-07T15:00:00Z", "level": "error",
             "message": "QA gzip error", "tags": {"host": "qa-host"}}
        ]}
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(json.dumps(payload).encode())
        r = requests.post(f"{BASE_URL}/api/ingest/logs",
                          headers={"X-API-Key": created_key["key"],
                                   "Content-Type": "application/json",
                                   "Content-Encoding": "gzip"},
                          data=buf.getvalue(), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["ingested"] == 1

    def test_metrics(self, created_key):
        payload = {"host": "qa-host", "batch": [
            {"service": "qa-svc", "name": "qa.metric", "value": 42.5, "unit": "ms",
             "timestamp": "2026-07-07T15:00:00Z"}
        ]}
        r = requests.post(f"{BASE_URL}/api/ingest/metrics",
                          headers={"X-API-Key": created_key["key"], "Content-Type": "application/json"},
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["ingested"] == 1

    def test_traces(self, created_key):
        payload = {"batch": [
            {"trace_id": "ffee00112233445566778899aabbccdd", "span_id": "aa11bb22cc33dd44",
             "service": "qa-svc", "name": "GET /qa", "duration_ms": 55, "status": "OK",
             "timestamp": "2026-07-07T15:00:00Z"}
        ]}
        r = requests.post(f"{BASE_URL}/api/ingest/traces",
                          headers={"X-API-Key": created_key["key"], "Content-Type": "application/json"},
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ingested"] == 1
        assert j["traces"] == 1

    def test_heartbeat_and_agents(self, created_key, admin_headers):
        r = requests.post(f"{BASE_URL}/api/ingest/heartbeat",
                          headers={"X-API-Key": created_key["key"], "Content-Type": "application/json"},
                          json={"host": "qa-host-2", "agent_version": "1.0.0", "environment": "dev",
                                "services": [{"name": "qa-svc", "runtime": "go"}]}, timeout=30)
        assert r.status_code == 200
        time.sleep(1)
        r2 = requests.get(f"{BASE_URL}/api/oneagent/agents", headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        agents = r2.json()["agents"]
        hosts = [a["host"] for a in agents]
        assert "qa-host-2" in hosts, f"qa-host-2 not in {hosts}"

    def test_missing_batch(self, created_key):
        r = requests.post(f"{BASE_URL}/api/ingest/logs",
                          headers={"X-API-Key": created_key["key"], "Content-Type": "application/json"},
                          json={"host": "x"}, timeout=30)
        assert r.status_code == 400


# ─── Downloads ────────────────────────────────────────────────────
class TestDownloads:
    def test_install_script(self):
        r = requests.get(f"{BASE_URL}/api/oneagent/install.sh", timeout=30)
        assert r.status_code == 200
        assert r.text.startswith("#!/usr/bin/env bash") or r.text.startswith("#!/bin/bash"), r.text[:80]

    def test_download_amd64(self):
        r = requests.get(f"{BASE_URL}/api/oneagent/download/binary?arch=amd64", timeout=60, stream=True)
        assert r.status_code == 200
        cl = int(r.headers.get("Content-Length", "0"))
        assert cl > 1_000_000, f"binary too small: {cl}"

    def test_download_arm64(self):
        r = requests.get(f"{BASE_URL}/api/oneagent/download/binary?arch=arm64", timeout=60, stream=True)
        assert r.status_code == 200

    def test_download_invalid_arch(self):
        r = requests.get(f"{BASE_URL}/api/oneagent/download/binary?arch=evil", timeout=30)
        assert r.status_code == 422

    def test_download_source(self):
        r = requests.get(f"{BASE_URL}/api/oneagent/download/source", timeout=60, stream=True)
        assert r.status_code == 200
        ct = r.headers.get("Content-Type", "")
        assert "gzip" in ct or "octet" in ct


# ─── Regression ──────────────────────────────────────────────────
class TestRegression:
    def test_ai_intel_tools(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/ai-intelligence/tools", headers=admin_headers, timeout=30)
        assert r.status_code == 200

    def test_login_still_works(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
        assert r.status_code == 200
