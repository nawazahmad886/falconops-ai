"""
FalconOps AI - Enterprise Knowledge Graph tests (iteration 69)

Covers: the new governance fields mutation (owner/business_criticality/
incident_response_target_minutes/business_service) on db.topology_nodes via
resource_explorer_service, the thin-wrapper /api/knowledge-graph/entity/{id}
read (reuses resource_explorer_service.get_resource(), adds runbooks +
similar_past_incidents), and the business-services rollup aggregation.
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


@pytest.fixture(scope="module")
def sample_resource_id(authenticated_client):
    """Seed a demo server, force a bridge sync (bypassing the 60s scheduler tick),
    then grab any resulting resource's id. Skips gracefully if nothing bridges —
    this mirrors test_iteration68's approach for the same underlying seed data."""
    requests.post(f"{BASE_URL}/api/servers/simulate")
    sync = authenticated_client.post(f"{BASE_URL}/api/resources/sync")
    if sync.status_code != 200:
        pytest.skip(f"resource sync failed: {sync.status_code} - {sync.text}")

    listing = authenticated_client.get(f"{BASE_URL}/api/resources?limit=1")
    if listing.status_code != 200 or not listing.json().get("resources"):
        pytest.skip("no resources available in topology_nodes after sync")
    return listing.json()["resources"][0]["id"]


class TestGovernanceMutation:
    def test_round_trips_all_four_fields(self, authenticated_client, sample_resource_id):
        unique_owner = f"team-{uuid.uuid4().hex[:8]}@company.com"
        body = {
            "owner": unique_owner,
            "business_criticality": "high",
            "incident_response_target_minutes": 30,
            "business_service": f"TestService-{uuid.uuid4().hex[:6]}",
        }
        r = authenticated_client.put(f"{BASE_URL}/api/resources/{sample_resource_id}/governance", json=body)
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["owner"] == unique_owner
        assert updated["business_criticality"] == "high"
        assert updated["incident_response_target_minutes"] == 30
        assert updated["business_service"] == body["business_service"]
        print(f"✓ governance PUT round-tripped all 4 fields for resource {sample_resource_id}")

    def test_invalid_criticality_rejected(self, authenticated_client, sample_resource_id):
        r = authenticated_client.put(
            f"{BASE_URL}/api/resources/{sample_resource_id}/governance",
            json={"business_criticality": "not_a_real_level"},
        )
        assert r.status_code == 400, r.text
        print("✓ invalid business_criticality rejected with 400")

    def test_unknown_resource_404s(self, authenticated_client):
        r = authenticated_client.put(
            f"{BASE_URL}/api/resources/nonexistent-{uuid.uuid4().hex[:8]}/governance",
            json={"owner": "someone"},
        )
        assert r.status_code == 404

    def test_requires_write_access(self, sample_resource_id):
        r = requests.put(f"{BASE_URL}/api/resources/{sample_resource_id}/governance", json={"owner": "x"})
        assert r.status_code in (401, 403)


class TestEntityGraph:
    def test_reuses_resource_explorer_shape(self, authenticated_client, sample_resource_id):
        """The entity graph must never diverge from what GET /api/resources/{id}
        already computes for risk/related_problems — it's a thin wrapper, not a
        second independent composition."""
        resource_resp = authenticated_client.get(f"{BASE_URL}/api/resources/{sample_resource_id}")
        assert resource_resp.status_code == 200, resource_resp.text
        base = resource_resp.json()

        graph_resp = authenticated_client.get(f"{BASE_URL}/api/knowledge-graph/entity/{sample_resource_id}")
        assert graph_resp.status_code == 200, graph_resp.text
        graph = graph_resp.json()

        assert graph["enrichment"].get("risk") == base["enrichment"].get("risk")
        assert graph["enrichment"].get("related_problems") == base["enrichment"].get("related_problems")
        assert "runbooks" in graph
        assert "similar_past_incidents" in graph
        assert "legacy_service_topology" in graph
        print("✓ entity graph reuses resource_explorer_service's composition exactly, adds runbooks/similar_past_incidents")

    def test_unknown_entity_404s(self, authenticated_client):
        r = authenticated_client.get(f"{BASE_URL}/api/knowledge-graph/entity/nonexistent-{uuid.uuid4().hex[:8]}")
        assert r.status_code == 404

    def test_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/knowledge-graph/entity/some-id").status_code in (401, 403)


class TestBusinessServicesRollup:
    def test_rollup_reflects_governance_updates(self, authenticated_client, sample_resource_id):
        unique_service = f"RollupTest-{uuid.uuid4().hex[:8]}"
        put = authenticated_client.put(
            f"{BASE_URL}/api/resources/{sample_resource_id}/governance",
            json={"business_service": unique_service},
        )
        assert put.status_code == 200, put.text

        r = authenticated_client.get(f"{BASE_URL}/api/knowledge-graph/business-services")
        assert r.status_code == 200, r.text
        data = r.json()
        names = {row["business_service"] for row in data["business_services"]}
        assert unique_service in names, f"expected '{unique_service}' in rollup, got {names}"
        row = next(row for row in data["business_services"] if row["business_service"] == unique_service)
        assert row["node_count"] >= 1
        assert row["worst_status"] in ("healthy", "degraded", "critical", "unknown")
        print(f"✓ business-services rollup reflects the just-set business_service '{unique_service}'")

    def test_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/knowledge-graph/business-services").status_code in (401, 403)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
