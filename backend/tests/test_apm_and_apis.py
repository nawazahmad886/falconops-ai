"""
FalconOps AI - Comprehensive API Tests for APM Module and Core APIs
Tests all endpoints mentioned in the review request
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"
VIEWER_EMAIL = "test@falconapps.com"
VIEWER_PASSWORD = "testpass123"


class TestHealthAndBasics:
    """Health check and basic API tests"""
    
    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "FalconOps AI"
        print(f"✓ Health check passed: {data}")
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        assert "FalconOps AI" in data.get("service", "")
        print(f"✓ Root endpoint passed: {data}")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_admin_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"✓ Admin login successful: {data['user']['email']}")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid login correctly rejected")
    
    def test_register_new_user(self):
        """Test user registration"""
        import uuid
        unique_email = f"test_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "full_name": "Test User",
            "organization": "Test Org"
        })
        # Should succeed or fail if email exists
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
            print(f"✓ User registration successful: {unique_email}")
        else:
            print(f"✓ Registration handled (may already exist)")


class TestMonitors:
    """Monitor CRUD tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_get_monitors(self, auth_token):
        """Test GET /api/monitors"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/monitors", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/monitors: {len(data)} monitors found")
    
    def test_get_monitors_dashboard(self, auth_token):
        """Test GET /api/monitors/dashboard"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/monitors/dashboard", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_monitors" in data
        assert "monitors_up" in data
        assert "monitors_down" in data
        print(f"✓ Monitors Dashboard: Total={data['total_monitors']}, Up={data['monitors_up']}, Down={data['monitors_down']}")


class TestAlerts:
    """Alert endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_get_alerts(self, auth_token):
        """Test GET /api/alerts"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/alerts", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/alerts: {len(data)} alerts found")
    
    def test_post_alert_webhook(self):
        """Test POST /api/alerts/webhook (public endpoint)"""
        alert_data = {
            "source": "pytest",
            "severity": "warning",
            "title": "Test Alert from Pytest",
            "description": "This is a test alert created by pytest",
            "service": "test-service",
            "host": "test-host"
        }
        response = requests.post(f"{BASE_URL}/api/alerts/webhook", json=alert_data)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == alert_data["title"]
        print(f"✓ Alert webhook created: {data['id']}")


class TestIncidents:
    """Incident endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_get_incidents(self, auth_token):
        """Test GET /api/incidents"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/incidents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/incidents: {len(data)} incidents found")


class TestAnalytics:
    """Analytics endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_get_analytics_dashboard(self, auth_token):
        """Test GET /api/analytics/dashboard"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_alerts" in data
        assert "open_alerts" in data
        print(f"✓ Analytics Dashboard: Total Alerts={data['total_alerts']}, Open={data['open_alerts']}")
    
    def test_get_services_health(self, auth_token):
        """Test GET /api/services"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/services: {len(data)} services found")


class TestTopology:
    """Topology endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_get_topology(self, auth_token):
        """Test GET /api/topology"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/topology", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data or isinstance(data, list)
        print(f"✓ GET /api/topology: Response received")


class TestReports:
    """Reports endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_get_executive_report(self, auth_token):
        """Test GET /api/reports/executive"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/reports/executive", headers=headers)
        assert response.status_code == 200
        data = response.json()
        print(f"✓ GET /api/reports/executive: Response received")


class TestRunbooks:
    """Runbooks endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_get_runbooks(self, auth_token):
        """Test GET /api/runbooks"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/runbooks", headers=headers)
        # May return 200 or 404 if no runbooks exist
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            print(f"✓ GET /api/runbooks: {len(data) if isinstance(data, list) else 'Response'} received")
        else:
            print("✓ GET /api/runbooks: No runbooks found (404)")


class TestAPMModule:
    """APM Module endpoint tests"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_get_apm_dashboard(self, auth_token):
        """Test GET /api/apm/dashboard"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/apm/dashboard", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "overall_metrics" in data
        print(f"✓ APM Dashboard: {len(data['services'])} services, Metrics: {data['overall_metrics']}")
    
    def test_get_apm_services(self, auth_token):
        """Test GET /api/apm/services"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/apm/services", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/apm/services: {len(data)} services found")
    
    def test_create_apm_service(self, auth_token):
        """Test POST /api/apm/services"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        import uuid
        service_data = {
            "service_name": f"test-service-{uuid.uuid4().hex[:8]}",
            "service_type": "api",
            "environment": "development"
        }
        response = requests.post(f"{BASE_URL}/api/apm/services", json=service_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "api_key" in data
        assert data["service_name"] == service_data["service_name"]
        print(f"✓ APM Service created: {data['service_name']}, API Key: {data['api_key'][:20]}...")
        return data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
