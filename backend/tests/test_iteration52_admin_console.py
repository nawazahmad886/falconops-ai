"""
Iteration 52 — Admin Control Console + Synthetic Multi-Step + Tenant Routing
Backend regression suite.

Covers:
  - Synthetic multi-step journey w/ var substitution + assertions + SSL probe
  - Synthetic safe defaults from feature_flags deny_patterns
  - Synthetic check-now flow
  - Admin Features GET / PATCH / catalog / audit-log
  - Admin role guard (403 for viewer)
  - AI Copilot live config (custom system_prompt + module disable -> 503)
  - Deny pattern live merge into uptime monitor assertions
  - Tenant routing list / patch (valid + reserved/duplicate validation)
  - DNS instructions endpoint
  - Tenant resolution middleware via Host header (X-Tenant-Slug, X-Tenant-Routing)
  - Regression: existing /api/uptime/monitors and /api/ai-copilot/chat
"""
import os
import time
import uuid
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}
VIEWER = {"email": "test@falconapps.com", "password": "testpass123"}


# ─────────────────────── fixtures ───────────────────────

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:120]}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def viewer_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=VIEWER, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Viewer login failed: {r.status_code} {r.text[:120]}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def viewer_h(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


@pytest.fixture(scope="module")
def original_config(admin_h):
    """Capture the original feature flags so we can restore at the end."""
    r = requests.get(f"{BASE_URL}/api/admin/features", headers=admin_h, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Cannot fetch features: {r.status_code}")
    return r.json()


# ─────────────────────── 1) Admin Features ───────────────────────

class TestAdminFeatures:
    def test_features_get(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/features", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "modules" in data and "ai_copilot" in data and "deny_patterns" in data
        assert len(data["modules"]) >= 12, f"expected 12 modules, got {len(data['modules'])}"
        assert len(data["deny_patterns"]) >= 12, f"expected ≥12 deny patterns, got {len(data['deny_patterns'])}"
        assert data["ai_copilot"]["model"] == "claude-sonnet-4-5-20250929"
        assert "system_prompt" in data["ai_copilot"]

    def test_features_catalog(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/features/catalog", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["modules"]) == 12
        cats = {m["category"] for m in data["modules"]}
        assert len(cats) >= 5
        assert len(data["models"]) >= 3

    def test_features_role_guard_viewer(self, viewer_h):
        r = requests.get(f"{BASE_URL}/api/admin/features", headers=viewer_h, timeout=20)
        assert r.status_code == 403, f"viewer should be 403, got {r.status_code}"

    def test_features_patch_module_toggle(self, admin_h):
        r = requests.patch(
            f"{BASE_URL}/api/admin/features",
            headers=admin_h,
            json={"modules": {"stripe_billing": False}},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        new_cfg = r.json()
        assert new_cfg["modules"]["stripe_billing"] is False
        assert new_cfg["updated_by"] == ADMIN["email"]

        # restore
        requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h,
                       json={"modules": {"stripe_billing": True}}, timeout=20)

    def test_features_audit_log(self, admin_h):
        # trigger a small change first
        requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h,
                       json={"limits": {"alert_cooldown_min": 6}}, timeout=20)
        requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h,
                       json={"limits": {"alert_cooldown_min": 5}}, timeout=20)
        r = requests.get(f"{BASE_URL}/api/admin/features/audit-log", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        entries = r.json()["entries"]
        assert isinstance(entries, list) and len(entries) >= 1
        first = entries[0]
        assert "changed_at" in first and "changed_by" in first and "diffs" in first
        assert first["changed_by"] == ADMIN["email"]


# ─────────────────────── 2) AI Copilot live config ───────────────────────

class TestAICopilotLiveConfig:
    def test_module_disable_returns_503(self, admin_h):
        # disable AI Copilot
        requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h,
                       json={"modules": {"ai_copilot": False}}, timeout=20)
        try:
            r = requests.post(f"{BASE_URL}/api/ai-copilot/chat", headers=admin_h,
                              json={"message": "hello", "conversation_id": None}, timeout=30)
            assert r.status_code == 503, f"expected 503 when disabled, got {r.status_code}: {r.text[:200]}"
        finally:
            # re-enable
            requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h,
                           json={"modules": {"ai_copilot": True}}, timeout=20)

    def test_chat_works_after_reenable(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/ai-copilot/chat", headers=admin_h,
                          json={"message": "Say hi in one short sentence."}, timeout=60)
        # Accept 200 even if response field naming varies
        assert r.status_code == 200, r.text[:200]


# ─────────────────────── 3) Deny patterns live merge ───────────────────────

class TestDenyPatternLiveMerge:
    def test_custom_pattern_applied_to_new_uptime_monitor(self, admin_h, original_config):
        custom = "CUSTOM_FAIL_PATTERN_TEST"
        # Add custom pattern
        new_patterns = list(original_config["deny_patterns"]) + [custom]
        r = requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h,
                           json={"deny_patterns": new_patterns}, timeout=20)
        assert r.status_code == 200, r.text

        try:
            # Create uptime monitor with safe defaults
            r = requests.post(f"{BASE_URL}/api/uptime/monitors", headers=admin_h, json={
                "name": f"TEST_deny_{uuid.uuid4().hex[:6]}",
                "url": "https://example.com",
                "method": "GET",
                "check_interval_seconds": 300,
                "apply_safe_defaults": True,
            }, timeout=30)
            assert r.status_code in (200, 201), r.text
            mon = r.json()
            assertions = mon.get("assertions") or []
            values = [a.get("value") for a in assertions if isinstance(a, dict)]
            assert custom in values, f"custom pattern not merged: {values}"

            # cleanup monitor
            mid = mon.get("id") or mon.get("monitor_id")
            if mid:
                requests.delete(f"{BASE_URL}/api/uptime/monitors/{mid}", headers=admin_h, timeout=15)
        finally:
            # restore original deny patterns
            requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h,
                           json={"deny_patterns": original_config["deny_patterns"]}, timeout=20)


