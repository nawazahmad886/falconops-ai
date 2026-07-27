"""
FalconOps AI - Problems console tests (iteration 65)

Covers: federation correctness across db.alerts_engine + db.soc_events, assign
routing to the correct source collection, suppress filtering, statistics
honesty (no fabricated mttd/availability fields), WS live broadcast, and
auth requirements on every new endpoint.
"""
import os
import time
import uuid
import requests
import pytest
from websockets.sync.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
WS_BASE_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


def _seed_alert_and_get_id(authenticated_client) -> str:
    """seed_alerts only returns a count, not the created alert's id, so fetch
    the most-recently-touched alerts_engine row right after seeding. Sorts by
    last_occurrence (not created_at) since create_alert() dedups on matching
    entity_id+metric_name — a repeat seed can bump an existing row's
    last_occurrence instead of inserting a new one, leaving created_at stale."""
    r = authenticated_client.post(f"{BASE_URL}/api/seed/alerts?count=1")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    listing = authenticated_client.get(
        f"{BASE_URL}/api/alert-engine?limit=1&sort_by=last_occurrence&sort_order=desc"
    )
    assert listing.status_code == 200, listing.text
    alerts = listing.json()["alerts"]
    assert alerts, "no alerts_engine row found right after seeding"
    return alerts[0]["id"]


def _ingest_unique_soc_event(severity="high"):
    """A unique service name keeps this event below correlate_event()'s
    count-threshold, so it stays correlated=False and appears as its own
    singleton se: Problem rather than being absorbed into a soc_incident."""
    service = f"test-svc-{uuid.uuid4().hex[:10]}"
    r = requests.post(f"{BASE_URL}/api/soc-engine/ingest", json={
        "source": "test", "service": service, "severity": severity,
        "message": f"test event {uuid.uuid4().hex[:8]}",
    })
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    return r.json(), service


class TestFederationCorrectness:
    def test_seeded_alert_appears_as_ae_problem(self, authenticated_client):
        _seed_alert_and_get_id(authenticated_client)
        r = authenticated_client.get(f"{BASE_URL}/api/problems?source=alert_engine&limit=50")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        problems = r.json()["problems"]
        assert any(p["id"].startswith("ae:") for p in problems), "no alert_engine-sourced problem found"
        ae_problem = next(p for p in problems if p["id"].startswith("ae:"))
        assert ae_problem["severity"] in ("critical", "high", "medium", "low", "info")
        assert ae_problem["status"] in ("open", "acknowledged", "resolved", "closed")
        print(f"✓ alerts_engine row appears as {ae_problem['id']} with mapped severity/status")

    def test_soc_event_appears_as_se_problem(self, authenticated_client):
        ingested, service = _ingest_unique_soc_event(severity="high")
        r = authenticated_client.get(f"{BASE_URL}/api/problems?source=soc_event&service={service}")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        problems = r.json()["problems"]
        assert len(problems) == 1, f"expected exactly 1 se: problem for {service}, got {problems}"
        se_problem = problems[0]
        assert se_problem["id"] == f"se:{ingested['event_id']}"
        assert se_problem["severity"] == "high"
        assert se_problem["status"] == "open"
        print(f"✓ soc_events row appears as {se_problem['id']} with correctly mapped severity/status")


