"""
Iteration 57 — Phase 24: Payment + Contact + Admin Monetization tests
Covers:
  Public: GET /api/pricing/plans, POST /api/contact (incl. validation)
  Admin: CRUD /api/admin/plans, /api/admin/email-templates, /api/admin/leads
  Billing: GET /api/billing/plans (DB-backed), POST /api/billing/checkout (free/enterprise reject + Stripe session)
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


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def viewer_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": VIEWER_EMAIL, "password": VIEWER_PASS})
    if r.status_code != 200:
        pytest.skip("viewer login failed")
    return r.json().get("access_token")


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ============ PUBLIC ============
class TestPricingPublic:
    def test_pricing_plans_returns_seeded_plans(self, api):
        r = api.get(f"{BASE_URL}/api/pricing/plans")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "plans" in data and "count" in data
        plans = data["plans"]
        ids = {p["id"] for p in plans}
        # The 4 seeded plans must all be present and active
        for pid in ("trial", "standard", "professional", "enterprise"):
            assert pid in ids, f"missing seeded plan {pid} in {ids}"
        # validate field shape on professional plan
        pro = next(p for p in plans if p["id"] == "professional")
        assert pro["highlight"] is True
        assert pro["price"] == 799.0
        assert isinstance(pro["features"], list) and len(pro["features"]) >= 3


class TestContactPublic:
    def test_contact_submit_creates_lead(self, api):
        payload = {
            "name": "TEST_Lead Iter57",
            "email": "test_iter57_lead@example.com",
            "company": "TEST Corp",
            "phone": "+1-555-0100",
            "team_size": "10-50",
            "message": "Testing the contact form from pytest iteration 57.",
            "plan_id": "enterprise",
        }
        r = api.post(f"{BASE_URL}/api/contact", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "lead_id" in data
        assert "sales_email_sent" in data
        assert "confirmation_email_sent" in data
        assert data["lead"]["status"] == "new"
        assert data["lead"]["name"] == payload["name"]

    def test_contact_invalid_email_returns_422(self, api):
        r = api.post(f"{BASE_URL}/api/contact", json={
            "name": "Bad", "email": "not-an-email", "message": "hi"
        })
        assert r.status_code == 422

    def test_contact_missing_required_fields_returns_422(self, api):
        r = api.post(f"{BASE_URL}/api/contact", json={"email": "x@y.com"})
        assert r.status_code == 422


# ============ ADMIN — auth checks ============
class TestAdminAuth:
    def test_admin_plans_requires_auth(self, api):
        r = api.get(f"{BASE_URL}/api/admin/plans")
        assert r.status_code in (401, 403)

    def test_admin_plans_forbidden_for_viewer(self, api, viewer_token):
        r = api.get(f"{BASE_URL}/api/admin/plans", headers=H(viewer_token))
        assert r.status_code in (401, 403), f"viewer should not access admin plans: {r.status_code}"


# ============ ADMIN — Plans CRUD ============
class TestAdminPlans:
    def test_list_plans(self, api, admin_token):
        r = api.get(f"{BASE_URL}/api/admin/plans", headers=H(admin_token))
        assert r.status_code == 200
        assert "plans" in r.json()

    def test_plan_create_update_delete(self, api, admin_token):
        pid = f"TEST_plan_{uuid.uuid4().hex[:8]}"
        body = {
            "id": pid, "name": "TEST Plan", "tagline": "pytest", "price": 100.0,
            "currency": "USD", "billing_type": "subscription", "interval": "month",
            "features": ["a", "b"], "button_text": "Buy", "is_active": True, "sort_order": 99,
        }
        # Create
        r = api.post(f"{BASE_URL}/api/admin/plans", json=body, headers=H(admin_token))
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["id"] == pid
        assert created["price"] == 100.0
        # Duplicate -> 409
        r2 = api.post(f"{BASE_URL}/api/admin/plans", json=body, headers=H(admin_token))
        assert r2.status_code == 409
        # Update
        body["price"] = 150.0
        body["features"] = ["a", "b", "c"]
        r3 = api.put(f"{BASE_URL}/api/admin/plans/{pid}", json=body, headers=H(admin_token))
        assert r3.status_code == 200
        assert r3.json()["price"] == 150.0
        assert len(r3.json()["features"]) == 3
        # Update non-existent -> 404
        r4 = api.put(f"{BASE_URL}/api/admin/plans/__nope__{uuid.uuid4().hex[:6]}", json=body, headers=H(admin_token))
        assert r4.status_code == 404
        # Delete
        r5 = api.delete(f"{BASE_URL}/api/admin/plans/{pid}", headers=H(admin_token))
        assert r5.status_code == 200 and r5.json()["deleted"] is True
        # Delete non-existent -> 404
        r6 = api.delete(f"{BASE_URL}/api/admin/plans/{pid}", headers=H(admin_token))
        assert r6.status_code == 404


# ============ ADMIN — Email Templates ============
class TestAdminEmailTemplates:
    def test_list_templates_returns_seeded(self, api, admin_token):
        r = api.get(f"{BASE_URL}/api/admin/email-templates", headers=H(admin_token))
        assert r.status_code == 200
        templates = r.json()["templates"]
        names = {t["name"] for t in templates}
        for n in ("contact_sales", "contact_confirmation", "welcome", "alert"):
            assert n in names, f"missing seeded template {n}"

    def test_template_crud(self, api, admin_token):
        tid = f"TEST_tmpl_{uuid.uuid4().hex[:8]}"
        body = {
            "id": tid, "name": tid, "subject": "Hi {{name}}",
            "body_html": "<p>Hello {{name}}</p>", "body_text": "Hello {{name}}",
            "variables": ["name"], "is_active": True,
        }
        r = api.post(f"{BASE_URL}/api/admin/email-templates", json=body, headers=H(admin_token))
        assert r.status_code == 200, r.text
        body["subject"] = "Updated {{name}}"
        r2 = api.put(f"{BASE_URL}/api/admin/email-templates/{tid}", json=body, headers=H(admin_token))
        assert r2.status_code == 200
        assert r2.json()["subject"] == "Updated {{name}}"
        r3 = api.delete(f"{BASE_URL}/api/admin/email-templates/{tid}", headers=H(admin_token))
        assert r3.status_code == 200
        r4 = api.delete(f"{BASE_URL}/api/admin/email-templates/{tid}", headers=H(admin_token))
        assert r4.status_code == 404

    def test_send_test_email_returns_200_or_500(self, api, admin_token):
        # Resend may be sandboxed; per spec accept 200 or 500
        body = {"recipient": "test_iter57@example.com", "variables": {"name": "TestUser", "message": "hi"}}
        r = api.post(
            f"{BASE_URL}/api/admin/email-templates/contact_confirmation/send-test",
            json=body, headers=H(admin_token),
        )
        assert r.status_code in (200, 500), f"unexpected status {r.status_code}: {r.text}"


# ============ ADMIN — Leads ============
class TestAdminLeads:
    def test_leads_list_and_filter(self, api, admin_token):
        r = api.get(f"{BASE_URL}/api/admin/leads", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "leads" in data
        # At least the lead from TestContactPublic should be there (status=new)
        r2 = api.get(f"{BASE_URL}/api/admin/leads?status=new", headers=H(admin_token))
        assert r2.status_code == 200
        for lead in r2.json()["leads"]:
            assert lead["status"] == "new"

    def test_lead_update_and_delete(self, api, admin_token):
        # Create a lead via public contact endpoint
        cp = api.post(f"{BASE_URL}/api/contact", json={
            "name": "TEST_LeadCRUD", "email": "test_leadcrud@example.com",
            "message": "crud test", "plan_id": "professional",
        })
        assert cp.status_code == 200
        lead_id = cp.json()["lead_id"]
        # Update
        r = api.put(f"{BASE_URL}/api/admin/leads/{lead_id}",
                    json={"status": "contacted", "notes": "called", "assigned_to": "admin"},
                    headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["status"] == "contacted"
        assert r.json()["notes"] == "called"
        # Update non-existent
        r2 = api.put(f"{BASE_URL}/api/admin/leads/__nope__{uuid.uuid4().hex[:6]}",
                     json={"status": "won"}, headers=H(admin_token))
        assert r2.status_code == 404
        # Delete
        r3 = api.delete(f"{BASE_URL}/api/admin/leads/{lead_id}", headers=H(admin_token))
        assert r3.status_code == 200
        r4 = api.delete(f"{BASE_URL}/api/admin/leads/{lead_id}", headers=H(admin_token))
        assert r4.status_code == 404


# ============ BILLING ============
class TestBilling:
    def test_billing_plans_db_backed(self, api, admin_token):
        r = api.get(f"{BASE_URL}/api/billing/plans", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        ids = {p.get("id") for p in data}
        # Once DB plans are seeded, DB ids (trial/standard/etc.) should appear
        assert ids & {"trial", "standard", "professional", "enterprise", "free", "pro"}

    def test_checkout_rejects_enterprise(self, api, admin_token):
        r = api.post(f"{BASE_URL}/api/billing/checkout",
                     json={"plan_id": "enterprise", "origin_url": "https://example.com"},
                     headers=H(admin_token))
        assert r.status_code == 400
        # error message references enterprise OR free
        detail = (r.json().get("detail") or "").lower()
        assert "enterprise" in detail or "contact" in detail or "free" in detail

    def test_checkout_rejects_free_trial(self, api, admin_token):
        r = api.post(f"{BASE_URL}/api/billing/checkout",
                     json={"plan_id": "trial", "origin_url": "https://example.com"},
                     headers=H(admin_token))
        assert r.status_code == 400

    def test_checkout_creates_stripe_session_for_paid(self, api, admin_token):
        r = api.post(f"{BASE_URL}/api/billing/checkout",
                     json={"plan_id": "standard", "origin_url": "https://example.com"},
                     headers=H(admin_token))
        # Stripe may legitimately error; accept 200 with checkout URL OR 500 if Stripe sandbox is down
        assert r.status_code in (200, 500), f"unexpected: {r.status_code} {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert "url" in data
            assert data["url"].startswith("https://checkout.stripe.com/"), f"unexpected url: {data['url']}"
            assert "session_id" in data
