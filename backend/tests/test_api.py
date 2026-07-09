"""
Backend API Tests for FalconApps NOC Platform
Tests authentication, alerts, incidents, and analytics endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials
TEST_EMAIL = f"test_{uuid.uuid4().hex[:8]}@falconapps.com"
TEST_PASSWORD = "testpass123"
TEST_NAME = "Test User"

class TestHealthEndpoints:
    """Health check endpoint tests"""
    
    def test_health_check(self):
        """Test /api/health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "falconapps-api"
        print("✓ Health check passed")
    
    def test_root_endpoint(self):
        """Test /api/ root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "FalconApps" in data["message"]
        print("✓ Root endpoint passed")


class TestAuthEndpoints:
    """Authentication endpoint tests"""
    
    @pytest.fixture(scope="class")
    def registered_user(self):
        """Register a test user and return credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": TEST_NAME,
            "organization": "FalconApps"
        })
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            # User already exists, try login
            login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            if login_response.status_code == 200:
                return login_response.json()
        pytest.skip("Could not register or login test user")
    
    def test_register_user(self):
        """Test user registration"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@falconapps.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "full_name": "New Test User",
            "organization": "TestOrg"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == unique_email
        print(f"✓ User registration passed for {unique_email}")
    
    def test_login_success(self, registered_user):
        """Test successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        print("✓ Login success test passed")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials test passed")
    
    def test_get_me_authenticated(self, registered_user):
        """Test /auth/me endpoint with valid token"""
        token = registered_user["access_token"]
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "full_name" in data
        print("✓ Get me authenticated test passed")
    
    def test_get_me_unauthenticated(self):
        """Test /auth/me endpoint without token"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ Get me unauthenticated test passed")


class TestAlertEndpoints:
    """Alert management endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        # Try to login with existing test user
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@falconapps.com",
            "password": "testpass123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        
        # Register new user if login fails
        unique_email = f"test_{uuid.uuid4().hex[:8]}@falconapps.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "full_name": "Test User"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get auth token")
    
    def test_create_alert_webhook(self):
        """Test alert webhook endpoint (no auth required)"""
        response = requests.post(f"{BASE_URL}/api/alerts/webhook", json={
            "source": "Prometheus",
            "severity": "warning",
            "title": f"Test Alert {uuid.uuid4().hex[:8]}",
            "description": "Test alert from pytest",
            "service": "test-service",
            "host": "test-host-01"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "open"
        assert data["severity"] == "warning"
        print(f"✓ Alert webhook test passed - Alert ID: {data['id']}")
        return data["id"]
    
    def test_get_alerts(self, auth_token):
        """Test get alerts endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/alerts",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get alerts test passed - Found {len(data)} alerts")
    
    def test_get_alerts_with_filters(self, auth_token):
        """Test get alerts with filters"""
        response = requests.get(
            f"{BASE_URL}/api/alerts?status=open&severity=warning",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Verify filters work
        for alert in data:
            assert alert["status"] == "open"
            assert alert["severity"] == "warning"
        print(f"✓ Get alerts with filters test passed - Found {len(data)} filtered alerts")
    
    def test_get_alerts_unauthenticated(self):
        """Test get alerts without auth"""
        response = requests.get(f"{BASE_URL}/api/alerts")
        assert response.status_code == 401
        print("✓ Get alerts unauthenticated test passed")


class TestIncidentEndpoints:
    """Incident management endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@falconapps.com",
            "password": "testpass123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get auth token")
    
    def test_get_incidents(self, auth_token):
        """Test get incidents endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/incidents",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get incidents test passed - Found {len(data)} incidents")
    
    def test_get_incidents_with_filters(self, auth_token):
        """Test get incidents with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/incidents?status=open",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for incident in data:
            assert incident["status"] in ["open", "investigating"]
        print(f"✓ Get incidents with filters test passed")


class TestAnalyticsEndpoints:
    """Analytics endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@falconapps.com",
            "password": "testpass123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get auth token")
    
    def test_get_dashboard_analytics(self, auth_token):
        """Test dashboard analytics endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/dashboard",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields
        assert "total_alerts" in data
        assert "open_alerts" in data
        assert "resolved_alerts" in data
        assert "total_incidents" in data
        assert "open_incidents" in data
        assert "avg_mttr_seconds" in data
        assert "alerts_by_severity" in data
        assert "alerts_by_service" in data
        assert "incidents_trend" in data
        assert "sla_compliance" in data
        
        # Verify data types
        assert isinstance(data["total_alerts"], int)
        assert isinstance(data["sla_compliance"], (int, float))
        assert isinstance(data["alerts_by_severity"], dict)
        
        print(f"✓ Dashboard analytics test passed")
        print(f"  - Total alerts: {data['total_alerts']}")
        print(f"  - Open alerts: {data['open_alerts']}")
        print(f"  - SLA compliance: {data['sla_compliance']}%")


class TestServicesEndpoints:
    """Services endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@falconapps.com",
            "password": "testpass123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get auth token")
    
    def test_get_services(self, auth_token):
        """Test get services endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/services",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Verify service structure if services exist
        if len(data) > 0:
            service = data[0]
            assert "name" in service
            assert "health" in service
            assert "open_alerts" in service
        
        print(f"✓ Get services test passed - Found {len(data)} services")


class TestRunbookEndpoints:
    """Runbook endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@falconapps.com",
            "password": "testpass123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get auth token")
    
    def test_create_runbook(self, auth_token):
        """Test create runbook endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/runbooks",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "name": f"Test Runbook {uuid.uuid4().hex[:8]}",
                "description": "Test runbook from pytest",
                "service": "test-service",
                "steps": [
                    {"action": "check_logs", "description": "Check service logs"},
                    {"action": "restart_service", "description": "Restart the service"}
                ],
                "auto_execute": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert len(data["steps"]) == 2
        print(f"✓ Create runbook test passed - Runbook ID: {data['id']}")
    
    def test_get_runbooks(self, auth_token):
        """Test get runbooks endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/runbooks",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get runbooks test passed - Found {len(data)} runbooks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
