"""Tests for AI Intelligence Layer endpoints (FalconOpsAI)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://health-rules-engine.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# --- Auth guard ---
def test_ask_requires_auth():
    r = requests.post(f"{API}/ai-intelligence/ask", json={"query": "hi", "mode": "copilot"}, timeout=15)
    assert r.status_code in (401, 403)


def test_tools_requires_auth():
    r = requests.get(f"{API}/ai-intelligence/tools", timeout=15)
    assert r.status_code in (401, 403)


# --- Tools ---
def test_list_tools(h):
    r = requests.get(f"{API}/ai-intelligence/tools", headers=h, timeout=15)
    assert r.status_code == 200
    tools = r.json()["tools"]
    assert len(tools) == 6
    names = {t.get("name") for t in tools}
    assert {"get_logs", "get_metrics", "get_traces", "get_deployments", "get_incidents", "get_agent_status"} <= names


def test_execute_get_agent_status(h):
    r = requests.post(
        f"{API}/ai-intelligence/tools/get_agent_status/execute",
        headers=h,
        json={"params": {"service": "payment-api"}},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("tool") == "get_agent_status"
    assert isinstance(data.get("data"), list)
    assert isinstance(data.get("any_healthy"), bool)
    assert data.get("count") == len(data["data"])
    assert isinstance(data.get("summary"), str) and len(data["summary"]) > 0


def test_execute_get_logs(h):
    r = requests.post(
        f"{API}/ai-intelligence/tools/get_logs/execute",
        headers=h,
        json={"params": {"service": "payment-api", "minutes": 60, "level": "error"}},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("count", 0) >= 12, f"expected >=12 errors, got {data}"


def test_execute_get_metrics(h):
    r = requests.post(
        f"{API}/ai-intelligence/tools/get_metrics/execute",
        headers=h,
        json={"params": {"service": "payment-api"}},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # metric catalog present
    assert isinstance(data, dict)
    # look for a catalog / metrics/series key
    assert data.get("tool") == "get_metrics"
    assert isinstance(data.get("data"), list)
    assert data.get("count", 0) >= 1
    names = {m.get("name") for m in data["data"]}
    assert {"p95_latency_ms", "cpu_usage"} & names


def test_execute_unknown_tool_graceful(h):
    r = requests.post(
        f"{API}/ai-intelligence/tools/nonexistent_tool/execute",
        headers=h,
        json={"params": {}},
        timeout=15,
    )
    # should NOT be a 500
    assert r.status_code != 500
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    # Should contain error field
    assert "error" in body or r.status_code in (400, 404, 422)


# --- Services / history ---
def test_services(h):
    r = requests.get(f"{API}/ai-intelligence/services", headers=h, timeout=15)
    assert r.status_code == 200
    svcs = r.json().get("services", [])
    # services may be list of strings or dicts
    flat = [s if isinstance(s, str) else s.get("name") or s.get("service") for s in svcs]
    assert "payment-api" in flat


def test_history(h):
    r = requests.get(f"{API}/ai-intelligence/history", headers=h, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "analyses" in data
    assert data["count"] >= 0  # non-negative
    return data


def test_analysis_unknown_id_404(h):
    r = requests.get(f"{API}/ai-intelligence/analysis/does-not-exist-xyz", headers=h, timeout=15)
    assert r.status_code == 404


# --- RAG ---
def test_rag_stats(h):
    r = requests.get(f"{API}/ai-intelligence/rag/stats", headers=h, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("available") is True
    store = str(data.get("store", "")).lower()
    assert "chromadb" in store
    assert data.get("incident_history_count", 0) >= 6


def test_rag_reindex(h):
    r = requests.post(f"{API}/ai-intelligence/rag/reindex", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("status") == "ok"
    assert "incidents_indexed" in data
    assert "logs_indexed" in data


# --- LLM /ask (limit to 2 calls per instructions) ---
def test_ask_copilot_mode(h):
    r = requests.post(
        f"{API}/ai-intelligence/ask",
        headers=h,
        json={"query": "Show errors in the last 60 minutes", "mode": "copilot"},
        timeout=120,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("summary", "evidence", "confidence", "recommended_actions", "tool_trace", "mode"):
        assert k in data, f"missing {k} in response: {list(data.keys())}"
    assert data["mode"] == "copilot"
    assert isinstance(data["evidence"], list)
    assert isinstance(data["recommended_actions"], list)
    assert 0.0 <= float(data["confidence"]) <= 1.0
    tools_used = [t.get("tool") or t.get("name") for t in data["tool_trace"]]
    assert "get_logs" in tools_used


def test_ask_incident_auto_route(h):
    r = requests.post(
        f"{API}/ai-intelligence/ask",
        headers=h,
        json={"query": "Why is payment-api slow?", "mode": "auto"},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("mode") == "incident", f"expected incident mode, got {data.get('mode')}"
    assert data.get("service") == "payment-api"
    assert float(data.get("confidence", 0)) > 0.5
    assert len(data.get("evidence", [])) > 0
    assert len(data.get("recommended_actions", [])) > 0
    assert len(data.get("tool_trace", [])) >= 6
    assert "similar_incidents" in data
    assert isinstance(data["similar_incidents"], list)


# --- Regression ---
def test_regression_log_analyzer_stats(h):
    r = requests.get(f"{API}/log-analyzer/stats", headers=h, timeout=15)
    assert r.status_code == 200


def test_regression_ai_monitoring_timeseries(h):
    r = requests.get(f"{API}/ai-monitoring/timeseries", headers=h, timeout=15)
    assert r.status_code == 200
