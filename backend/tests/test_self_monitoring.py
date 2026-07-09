"""
FalconOps AI - Self-Monitoring Module Tests
Tests for platform health endpoints: /api/self-monitor/health and /api/self-monitor/ping
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSelfMonitoringPing:
    """Test /api/self-monitor/ping endpoint (no auth required)"""
    
    def test_ping_returns_ok(self):
        """Ping endpoint should return status ok without authentication"""
        response = requests.get(f"{BASE_URL}/api/self-monitor/ping")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Response should have 'status' field"
        assert data["status"] == "ok", f"Expected status 'ok', got {data['status']}"
        assert "timestamp" in data, "Response should have 'timestamp' field"
        print(f"PASS: Ping endpoint returned status=ok, timestamp={data['timestamp']}")


class TestSelfMonitoringHealthAuth:
    """Test /api/self-monitor/health authentication requirements"""
    
    def test_health_requires_auth(self):
        """Health endpoint should return 401 without authentication"""
        response = requests.get(f"{BASE_URL}/api/self-monitor/health")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("PASS: Health endpoint correctly requires authentication (401)")
    
    def test_health_rejects_invalid_token(self):
        """Health endpoint should reject invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401 with invalid token, got {response.status_code}"
        print("PASS: Health endpoint correctly rejects invalid token (401)")


class TestSelfMonitoringHealthData:
    """Test /api/self-monitor/health endpoint data structure"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@falconapps.com", "password": "Admin@123"}
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                print(f"PASS: Login successful, got access_token")
                return token
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_health_returns_comprehensive_data(self, auth_token):
        """Health endpoint should return comprehensive health data"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check top-level required fields
        required_fields = ["status", "mongodb", "system", "process", "services", "background_jobs", "recent_errors"]
        for field in required_fields:
            assert field in data, f"Response missing required field: {field}"
        
        print(f"PASS: Health endpoint returned all required fields: {required_fields}")
    
    def test_health_status_values(self, auth_token):
        """Health status should be healthy, warning, or critical"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        valid_statuses = ["healthy", "warning", "critical"]
        assert data["status"] in valid_statuses, f"Status '{data['status']}' not in {valid_statuses}"
        print(f"PASS: Health status is valid: {data['status']}")
    
    def test_mongodb_health_structure(self, auth_token):
        """MongoDB health should have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        mongo = response.json()["mongodb"]
        
        # Check MongoDB status
        assert "status" in mongo, "MongoDB should have 'status' field"
        assert mongo["status"] in ["healthy", "critical"], f"MongoDB status '{mongo['status']}' invalid"
        
        # Check MongoDB metrics
        if mongo["status"] == "healthy":
            assert "latency_ms" in mongo, "MongoDB should have 'latency_ms'"
            assert "total_collections" in mongo, "MongoDB should have 'total_collections'"
            assert "total_documents" in mongo, "MongoDB should have 'total_documents'"
            assert "data_size_mb" in mongo, "MongoDB should have 'data_size_mb'"
            assert mongo["latency_ms"] >= 0, "Latency should be non-negative"
        
        print(f"PASS: MongoDB health structure valid - status={mongo['status']}, latency={mongo.get('latency_ms', 'N/A')}ms")
    
    def test_system_resources_structure(self, auth_token):
        """System resources should have CPU, memory, disk metrics"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        system = response.json()["system"]
        
        # Check required system metrics
        required_metrics = ["cpu_percent", "memory_percent", "disk_percent"]
        for metric in required_metrics:
            assert metric in system, f"System should have '{metric}'"
            assert isinstance(system[metric], (int, float)), f"{metric} should be numeric"
            assert 0 <= system[metric] <= 100, f"{metric} should be 0-100, got {system[metric]}"
        
        # Check additional system info
        assert "load_avg_1m" in system, "System should have 'load_avg_1m'"
        assert "memory_total_gb" in system, "System should have 'memory_total_gb'"
        assert "disk_total_gb" in system, "System should have 'disk_total_gb'"
        
        print(f"PASS: System resources valid - CPU={system['cpu_percent']}%, Memory={system['memory_percent']}%, Disk={system['disk_percent']}%")
    
    def test_process_info_structure(self, auth_token):
        """Process info should have PID, uptime, memory, threads"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        process = response.json()["process"]
        
        # Check required process fields
        required_fields = ["pid", "uptime_seconds", "uptime_human", "memory_rss_mb", "threads"]
        for field in required_fields:
            assert field in process, f"Process should have '{field}'"
        
        assert isinstance(process["pid"], int), "PID should be integer"
        assert process["pid"] > 0, "PID should be positive"
        assert process["uptime_seconds"] >= 0, "Uptime should be non-negative"
        assert process["threads"] > 0, "Threads should be positive"
        
        print(f"PASS: Process info valid - PID={process['pid']}, Uptime={process['uptime_human']}, RSS={process['memory_rss_mb']}MB, Threads={process['threads']}")
    
    def test_services_array_structure(self, auth_token):
        """Services should be array of 12 items with correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        services = response.json()["services"]
        
        # Check services is array with 12 items
        assert isinstance(services, list), "Services should be a list"
        assert len(services) == 12, f"Expected 12 services, got {len(services)}"
        
        # Check each service structure
        for svc in services:
            assert "name" in svc, "Service should have 'name'"
            assert "status" in svc, "Service should have 'status'"
            assert "description" in svc, "Service should have 'description'"
            assert svc["status"] in ["operational", "degraded"], f"Service status '{svc['status']}' invalid"
        
        # Count operational services
        operational = sum(1 for s in services if s["status"] == "operational")
        print(f"PASS: Services array valid - {operational}/12 operational")
        
        # List service names
        service_names = [s["name"] for s in services]
        print(f"  Services: {service_names}")
    
    def test_background_jobs_structure(self, auth_token):
        """Background jobs should be array with job details"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        jobs = response.json()["background_jobs"]
        
        # Check jobs is array
        assert isinstance(jobs, list), "Background jobs should be a list"
        
        # Check each job structure if any exist
        for job in jobs:
            assert "id" in job, "Job should have 'id'"
            assert "name" in job, "Job should have 'name'"
            assert "status" in job, "Job should have 'status'"
        
        print(f"PASS: Background jobs valid - {len(jobs)} active jobs")
    
    def test_recent_errors_structure(self, auth_token):
        """Recent errors should be array (can be empty)"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        errors = response.json()["recent_errors"]
        
        # Check errors is array
        assert isinstance(errors, list), "Recent errors should be a list"
        
        print(f"PASS: Recent errors valid - {len(errors)} errors")
    
    def test_health_additional_metadata(self, auth_token):
        """Health should include version, platform, timestamp"""
        response = requests.get(
            f"{BASE_URL}/api/self-monitor/health",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        assert "version" in data, "Response should have 'version'"
        assert "platform" in data, "Response should have 'platform'"
        assert "timestamp" in data, "Response should have 'timestamp'"
        
        print(f"PASS: Metadata valid - Platform={data['platform']}, Version={data['version']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
