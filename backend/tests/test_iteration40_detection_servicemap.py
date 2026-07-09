"""
FalconOps AI - Iteration 40 Tests
Testing 3 NEW features:
1. Detection Rules - CRUD operations, 8 system defaults, enable/disable
2. Incident Intelligence - AI-powered correlation with summaries and root cause hints
3. Service Map - D3 topology data from /api/topology
4. CI/CD - Verify ci-cd.yml exists
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ======================== FIXTURES ========================

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@falconapps.com",
        "password": "Admin@123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")

@pytest.fixture(scope="module")
def viewer_token():
    """Get viewer authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@falconapps.com",
        "password": "testpass123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Viewer authentication failed")

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

@pytest.fixture
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}", "Content-Type": "application/json"}


# ======================== DETECTION RULES TESTS ========================

class TestDetectionRulesAPI:
    """Detection Rules CRUD and system defaults tests"""
    
    def test_get_rules_returns_8_system_defaults(self, admin_headers):
        """GET /api/detection/rules should return 8 system default rules"""
        response = requests.get(f"{BASE_URL}/api/detection/rules", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        rules = response.json()
        assert isinstance(rules, list), "Response should be a list"
        
        # Check for 8 system default rules
        system_rules = [r for r in rules if r.get("is_system") == True]
        assert len(system_rules) >= 8, f"Expected at least 8 system rules, got {len(system_rules)}"
        
        # Verify expected rule IDs
        expected_rule_ids = [
            "high_error_rate", "slow_response", "service_down", "memory_high",
            "cpu_high", "disk_full", "ssl_expiry", "anomaly_detected"
        ]
        actual_rule_ids = [r["rule_id"] for r in system_rules]
        for expected_id in expected_rule_ids:
            assert expected_id in actual_rule_ids, f"Missing system rule: {expected_id}"
        
        print(f"✓ Found {len(system_rules)} system rules with all 8 expected defaults")
    
    def test_rules_have_required_fields(self, admin_headers):
        """Verify rules have all required fields"""
        response = requests.get(f"{BASE_URL}/api/detection/rules", headers=admin_headers)
        assert response.status_code == 200
        
        rules = response.json()
        required_fields = ["rule_id", "name", "metric", "operator", "threshold", "severity", "enabled", "category"]
        
        for rule in rules[:3]:  # Check first 3 rules
            for field in required_fields:
                assert field in rule, f"Rule missing field: {field}"
        
        print("✓ Rules have all required fields")
    
    def test_create_custom_rule_admin_only(self, admin_headers):
        """POST /api/detection/rules creates custom rule (admin only)"""
        payload = {
            "name": "TEST_Custom_High_Latency",
            "description": "Test rule for high latency detection",
            "metric": "latency_ms",
            "operator": "gt",
            "threshold": 5000,
            "severity": "warning",
            "cooldown_min": 15,
            "enabled": True,
            "category": "performance"
        }
        
        response = requests.post(f"{BASE_URL}/api/detection/rules", json=payload, headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        created_rule = response.json()
        assert created_rule["name"] == payload["name"]
        assert created_rule["metric"] == payload["metric"]
        assert created_rule["threshold"] == payload["threshold"]
        assert created_rule["is_system"] == False, "Custom rule should not be system rule"
        
        # Store rule_id for cleanup
        self.__class__.test_rule_id = created_rule["rule_id"]
        print(f"✓ Created custom rule: {created_rule['rule_id']}")
    
    def test_create_rule_viewer_forbidden(self, viewer_headers):
        """Viewer should not be able to create rules"""
        payload = {
            "name": "TEST_Viewer_Rule",
            "metric": "test_metric",
            "operator": "gt",
            "threshold": 100,
            "severity": "warning",
            "category": "custom"
        }
        
        response = requests.post(f"{BASE_URL}/api/detection/rules", json=payload, headers=viewer_headers)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Viewer correctly forbidden from creating rules")
    
    def test_update_rule(self, admin_headers):
        """PUT /api/detection/rules/{id} updates rule"""
        rule_id = getattr(self.__class__, 'test_rule_id', None)
        if not rule_id:
            pytest.skip("No test rule created")
        
        updates = {
            "threshold": 6000,
            "severity": "critical",
            "enabled": False
        }
        
        response = requests.put(f"{BASE_URL}/api/detection/rules/{rule_id}", json=updates, headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        updated_rule = response.json()
        assert updated_rule["threshold"] == 6000
        assert updated_rule["severity"] == "critical"
        assert updated_rule["enabled"] == False
        print(f"✓ Updated rule {rule_id}")
    
    def test_toggle_rule_enabled(self, admin_headers):
        """Test enable/disable toggle on rules"""
        rule_id = getattr(self.__class__, 'test_rule_id', None)
        if not rule_id:
            pytest.skip("No test rule created")
        
        # Enable the rule
        response = requests.put(f"{BASE_URL}/api/detection/rules/{rule_id}", 
                               json={"enabled": True}, headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["enabled"] == True
        
        # Disable the rule
        response = requests.put(f"{BASE_URL}/api/detection/rules/{rule_id}", 
                               json={"enabled": False}, headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["enabled"] == False
        print("✓ Rule enable/disable toggle working")
    
    def test_delete_custom_rule(self, admin_headers):
        """DELETE /api/detection/rules/{id} deletes non-system rule"""
        rule_id = getattr(self.__class__, 'test_rule_id', None)
        if not rule_id:
            pytest.skip("No test rule created")
        
        response = requests.delete(f"{BASE_URL}/api/detection/rules/{rule_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json().get("deleted") == True
        print(f"✓ Deleted custom rule {rule_id}")
    
    def test_cannot_delete_system_rule(self, admin_headers):
        """System rules cannot be deleted"""
        response = requests.delete(f"{BASE_URL}/api/detection/rules/high_error_rate", headers=admin_headers)
        assert response.status_code == 200
        
        result = response.json()
        assert "error" in result or result.get("deleted") == False, "Should not delete system rule"
        
        # Verify rule still exists
        rules_response = requests.get(f"{BASE_URL}/api/detection/rules", headers=admin_headers)
        rules = rules_response.json()
        system_rule_ids = [r["rule_id"] for r in rules if r.get("is_system")]
        assert "high_error_rate" in system_rule_ids, "System rule should still exist"
        print("✓ System rule deletion correctly prevented")


class TestDetectionStats:
    """Detection statistics endpoint tests"""
    
    def test_get_detection_stats(self, admin_headers):
        """GET /api/detection/stats returns active rules, alerts, threats count"""
        response = requests.get(f"{BASE_URL}/api/detection/stats", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        stats = response.json()
        assert "active_rules" in stats, "Missing active_rules"
        assert "alerts_fired_24h" in stats, "Missing alerts_fired_24h"
        assert "threats_detected_24h" in stats, "Missing threats_detected_24h"
        assert "categories" in stats, "Missing categories"
        
        # Verify categories breakdown
        categories = stats["categories"]
        expected_categories = ["performance", "availability", "resource", "security", "ai", "custom"]
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
        
        print(f"✓ Stats: {stats['active_rules']} active rules, {stats['alerts_fired_24h']} alerts, {stats['threats_detected_24h']} threats")


# ======================== INCIDENT INTELLIGENCE TESTS ========================

class TestIncidentIntelligence:
    """Incident Intelligence with AI summaries and root cause hints"""
    
    def test_get_incidents_with_intelligence(self, admin_headers):
        """GET /api/detection/incidents returns correlated incidents with AI summaries"""
        response = requests.get(f"{BASE_URL}/api/detection/incidents?hours=24&limit=20", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        incidents = response.json()
        assert isinstance(incidents, list), "Response should be a list"
        
        # If there are incidents, verify structure
        if len(incidents) > 0:
            incident = incidents[0]
            required_fields = ["id", "monitor_name", "type", "severity", "status", "summary", "root_cause_hint", "alert_count"]
            for field in required_fields:
                assert field in incident, f"Incident missing field: {field}"
            
            # Verify AI-generated fields
            assert isinstance(incident["summary"], str) and len(incident["summary"]) > 0, "Summary should be non-empty string"
            assert isinstance(incident["root_cause_hint"], str) and len(incident["root_cause_hint"]) > 0, "Root cause hint should be non-empty string"
            
            print(f"✓ Found {len(incidents)} incidents with AI summaries and root cause hints")
        else:
            print("✓ No incidents in last 24h (endpoint working correctly)")
    
    def test_incidents_have_correlation_data(self, admin_headers):
        """Verify incidents have correlation/grouping data"""
        response = requests.get(f"{BASE_URL}/api/detection/incidents?hours=24&limit=20", headers=admin_headers)
        assert response.status_code == 200
        
        incidents = response.json()
        if len(incidents) > 0:
            for incident in incidents[:3]:
                assert "alert_count" in incident, "Missing alert_count for correlation"
                assert "first_seen" in incident or "last_seen" in incident, "Missing timeline data"
            print("✓ Incidents have correlation and timeline data")
        else:
            print("✓ No incidents to verify (endpoint working)")


# ======================== SERVICE MAP / TOPOLOGY TESTS ========================

class TestServiceMapTopology:
    """Service Map D3 topology data tests"""
    
    def test_get_topology_returns_nodes_and_edges(self, admin_headers):
        """GET /api/topology returns nodes and edges for D3 graph"""
        response = requests.get(f"{BASE_URL}/api/topology", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        topology = response.json()
        assert "nodes" in topology, "Missing nodes"
        assert "edges" in topology, "Missing edges"
        assert "health_summary" in topology, "Missing health_summary"
        
        print(f"✓ Topology: {len(topology['nodes'])} nodes, {len(topology['edges'])} edges")
    
    def test_topology_nodes_have_required_fields(self, admin_headers):
        """Verify topology nodes have fields needed for D3 rendering"""
        response = requests.get(f"{BASE_URL}/api/topology", headers=admin_headers)
        assert response.status_code == 200
        
        topology = response.json()
        nodes = topology.get("nodes", [])
        
        if len(nodes) > 0:
            required_fields = ["id", "name", "type", "status", "health_score"]
            for node in nodes[:3]:
                for field in required_fields:
                    assert field in node, f"Node missing field: {field}"
            print(f"✓ Nodes have all required D3 fields")
        else:
            print("✓ No nodes in topology (endpoint working)")
    
    def test_topology_health_summary(self, admin_headers):
        """Verify health summary has required metrics"""
        response = requests.get(f"{BASE_URL}/api/topology", headers=admin_headers)
        assert response.status_code == 200
        
        topology = response.json()
        summary = topology.get("health_summary", {})
        
        required_fields = ["total_services", "healthy", "degraded", "down", "total_dependencies"]
        for field in required_fields:
            assert field in summary, f"Health summary missing: {field}"
        
        print(f"✓ Health summary: {summary['total_services']} services, {summary['healthy']} healthy")
    
    def test_topology_cascade_risks(self, admin_headers):
        """Verify cascade_risks field exists"""
        response = requests.get(f"{BASE_URL}/api/topology", headers=admin_headers)
        assert response.status_code == 200
        
        topology = response.json()
        assert "cascade_risks" in topology, "Missing cascade_risks"
        assert isinstance(topology["cascade_risks"], list), "cascade_risks should be a list"
        print(f"✓ Cascade risks: {len(topology['cascade_risks'])} risks identified")


# ======================== CI/CD TESTS ========================

class TestCICD:
    """CI/CD configuration file tests"""
    
    def test_cicd_yml_exists(self):
        """Verify .github/workflows/ci-cd.yml exists"""
        import os
        cicd_path = "/app/.github/workflows/ci-cd.yml"
        assert os.path.exists(cicd_path), f"CI/CD file not found at {cicd_path}"
        
        with open(cicd_path, 'r') as f:
            content = f.read()
        
        # Verify key sections
        assert "test-backend" in content, "Missing test-backend job"
        assert "test-frontend" in content, "Missing test-frontend job"
        assert "build-and-push" in content, "Missing build-and-push job"
        assert "deploy" in content, "Missing deploy job"
        
        print("✓ CI/CD yml exists with test, build, deploy stages")


# ======================== CLEANUP ========================

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(admin_token):
    """Cleanup any TEST_ prefixed rules after tests"""
    yield
    
    if admin_token:
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        response = requests.get(f"{BASE_URL}/api/detection/rules", headers=headers)
        if response.status_code == 200:
            rules = response.json()
            for rule in rules:
                if rule.get("name", "").startswith("TEST_") and not rule.get("is_system"):
                    requests.delete(f"{BASE_URL}/api/detection/rules/{rule['rule_id']}", headers=headers)
                    print(f"Cleaned up test rule: {rule['rule_id']}")
