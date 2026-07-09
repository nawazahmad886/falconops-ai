"""
FalconOps AI - Security Monitoring Module Tests
Tests for security event ingestion, threat detection, user activity analysis, and dashboard APIs
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


class TestSecurityMonitoringBackend:
    """Security Monitoring API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                self.authenticated = True
            else:
                self.authenticated = False
        else:
            self.authenticated = False
    
    # ======================== DASHBOARD TESTS ========================
    
    def test_security_dashboard_returns_200(self):
        """Test GET /api/security/dashboard returns 200"""
        response = self.session.get(f"{BASE_URL}/api/security/dashboard?hours=24")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /api/security/dashboard returns 200")
    
    def test_security_dashboard_has_required_fields(self):
        """Test dashboard response has all required fields"""
        response = self.session.get(f"{BASE_URL}/api/security/dashboard?hours=24")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = [
            "total_events", "active_threats", "critical_threats", 
            "severity_breakdown", "timeline", "top_source_ips", "top_threat_types"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"PASS: Dashboard has all required fields: {required_fields}")
        print(f"  - total_events: {data.get('total_events')}")
        print(f"  - active_threats: {data.get('active_threats')}")
        print(f"  - critical_threats: {data.get('critical_threats')}")
    
    def test_security_dashboard_timeline_structure(self):
        """Test dashboard timeline has correct structure"""
        response = self.session.get(f"{BASE_URL}/api/security/dashboard?hours=24")
        assert response.status_code == 200
        
        data = response.json()
        timeline = data.get("timeline", [])
        
        assert isinstance(timeline, list), "Timeline should be a list"
        
        if len(timeline) > 0:
            entry = timeline[0]
            assert "hour" in entry, "Timeline entry missing 'hour'"
            assert "events" in entry, "Timeline entry missing 'events'"
            assert "threats" in entry, "Timeline entry missing 'threats'"
        
        print(f"PASS: Dashboard timeline has correct structure ({len(timeline)} entries)")
    
    # ======================== THREATS TESTS ========================
    
    def test_get_threats_returns_200(self):
        """Test GET /api/security/threats returns 200"""
        response = self.session.get(f"{BASE_URL}/api/security/threats?status=active&limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /api/security/threats returns 200")
    
    def test_get_threats_returns_list(self):
        """Test threats endpoint returns a list"""
        response = self.session.get(f"{BASE_URL}/api/security/threats?status=active")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Threats response should be a list"
        print(f"PASS: Threats endpoint returns list with {len(data)} threats")
    
    def test_threats_have_required_fields(self):
        """Test each threat has required fields"""
        response = self.session.get(f"{BASE_URL}/api/security/threats?status=active&limit=10")
        assert response.status_code == 200
        
        threats = response.json()
        
        if len(threats) > 0:
            threat = threats[0]
            required_fields = ["id", "type", "severity", "message", "timestamp", "status"]
            
            for field in required_fields:
                assert field in threat, f"Threat missing required field: {field}"
            
            # Check for MITRE fields (optional but expected)
            if "mitre_technique" in threat:
                print(f"  - MITRE technique: {threat.get('mitre_technique')}")
            
            print(f"PASS: Threats have required fields. Sample threat type: {threat.get('type')}")
        else:
            print("PASS: Threats endpoint works (no active threats found)")
    
    # ======================== USER ACTIVITY TESTS ========================
    
    def test_user_activity_returns_200(self):
        """Test GET /api/security/user-activity returns 200"""
        response = self.session.get(f"{BASE_URL}/api/security/user-activity?hours=24")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /api/security/user-activity returns 200")
    
    def test_user_activity_has_required_fields(self):
        """Test user activity response has required fields"""
        response = self.session.get(f"{BASE_URL}/api/security/user-activity?hours=24")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = ["suspicious_users", "multi_ip_users", "privileged_actions"]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"PASS: User activity has required fields")
        print(f"  - suspicious_users: {len(data.get('suspicious_users', []))}")
        print(f"  - multi_ip_users: {len(data.get('multi_ip_users', []))}")
        print(f"  - privileged_actions: {len(data.get('privileged_actions', []))}")
    
    # ======================== EVENTS TESTS ========================
    
    def test_get_events_returns_200(self):
        """Test GET /api/security/events returns 200"""
        response = self.session.get(f"{BASE_URL}/api/security/events?hours=24&limit=100")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: GET /api/security/events returns 200")
    
    def test_get_events_has_pagination(self):
        """Test events endpoint has pagination fields"""
        response = self.session.get(f"{BASE_URL}/api/security/events?hours=24&limit=10&offset=0")
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data, "Response missing 'events' field"
        assert "total" in data, "Response missing 'total' field"
        assert "limit" in data, "Response missing 'limit' field"
        assert "offset" in data, "Response missing 'offset' field"
        
        print(f"PASS: Events endpoint has pagination. Total: {data.get('total')}, Returned: {len(data.get('events', []))}")
    
    def test_get_events_with_filters(self):
        """Test events endpoint with category and severity filters"""
        # Test category filter
        response = self.session.get(f"{BASE_URL}/api/security/events?hours=24&category=authentication")
        assert response.status_code == 200
        
        # Test severity filter
        response = self.session.get(f"{BASE_URL}/api/security/events?hours=24&severity=critical")
        assert response.status_code == 200
        
        # Test search filter
        response = self.session.get(f"{BASE_URL}/api/security/events?hours=24&search=login")
        assert response.status_code == 200
        
        print("PASS: Events endpoint accepts category, severity, and search filters")
    
    # ======================== EVENT INGESTION TESTS ========================
    
    def test_ingest_event_returns_200(self):
        """Test POST /api/security/events ingests a security event"""
        event_payload = {
            "action": "login_failed",
            "user": "test_user_security",
            "source_ip": "192.168.100.100",
            "category": "authentication",
            "severity": "warning",
            "message": "Test failed login attempt from security test",
            "host": "test-server-01",
            "service": "sshd"
        }
        
        response = self.session.post(f"{BASE_URL}/api/security/events", json=event_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response missing 'id' field"
        assert "threats_detected" in data, "Response missing 'threats_detected' field"
        
        print(f"PASS: Event ingested successfully. ID: {data.get('id')}, Threats detected: {data.get('threats_detected')}")
    
    # ======================== THREAT UPDATE TESTS ========================
    
    def test_update_threat_status(self):
        """Test PUT /api/security/threats/{threat_id} updates threat status"""
        # First get an active threat
        threats_response = self.session.get(f"{BASE_URL}/api/security/threats?status=active&limit=1")
        assert threats_response.status_code == 200
        
        threats = threats_response.json()
        
        if len(threats) > 0:
            threat_id = threats[0].get("id")
            
            # Update threat status to resolved
            update_response = self.session.put(
                f"{BASE_URL}/api/security/threats/{threat_id}",
                json={"status": "resolved"}
            )
            
            assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
            
            data = update_response.json()
            assert "message" in data or "error" not in data, "Update should succeed"
            
            print(f"PASS: Threat {threat_id} status updated to resolved")
        else:
            print("SKIP: No active threats to update (test still passes)")
    
    def test_update_nonexistent_threat(self):
        """Test updating a non-existent threat returns appropriate response"""
        response = self.session.put(
            f"{BASE_URL}/api/security/threats/nonexistent-threat-id-12345",
            json={"status": "resolved"}
        )
        
        # Should return 200 with error message or 404
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            # Should have error message about threat not found
            assert "error" in data or "Threat not found" in str(data), "Should indicate threat not found"
        
        print("PASS: Non-existent threat update handled correctly")
    
    # ======================== CORRELATIONS TESTS ========================
    
    def test_get_correlations_returns_200(self):
        """Test GET /api/security/correlations returns 200"""
        response = self.session.get(f"{BASE_URL}/api/security/correlations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Correlations should return a list"
        
        print(f"PASS: GET /api/security/correlations returns 200 with {len(data)} correlations")
    
    # ======================== DEMO DATA GENERATION TESTS ========================
    
    def test_simulate_security_events(self):
        """Test POST /api/security/simulate generates demo data"""
        if not self.authenticated:
            pytest.skip("Authentication required for simulate endpoint")
        
        response = self.session.post(f"{BASE_URL}/api/security/simulate?count=50")
        
        # May require write access
        if response.status_code == 403:
            print("SKIP: Simulate endpoint requires write access (403)")
            return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "events_created" in data, "Response missing 'events_created'"
        assert "threats_detected" in data, "Response missing 'threats_detected'"
        
        print(f"PASS: Demo data generated. Events: {data.get('events_created')}, Threats: {data.get('threats_detected')}")
    
    # ======================== AUTHENTICATION TESTS ========================
    
    def test_dashboard_without_auth(self):
        """Test dashboard endpoint behavior without authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.get(f"{BASE_URL}/api/security/dashboard")
        
        # Should work (get_current_user is optional) or return 401
        assert response.status_code in [200, 401], f"Unexpected status: {response.status_code}"
        print(f"PASS: Dashboard without auth returns {response.status_code}")
    
    def test_threat_update_requires_auth(self):
        """Test threat update requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.put(
            f"{BASE_URL}/api/security/threats/test-id",
            json={"status": "resolved"}
        )
        
        # Should return 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"PASS: Threat update requires auth (returns {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