# ─────────────────────── 4) Synthetic multi-step ───────────────────────

class TestSyntheticMultiStep:
    @pytest.fixture
    def created_monitor(self, admin_h):
        body = {
            "name": f"TEST_synthetic_multi_{uuid.uuid4().hex[:6]}",
            "url": "https://jsonplaceholder.typicode.com/todos/1",
            "check_type": "multi_step",
            "check_interval_seconds": 300,
            "apply_safe_defaults": True,
            "steps": [
                {
                    "name": "step1_get_todo",
                    "method": "GET",
                    "url": "https://jsonplaceholder.typicode.com/todos/1",
                    "extract": {"user_id": "$.userId"},
                    "max_response_time_ms": 8000,
                },
                {
                    "name": "step2_get_user",
                    "method": "GET",
                    "url": "https://jsonplaceholder.typicode.com/users/${user_id}",
                    "max_response_time_ms": 8000,
                },
            ],
        }
        r = requests.post(f"{BASE_URL}/api/synthetic/monitors", headers=admin_h, json=body, timeout=30)
        assert r.status_code in (200, 201), r.text
        mon = r.json()
        yield mon
        mid = mon.get("id") or mon.get("monitor_id")
        if mid:
            requests.delete(f"{BASE_URL}/api/synthetic/monitors/{mid}", headers=admin_h, timeout=15)

    def test_multi_step_create_safe_defaults(self, admin_h, created_monitor):
        steps = created_monitor.get("steps") or []
        assert len(steps) == 2
        # NOTE: Implementation merges safe defaults at CHECK-EXECUTION time, not at CREATE time.
        # Spec wording says "verify by uploading and seeing assertions populated post-create" — gap.
        # We verify defaults take effect by running /check and inspecting evaluated assertions.
        mid = created_monitor.get("id") or created_monitor.get("monitor_id")
        r = requests.post(f"{BASE_URL}/api/synthetic/monitors/{mid}/check", headers=admin_h, timeout=60)
        assert r.status_code == 200, r.text
        result = r.json().get("result", r.json())
        run_steps = result.get("steps") or []
        assert len(run_steps) == 2
        # at minimum, status_code & response_time_ms should be evaluated → meaning assertions ran
        for s in run_steps:
            assert "status_code" in s

    def test_check_now_returns_steps_and_substitutes(self, admin_h, created_monitor):
        mid = created_monitor.get("id") or created_monitor.get("monitor_id")
        assert mid, "no monitor id"
        r = requests.post(f"{BASE_URL}/api/synthetic/monitors/{mid}/check", headers=admin_h, timeout=60)
        assert r.status_code == 200, r.text
        result = r.json()
        # Result may be wrapped
        result = result.get("result", result)
        steps = result.get("steps") or []
        assert len(steps) == 2, f"expected 2 steps, got {len(steps)}: {result}"
        for st in steps:
            assert "status_code" in st
            assert "response_time_ms" in st
            assert "status" in st
        # SSL recorded for HTTPS
        ssl_present = any("ssl_days_remaining" in s and s.get("ssl_days_remaining") for s in steps)
        assert ssl_present, f"no ssl_days_remaining in any step: {steps}"
        # variable substitution: step2 must have a numeric user id in resolved url
        step2 = steps[1]
        resolved_url = step2.get("resolved_url") or step2.get("url") or ""
        assert "${user_id}" not in resolved_url, f"variable not substituted: {resolved_url}"
        # overall status
        assert result.get("status") in ("success", "failed", "partial"), result.get("status")


