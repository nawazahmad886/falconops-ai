"""
FalconOps AI - Connector SDK Tests (iteration 64)

Covers: the connector registry/catalog surface, secret encryption at rest
(round-trip through the existing masking UX), an honest unhealthy result for
a misconfigured/unsafe Prometheus target (no fabricated success), the removed
AWS simulate-data fallback (fetch endpoints now return [] rather than fake
events when unconfigured), AI-context auto-registration into the existing
AI tool-calling surface, and a regression check that non-SDK integrations
(e.g. Slack) are unaffected.
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
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestConnectorRegistry:
    """GET /api/connectors — every registered connector's identity/capabilities/status"""

    def test_list_connectors_returns_200(self, authenticated_client):
        response = authenticated_client.get(f"{BASE_URL}/api/connectors")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/connectors returned 200")

    def test_prometheus_registered_with_expected_capabilities(self, authenticated_client):
        response = authenticated_client.get(f"{BASE_URL}/api/connectors")
        assert response.status_code == 200
        connectors = {c["id"]: c for c in response.json().get("connectors", [])}
        assert "prometheus" in connectors, f"prometheus not in registry: {list(connectors.keys())}"
        caps = connectors["prometheus"]["capabilities"]
        assert "metrics" in caps, f"Missing 'metrics' capability: {caps}"
        assert "ai_context" in caps, f"Missing 'ai_context' capability: {caps}"
        print(f"✓ prometheus registered with capabilities: {caps}")

    def test_aws_connectors_registered(self, authenticated_client):
        response = authenticated_client.get(f"{BASE_URL}/api/connectors")
        assert response.status_code == 200
        connectors = {c["id"]: c for c in response.json().get("connectors", [])}
        for cid in ("aws_cloudtrail", "aws_vpc_flowlogs"):
            assert cid in connectors, f"{cid} not in registry: {list(connectors.keys())}"
            assert "events" in connectors[cid]["capabilities"]
        print("✓ AWS connectors registered with 'events' capability")


class TestCatalogAdditiveFields:
    """The 11 pre-existing catalog entries must be unaffected; prometheus is additive."""

    def test_catalog_still_has_original_entries_plus_prometheus(self, authenticated_client):
        response = authenticated_client.get(f"{BASE_URL}/api/admin/integrations/catalog")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        catalog = response.json()
        ids = {item["id"] for item in catalog}
        original_ids = {
            "aws_cloudtrail", "aws_vpc_flowlogs", "slack", "pagerduty", "servicenow",
            "sendgrid", "elasticsearch", "datadog", "jira", "splunk", "custom_webhook",
        }
        assert original_ids.issubset(ids), f"Missing original catalog entries: {original_ids - ids}"
        assert "prometheus" in ids, "prometheus missing from catalog"
        print(f"✓ catalog has all {len(original_ids)} original entries plus prometheus ({len(catalog)} total)")


class TestEncryptionRoundTrip:
    """Secrets must never appear in plaintext in an API response, before or after encryption."""

    def test_prometheus_bearer_token_masked_on_read(self, authenticated_client):
        secret = f"test-secret-{uuid.uuid4().hex}"
        save_resp = authenticated_client.put(f"{BASE_URL}/api/admin/integrations/prometheus", json={
            "config": {
                "prometheus_url": "http://localhost:9090",
                "bearer_token": secret,
                "default_queries": "up",
            },
            "enabled": False,
        })
        assert save_resp.status_code == 200, f"Expected 200, got {save_resp.status_code}: {save_resp.text}"

        get_resp = authenticated_client.get(f"{BASE_URL}/api/admin/integrations/prometheus")
        assert get_resp.status_code == 200
        data = get_resp.json()
        stored_token = data.get("config", {}).get("bearer_token", "")
        assert secret not in stored_token, "raw secret value leaked in GET response"
        assert "****" in stored_token, f"expected masked value, got: {stored_token!r}"
        print("✓ prometheus bearer_token round-trips masked, raw value never exposed")


