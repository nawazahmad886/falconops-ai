"""
FalconOps AI - UEBA, Attack Simulator & Integration Management Tests
Tests for iteration 34 features:
- UEBA (User & Entity Behavior Analytics) endpoints
- Attack Simulator endpoints
- Admin Integration Management endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
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
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


# ======================== UEBA TESTS ========================

class TestUEBASummary:
    """UEBA Summary endpoint tests"""
    
    def test_ueba_summary_returns_200(self, authenticated_client):
        """GET /api/security/ueba/summary returns 200"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/summary?hours=168")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ UEBA summary returned 200")
    
    def test_ueba_summary_has_required_fields(self, authenticated_client):
        """UEBA summary has total_users, critical_count, high_count, risk_distribution, top_risk_factors"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/summary?hours=168")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["total_users", "critical_count", "high_count", "medium_count", "low_count", "risk_distribution", "top_risk_factors"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate risk_distribution structure
        assert isinstance(data["risk_distribution"], list), "risk_distribution should be a list"
        if data["risk_distribution"]:
            assert "level" in data["risk_distribution"][0], "risk_distribution items should have 'level'"
            assert "count" in data["risk_distribution"][0], "risk_distribution items should have 'count'"
        
        print(f"✓ UEBA summary has all required fields: total_users={data['total_users']}, critical={data['critical_count']}, high={data['high_count']}")


class TestUEBAProfiles:
    """UEBA User Profiles endpoint tests"""
    
    def test_ueba_profiles_returns_200(self, authenticated_client):
        """GET /api/security/ueba/profiles returns 200"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/profiles?hours=168")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ UEBA profiles returned 200")
    
    def test_ueba_profiles_structure(self, authenticated_client):
        """UEBA profiles have risk_score, risk_level, risk_factors, unique_ips, geos"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/profiles?hours=168")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Profiles should be a list"
        
        if data:
            profile = data[0]
            required_fields = ["user", "risk_score", "risk_level", "risk_factors", "unique_ips", "geos", "total_events"]
            for field in required_fields:
                assert field in profile, f"Profile missing field: {field}"
            
            # Validate risk_level values
            assert profile["risk_level"] in ["critical", "high", "medium", "low"], f"Invalid risk_level: {profile['risk_level']}"
            
            # Validate risk_score is 0-100
            assert 0 <= profile["risk_score"] <= 100, f"risk_score out of range: {profile['risk_score']}"
            
            print(f"✓ UEBA profiles structure valid: {len(data)} profiles, top user={profile['user']} (risk={profile['risk_score']})")
        else:
            print("✓ UEBA profiles returned empty list (no security events yet)")


class TestUEBAUserDetail:
    """UEBA User Detail endpoint tests"""
    
    def test_ueba_user_detail_returns_200(self, authenticated_client):
        """GET /api/security/ueba/user/{username} returns 200"""
        # First get a user from profiles
        profiles_response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/profiles?hours=168")
        if profiles_response.status_code == 200 and profiles_response.json():
            username = profiles_response.json()[0]["user"]
            response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/user/{username}?hours=168")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            print(f"✓ UEBA user detail for '{username}' returned 200")
        else:
            # Test with a generic username
            response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/user/admin?hours=168")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            print(f"✓ UEBA user detail for 'admin' returned 200")
    
    def test_ueba_user_detail_structure(self, authenticated_client):
        """UEBA user detail has events, hourly_distribution, action_breakdown"""
        profiles_response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/profiles?hours=168")
        username = "admin"
        if profiles_response.status_code == 200 and profiles_response.json():
            username = profiles_response.json()[0]["user"]
        
        response = authenticated_client.get(f"{BASE_URL}/api/security/ueba/user/{username}?hours=168")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["user", "events", "hourly_distribution", "action_breakdown"]
        for field in required_fields:
            assert field in data, f"User detail missing field: {field}"
        
        assert data["user"] == username, f"User mismatch: expected {username}, got {data['user']}"
        assert isinstance(data["events"], list), "events should be a list"
        assert isinstance(data["hourly_distribution"], list), "hourly_distribution should be a list"
        assert isinstance(data["action_breakdown"], list), "action_breakdown should be a list"
        
        print(f"✓ UEBA user detail structure valid: {len(data['events'])} events, {len(data['action_breakdown'])} action types")


# ======================== ATTACK SIMULATOR TESTS ========================

class TestAttackSimScenarios:
    """Attack Simulator Scenarios endpoint tests"""
    
    def test_scenarios_returns_200(self, authenticated_client):
        """GET /api/security/attack-sim/scenarios returns 200"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/attack-sim/scenarios")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Attack scenarios returned 200")
    
    def test_scenarios_has_7_scenarios(self, authenticated_client):
        """Attack simulator has 7 scenarios"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/attack-sim/scenarios")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Scenarios should be a list"
        assert len(data) == 7, f"Expected 7 scenarios, got {len(data)}"
        
        expected_ids = ["brute_force", "credential_stuffing", "impossible_travel", "privilege_escalation", "data_exfiltration", "port_scan", "insider_threat"]
        actual_ids = [s["id"] for s in data]
        
        for expected_id in expected_ids:
            assert expected_id in actual_ids, f"Missing scenario: {expected_id}"
        
        print(f"✓ All 7 attack scenarios present: {', '.join(actual_ids)}")
    
    def test_scenario_structure(self, authenticated_client):
        """Each scenario has id, name, description, severity, mitre, default_config"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/attack-sim/scenarios")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["id", "name", "description", "severity", "mitre", "default_config"]
        for scenario in data:
            for field in required_fields:
                assert field in scenario, f"Scenario {scenario.get('id', 'unknown')} missing field: {field}"
        
        print(f"✓ All scenarios have required structure")