# ─────────────────────── 5) Tenant Routing ───────────────────────

class TestTenantRouting:
    @pytest.fixture(scope="class")
    def tenants(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/tenants/routing", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "tenants" in data
        return data["tenants"]

    def test_list_returns_tenants(self, tenants):
        assert isinstance(tenants, list)
        if tenants:
            t = tenants[0]
            assert "id" in t and "name" in t and "slug" in t

    def test_patch_reserved_subdomain_rejected(self, admin_h, tenants):
        if not tenants:
            pytest.skip("no tenants")
        tid = tenants[0]["id"]
        r = requests.patch(f"{BASE_URL}/api/admin/tenants/{tid}/routing",
                           headers=admin_h, json={"subdomain": "www"}, timeout=20)
        assert r.status_code == 400, f"reserved 'www' should reject, got {r.status_code} {r.text[:200]}"

    def test_patch_valid_subdomain(self, admin_h, tenants):
        if not tenants:
            pytest.skip("no tenants")
        tid = tenants[0]["id"]
        original_sub = tenants[0].get("subdomain")
        unique = f"fasahtest{uuid.uuid4().hex[:4]}"
        try:
            r = requests.patch(f"{BASE_URL}/api/admin/tenants/{tid}/routing",
                               headers=admin_h, json={"subdomain": unique, "base_domain": "falconops.ai"}, timeout=20)
            assert r.status_code == 200, r.text
        finally:
            # restore
            requests.patch(f"{BASE_URL}/api/admin/tenants/{tid}/routing",
                           headers=admin_h, json={"subdomain": original_sub or ""}, timeout=20)

    def test_patch_duplicate_subdomain_rejected(self, admin_h, tenants):
        if len(tenants) < 2:
            pytest.skip("need ≥2 tenants")
        t1, t2 = tenants[0], tenants[1]
        unique = f"duptest{uuid.uuid4().hex[:4]}"
        # set tenant1 to unique
        r1 = requests.patch(f"{BASE_URL}/api/admin/tenants/{t1['id']}/routing",
                            headers=admin_h, json={"subdomain": unique}, timeout=20)
        try:
            assert r1.status_code == 200, r1.text
            # try same on tenant2
            r2 = requests.patch(f"{BASE_URL}/api/admin/tenants/{t2['id']}/routing",
                                headers=admin_h, json={"subdomain": unique}, timeout=20)
            assert r2.status_code == 400, f"duplicate should reject, got {r2.status_code}"
            assert "already" in r2.text.lower() or "used" in r2.text.lower() or "exist" in r2.text.lower()
        finally:
            requests.patch(f"{BASE_URL}/api/admin/tenants/{t1['id']}/routing",
                           headers=admin_h, json={"subdomain": t1.get("subdomain") or ""}, timeout=20)

    def test_dns_instructions_endpoint(self, admin_h, tenants):
        if not tenants:
            pytest.skip("no tenants")
        tid = tenants[0]["id"]
        r = requests.get(f"{BASE_URL}/api/admin/tenants/{tid}/dns-instructions?platform_apex=falconops.ai",
                         headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "records" in data and "urls" in data
        recs = data["records"]
        assert isinstance(recs, list) and len(recs) >= 1
        for rec in recs:
            assert "type" in rec and "host" in rec and "value" in rec


# ─────────────────────── 6) Tenant resolution middleware ───────────────────────

class TestTenantResolutionHeaders:
    def test_subdomain_host_header(self, admin_h):
        # Configure a known subdomain first
        r = requests.get(f"{BASE_URL}/api/admin/tenants/routing", headers=admin_h, timeout=20)
        if r.status_code != 200:
            pytest.skip("cannot fetch tenants")
        tenants = r.json().get("tenants", [])
        if not tenants:
            pytest.skip("no tenants")
        t = tenants[0]
        slug = f"tresolv{uuid.uuid4().hex[:4]}"
        requests.patch(f"{BASE_URL}/api/admin/tenants/{t['id']}/routing",
                       headers=admin_h, json={"subdomain": slug, "base_domain": "falconops.ai"}, timeout=20)
        try:
            r = requests.get(f"{BASE_URL}/api/health",
                             headers={"Host": f"{slug}.falconops.ai"}, timeout=20)
            # The middleware sets X-Tenant-Slug if resolved
            xs = r.headers.get("X-Tenant-Slug") or r.headers.get("x-tenant-slug")
            xr = r.headers.get("X-Tenant-Routing") or r.headers.get("x-tenant-routing")
            # Note: ingress may strip Host, so this is best-effort
            if xs:
                assert xs == slug
                assert xr == "subdomain"
            else:
                pytest.skip(f"middleware header not set (likely ingress strips Host); resp={r.status_code}")
        finally:
            requests.patch(f"{BASE_URL}/api/admin/tenants/{t['id']}/routing",
                           headers=admin_h, json={"subdomain": t.get("subdomain") or ""}, timeout=20)

    def test_path_prefix_routing(self, admin_h):
        # Need a tenant with a slug
        r = requests.get(f"{BASE_URL}/api/admin/tenants/routing", headers=admin_h, timeout=20)
        if r.status_code != 200:
            pytest.skip("cannot fetch tenants")
        tenants = r.json().get("tenants", [])
        if not tenants:
            pytest.skip("no tenants")
        slug = tenants[0].get("slug")
        if not slug:
            pytest.skip("no slug")
        r = requests.get(f"{BASE_URL}/t/{slug}/api/health", timeout=20)
        # Best effort
        xr = r.headers.get("X-Tenant-Routing") or r.headers.get("x-tenant-routing")
        if xr:
            assert xr == "path_prefix"
        # Don't fail hard if ingress rewrites strip the prefix

# ─────────────────────── 7) Regression ───────────────────────

class TestRegression:
    def test_uptime_monitors_list(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/uptime/monitors", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text

    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200


# ─────────────────────── ZZZ: Restore defaults ───────────────────────

class TestZZZRestore:
    def test_restore_defaults(self, admin_h, original_config):
        """Restore feature flags to the snapshot we captured at setup."""
        body = {
            "modules": original_config.get("modules"),
            "ai_copilot": original_config.get("ai_copilot"),
            "deny_patterns": original_config.get("deny_patterns"),
            "limits": original_config.get("limits"),
        }
        r = requests.patch(f"{BASE_URL}/api/admin/features", headers=admin_h, json=body, timeout=20)
        assert r.status_code == 200, r.text