class TestPrometheusConnectorHonestUnhealthy:
    """No fabricated success — an unreachable/unsafe target must report unhealthy."""

    def test_private_target_refused_by_ssrf_guard(self, authenticated_client):
        save_resp = authenticated_client.put(f"{BASE_URL}/api/admin/integrations/prometheus", json={
            "config": {"prometheus_url": "http://10.255.255.1:9999", "default_queries": "up"},
            "enabled": True,
        })
        assert save_resp.status_code == 200, save_resp.text

        test_resp = authenticated_client.post(f"{BASE_URL}/api/connectors/prometheus/test")
        assert test_resp.status_code == 200, f"Expected 200, got {test_resp.status_code}: {test_resp.text}"
        result = test_resp.json()
        assert result.get("success") is False, f"Expected success=False for a private target, got: {result}"
        print(f"✓ private prometheus_url correctly reported unhealthy: {result.get('message')}")


class TestAWSNoFakeData:
    """Regression test for the removed _simulate_events()/_simulate_logs() fallback."""

    def test_cloudtrail_events_empty_when_unconfigured(self, authenticated_client):
        # Disable (not delete) so we don't disturb any real config an operator may have set.
        authenticated_client.patch(
            f"{BASE_URL}/api/admin/integrations/aws_cloudtrail/toggle", json={"enabled": False}
        )
        response = authenticated_client.get(f"{BASE_URL}/api/aws/events/cloudtrail?limit=20")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        events = response.json()
        assert events == [], f"Expected [] (no simulated fallback data), got {len(events)} events"
        print("✓ GET /api/aws/events/cloudtrail returns [] instead of simulated data")

    def test_vpc_flow_events_empty_when_unconfigured(self, authenticated_client):
        authenticated_client.patch(
            f"{BASE_URL}/api/admin/integrations/aws_vpc_flowlogs/toggle", json={"enabled": False}
        )
        response = authenticated_client.get(f"{BASE_URL}/api/aws/events/vpc?limit=20")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.json() == [], "Expected [] (no simulated fallback data)"
        print("✓ GET /api/aws/events/vpc returns [] instead of simulated data")

    def test_fetch_reports_zero_not_fabricated_count(self, authenticated_client):
        response = authenticated_client.post(f"{BASE_URL}/api/aws/fetch")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        result = response.json()
        assert result.get("cloudtrail", -1) == 0
        assert result.get("vpc_flow", -1) == 0
        print("✓ POST /api/aws/fetch reports 0/0 rather than a fabricated count")


class TestAIToolAutoRegistration:
    """Connector-sourced AI-context tools must appear in the existing AI tool registry."""

    def test_connector_prometheus_context_listed(self, authenticated_client):
        response = authenticated_client.get(f"{BASE_URL}/api/ai-intelligence/tools")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        tool_names = {t["name"] for t in response.json().get("tools", [])}
        assert "connector_prometheus_context" in tool_names, f"Missing tool: {tool_names}"
        print("✓ connector_prometheus_context listed in GET /api/ai-intelligence/tools")

    def test_connector_prometheus_context_executes(self, authenticated_client):
        response = authenticated_client.post(
            f"{BASE_URL}/api/ai-intelligence/tools/connector_prometheus_context/execute",
            json={"params": {"minutes": 5}},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        for field in ("tool", "data", "summary"):
            assert field in data, f"Missing field in tool envelope: {field}"
        print(f"✓ connector_prometheus_context executed: {data.get('summary')}")


class TestExistingIntegrationsUnaffected:
    """Non-SDK integrations must keep working exactly as before this change."""

    def test_slack_save_and_read_unaffected(self, authenticated_client):
        save_resp = authenticated_client.put(f"{BASE_URL}/api/admin/integrations/slack", json={
            "config": {"webhook_url": "https://hooks.slack.com/services/T00/B00/XXXX", "channel": "#alerts"},
            "enabled": False,
        })
        assert save_resp.status_code == 200, f"Expected 200, got {save_resp.status_code}: {save_resp.text}"

        get_resp = authenticated_client.get(f"{BASE_URL}/api/admin/integrations/slack")
        assert get_resp.status_code == 200
        assert get_resp.json().get("config", {}).get("channel") == "#alerts"
        print("✓ slack integration save/read unaffected by the Connector SDK")


class TestAuthRequired:
    """Unauthenticated requests to the new Connector SDK routes must be rejected."""

    def test_list_connectors_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/connectors")
        assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"

    def test_test_connector_requires_auth(self):
        response = requests.post(f"{BASE_URL}/api/connectors/prometheus/test")
        assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"

    def test_poll_connector_requires_auth(self):
        response = requests.post(f"{BASE_URL}/api/connectors/prometheus/poll")
        assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"

    def test_recommendations_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/connectors/prometheus/recommendations")
        assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
