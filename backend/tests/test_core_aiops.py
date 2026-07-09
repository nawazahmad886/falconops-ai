"""
Test Core AIOps Hub API - Central intelligence page that aggregates all AIOps subsystems
Tests: /api/core-aiops/overview endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCoreAIOpsAPI:
    """Core AIOps Hub API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@falconapps.com", "password": "Admin@123"}
        )
        assert login_response.status_code == 200, "Login failed"
        self.token = login_response.json()["access_token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_core_aiops_overview_returns_200(self):
        """Test that /api/core-aiops/overview returns 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        assert response.status_code == 200
        print("GET /api/core-aiops/overview: 200 OK")
    
    def test_core_aiops_overview_has_system_health(self):
        """Test response includes system_health score"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        data = response.json()
        
        assert "system_health" in data
        assert isinstance(data["system_health"], (int, float))
        assert 0 <= data["system_health"] <= 100
        print(f"System health score: {data['system_health']}")
    
    def test_core_aiops_overview_has_summary(self):
        """Test response includes summary with key metrics"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        data = response.json()
        
        assert "summary" in data
        summary = data["summary"]
        
        # Check all required summary fields
        required_fields = [
            "total_alerts", "active_alerts", "critical_alerts",
            "total_incidents", "active_incidents",
            "total_servers", "healthy_servers",
            "monitors_total", "monitors_up",
            "event_analyses", "knowledge_patterns",
            "ingested_alerts", "unanalyzed_alerts"
        ]
        
        for field in required_fields:
            assert field in summary, f"Missing summary field: {field}"
            assert isinstance(summary[field], int), f"Field {field} should be integer"
        
        print(f"Summary fields verified: {len(required_fields)} fields present")
        print(f"Active alerts: {summary['active_alerts']}, Critical: {summary['critical_alerts']}")
    
    def test_core_aiops_overview_has_capabilities_array(self):
        """Test response includes capabilities array with 12 items"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        data = response.json()
        
        assert "capabilities" in data
        assert isinstance(data["capabilities"], list)
        assert len(data["capabilities"]) == 12, f"Expected 12 capabilities, got {len(data['capabilities'])}"
        print(f"Capabilities count: {len(data['capabilities'])}")
    
    def test_core_aiops_capability_structure(self):
        """Test each capability has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        data = response.json()
        
        required_cap_fields = ["id", "name", "description", "category", "status", "path", "stats", "icon"]
        
        for cap in data["capabilities"]:
            for field in required_cap_fields:
                assert field in cap, f"Capability {cap.get('name', 'unknown')} missing field: {field}"
        
        print(f"All capabilities have required fields: {required_cap_fields}")
    
    def test_core_aiops_capability_categories(self):
        """Test capabilities have valid categories"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        data = response.json()
        
        valid_categories = [
            "detection", "correlation", "analysis", "intelligence",
            "prediction", "operations", "monitoring", "automation", "observability"
        ]
        
        for cap in data["capabilities"]:
            assert cap["category"] in valid_categories, f"Invalid category: {cap['category']}"
        
        # Check category distribution
        categories = [cap["category"] for cap in data["capabilities"]]
        print(f"Category distribution: {dict((c, categories.count(c)) for c in set(categories))}")
    
    def test_core_aiops_capability_paths(self):
        """Test capabilities have valid navigation paths"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        data = response.json()
        
        expected_paths = {
            "anomaly_detection": "/aiops-brain",
            "event_correlation": "/aiops-brain",
            "root_cause": "/incident-engine",
            "impact_analysis": "/aiops-brain",
            "event_analyzer": "/event-analyzer",
            "capacity_prediction": "/capacity-prediction",
            "alert_engine": "/alert-engine",
            "incident_management": "/incident-engine",
            "noc_dashboard": "/noc-dashboard",
            "runbook_automation": "/runbooks",
            "topology_map": "/topology",
            "knowledge_base": "/event-analyzer",
        }
        
        for cap in data["capabilities"]:
            cap_id = cap["id"]
            assert cap_id in expected_paths, f"Unknown capability: {cap_id}"
            assert cap["path"] == expected_paths[cap_id], f"Wrong path for {cap_id}: expected {expected_paths[cap_id]}, got {cap['path']}"
        
        print("All capability paths verified correctly")
    
    def test_core_aiops_severity_distribution(self):
        """Test response includes severity distribution"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        data = response.json()
        
        assert "severity_distribution" in data
        assert isinstance(data["severity_distribution"], dict)
        print(f"Severity distribution: {data['severity_distribution']}")
    
    def test_core_aiops_last_updated(self):
        """Test response includes last_updated timestamp"""
        response = requests.get(
            f"{BASE_URL}/api/core-aiops/overview",
            headers=self.headers
        )
        data = response.json()
        
        assert "last_updated" in data
        assert isinstance(data["last_updated"], str)
        print(f"Last updated: {data['last_updated']}")
    
    def test_core_aiops_requires_auth(self):
        """Test endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/core-aiops/overview")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("Authentication required: PASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
