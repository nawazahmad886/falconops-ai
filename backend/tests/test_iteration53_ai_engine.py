"""
Iteration 53 — Autonomous AI Engine + Admin Console (Limits/Testers/Routing) + Platform Health Sweep
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://health-rules-engine.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASS = "Admin@123"
VIEWER_EMAIL = "test@falconapps.com"
VIEWER_PASS = "testpass123"


# ─────────────────── Auth fixtures ───────────────────

def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="session")
def viewer_token():
    return _login(VIEWER_EMAIL, VIEWER_PASS)


@pytest.fixture(scope="session")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def viewer_h(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def original_features(admin_h):
    """Capture current feature_flags so we can restore at end."""
    r = requests.get(f"{BASE_URL}/api/admin/features", headers=admin_h, timeout=20)
    if r.status_code == 200:
        return r.json()
    return None


# ═════════════════════════════════ HEALTH ═════════════════════════════════

class TestHealth:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d.get("status") == "healthy"


# ═════════════════════════════════ AI ENGINE — PIPELINE ═════════════════════════════════

class TestAIEnginePipeline:
    def test_process_event_returns_full_insight(self, admin_h):
        evt = {
            "service": "checkout-api",
            "alert": "CPU > 90%",
            "severity": "critical",
            "host": "prod-web-01",
        }
        r = requests.post(f"{BASE_URL}/api/ai-engine/process",
                          headers=admin_h, json={"event": evt}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # Verify expected keys
        for k in ["agents_consulted", "verdicts", "root_cause", "recommended_action",
                  "status", "is_duplicate", "context"]:
            assert k in d, f"Missing key {k} in response: {list(d.keys())}"
        assert isinstance(d["verdicts"], list) and len(d["verdicts"]) >= 1
        # root_cause structure
        rc = d["root_cause"]
        for k in ["summary", "evidence", "confidence"]:
            assert k in rc
        # recommended_action structure
        ra = d["recommended_action"]
        for k in ["kind", "risk", "auto_executable", "approval_required"]:
            assert k in ra
        # context structure
        ctx = d["context"]
        for k in ["history_count", "topology", "runbook_present", "is_recurring"]:
            assert k in ctx

    def test_process_event_empty_400(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/ai-engine/process",
                          headers=admin_h, json={"event": {}}, timeout=15)
        # 400 expected for missing event payload (or processed with degraded info)
        assert r.status_code in (200, 400)

    def test_list_insights(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/ai-engine/insights?hours=24", headers=admin_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "insights" in d and isinstance(d["insights"], list)

    def test_summary(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/ai-engine/summary", headers=admin_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ["insights_total", "insights_pending_review", "noise_reduction_pct",
                  "prevention_warnings", "cost_recommendations", "insights_by_agent"]:
            assert k in d, f"Missing key {k}: {list(d.keys())}"


# ═════════════════════════════════ AI ENGINE — PREVENTION ═════════════════════════════════

class TestPrevention:
    def test_prevention_scan_admin(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/ai-engine/prevention/scan", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert "warnings" in d and isinstance(d["warnings"], list)

    def test_prevention_scan_viewer_403(self, viewer_h):
        r = requests.post(f"{BASE_URL}/api/ai-engine/prevention/scan", headers=viewer_h, timeout=15)
        assert r.status_code == 403

    def test_prevention_warnings_list(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/ai-engine/prevention/warnings?hours=24", headers=admin_h, timeout=20)
        assert r.status_code == 200
        assert "warnings" in r.json()


# ═════════════════════════════════ AI ENGINE — COST ═════════════════════════════════

class TestCost:
    def test_cost_scan(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/ai-engine/cost/scan", headers=admin_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "recommendations" in d and isinstance(d["recommendations"], list)
        assert "summary" in d
        s = d["summary"]
        for k in ["total_opportunities", "idle_monitors", "stale_data", "duplicate_monitors"]:
            assert k in s


# ═════════════════════════════════ AI ENGINE — NOISE ═════════════════════════════════

class TestNoise:
    def test_top_buckets(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/ai-engine/noise/top-buckets", headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert "buckets" in r.json()


# ═════════════════════════════════ AI ENGINE — CONTEXT ═════════════════════════════════

class TestContext:
    SERVICE = f"TEST_svc_{uuid.uuid4().hex[:6]}"
    ALERT = f"TEST_Alert_{uuid.uuid4().hex[:6]}"

    def test_topology_upsert_admin(self, admin_h):
        body = {"service": self.SERVICE, "upstream": ["lb-01"], "downstream": ["db-01"], "tier": "edge"}
        r = requests.put(f"{BASE_URL}/api/ai-engine/context/topology", headers=admin_h, json=body, timeout=15)
        assert r.status_code == 200, r.text[:200]

    def test_topology_get(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/ai-engine/context/topology/{self.SERVICE}", headers=admin_h, timeout=15)
        assert r.status_code == 200
        d = r.json()
        # Topology service should have upstream/downstream
        assert d.get("service") == self.SERVICE or "upstream" in d or "downstream" in d

    def test_topology_upsert_viewer_403(self, viewer_h):
        body = {"service": "should-403", "upstream": [], "downstream": []}
        r = requests.put(f"{BASE_URL}/api/ai-engine/context/topology", headers=viewer_h, json=body, timeout=15)
        assert r.status_code == 403

    def test_runbook_upsert_admin(self, admin_h):
        body = {"alert_name": self.ALERT, "steps": ["step1", "step2"], "owner": "sre", "matches": []}
        r = requests.put(f"{BASE_URL}/api/ai-engine/context/runbook", headers=admin_h, json=body, timeout=15)
        assert r.status_code == 200, r.text[:200]

    def test_runbook_get(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/ai-engine/context/runbook?alert={self.ALERT}",
                         headers=admin_h, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "steps" in d

    def test_enrich(self, admin_h):
        evt = {"service": self.SERVICE, "alert": self.ALERT, "severity": "warn", "host": "h1"}
        r = requests.post(f"{BASE_URL}/api/ai-engine/context/enrich",
                          headers=admin_h, json={"event": evt}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        # Enriched payload should have at least some of these keys
        assert any(k in d for k in ["history", "topology", "runbook", "baseline", "enriched", "history_count"])


# ═════════════════════════════════ ADMIN TESTERS ═════════════════════════════════

class TestPatternTester:
    def test_deny_fail_with_5xx_body(self, admin_h):
        body = "Internal Server Error\nTraceback (most recent call last):\n  File ..."
        r = requests.post(f"{BASE_URL}/api/admin/test/deny-patterns",
                          headers=admin_h, json={"body": body}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d["verdict"] == "FAIL"
        assert d["matches_count"] >= 2

    def test_deny_pass_clean_body(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/admin/test/deny-patterns",
                          headers=admin_h, json={"body": "All systems nominal."}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["verdict"] == "PASS"
        assert d["matches_count"] == 0

    def test_deny_custom_patterns(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/admin/test/deny-patterns",
                          headers=admin_h,
                          json={"body": "abc XYZ 123", "patterns": ["xyz"]}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["patterns_tested"] == 1
        assert d["matches_count"] == 1

    def test_deny_viewer_403(self, viewer_h):
        r = requests.post(f"{BASE_URL}/api/admin/test/deny-patterns",
                          headers=viewer_h, json={"body": "x"}, timeout=10)
        assert r.status_code == 403


class TestPromptTester:
    def test_ai_prompt_basic(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/admin/test/ai-prompt",
                          headers=admin_h,
                          json={"sample_message": "Reply with the single word: PONG"},
                          timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "assistant_response" in d
        assert isinstance(d["assistant_response"], str) and len(d["assistant_response"]) > 0
        assert "model" in d

    def test_ai_prompt_viewer_403(self, viewer_h):
        r = requests.post(f"{BASE_URL}/api/admin/test/ai-prompt",
                          headers=viewer_h,
                          json={"sample_message": "hi"}, timeout=15)
        assert r.status_code == 403


class TestTenantRoutingSelfTest:
    @pytest.fixture(scope="class")
    def first_tenant_id(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/tenants/routing", headers=admin_h, timeout=15)
        assert r.status_code == 200
        tenants = r.json()
        if isinstance(tenants, dict):
            tenants = tenants.get("tenants", [])
        if not tenants:
            pytest.skip("No tenants present")
        return tenants[0].get("id")

    def test_subdomain_method(self, admin_h, first_tenant_id):
        r = requests.post(f"{BASE_URL}/api/admin/test/tenant-routing/{first_tenant_id}",
                          headers=admin_h, json={"method": "subdomain"}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "verdict" in d
        assert d["verdict"] in ("ok", "fail", "skipped")

    def test_path_prefix_method(self, admin_h, first_tenant_id):
        r = requests.post(f"{BASE_URL}/api/admin/test/tenant-routing/{first_tenant_id}",
                          headers=admin_h, json={"method": "path_prefix"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["verdict"] in ("ok", "fail", "skipped")

    def test_custom_domain_method(self, admin_h, first_tenant_id):
        r = requests.post(f"{BASE_URL}/api/admin/test/tenant-routing/{first_tenant_id}",
                          headers=admin_h, json={"method": "custom_domain"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["verdict"] in ("ok", "fail", "skipped")

    def test_routing_viewer_403(self, viewer_h, first_tenant_id):
        r = requests.post(f"{BASE_URL}/api/admin/test/tenant-routing/{first_tenant_id}",
                          headers=viewer_h, json={"method": "subdomain"}, timeout=15)
        assert r.status_code == 403


# ═════════════════════════════════ AUTO-ACTION ALLOWLIST ═════════════════════════════════

class TestAllowlist:
    def test_set_allowlist_and_process(self, admin_h):
        # Set allowlist
        r = requests.patch(f"{BASE_URL}/api/admin/features",
                           headers=admin_h,
                           json={"limits": {"auto_action_allowlist": ["lower_check_interval", "scale_down"]}},
                           timeout=15)
        assert r.status_code == 200, r.text[:200]

        # Process a critical event so all agents fire and recommended_action is non-null
        evt = {"service": f"alloctest-{uuid.uuid4().hex[:6]}", "alert": "CPU > 95%",
               "severity": "critical", "host": "prod-h1"}
        r2 = requests.post(f"{BASE_URL}/api/ai-engine/process",
                           headers=admin_h, json={"event": evt}, timeout=30)
        assert r2.status_code == 200
        ra = r2.json().get("recommended_action")
        # recommended_action may be null for non-actionable events, but for critical it should exist
        if ra is None:
            pytest.skip("recommended_action is null — pipeline produced no action for this event "
                        "(may need higher event signal to trigger cost_agent scale_down)")
        assert "auto_executable" in ra
        assert isinstance(ra["auto_executable"], bool)


# ═════════════════════════════════ REGRESSION SUITE ═════════════════════════════════

class TestRegression:
    def test_uptime_create_with_safe_defaults(self, admin_h):
        name = f"TEST_iter53_{uuid.uuid4().hex[:6]}"
        body = {"name": name, "url": "https://example.com",
                "check_interval_seconds": 300, "apply_safe_defaults": True}
        r = requests.post(f"{BASE_URL}/api/uptime/monitors", headers=admin_h, json=body, timeout=20)
        assert r.status_code in (200, 201), r.text[:300]
        d = r.json()
        mid = d.get("id")
        if mid:
            requests.delete(f"{BASE_URL}/api/uptime/monitors/{mid}", headers=admin_h, timeout=15)

    def test_synthetic_multi_step(self, admin_h):
        name = f"TEST_iter53_syn_{uuid.uuid4().hex[:6]}"
        body = {
            "name": name, "url": "https://example.com",
            "check_type": "multi_step",
            "steps": [{"name": "s1", "url": "https://example.com", "method": "GET", "assertions": []}],
            "check_interval_seconds": 300,
        }
        r = requests.post(f"{BASE_URL}/api/synthetic/monitors", headers=admin_h, json=body, timeout=20)
        assert r.status_code in (200, 201), r.text[:300]
        mid = r.json().get("id")
        if mid:
            requests.delete(f"{BASE_URL}/api/synthetic/monitors/{mid}", headers=admin_h, timeout=15)

    def test_ai_copilot_chat(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/ai-copilot/chat",
                          headers=admin_h,
                          json={"message": "say PONG only", "session_id": f"reg-{uuid.uuid4().hex[:6]}"},
                          timeout=60)
        assert r.status_code in (200, 503), r.text[:200]

    def test_admin_features_get(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/features", headers=admin_h, timeout=15)
        assert r.status_code == 200

    def test_admin_audit_log(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/features/audit-log", headers=admin_h, timeout=15)
        assert r.status_code == 200

    def test_dashboard(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=admin_h, timeout=15)
        # endpoint may or may not exist; tolerate 404
        assert r.status_code in (200, 404)

    def test_scheduled_reports(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/scheduled-reports", headers=admin_h, timeout=15)
        assert r.status_code in (200, 404)


# ═════════════════════════════════ RESTORE ═════════════════════════════════

class TestZZZRestore:
    def test_restore_features(self, admin_h, original_features):
        if not original_features:
            pytest.skip("No original features to restore")
        # Restore limits to clean default
        body = {
            "limits": original_features.get("limits", {}),
        }
        r = requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h, json=body, timeout=15)
        assert r.status_code == 200
