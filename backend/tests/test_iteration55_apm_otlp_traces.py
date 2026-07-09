"""Backend tests for OTLP ingestion + Trace Viewer endpoints (iteration 55)."""
import os
import time
import requests
import pytest

def _load_backend_url():
    val = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not val:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    return val.rstrip("/")


BASE_URL = _load_backend_url()
ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}
VIEWER = {"email": "test@falconapps.com", "password": "testpass123"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def viewer_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=VIEWER, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ─────────── OTLP ingestion (unauthenticated) ───────────

def _otlp_payload(trace_id, span_id, parent_id, service, name, status_code=1):
    now_ns = str(int(time.time() * 1_000_000_000))
    end_ns = str(int(time.time() * 1_000_000_000) + 50_000_000)
    span = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": name,
        "kind": 2,
        "startTimeUnixNano": now_ns,
        "endTimeUnixNano": end_ns,
        "status": {"code": status_code},
    }
    if parent_id:
        span["parentSpanId"] = parent_id
    return {
        "resourceSpans": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
            "scopeSpans": [{"scope": {"name": "test"}, "spans": [span]}],
        }]
    }


def test_otlp_ingest_accepts_payload():
    payload = _otlp_payload("aabbccddeeff00112233445566778899", "1111111122222222", None, "test-svc-otlp", "GET /test")
    r = requests.post(f"{BASE_URL}/api/otel/v1/traces", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("accepted") == 1


def test_otlp_ingest_invalid_json_returns_400():
    r = requests.post(f"{BASE_URL}/api/otel/v1/traces", data="notjson",
                      headers={"Content-Type": "application/json"}, timeout=15)
    assert r.status_code == 400


def test_otlp_metrics_endpoint():
    r = requests.post(f"{BASE_URL}/api/otel/v1/metrics", json={"resourceMetrics": []}, timeout=15)
    assert r.status_code == 200
    assert "accepted" in r.json()


def test_otlp_logs_endpoint():
    r = requests.post(f"{BASE_URL}/api/otel/v1/logs", json={"resourceLogs": []}, timeout=15)
    assert r.status_code == 200


# ─────────── Trace viewer (auth required) ───────────

def test_list_traces_requires_auth():
    r = requests.get(f"{BASE_URL}/api/traces", timeout=15)
    assert r.status_code in (401, 403)


def test_list_traces_admin(auth_h):
    r = requests.get(f"{BASE_URL}/api/traces?hours=720", headers=auth_h, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "traces" in data and "count" in data
    assert isinstance(data["traces"], list)


def test_list_traces_viewer_can_read(viewer_token):
    r = requests.get(f"{BASE_URL}/api/traces?hours=720",
                     headers={"Authorization": f"Bearer {viewer_token}"}, timeout=15)
    assert r.status_code == 200


def test_list_traces_status_filter(auth_h):
    r = requests.get(f"{BASE_URL}/api/traces?hours=720&status=OK", headers=auth_h, timeout=15)
    assert r.status_code == 200
    for t in r.json()["traces"]:
        assert t["status"] == "OK"


def test_list_traces_invalid_status_rejected(auth_h):
    r = requests.get(f"{BASE_URL}/api/traces?hours=1&status=BOGUS", headers=auth_h, timeout=15)
    assert r.status_code == 422


def test_services_list(auth_h):
    r = requests.get(f"{BASE_URL}/api/traces/services/list", headers=auth_h, timeout=15)
    assert r.status_code == 200
    assert "services" in r.json()
    assert isinstance(r.json()["services"], list)


def test_service_dependencies(auth_h):
    r = requests.get(f"{BASE_URL}/api/traces/services/dependencies?hours=168",
                     headers=auth_h, timeout=15)
    assert r.status_code == 200
    data = r.json()
    for k in ("nodes", "edges", "node_count", "edge_count"):
        assert k in data


def test_stats_summary(auth_h):
    r = requests.get(f"{BASE_URL}/api/traces/stats/summary?hours=720", headers=auth_h, timeout=15)
    assert r.status_code == 200
    data = r.json()
    for k in ("total", "errors", "error_rate_pct", "avg_duration",
              "max_duration", "services_count", "total_spans"):
        assert k in data, f"missing {k}"


def test_get_trace_by_id_after_ingest(auth_h):
    # Ingest parent + child span in same batch so we can verify tree + dependency edge
    trace_id = "ffeeddccbbaa99887766554433221100"
    now_ns = int(time.time() * 1_000_000_000)
    payload = {
        "resourceSpans": [
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "svc-a-tree"}}]},
                "scopeSpans": [{"scope": {"name": "test"}, "spans": [{
                    "traceId": trace_id, "spanId": "abcdef0011223344",
                    "name": "root-op", "kind": 2,
                    "startTimeUnixNano": str(now_ns),
                    "endTimeUnixNano": str(now_ns + 100_000_000),
                    "status": {"code": 1},
                }]}],
            },
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "svc-b-tree"}}]},
                "scopeSpans": [{"scope": {"name": "test"}, "spans": [{
                    "traceId": trace_id, "spanId": "1122334455667788",
                    "parentSpanId": "abcdef0011223344",
                    "name": "child-op", "kind": 3,
                    "startTimeUnixNano": str(now_ns + 10_000_000),
                    "endTimeUnixNano": str(now_ns + 50_000_000),
                    "status": {"code": 2},
                }]}],
            },
        ]
    }
    r0 = requests.post(f"{BASE_URL}/api/otel/v1/traces", json=payload, timeout=15)
    assert r0.status_code == 200 and r0.json()["accepted"] == 2
    time.sleep(0.5)

    r = requests.get(f"{BASE_URL}/api/traces/{trace_id}", headers=auth_h, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "trace" in data and "spans" in data and "tree" in data
    assert len(data["spans"]) >= 2
    assert isinstance(data["tree"], list) and len(data["tree"]) >= 1
    # Status overall should be ERROR since child errored
    assert data["trace"]["status"] == "ERROR"
    # Tree root should have child
    root = data["tree"][0]
    assert "children" in root and len(root["children"]) >= 1


def test_get_trace_404(auth_h):
    r = requests.get(f"{BASE_URL}/api/traces/nonexistent_trace_id_xxx", headers=auth_h, timeout=15)
    assert r.status_code == 404


def test_dependencies_built_after_ingest(auth_h):
    # After previous test ingested svc-a-tree -> svc-b-tree, dependencies should include the edge
    r = requests.get(f"{BASE_URL}/api/traces/services/dependencies?hours=168", headers=auth_h, timeout=15)
    data = r.json()
    found = any(e.get("service") == "svc-a-tree" and e.get("depends_on") == "svc-b-tree"
                for e in data.get("edges", []))
    assert found, f"Expected service edge not found. edges={data.get('edges')}"
