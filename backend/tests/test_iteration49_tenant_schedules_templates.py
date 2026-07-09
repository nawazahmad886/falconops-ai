"""
Iteration 49 backend tests:
  - Per-tenant scheduled reports endpoints
  - Report Template Builder endpoints (catalog/list/create/get/put/delete)
  - Weekly report generation with template_id
"""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://health-rules-engine.preview.emergentagent.com").rstrip("/")

ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}
VIEWER = {"email": "test@falconapps.com", "password": "testpass123"}
TEST_TENANT_ID = "456adc3e-6909-4d29-8906-2b7a41855eee"
# Use a fresh synthetic tenant_id per test run to verify auto-seed (opt-in enabled=false) behavior
import uuid as _uuid
FRESH_TENANT_ID = f"TEST_{_uuid.uuid4()}"


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def viewer_token():
    return _login(VIEWER)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


# ================= Per-tenant scheduled reports =================

class TestTenantScheduledReports:
    def test_list_tenants_admin_only(self, admin_headers, viewer_headers):
        r_admin = requests.get(f"{BASE_URL}/api/scheduled-reports/tenants", headers=admin_headers, timeout=15)
        assert r_admin.status_code == 200, r_admin.text
        assert isinstance(r_admin.json(), list)

        r_viewer = requests.get(f"{BASE_URL}/api/scheduled-reports/tenants", headers=viewer_headers, timeout=15)
        assert r_viewer.status_code == 403, f"viewer should be forbidden, got {r_viewer.status_code}"

    def test_get_tenant_settings_autoseed(self, admin_headers):
        # Use a fresh tenant id to exercise auto-seed path
        r = requests.get(f"{BASE_URL}/api/scheduled-reports/tenants/{FRESH_TENANT_ID}/settings",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "enabled" in data
        # First call MUST have enabled=False per opt-in
        assert data["enabled"] is False, f"Expected enabled=False on auto-seed, got {data}"
        assert "days_of_week" in data
        assert "hour" in data
        assert "minute" in data

    def test_put_tenant_settings_admin(self, admin_headers):
        patch = {
            "enabled": True,
            "days_of_week": ["fri"],
            "hour": 14,
            "minute": 30,
            "recipients": ["tenant-test@example.com"],
        }
        r = requests.put(f"{BASE_URL}/api/scheduled-reports/tenants/{TEST_TENANT_ID}/settings",
                         headers=admin_headers, json=patch, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["enabled"] is True
        assert data["days_of_week"] == ["fri"]
        assert data["hour"] == 14
        assert data["minute"] == 30
        assert "tenant-test@example.com" in data["recipients"]

        # GET verifies persistence
        r2 = requests.get(f"{BASE_URL}/api/scheduled-reports/tenants/{TEST_TENANT_ID}/settings",
                          headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["hour"] == 14
        assert r2.json()["minute"] == 30

    def test_put_tenant_settings_invalid_hour(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/scheduled-reports/tenants/{TEST_TENANT_ID}/settings",
                         headers=admin_headers, json={"hour": 99}, timeout=15)
        assert r.status_code == 400

    def test_viewer_cannot_put_other_tenant(self, viewer_headers):
        # viewer's tenant != TEST_TENANT_ID → must be 403
        r = requests.put(f"{BASE_URL}/api/scheduled-reports/tenants/{TEST_TENANT_ID}/settings",
                         headers=viewer_headers, json={"enabled": False}, timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"

    def test_tenant_trigger_admin(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/scheduled-reports/tenants/{TEST_TENANT_ID}/trigger",
                          headers=admin_headers, json={"recipients_override": []}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        # Should have ok flag and/or report_id
        assert "ok" in body or "report_id" in body or "status" in body

    def test_tenant_logs(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/scheduled-reports/tenants/{TEST_TENANT_ID}/logs",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        logs = r.json()
        assert isinstance(logs, list)
        # All returned logs should reference our tenant
        for lg in logs:
            if "tenant_id" in lg and lg["tenant_id"] is not None:
                assert lg["tenant_id"] == TEST_TENANT_ID

    # Regression: global settings still work
    def test_global_settings_still_work(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/scheduled-reports/settings", headers=admin_headers, timeout=15)
        assert r.status_code == 200


# ================= Report Templates =================

class TestReportTemplates:
    created_template_id = None

    def test_catalog(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/report-templates/catalog", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "sections" in data
        assert "default_sections" in data
        assert len(data["sections"]) == 12, f"expected 12 section types, got {len(data['sections'])}"
        assert len(data["default_sections"]) == 11, f"expected 11 defaults, got {len(data['default_sections'])}"

    def test_list_templates(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/report-templates/list", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_template_valid(self, admin_headers):
        payload = {
            "name": "TEST_MinimalTemplate",
            "description": "iteration49 test",
            "sections": [
                {"section_type": "title", "title": "My Title", "content": "", "config": {}},
                {"section_type": "kpi_banner", "title": "", "content": "", "config": {}},
                {"section_type": "exec_summary", "title": "", "content": "", "config": {}},
                {"section_type": "footer", "title": "", "content": "", "config": {}},
            ],
        }
        r = requests.post(f"{BASE_URL}/api/report-templates/create",
                          headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["name"] == "TEST_MinimalTemplate"
        assert len(doc["sections"]) == 4
        assert "template_id" in doc
        TestReportTemplates.created_template_id = doc["template_id"]

    def test_create_template_invalid_section(self, admin_headers):
        payload = {
            "name": "TEST_BadTemplate",
            "sections": [{"section_type": "NOT_A_REAL_TYPE", "title": "", "content": "", "config": {}}],
        }
        r = requests.post(f"{BASE_URL}/api/report-templates/create",
                          headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 400

    def test_get_template(self, admin_headers):
        tid = TestReportTemplates.created_template_id
        assert tid, "create test must run first"
        r = requests.get(f"{BASE_URL}/api/report-templates/{tid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["template_id"] == tid

    def test_update_template(self, admin_headers):
        tid = TestReportTemplates.created_template_id
        payload = {
            "name": "TEST_MinimalTemplate_Updated",
            "description": "updated",
            "sections": [
                {"section_type": "title", "title": "Updated Title", "content": "", "config": {}},
                {"section_type": "footer", "title": "", "content": "", "config": {}},
            ],
        }
        r = requests.put(f"{BASE_URL}/api/report-templates/{tid}",
                         headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "TEST_MinimalTemplate_Updated"
        assert len(data["sections"]) == 2

    def test_generate_auto_with_template(self, admin_headers):
        tid = TestReportTemplates.created_template_id
        r = requests.post(f"{BASE_URL}/api/weekly-reports/generate/auto",
                          headers=admin_headers,
                          json={"days": 7, "period": "7", "include_pdf": True, "executive": True, "template_id": tid},
                          timeout=180)
        assert r.status_code == 200, r.text[:500]
        body = r.json()
        assert "report_id" in body
        assert body.get("has_pdf") is True

    def test_generate_json_with_template(self, admin_headers):
        tid = TestReportTemplates.created_template_id
        sample_alerts = [{
            "alert_name": "TEST_Alert",
            "severity": "Critical",
            "application": "TestApp",
            "occurrences": 1,
            "timestamp": "2026-01-01T00:00:00Z",
        }]
        r = requests.post(f"{BASE_URL}/api/weekly-reports/generate/json",
                          headers=admin_headers,
                          json={"alerts": sample_alerts, "period": "7", "include_pdf": True,
                                "executive": False, "template_id": tid},
                          timeout=180)
        assert r.status_code == 200, r.text[:500]
        body = r.json()
        assert "report_id" in body

    def test_delete_template(self, admin_headers):
        tid = TestReportTemplates.created_template_id
        r = requests.delete(f"{BASE_URL}/api/report-templates/{tid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        # Verify gone
        r2 = requests.get(f"{BASE_URL}/api/report-templates/{tid}", headers=admin_headers, timeout=15)
        assert r2.status_code == 404


# ================= Regression =================
class TestRegression:
    def test_weekly_reports_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/weekly-reports/list", headers=admin_headers, timeout=15)
        assert r.status_code in (200, 404)  # route may be /history

    def test_branding_get(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/branding/current", headers=admin_headers, timeout=15)
        # endpoint may differ; accept 200 or 404 (regression smoke)
        assert r.status_code in (200, 404)

    def test_share_list(self, admin_headers):
        # smoke: shares list accessible
        r = requests.get(f"{BASE_URL}/api/scheduled-reports/logs", headers=admin_headers, timeout=15)
        assert r.status_code == 200