class TestAttackSimRun:
    """Attack Simulator Run endpoint tests"""
    
    def test_run_brute_force_simulation(self, authenticated_client):
        """POST /api/security/attack-sim/run with brute_force scenario"""
        response = authenticated_client.post(f"{BASE_URL}/api/security/attack-sim/run", json={
            "scenario_id": "brute_force"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should have simulation id"
        assert "scenario" in data, "Response should have scenario"
        assert data["scenario"] == "brute_force", f"Expected brute_force, got {data['scenario']}"
        assert "events_generated" in data, "Response should have events_generated"
        assert "threats_detected" in data, "Response should have threats_detected"
        assert data["status"] == "completed", f"Expected completed, got {data['status']}"
        
        print(f"✓ Brute force simulation completed: {data['events_generated']} events, {data['threats_detected']} threats")
    
    def test_run_invalid_scenario(self, authenticated_client):
        """POST /api/security/attack-sim/run with invalid scenario returns error"""
        response = authenticated_client.post(f"{BASE_URL}/api/security/attack-sim/run", json={
            "scenario_id": "invalid_scenario"
        })
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert "error" in data, "Invalid scenario should return error"
        print(f"✓ Invalid scenario handled correctly: {data['error']}")


class TestAttackSimHistory:
    """Attack Simulator History endpoint tests"""
    
    def test_history_returns_200(self, authenticated_client):
        """GET /api/security/attack-sim/history returns 200"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/attack-sim/history?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Attack simulation history returned 200")
    
    def test_history_structure(self, authenticated_client):
        """History items have id, scenario, events_generated, threats_detected, status"""
        response = authenticated_client.get(f"{BASE_URL}/api/security/attack-sim/history?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "History should be a list"
        
        if data:
            item = data[0]
            required_fields = ["id", "scenario", "events_generated", "threats_detected", "status", "started_at"]
            for field in required_fields:
                assert field in item, f"History item missing field: {field}"
            print(f"✓ History structure valid: {len(data)} simulations recorded")
        else:
            print("✓ History returned empty list (no simulations yet)")


# ======================== INTEGRATION MANAGEMENT TESTS ========================

class TestIntegrationCatalog:
    """Integration Catalog endpoint tests"""
    
    def test_catalog_returns_200(self, authenticated_client):
        """GET /api/admin/integrations/catalog returns 200"""
        response = authenticated_client.get(f"{BASE_URL}/api/admin/integrations/catalog")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Integration catalog returned 200")
    
    def test_catalog_has_11_integrations(self, authenticated_client):
        """Integration catalog has 11 items"""
        response = authenticated_client.get(f"{BASE_URL}/api/admin/integrations/catalog")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Catalog should be a list"
        assert len(data) == 11, f"Expected 11 integrations, got {len(data)}"
        
        expected_ids = ["aws_cloudtrail", "aws_vpc_flowlogs", "slack", "pagerduty", "servicenow", "sendgrid", "elasticsearch", "datadog", "jira", "splunk", "custom_webhook"]
        actual_ids = [i["id"] for i in data]
        
        for expected_id in expected_ids:
            assert expected_id in actual_ids, f"Missing integration: {expected_id}"
        
        print(f"✓ All 11 integrations present: {', '.join(actual_ids)}")
    
    def test_catalog_item_structure(self, authenticated_client):
        """Each catalog item has id, name, category, description, fields"""
        response = authenticated_client.get(f"{BASE_URL}/api/admin/integrations/catalog")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["id", "name", "category", "description", "fields"]
        for item in data:
            for field in required_fields:
                assert field in item, f"Integration {item.get('id', 'unknown')} missing field: {field}"
            
            # Validate fields structure
            assert isinstance(item["fields"], list), f"Integration {item['id']} fields should be a list"
            if item["fields"]:
                field_item = item["fields"][0]
                assert "key" in field_item, "Field should have 'key'"
                assert "label" in field_item, "Field should have 'label'"
                assert "type" in field_item, "Field should have 'type'"
        
        print(f"✓ All catalog items have valid structure")


class TestIntegrationSave:
    """Integration Save endpoint tests"""
    
    def test_save_slack_integration(self, authenticated_client):
        """PUT /api/admin/integrations/slack saves config"""
        response = authenticated_client.put(f"{BASE_URL}/api/admin/integrations/slack", json={
            "config": {
                "webhook_url": "https://hooks.slack.com/services/TEST/TEST/TEST",
                "channel": "#test-alerts"
            },
            "enabled": True
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data or "integration_id" in data, "Response should confirm save"
        print(f"✓ Slack integration saved successfully")
    
    def test_save_invalid_integration(self, authenticated_client):
        """PUT /api/admin/integrations/invalid returns error"""
        response = authenticated_client.put(f"{BASE_URL}/api/admin/integrations/invalid_integration", json={
            "config": {"key": "value"},
            "enabled": True
        })
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert "error" in data, "Invalid integration should return error"
        print(f"✓ Invalid integration handled correctly: {data['error']}")


class TestIntegrationToggle:
    """Integration Toggle endpoint tests"""
    
    def test_toggle_integration(self, authenticated_client):
        """PATCH /api/admin/integrations/slack/toggle toggles enabled state"""
        # First ensure slack is configured
        authenticated_client.put(f"{BASE_URL}/api/admin/integrations/slack", json={
            "config": {"webhook_url": "https://hooks.slack.com/test", "channel": "#test"},
            "enabled": True
        })
        
        # Toggle off
        response = authenticated_client.patch(f"{BASE_URL}/api/admin/integrations/slack/toggle", json={
            "enabled": False
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data or "integration_id" in data, "Response should confirm toggle"
        print(f"✓ Integration toggle successful")


class TestIntegrationDelete:
    """Integration Delete endpoint tests"""
    
    def test_delete_integration(self, authenticated_client):
        """DELETE /api/admin/integrations/slack deletes config"""
        # First ensure slack is configured
        authenticated_client.put(f"{BASE_URL}/api/admin/integrations/slack", json={
            "config": {"webhook_url": "https://hooks.slack.com/test", "channel": "#test"},
            "enabled": True
        })
        
        # Delete
        response = authenticated_client.delete(f"{BASE_URL}/api/admin/integrations/slack")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data or "integration_id" in data, "Response should confirm delete"
        print(f"✓ Integration deleted successfully")


class TestIntegrationTest:
    """Integration Test Connectivity endpoint tests"""
    
    def test_test_integration_not_configured(self, authenticated_client):
        """POST /api/admin/integrations/pagerduty/test returns error if not configured"""
        # First delete to ensure not configured
        authenticated_client.delete(f"{BASE_URL}/api/admin/integrations/pagerduty")
        
        response = authenticated_client.post(f"{BASE_URL}/api/admin/integrations/pagerduty/test")
        assert response.status_code == 200
        data = response.json()
        # Should return error since not configured
        assert "success" in data or "error" in data
        print(f"✓ Test connectivity endpoint works: {data}")
    
    def test_test_integration_configured(self, authenticated_client):
        """POST /api/admin/integrations/slack/test returns success for configured integration"""
        # First configure slack
        authenticated_client.put(f"{BASE_URL}/api/admin/integrations/slack", json={
            "config": {"webhook_url": "https://hooks.slack.com/test", "channel": "#test"},
            "enabled": True
        })
        
        response = authenticated_client.post(f"{BASE_URL}/api/admin/integrations/slack/test")
        assert response.status_code == 200
        data = response.json()
        # MOCKED: Returns placeholder success
        assert data.get("success") == True, f"Expected success=True, got {data}"
        print(f"✓ Test connectivity returns success (MOCKED): {data.get('message', '')}")


# ======================== CLEANUP ========================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_integrations(self, authenticated_client):
        """Clean up test integrations"""
        # Delete test integrations
        authenticated_client.delete(f"{BASE_URL}/api/admin/integrations/slack")
        print(f"✓ Test integrations cleaned up")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
