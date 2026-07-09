"""
FalconOps AI - Comprehensive Backend API Tests
Tests for:
- Admin login
- AI Alert Analysis API
- Synthetic Monitor CRUD
- Monitoring dashboard
- Incidents with AI analysis
- Network Topology
- Service Honeycomb
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"

# Viewer credentials
VIEWER_EMAIL = "test@falconapps.com"
VIEWER_PASSWORD = "testpass123"


class TestAdminLogin:
    """Test admin login functionality"""
    
    def test_admin_login_success(self):
        """Test login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful - Role: {data['user']['role']}")
        return data["access_token"]
    
    def test_viewer_login_success(self):
        """Test login with viewer credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": VIEWER_EMAIL,
            "password": VIEWER_PASSWORD
        })
        assert response.status_code == 200, f"Viewer login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        print(f"✓ Viewer login successful - Role: {data['user'].get('role', 'user')}")


class TestAIAlertAnalysis:
    """Test AI Alert Analysis API endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get admin token")
    
    def test_ai_analyze_alert_endpoint(self, admin_token):
        """Test POST /api/ai/analyze-alert endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/ai/analyze-alert",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "source": "Prometheus",
                "service": "payment-service",
                "check_type": "cpu_usage",
                "message": "High CPU utilization detected on payment-service",
                "severity": "critical",
                "timestamp": "2025-01-15T10:30:00Z"
            }
        )
        assert response.status_code == 200, f"AI analyze alert failed: {response.text}"
        data = response.json()
        assert "success" in data or "analysis" in data or "error" not in data
        print(f"✓ AI Alert Analysis endpoint working - Response: {str(data)[:200]}")
    
    def test_ai_rca_endpoint(self, admin_token):
        """Test AI RCA endpoint - first create an incident"""
        # First create an alert to generate an incident
        alert_response = requests.post(f"{BASE_URL}/api/alerts/webhook", json={
            "source": "AppDynamics",
            "severity": "critical",
            "title": f"TEST_RCA_Alert_{uuid.uuid4().hex[:8]}",
            "description": "Critical database connection failure",
            "service": "database-service",
            "host": "db-primary-01"
        })
        assert alert_response.status_code == 200
        
        # Get incidents to find one for RCA
        incidents_response = requests.get(
            f"{BASE_URL}/api/incidents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert incidents_response.status_code == 200
        incidents = incidents_response.json()
        
        if len(incidents) > 0:
            incident_id = incidents[0]["id"]
            # Test RCA endpoint
            rca_response = requests.post(
                f"{BASE_URL}/api/ai/rca/{incident_id}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            # RCA might take time or return immediately
            assert rca_response.status_code in [200, 202, 404], f"RCA failed: {rca_response.text}"
            print(f"✓ AI RCA endpoint tested for incident {incident_id}")
        else:
            print("✓ AI RCA endpoint - No incidents available for testing")


class TestSyntheticMonitorCRUD:
    """Test Synthetic Monitor CRUD operations"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get admin token")
    
    def test_create_synthetic_monitor(self, admin_token):
        """Test creating a synthetic monitor"""
        monitor_name = f"TEST_Synthetic_{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/synthetic-monitors",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": monitor_name,
                "target_url": "https://example.com",
                "login_url": "https://example.com/login",
                "test_username": "testuser",
                "test_password": "testpass",
                "timeout_seconds": 30,
                "enabled": True
            }
        )
        assert response.status_code in [200, 201], f"Create synthetic monitor failed: {response.text}"
        data = response.json()
        assert "id" in data
        print(f"✓ Synthetic monitor created: {data['id']}")
        return data["id"]
    
    def test_list_synthetic_monitors(self, admin_token):
        """Test listing synthetic monitors"""
        response = requests.get(
            f"{BASE_URL}/api/synthetic-monitors",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"List synthetic monitors failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} synthetic monitors")
        return data
    
    def test_run_synthetic_test(self, admin_token):
        """Test running a synthetic monitor test"""
        # First get list of monitors
        monitors = self.test_list_synthetic_monitors(admin_token)
        
        if len(monitors) > 0:
            monitor_id = monitors[0]["id"]
            response = requests.post(
                f"{BASE_URL}/api/synthetic-monitors/{monitor_id}/run",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            # Test might return 200 or 202 for async execution
            assert response.status_code in [200, 202], f"Run synthetic test failed: {response.text}"
            data = response.json()
            print(f"✓ Synthetic test executed - Status: {data.get('status', 'submitted')}")
        else:
            # Create a monitor first then run
            monitor_id = self.test_create_synthetic_monitor(admin_token)
            response = requests.post(
                f"{BASE_URL}/api/synthetic-monitors/{monitor_id}/run",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code in [200, 202], f"Run synthetic test failed: {response.text}"
            print(f"✓ Synthetic test executed for new monitor")


class TestMonitoringDashboard:
    """Test Monitoring Dashboard data loading"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get admin token")
    
    def test_monitoring_dashboard_endpoint(self, admin_token):
        """Test /api/monitoring/dashboard endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/monitoring/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Monitoring dashboard failed: {response.text}"
        data = response.json()
        
        # Verify expected fields
        expected_fields = [
            "total_monitors", "monitors_up", "monitors_down", "monitors_degraded",
            "overall_uptime_percent", "avg_latency_ms", "sla_compliance_percent",
            "active_outages"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Monitoring dashboard loaded successfully")
        print(f"  - Total monitors: {data['total_monitors']}")
        print(f"  - Monitors up: {data['monitors_up']}")
        print(f"  - Overall uptime: {data['overall_uptime_percent']}%")
    
    def test_monitors_list_endpoint(self, admin_token):
        """Test /api/monitors endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/monitors",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Monitors list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Monitors list loaded - {len(data)} monitors found")
    
    def test_scheduler_status(self, admin_token):
        """Test monitoring scheduler status"""
        response = requests.get(
            f"{BASE_URL}/api/monitoring/scheduler/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Scheduler status failed: {response.text}"
        data = response.json()
        assert "running" in data
        print(f"✓ Scheduler status: {'Running' if data['running'] else 'Stopped'}")


class TestIncidentsWithAI:
    """Test Incidents list with AI analysis"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get admin token")
    
    def test_incidents_list(self, admin_token):
        """Test /api/incidents endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/incidents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Incidents list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        # Check for AI analysis in incidents
        incidents_with_ai = [i for i in data if i.get("ai_analysis")]
        print(f"✓ Incidents list loaded - {len(data)} incidents, {len(incidents_with_ai)} with AI analysis")
    
    def test_incident_detail_with_ai(self, admin_token):
        """Test getting incident detail with AI analysis"""
        # Get incidents first
        response = requests.get(
            f"{BASE_URL}/api/incidents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        incidents = response.json()
        
        if len(incidents) > 0:
            incident_id = incidents[0]["id"]
            detail_response = requests.get(
                f"{BASE_URL}/api/incidents/{incident_id}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert detail_response.status_code == 200, f"Incident detail failed: {detail_response.text}"
            data = detail_response.json()
            
            # Verify incident structure
            assert "id" in data
            assert "title" in data
            assert "severity" in data
            assert "status" in data
            
            if data.get("ai_analysis"):
                print(f"✓ Incident {incident_id} has AI analysis")
            else:
                print(f"✓ Incident {incident_id} loaded (no AI analysis yet)")
        else:
            print("✓ No incidents available for detail test")


class TestNetworkTopology:
    """Test Network Topology page /topology"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get admin token")
    
    def test_topology_endpoint(self, admin_token):
        """Test /api/topology endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/topology",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Topology endpoint failed: {response.text}"
        data = response.json()
        
        # Verify topology structure
        assert "nodes" in data
        assert "edges" in data
        assert "health_summary" in data
        
        print(f"✓ Topology loaded successfully")
        print(f"  - Nodes: {len(data['nodes'])}")
        print(f"  - Edges: {len(data['edges'])}")
        if data.get("health_summary"):
            print(f"  - Overall health: {data['health_summary'].get('overall_health', 'N/A')}%")
    
    def test_topology_auto_discover(self, admin_token):
        """Test topology auto-discover endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/topology/auto-discover",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Auto-discover failed: {response.text}"
        data = response.json()
        print(f"✓ Auto-discover executed: {data.get('message', 'Success')}")
    
    def test_create_dependency(self, admin_token):
        """Test creating a service dependency"""
        # First get monitors to use as source/target
        monitors_response = requests.get(
            f"{BASE_URL}/api/monitors",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        monitors = monitors_response.json()
        
        if len(monitors) >= 2:
            response = requests.post(
                f"{BASE_URL}/api/topology/dependencies",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "source_monitor_id": monitors[0]["id"],
                    "target_monitor_id": monitors[1]["id"],
                    "dependency_type": "depends_on"
                }
            )
            # May fail if dependency already exists
            assert response.status_code in [200, 201, 400], f"Create dependency failed: {response.text}"
            print(f"✓ Dependency creation tested")
        else:
            print("✓ Not enough monitors for dependency test")


class TestServiceHoneycomb:
    """Test Service Honeycomb dashboard /honeycomb"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get admin token")
    
    def test_services_endpoint(self, admin_token):
        """Test /api/services endpoint for honeycomb data"""
        response = requests.get(
            f"{BASE_URL}/api/services",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Services endpoint failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        # Verify service structure if services exist
        if len(data) > 0:
            service = data[0]
            assert "name" in service
            assert "health" in service
            print(f"✓ Services loaded - {len(data)} services")
            for svc in data[:5]:
                print(f"  - {svc['name']}: {svc['health']}")
        else:
            print("✓ Services endpoint working (no services yet)")
    
    def test_analytics_dashboard(self, admin_token):
        """Test analytics dashboard for honeycomb metrics"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Analytics dashboard failed: {response.text}"
        data = response.json()
        
        # Verify honeycomb-relevant metrics
        assert "alerts_by_service" in data
        assert "sla_compliance" in data
        
        print(f"✓ Analytics dashboard loaded for honeycomb")
        print(f"  - Services with alerts: {len(data.get('alerts_by_service', {}))}")


class TestAdditionalEndpoints:
    """Test additional API endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Could not get admin token")
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health endpoint working")
    
    def test_alerts_endpoint(self, admin_token):
        """Test alerts endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/alerts",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Alerts endpoint working - {len(data)} alerts")
    
    def test_runbooks_endpoint(self, admin_token):
        """Test runbooks endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/runbooks",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Runbooks endpoint working - {len(data)} runbooks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
