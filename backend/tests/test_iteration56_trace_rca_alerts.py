"""
Iteration 56 — Trace RCA + Trace-driven Alerts + Enterprise bundle hardening.
Tests the new /api/traces/{trace_id}/rca, /api/traces/alert-rules CRUD/evaluate,
correlation router un-shadowing, CORS env behaviour, and the enterprise bundle.
"""
import io
import os
import re
import tarfile
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}


# ──────────────────── Fixtures ────────────────────

@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def any_trace_id(admin_headers):
    """Return any seeded trace_id, sending one ourselves if list empty."""
    r = requests.get(f"{BASE_URL}/api/traces?hours=8760&limit=5", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    traces = r.json().get("traces") or []
    if traces:
        return traces[0]["trace_id"]
    # Push one OTLP trace
    tid = uuid.uuid4().hex
    sid = uuid.uuid4().hex[:16]
    now_ns = str(int(time.time() * 1_000_000_000))
    end_ns = str(int(time.time() * 1_000_000_000) + 100_000_000)
    payload = {"resourceSpans": [{
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "test-rca-svc"}}]},
        "scopeSpans": [{"spans": [{
            "traceId": tid, "spanId": sid, "name": "GET /ping",
            "startTimeUnixNano": now_ns, "endTimeUnixNano": end_ns,
            "kind": 2, "status": {"code": 1},
        }]}],
    }]}
    rr = requests.post(f"{BASE_URL}/api/otel/v1/traces", json=payload, timeout=30)
    assert rr.status_code == 200
    time.sleep(1)
    return tid


# ──────────────────── Trace RCA ────────────────────

