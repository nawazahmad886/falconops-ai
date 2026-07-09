"""
Iteration 62 — AI Log Analyzer backend tests.

Covers: /api/log-analyzer/{analyze, history, analysis/{id}, explain, patterns, stats}
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend/.env at runtime
    try:
        for ln in open("/app/frontend/.env"):
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")
                break
    except Exception:
        pass

ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"

ERROR_LOGS_TEMPLATE = """2025-01-15T10:00:00Z INFO Starting service worker-{uid}
2025-01-15T10:00:01Z INFO Connected to database
2025-01-15T10:01:02Z WARN Memory usage at 85%
2025-01-15T10:01:30Z ERROR Failed to allocate buffer for request id=abc-{uid}
2025-01-15T10:01:31Z ERROR java.lang.OutOfMemoryError: Java heap space at com.example.App.handle(App.java:42)
2025-01-15T10:01:32Z FATAL Container OOMKilled exit code 137 pod=worker-7
2025-01-15T10:01:33Z ERROR java.lang.OutOfMemoryError: Java heap space at com.example.App.handle(App.java:42)
2025-01-15T10:01:34Z ERROR Connection reset by peer
2025-01-15T10:01:35Z FATAL OOMKilled pod terminated
"""

HEALTHY_LOGS = """2025-01-15T10:00:00Z INFO service started ok
2025-01-15T10:00:05Z INFO request handled in 12ms
2025-01-15T10:00:08Z DEBUG cache hit ratio 0.98
2025-01-15T10:00:10Z INFO heartbeat ok
"""


@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ─── helper to make payload unique each test run (force cache miss) ──────────
@pytest.fixture(scope="module")
def unique_id():
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def error_logs(unique_id):
    return ERROR_LOGS_TEMPLATE.format(uid=unique_id)


# ───────────────────────── ANALYZE — fresh + cache hit ───────────────────────
class TestAnalyzePipeline:

    def test_analyze_critical(self, headers, error_logs, request):
        r = requests.post(
            f"{BASE_URL}/api/log-analyzer/analyze",
            json={"logs": error_logs, "source": "test"},
            headers=headers, timeout=120,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["severity"] in ("High", "Critical"), f"severity={d.get('severity')}"
        assert d.get("error_type"), "error_type empty"
        assert d.get("summary") and len(d["summary"]) <= 560
        assert d.get("root_cause")
        assert d.get("suggested_fix")
        rp = d.get("recurring_pattern") or {}
        assert "status" in rp and "explanation" in rp
        assert d.get("line_count", 0) > 0
        assert d.get("chunks", 0) >= 1
        assert d.get("provider"), "provider missing"
        assert d.get("model"), "model missing"
        assert d.get("pipeline_latency_ms", 0) > 0
        assert d.get("cached") is False
        assert d.get("id")
        request.config.cache.set("la_id", d["id"])
        request.config.cache.set("la_first_latency", d["pipeline_latency_ms"])

    def test_analyze_cache_hit(self, headers, error_logs):
        r = requests.post(
            f"{BASE_URL}/api/log-analyzer/analyze",
            json={"logs": error_logs, "source": "test"},
            headers=headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("cached") is True, f"expected cached=true, got {d.get('cached')}"
        assert d.get("pipeline_latency_ms", 99999) < 1500

    def test_analyze_healthy_low(self, headers, unique_id):
        payload = HEALTHY_LOGS + f"# tag-{unique_id}\n"
        r = requests.post(
            f"{BASE_URL}/api/log-analyzer/analyze",
            json={"logs": payload, "source": "test"},
            headers=headers, timeout=120,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["severity"] in ("Low", "Medium"), f"sev={d['severity']}"

    def test_analyze_empty_returns_422(self, headers):
        r = requests.post(
            f"{BASE_URL}/api/log-analyzer/analyze",
            json={"logs": "", "source": "test"},
            headers=headers, timeout=15,
        )
        assert r.status_code == 422

    def test_analyze_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/log-analyzer/analyze",
            json={"logs": "x"}, timeout=15,
        )
        assert r.status_code in (401, 403)


# ─────────────────────────────── HISTORY ─────────────────────────────────────
class TestHistory:
    def test_history_list(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/log-analyzer/history?limit=10",
            headers=headers, timeout=20,
        )
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "count" in d
        assert isinstance(d["items"], list)
        if d["items"]:
            it = d["items"][0]
            for k in ("id", "severity", "error_type", "summary", "created_at"):
                assert k in it
            # sorted desc
            if len(d["items"]) > 1:
                assert d["items"][0]["created_at"] >= d["items"][1]["created_at"]

    def test_history_severity_filter(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/log-analyzer/history?severity=Critical&limit=20",
            headers=headers, timeout=20,
        )
        assert r.status_code == 200
        items = r.json().get("items", [])
        for it in items:
            assert it["severity"] == "Critical"


# ─────────────────────── ANALYSIS GET / DELETE ───────────────────────────────
class TestAnalysisCRUD:
    def test_get_existing(self, headers, request):
        aid = request.config.cache.get("la_id", None)
        if not aid:
            pytest.skip("no id from analyze test")
        r = requests.get(f"{BASE_URL}/api/log-analyzer/analysis/{aid}",
                         headers=headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == aid
        assert d.get("severity")

    def test_get_404(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/log-analyzer/analysis/nonexistent-{uuid.uuid4().hex}",
            headers=headers, timeout=15,
        )
        assert r.status_code == 404

    def test_delete_then_404(self, headers, request):
        aid = request.config.cache.get("la_id", None)
        if not aid:
            pytest.skip("no id")
        r = requests.delete(f"{BASE_URL}/api/log-analyzer/analysis/{aid}",
                            headers=headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        # subsequent GET → 404
        r2 = requests.get(f"{BASE_URL}/api/log-analyzer/analysis/{aid}",
                          headers=headers, timeout=15)
        assert r2.status_code == 404


# ─────────────────────────────── EXPLAIN ─────────────────────────────────────
class TestExplain:
    def test_explain(self, headers):
        r = requests.post(
            f"{BASE_URL}/api/log-analyzer/explain",
            json={"error": "java.lang.OutOfMemoryError: Java heap space",
                  "context": "pod restarted with exit 137"},
            headers=headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("explanation"), "no explanation"
        assert isinstance(d.get("likely_causes"), list)
        assert isinstance(d.get("next_steps"), list)
        assert "external_docs_hint" in d


# ─────────────────────────── PATTERNS / STATS ────────────────────────────────
class TestPatternsStats:
    def test_patterns(self, headers, error_logs, unique_id):
        # Seed at least one analysis (new payload to be safe)
        seed = error_logs + f"\n# seed-{unique_id}-patterns\n"
        requests.post(
            f"{BASE_URL}/api/log-analyzer/analyze",
            json={"logs": seed, "source": "test"},
            headers=headers, timeout=120,
        )
        r = requests.get(f"{BASE_URL}/api/log-analyzer/patterns",
                         headers=headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "patterns" in d and isinstance(d["patterns"], list)
        if d["patterns"]:
            p = d["patterns"][0]
            for k in ("error_type", "occurrences", "severities", "last_seen"):
                assert k in p

    def test_stats(self, headers):
        r = requests.get(f"{BASE_URL}/api/log-analyzer/stats",
                         headers=headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_analyses", "critical_count", "high_count",
                  "last_analysis_at", "last_severity"):
            assert k in d
        assert isinstance(d["total_analyses"], int)
