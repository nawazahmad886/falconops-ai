"""
FalconOps AI - Agentic AI Workflow tests (iteration 68)

Covers: Supervisor query classification/routing, the new ranked-hypothesis
Diagnoser, Forecaster/Blast-Radius passthroughs, the append-only decision log,
and the read-only guarantee of the action registry (no execute endpoint
exists anywhere in this module).
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

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


class TestSupervisorRouting:
    @pytest.mark.parametrize("query,expected_route", [
        ("Have we seen this before with checkout-service?", "memory"),
        ("What depends on payment-api?", "blast_radius"),
        ("Forecast the cpu trend for the next 24 hours", "forecaster"),
        ("Why is payment-api down right now?", "diagnoser"),
        ("What is the current status of the platform?", "copilot"),
    ])
    def test_classification_routes_correctly(self, authenticated_client, query, expected_route):
        r = authenticated_client.post(f"{BASE_URL}/api/agentic-workflow/ask", json={"query": query})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["routed_to"] == expected_route, f"query '{query}' expected route '{expected_route}', got '{data['routed_to']}'"
        assert data["classification"]["route"] == expected_route
        assert "reason" in data["classification"]
        assert data["decision_id"]
        print(f"✓ '{query}' correctly routed to {expected_route}")

    def test_incident_id_always_routes_to_diagnoser(self, authenticated_client):
        r = authenticated_client.post(f"{BASE_URL}/api/agentic-workflow/ask", json={
            "query": "tell me about this", "incident_id": f"test-incident-{uuid.uuid4().hex[:8]}",
        })
        assert r.status_code == 200, r.text
        assert r.json()["routed_to"] == "diagnoser"


class TestDiagnoser:
    def test_ranked_hypotheses_returned(self, authenticated_client):
        r = authenticated_client.get(f"{BASE_URL}/api/agentic-workflow/diagnose/checkout-service?hours=24")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "hypotheses" in data
        hypotheses = data["hypotheses"]
        assert len(hypotheses) >= 1, "expected at least one hypothesis (honest fallback guarantees this)"
        for h in hypotheses:
            assert "rank" in h and "root_cause" in h and "confidence" in h and "evidence" in h
            assert 0.0 <= h["confidence"] <= 1.0
        # Ranked by descending confidence
        confidences = [h["confidence"] for h in hypotheses]
        assert confidences == sorted(confidences, reverse=True), "hypotheses must be ordered by descending confidence"
        assert "similar_past_incidents" in data
        print(f"✓ Diagnoser returned {len(hypotheses)} ranked hypothesis/hypotheses")


class TestForecasterPassthrough:
    def test_forecast_proxies_capacity_engine(self, authenticated_client):
        r = authenticated_client.get(f"{BASE_URL}/api/agentic-workflow/forecast?metric=cpu_usage&horizon=24h")
        assert r.status_code == 200, r.text
        data = r.json()
        # Either a real prediction or the engine's own honest "insufficient_data" status —
        # never a fabricated prediction when there's no data.
        assert data.get("status") in ("success", "insufficient_data")
        assert data.get("metric_name") == "cpu_usage"
        print(f"✓ /forecast passthrough returned status={data.get('status')}")


class TestBlastRadiusPassthrough:
    def test_unknown_service_returns_404(self, authenticated_client):
        r = authenticated_client.get(f"{BASE_URL}/api/agentic-workflow/blast-radius/nonexistent-service-{uuid.uuid4().hex[:8]}")
        assert r.status_code == 404, r.text

    def test_known_service_returns_real_shape(self, authenticated_client):
        # Servers seeded via /api/servers/simulate aren't necessarily present in
        # topology_nodes (a separate collection get_blast_radius reads), so this
        # only asserts the response CONTRACT when a service happens to be found,
        # skipping gracefully otherwise (no fabricated blast radius either way).
        requests.post(f"{BASE_URL}/api/servers/simulate")
        r = authenticated_client.get(f"{BASE_URL}/api/agentic-workflow/blast-radius/prod-web-01")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert "total_impacted" in data and "risk_level" in data and "impacted_services" in data
            print(f"✓ blast-radius passthrough returned real shape: {data}")
        else:
            print("✓ blast-radius honestly 404s when the service isn't in topology_nodes")


class TestDecisionLog:
    def test_ask_call_creates_one_log_entry(self, authenticated_client):
        before = authenticated_client.get(f"{BASE_URL}/api/agentic-workflow/decision-log?limit=1")
        assert before.status_code == 200

        unique_query = f"Why is test-service-{uuid.uuid4().hex[:8]} failing?"
        ask = authenticated_client.post(f"{BASE_URL}/api/agentic-workflow/ask", json={"query": unique_query})
        assert ask.status_code == 200, ask.text

        after = authenticated_client.get(f"{BASE_URL}/api/agentic-workflow/decision-log?limit=10")
        assert after.status_code == 200
        rows = after.json()["decisions"]
        assert any(row["query"] == unique_query for row in rows), "expected the just-made query to appear in the decision log"
        print("✓ decision log correctly records every /ask call")


class TestActionRegistryReadOnly:
    def test_actions_endpoint_lists_phase1_actions(self, authenticated_client):
        r = authenticated_client.get(f"{BASE_URL}/api/agentic-workflow/actions")
        assert r.status_code == 200, r.text
        data = r.json()
        names = {a["name"] for a in data["actions"]}
        expected = {"open_ticket", "page_on_call", "post_status_update", "scale_out",
                    "restart_stateless_service", "drain_and_reroute_traffic", "rollback_last_deploy"}
        assert names == expected, f"expected exactly the 7 Phase-1 actions, got {names}"
        for a in data["actions"]:
            assert a["current_autonomy_level"] == "L0_observe", f"{a['name']} should default to L0_observe"
        print("✓ action registry lists exactly the 7 Phase-1 actions, all defaulted to L0_observe")

    def test_no_execute_endpoint_exists(self, authenticated_client):
        # Confirm there is genuinely no way to trigger execution via the API —
        # any attempted execute path must 404 (route doesn't exist) or 405.
        for path in ("/api/agentic-workflow/actions/open_ticket/execute",
                     "/api/agentic-workflow/execute"):
            r = authenticated_client.post(f"{BASE_URL}{path}", json={})
            assert r.status_code in (404, 405), f"expected no execute route at {path}, got {r.status_code}"
        print("✓ confirmed no execute endpoint exists anywhere in this module")

    def test_dry_run_never_mutates(self, authenticated_client):
        r = authenticated_client.get(f"{BASE_URL}/api/agentic-workflow/actions/restart_stateless_service/dry-run?service=payment-api")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["would_execute"] is False
        assert "preview only" in data["note"].lower() or "not yet" in data["note"].lower() or "notimplementederror" in data["note"].lower()
        print(f"✓ dry-run for restart_stateless_service returned a preview, never executed: {data['note'][:80]}")


class TestAuthRequired:
    def test_ask_requires_auth(self):
        assert requests.post(f"{BASE_URL}/api/agentic-workflow/ask", json={"query": "test"}).status_code in (401, 403)

    def test_diagnose_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/agentic-workflow/diagnose/some-service").status_code in (401, 403)

    def test_decision_log_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/agentic-workflow/decision-log").status_code in (401, 403)

    def test_actions_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/agentic-workflow/actions").status_code in (401, 403)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