class TestTraceRCA:
    def test_rca_unknown_trace_404(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/traces/nonexistent-trace-xyz/rca",
                          headers=admin_headers, timeout=60)
        assert r.status_code == 404

    def test_rca_returns_expected_shape(self, admin_headers, any_trace_id):
        r = requests.post(f"{BASE_URL}/api/traces/{any_trace_id}/rca",
                          headers=admin_headers, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        # required keys
        for k in ("trace_id", "slow_spans", "error_chains", "hotspots", "summary"):
            assert k in data, f"missing {k}"
        assert isinstance(data["slow_spans"], list)
        assert isinstance(data["error_chains"], list)
        assert isinstance(data["hotspots"], list)
        # summary structure
        summ = data["summary"]
        assert "text" in summ and isinstance(summ["text"], str) and len(summ["text"]) > 0
        assert "provider" in summ


# ──────────────────── Trace Alert Rules CRUD ────────────────────

class TestTraceAlertRules:
    def test_list_initially_returns_shape(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/traces/alert-rules", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "rules" in body and "count" in body
        assert isinstance(body["rules"], list)
        assert body["count"] == len(body["rules"])

    def test_list_not_shadowed_by_trace_id_route(self, admin_headers):
        """Ensure /alert-rules is NOT matched by /api/traces/{trace_id}."""
        r = requests.get(f"{BASE_URL}/api/traces/alert-rules", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # If shadowed by /api/traces/{trace_id}, response would be 404 or contain 'trace' key
        assert "rules" in r.json()

    def test_create_missing_service_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/traces/alert-rules",
                          headers=admin_headers,
                          json={"rule_type": "latency", "threshold_ms": 100},
                          timeout=30)
        # FastAPI will 422 for pydantic missing required field
        assert r.status_code in (400, 422), r.text

    def test_create_bad_rule_type_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/traces/alert-rules",
                          headers=admin_headers,
                          json={"service": "svc-x", "rule_type": "garbage", "threshold_ms": 1},
                          timeout=30)
        assert r.status_code == 400, r.text

    def test_full_crud_cycle(self, admin_headers):
        # CREATE
        payload = {
            "name": "TEST_latency_rule_iter56",
            "service": "test-rca-svc",
            "rule_type": "latency",
            "metric": "p95",
            "threshold_ms": 10.0,
            "min_traces": 1,
            "window_minutes": 60,
            "severity": "high",
        }
        c = requests.post(f"{BASE_URL}/api/traces/alert-rules",
                          headers=admin_headers, json=payload, timeout=30)
        assert c.status_code == 200, c.text
        rule = c.json()
        assert rule["service"] == "test-rca-svc"
        assert rule["rule_type"] == "latency"
        rule_id = rule["id"]
        assert rule_id

        # LIST → contains new rule
        l = requests.get(f"{BASE_URL}/api/traces/alert-rules",
                         headers=admin_headers, timeout=30)
        assert l.status_code == 200
        ids = [r["id"] for r in l.json()["rules"]]
        assert rule_id in ids

        # UPDATE
        upd = {**payload, "threshold_ms": 999.0, "name": "TEST_latency_rule_iter56_updated"}
        u = requests.put(f"{BASE_URL}/api/traces/alert-rules/{rule_id}",
                         headers=admin_headers, json=upd, timeout=30)
        assert u.status_code == 200, u.text
        assert u.json()["threshold_ms"] == 999.0
        assert u.json()["name"] == "TEST_latency_rule_iter56_updated"

        # EVALUATE
        e = requests.post(f"{BASE_URL}/api/traces/alert-rules/evaluate",
                          headers=admin_headers, timeout=60)
        assert e.status_code == 200, e.text
        ej = e.json()
        assert "evaluated" in ej and "results" in ej
        assert ej["evaluated"] >= 1

        # DELETE
        d = requests.delete(f"{BASE_URL}/api/traces/alert-rules/{rule_id}",
                            headers=admin_headers, timeout=30)
        assert d.status_code == 200
        assert d.json().get("deleted") is True

        # Verify gone
        l2 = requests.get(f"{BASE_URL}/api/traces/alert-rules",
                          headers=admin_headers, timeout=30)
        ids2 = [r["id"] for r in l2.json()["rules"]]
        assert rule_id not in ids2


# ──────────────────── Trace alert breaching scenario ────────────────────

class TestTraceAlertBreach:
    def test_breach_creates_alert(self, admin_headers):
        service = f"breach-svc-{uuid.uuid4().hex[:6]}"
        # 1) Create rule with very low threshold so it will breach
        rule_payload = {
            "name": f"TEST_breach_{service}",
            "service": service,
            "rule_type": "latency",
            "metric": "avg",
            "threshold_ms": 1.0,   # 1ms threshold
            "min_traces": 1,
            "window_minutes": 60,
            "severity": "high",
        }
        rc = requests.post(f"{BASE_URL}/api/traces/alert-rules",
                           headers=admin_headers, json=rule_payload, timeout=30)
        assert rc.status_code == 200, rc.text
        rule_id = rc.json()["id"]

        try:
            # 2) Send a slow trace for that service (duration 500ms)
            tid = uuid.uuid4().hex
            sid = uuid.uuid4().hex[:16]
            now_ns = int(time.time() * 1_000_000_000)
            end_ns = now_ns + 500_000_000  # 500ms
            payload = {"resourceSpans": [{
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
                "scopeSpans": [{"spans": [{
                    "traceId": tid, "spanId": sid, "name": "GET /slow",
                    "startTimeUnixNano": str(now_ns), "endTimeUnixNano": str(end_ns),
                    "kind": 2, "status": {"code": 1},
                }]}],
            }]}
            ti = requests.post(f"{BASE_URL}/api/otel/v1/traces", json=payload, timeout=30)
            assert ti.status_code == 200
            time.sleep(1)

            # 3) Run evaluator
            ev = requests.post(f"{BASE_URL}/api/traces/alert-rules/evaluate",
                               headers=admin_headers, timeout=60)
            assert ev.status_code == 200
            results = ev.json()["results"]
            mine = [r for r in results if r.get("rule_id") == rule_id]
            assert mine, f"No eval result for rule {rule_id}"
            assert mine[0]["breaching"] is True, f"Expected breaching: {mine[0]}"
            assert mine[0]["transitioned"] is True
            # alert id should exist
            assert mine[0].get("fired_alert_id"), "No alert was created on breach"
        finally:
            requests.delete(f"{BASE_URL}/api/traces/alert-rules/{rule_id}",
                            headers=admin_headers, timeout=30)


# ──────────────────── Old correlation router un-shadowed ────────────────────

class TestCorrelationUnshadow:
    def test_correlation_rules_reachable(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/correlation/rules",
                         headers=admin_headers, timeout=30)
        # Must be reachable (200/204) — not 404 due to shadow
        assert r.status_code in (200, 204), f"correlation/rules unreachable: {r.status_code} {r.text[:200]}"

    def test_correlation_stats_reachable(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/correlation/stats",
                         headers=admin_headers, timeout=30)
        assert r.status_code in (200, 204), f"correlation/stats unreachable: {r.status_code} {r.text[:200]}"


# ──────────────────── Health (verifies lazy emergentintegrations import) ────────────────────

class TestHealthAndCORS:
    def test_health_endpoint_ok(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200, r.text

    def test_cors_wildcard_drops_credentials(self):
        """When CORS_ORIGINS=*, server must NOT echo Access-Control-Allow-Credentials: true."""
        r = requests.options(
            f"{BASE_URL}/api/health",
            headers={
                "Origin": "https://random-origin.example.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=30,
        )
        # We only assert that with wildcard the credentials header is not 'true'.
        creds = r.headers.get("Access-Control-Allow-Credentials", "").lower()
        allow_origin = r.headers.get("Access-Control-Allow-Origin", "")
        # If wildcard, credentials should be absent or 'false' (per CORS spec)
        if allow_origin == "*":
            assert creds != "true", "Wildcard origin must not allow credentials"


# ──────────────────── Enterprise on-prem bundle ────────────────────

class TestEnterpriseBundle:
    def test_source_bundle_contains_required_files(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/licenses/download/source",
                         headers=admin_headers, timeout=300, stream=True)
        assert r.status_code == 200, f"bundle download failed: {r.status_code} {r.text[:300]}"
        ct = r.headers.get("content-type", "")
        assert "tar" in ct or "octet-stream" in ct or "gzip" in ct, f"unexpected content-type: {ct}"
        buf = io.BytesIO(r.content)
        try:
            tf = tarfile.open(fileobj=buf, mode="r:gz")
        except tarfile.ReadError:
            buf.seek(0)
            tf = tarfile.open(fileobj=buf, mode="r:*")
        names = tf.getnames()
        joined = "\n".join(names)

        required_patterns = [
            r"install\.sh",
            r"uninstall\.sh",
            r"upgrade\.sh",
            r"AIRGAP\.md",
            r"ENTERPRISE\.md",
            r"configs/",
            r"scripts/",
            r"kubernetes/helm/",
            r"emergentintegrations.*\.whl",
            r"Dockerfile",
        ]
        missing = [p for p in required_patterns if not re.search(p, joined)]
        assert not missing, f"Bundle missing patterns: {missing}. Sample names: {names[:30]}"