class TestAssignRouting:
    def test_assign_alert_engine_problem_lands_on_correct_collection(self, authenticated_client):
        alert_id = _seed_alert_and_get_id(authenticated_client)
        problem_id = f"ae:{alert_id}"

        r = authenticated_client.post(f"{BASE_URL}/api/problems/{problem_id}/assign", json={
            "assigned_to": "alice@example.com", "assignment_group": "SRE",
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["assigned_to"] == "alice@example.com"

        direct = authenticated_client.get(f"{BASE_URL}/api/alert-engine/{alert_id}")
        assert direct.status_code == 200, direct.text
        assert direct.json()["assigned_to"] == "alice@example.com"
        assert direct.json()["assignment_group"] == "SRE"
        print(f"✓ assign on {problem_id} landed on db.alerts_engine, not cross-contaminated")

    def test_assign_soc_event_problem(self, authenticated_client):
        ingested, service = _ingest_unique_soc_event(severity="medium")
        problem_id = f"se:{ingested['event_id']}"
        r = authenticated_client.post(f"{BASE_URL}/api/problems/{problem_id}/assign", json={
            "assigned_to": "bob@example.com",
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["assigned_to"] == "bob@example.com"
        print(f"✓ assign on {problem_id} (soc_event) succeeded")


class TestLifecycleActions:
    def test_acknowledge_then_resolve_soc_event(self, authenticated_client):
        ingested, service = _ingest_unique_soc_event(severity="low")
        problem_id = f"se:{ingested['event_id']}"

        ack = authenticated_client.post(f"{BASE_URL}/api/problems/{problem_id}/acknowledge")
        assert ack.status_code == 200, ack.text
        assert ack.json()["status"] == "acknowledged"

        res = authenticated_client.post(f"{BASE_URL}/api/problems/{problem_id}/resolve", json={"notes": "fixed"})
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "resolved"
        print(f"✓ {problem_id} transitioned open -> acknowledged -> resolved")

    def test_escalate_only_supported_for_alert_engine(self, authenticated_client):
        ingested, service = _ingest_unique_soc_event(severity="info")
        problem_id = f"se:{ingested['event_id']}"
        r = authenticated_client.post(f"{BASE_URL}/api/problems/{problem_id}/escalate")
        assert r.status_code == 409, f"Expected 409 for non-alert escalate, got {r.status_code}: {r.text}"
        print("✓ escalate on a non-ae: problem correctly rejected with 409, not a fake success")


class TestSuppressFiltering:
    def test_suppressed_problem_hidden_by_default(self, authenticated_client):
        ingested, service = _ingest_unique_soc_event(severity="critical")
        problem_id = f"se:{ingested['event_id']}"

        sup = authenticated_client.post(f"{BASE_URL}/api/problems/{problem_id}/suppress", json={"reason": "test suppression"})
        assert sup.status_code == 200, sup.text

        default_view = authenticated_client.get(f"{BASE_URL}/api/problems?source=soc_event&service={service}")
        assert default_view.status_code == 200
        assert not any(p["id"] == problem_id for p in default_view.json()["problems"]), "suppressed problem visible by default"

        with_suppressed = authenticated_client.get(
            f"{BASE_URL}/api/problems?source=soc_event&service={service}&include_suppressed=true"
        )
        assert with_suppressed.status_code == 200
        assert any(p["id"] == problem_id for p in with_suppressed.json()["problems"]), "suppressed problem missing even with include_suppressed=true"
        print(f"✓ {problem_id} hidden by default, visible with include_suppressed=true")

        authenticated_client.post(f"{BASE_URL}/api/problems/{problem_id}/unsuppress")


class TestStatisticsHonesty:
    def test_statistics_omits_fabricated_fields(self, authenticated_client):
        r = authenticated_client.get(f"{BASE_URL}/api/problems/statistics")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        for field in ("total", "by_status", "by_severity", "resolved_today", "ai_correlated_count", "sla_computed_over"):
            assert field in data, f"missing real field: {field}"
        assert "mttd_minutes" not in data, "mttd_minutes should be omitted, not fabricated"
        assert "availability_pct" not in data, "availability_pct should be omitted, not fabricated"
        print("✓ statistics response has no fabricated mttd_minutes/availability_pct fields")


class TestWSBroadcast:
    def test_problem_created_event_pushed_live(self, auth_token):
        with ws_connect(f"{WS_BASE_URL}/api/problems/live?token={auth_token}") as ws:
            requests.post(f"{BASE_URL}/api/soc-engine/ingest", json={
                "source": "test", "service": f"ws-test-{uuid.uuid4().hex[:8]}",
                "severity": "high", "message": "ws broadcast test",
            })
            deadline = time.time() + 10
            found = False
            while time.time() < deadline:
                try:
                    raw = ws.recv(timeout=max(0.1, deadline - time.time()))
                except (TimeoutError, ConnectionClosed):
                    break
                import json
                msg = json.loads(raw)
                if msg.get("type") == "problem.created" and msg.get("source") == "soc_event":
                    found = True
                    break
            assert found, "expected a problem.created broadcast for the new soc_event"
            print("✓ /api/problems/live pushed a problem.created event")


class TestAuthRequired:
    def test_list_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/problems").status_code in (401, 403)

    def test_statistics_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/problems/statistics").status_code in (401, 403)

    def test_timeline_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/problems/timeline").status_code in (401, 403)

    def test_search_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/problems/search?q=test").status_code in (401, 403)

    def test_detail_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/problems/ae:nonexistent").status_code in (401, 403)

    def test_assign_requires_auth(self):
        assert requests.post(f"{BASE_URL}/api/problems/ae:nonexistent/assign", json={}).status_code in (401, 403)

    def test_export_requires_auth(self):
        assert requests.post(f"{BASE_URL}/api/problems/export").status_code in (401, 403)

    def test_live_requires_token(self):
        with ws_connect(f"{WS_BASE_URL}/api/problems/live") as ws:
            import json
            msg = json.loads(ws.recv(timeout=10))
            assert msg.get("type") == "error"
            assert "token" in msg.get("error", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
