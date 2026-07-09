"""
Test Alert & Respond API Endpoints
- GET /api/alert-respond/policies - list policies
- POST /api/alert-respond/policies - create policy
- DELETE /api/alert-respond/policies/{id} - delete policy
- GET /api/alert-respond/violations - list violations
- POST /api/alert-respond/violations - create test violation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope='module')
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@falconapps.com", "password": "Admin@123"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get('access_token')


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with authentication"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestAlertRespondPolicies:
    """Test Policies CRUD endpoints"""

    def test_list_policies(self, auth_headers):
        """Test GET /api/alert-respond/policies"""
        response = requests.get(
            f"{BASE_URL}/api/alert-respond/policies",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "policies" in data
        assert isinstance(data["policies"], list)
        print(f"Found {len(data['policies'])} policies")

    def test_create_policy(self, auth_headers):
        """Test POST /api/alert-respond/policies"""
        payload = {
            "name": "TEST_Critical_Alert_Policy",
            "description": "Alert when critical health rule is violated",
            "trigger_type": "health_rule",
            "trigger_rules": [],
            "action_type": "alert",
            "action_config": {"channels": ["email", "slack"]},
            "enabled": True
        }
        response = requests.post(
            f"{BASE_URL}/api/alert-respond/policies",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["name"] == payload["name"]
        assert data["enabled"] == True
        print(f"Created policy with id: {data['id']}")
        return data["id"]

    def test_delete_policy(self, auth_headers):
        """Test DELETE /api/alert-respond/policies/{id}"""
        # First create a policy
        payload = {
            "name": "TEST_Policy_To_Delete",
            "description": "Will be deleted",
            "trigger_type": "health_rule",
            "action_type": "email",
            "enabled": False
        }
        create_res = requests.post(
            f"{BASE_URL}/api/alert-respond/policies",
            json=payload,
            headers=auth_headers
        )
        assert create_res.status_code == 200
        policy_id = create_res.json()["id"]
        
        # Delete the policy
        delete_res = requests.delete(
            f"{BASE_URL}/api/alert-respond/policies/{policy_id}",
            headers=auth_headers
        )
        assert delete_res.status_code == 200, f"Delete failed: {delete_res.text}"
        data = delete_res.json()
        assert data["deleted"] == True
        print(f"Deleted policy: {policy_id}")

    def test_delete_nonexistent_policy_returns_404(self, auth_headers):
        """Test DELETE returns 404 for non-existent policy"""
        response = requests.delete(
            f"{BASE_URL}/api/alert-respond/policies/nonexistent-id-12345",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestAlertRespondViolations:
    """Test Violations endpoints"""

    def test_list_violations(self, auth_headers):
        """Test GET /api/alert-respond/violations"""
        response = requests.get(
            f"{BASE_URL}/api/alert-respond/violations",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "violations" in data
        assert "total" in data
        assert isinstance(data["violations"], list)
        print(f"Found {data['total']} violations")

    def test_list_violations_with_limit(self, auth_headers):
        """Test GET /api/alert-respond/violations with limit param"""
        response = requests.get(
            f"{BASE_URL}/api/alert-respond/violations?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["violations"]) <= 10

    def test_list_violations_with_severity_filter(self, auth_headers):
        """Test GET /api/alert-respond/violations with severity filter"""
        response = requests.get(
            f"{BASE_URL}/api/alert-respond/violations?severity=critical",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # All returned violations should be critical (if any)
        for v in data["violations"]:
            assert v.get("severity") == "critical"

    def test_create_test_violation(self, auth_headers):
        """Test POST /api/alert-respond/violations (demo endpoint)"""
        response = requests.post(
            f"{BASE_URL}/api/alert-respond/violations",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["rule_name"] == "Demo Health Rule Violation"
        assert data["severity"] == "critical"
        assert data["state"] == "active"
        print(f"Created test violation: {data['id']}")


class TestAlertRespondAuth:
    """Test authentication requirements"""

    def test_policies_requires_auth(self):
        """Test that policies endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/alert-respond/policies")
        assert response.status_code == 401 or response.status_code == 403

    def test_violations_requires_auth(self):
        """Test that violations endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/alert-respond/violations")
        assert response.status_code == 401 or response.status_code == 403


# Cleanup fixture
@pytest.fixture(scope='module', autouse=True)
def cleanup_test_data(auth_token):
    """Cleanup TEST_ prefixed policies after all tests"""
    yield
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    # Get all policies
    res = requests.get(f"{BASE_URL}/api/alert-respond/policies", headers=headers)
    if res.status_code == 200:
        policies = res.json().get("policies", [])
        for p in policies:
            if p.get("name", "").startswith("TEST_"):
                requests.delete(
                    f"{BASE_URL}/api/alert-respond/policies/{p['id']}",
                    headers=headers
                )
                print(f"Cleaned up test policy: {p['name']}")
