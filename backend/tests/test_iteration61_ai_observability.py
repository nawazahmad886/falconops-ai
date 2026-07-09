"""
Phase 35: AI Observability v2 — Backend test suite.
Covers: health, evaluate (PII + healthy), policies CRUD + role check,
agent drilldown, timeseries, quarantine listing/lifecycle.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://health-rules-engine.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"
VIEWER_EMAIL = "test@falconapps.com"
VIEWER_PASSWORD = "testpass123"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def viewer_token():
    return _login(VIEWER_EMAIL, VIEWER_PASSWORD)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


# ---------- HEALTH ----------
class TestAIObsHealth:
    def test_health_returns_10_agents_and_extras(self, admin_headers):
        r = requests.get(f"{API}/ai-monitoring/health", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        agents = body.get("agents") or body.get("agent_list") or []
        # agents may be a list of dicts or list of ids — normalize
        agent_ids = []
        if isinstance(agents, list) and agents and isinstance(agents[0], dict):
            agent_ids = [a.get("id") or a.get("name") for a in agents]
        elif isinstance(agents, dict):
            agent_ids = list(agents.keys())
        else:
            agent_ids = list(agents)
        expected = {"hallucination", "injection", "cost", "performance", "quality",
                    "root_cause", "pii_leak", "toxicity", "policy", "drift"}
        missing = expected - set(agent_ids)
        assert not missing, f"missing agents: {missing}; got {agent_ids}"
        # Extra fields
        for k in ("active_policies", "pending_quarantine", "live_subscribers"):
            assert k in body, f"missing field {k} in health body: {list(body.keys())}"


# ---------- EVALUATE ----------
class TestAIObsEvaluate:
    def test_evaluate_pii_triggers_critical(self, admin_headers):
        payload = {
            "ai_output": "SSN 123-45-6789, card 4111 1111 1111 1111, email john@example.com, AKIAIOSFODNN7EXAMPLE",
            "user_input": "Please help",
            "skip_llm_agents": True,
        }
        r = requests.post(f"{API}/ai-monitoring/evaluate", json=payload, headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        verdict = body.get("verdict") or body
        assert verdict.get("system_status") == "critical", f"verdict={verdict}"
        # find pii_leak agent flagged
        agents = body.get("agents") or verdict.get("agents") or []
        pii = None
        if isinstance(agents, list):
            for a in agents:
                if (a.get("agent") or a.get("id") or a.get("name")) == "pii_leak":
                    pii = a
                    break
        elif isinstance(agents, dict):
            pii = agents.get("pii_leak")
        assert pii is not None, f"pii_leak agent not present in response: {agents}"
        assert pii.get("leak_detected") is True or pii.get("severity") == "high", f"pii_leak not flagged: {pii}"
        assert pii.get("severity") == "high"

    def test_evaluate_clean_output_healthy(self, admin_headers):
        payload = {
            "ai_output": "The weather is nice today. Have a great day!",
            "user_input": "How are you?",
            "skip_llm_agents": True,
        }
        r = requests.post(f"{API}/ai-monitoring/evaluate", json=payload, headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        verdict = body.get("verdict") or body
        assert verdict.get("system_status") == "healthy", f"verdict={verdict}"


# ---------- POLICIES ----------
class TestAIObsPolicies:
    created_id = None

    def test_create_policy_admin(self, admin_headers):
        payload = {
            "name": "TEST_policy_iter61",
            "rule": "block_when_contains:secret",
            "severity": "high",
            "enabled": True,
            "tags": ["test", "iter61"],
        }
        r = requests.post(f"{API}/ai-monitoring/policies", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code in (200, 201), r.text
        doc = r.json()
        assert "id" in doc
        assert doc["name"] == payload["name"]
        assert "created_at" in doc
        assert "created_by" in doc
        TestAIObsPolicies.created_id = doc["id"]

    def test_list_policies_contains_created(self, admin_headers):
        r = requests.get(f"{API}/ai-monitoring/policies", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("policies") or []
        ids = [it.get("id") for it in items]
        assert TestAIObsPolicies.created_id in ids, f"created policy missing in list: {ids}"

    def test_update_policy_admin(self, admin_headers):
        pid = TestAIObsPolicies.created_id
        assert pid, "no created policy id"
        r = requests.put(
            f"{API}/ai-monitoring/policies/{pid}",
            json={"name": "TEST_policy_iter61_updated", "rule": "block_when_contains:secret",
                  "severity": "high", "enabled": True, "tags": ["test", "iter61"]},
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["name"] == "TEST_policy_iter61_updated"
        assert doc["severity"] == "high"

    def test_viewer_cannot_create_policy(self, viewer_headers):
        r = requests.post(
            f"{API}/ai-monitoring/policies",
            json={"name": "TEST_viewer_denied", "rule": "block_when_contains:foo", "severity": "low", "enabled": True, "tags": []},
            headers=viewer_headers, timeout=30,
        )
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"

    def test_delete_policy_admin(self, admin_headers):
        pid = TestAIObsPolicies.created_id
        assert pid, "no created policy id"
        r = requests.delete(f"{API}/ai-monitoring/policies/{pid}", headers=admin_headers, timeout=30)
        assert r.status_code in (200, 204), r.text
        # verify gone
        r2 = requests.get(f"{API}/ai-monitoring/policies", headers=admin_headers, timeout=30)
        items = r2.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("policies") or []
        ids = [it.get("id") for it in items]
        assert pid not in ids


# ---------- AGENT DRILLDOWN ----------
class TestAIObsAgentDrilldown:
    def test_pii_leak_drilldown(self, admin_headers):
        r = requests.get(f"{API}/ai-monitoring/agents/pii_leak?hours=24&limit=5", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("total_evaluations", "flagged_count", "flagged_rate", "severity_mix", "recent_flagged"):
            assert k in body, f"missing {k}: {list(body.keys())}"
        assert isinstance(body["recent_flagged"], list)

    def test_unknown_agent_404(self, admin_headers):
        r = requests.get(f"{API}/ai-monitoring/agents/not_a_real_agent_xyz", headers=admin_headers, timeout=30)
        assert r.status_code == 404, f"expected 404 got {r.status_code}: {r.text}"


# ---------- TIMESERIES ----------
class TestAIObsTimeseries:
    def test_timeseries_returns_points(self, admin_headers):
        r = requests.get(f"{API}/ai-monitoring/timeseries?hours=24&bucket_minutes=15", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        points = body.get("points") if isinstance(body, dict) else body
        assert isinstance(points, list), f"points not a list: {body}"
        if points:
            p = points[0]
            for k in ("ts", "events", "tokens", "cost_usd", "avg_latency_ms", "critical", "warning", "healthy"):
                assert k in p, f"missing key {k} in point: {p}"


# ---------- QUARANTINE LIFECYCLE ----------
class TestAIObsQuarantine:
    event_id_pending = None
    event_id_release = None
    event_id_block = None

    def _make_event(self, headers):
        payload = {
            "ai_output": "SSN 555-44-3333 leaked TEST",
            "user_input": "diag",
            "skip_llm_agents": True,
        }
        r = requests.post(f"{API}/ai-monitoring/evaluate", json=payload, headers=headers, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        eid = body.get("event_id") or body.get("id") or (body.get("verdict") or {}).get("event_id")
        assert eid, f"no event_id in evaluate response: {list(body.keys())}"
        return eid

    def test_quarantine_create_pending(self, admin_headers):
        eid = self._make_event(admin_headers)
        TestAIObsQuarantine.event_id_pending = eid
        r = requests.post(f"{API}/ai-monitoring/quarantine/{eid}", headers=admin_headers, timeout=30,
                          json={"reason": "test"})
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body.get("status") == "pending", f"status not pending: {body}"

    def test_list_pending(self, admin_headers):
        r = requests.get(f"{API}/ai-monitoring/quarantine?status=pending", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("quarantine") or []
        assert isinstance(items, list)
        # The previously-quarantined event should be present
        eids = [it.get("event_id") or it.get("id") for it in items]
        assert TestAIObsQuarantine.event_id_pending in eids or len(items) >= 1

    def test_release_quarantine(self, admin_headers):
        eid = self._make_event(admin_headers)
        TestAIObsQuarantine.event_id_release = eid
        # quarantine first
        r0 = requests.post(f"{API}/ai-monitoring/quarantine/{eid}", headers=admin_headers, timeout=30,
                           json={"reason": "to release"})
        assert r0.status_code in (200, 201), r0.text
        # release
        r = requests.post(f"{API}/ai-monitoring/quarantine/{eid}/release", headers=admin_headers, timeout=30)
        assert r.status_code in (200, 201), r.text
        assert r.json().get("status") == "released"

    def test_block_quarantine(self, admin_headers):
        eid = self._make_event(admin_headers)
        TestAIObsQuarantine.event_id_block = eid
        r0 = requests.post(f"{API}/ai-monitoring/quarantine/{eid}", headers=admin_headers, timeout=30,
                           json={"reason": "to block"})
        assert r0.status_code in (200, 201), r0.text
        r = requests.post(f"{API}/ai-monitoring/quarantine/{eid}/block", headers=admin_headers, timeout=30)
        assert r.status_code in (200, 201), r.text
        assert r.json().get("status") == "blocked"
