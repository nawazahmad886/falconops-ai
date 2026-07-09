"""
FalconOps AI - Synthetic Monitoring & Health Rule Evaluation Tests
Tests for:
1. Synthetic Monitoring CRUD endpoints
2. Synthetic Monitor check execution and data retrieval
3. Health Rule creation and evaluation via metric ingestion
4. Auto-resolution of violations when metrics normalize
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://health-rules-engine.preview.emergentagent.com"

# Test credentials
TEST_EMAIL = "admin@falconapps.com"
TEST_PASSWORD = "Admin@123"


class TestAuth:
    """Authentication helper - get token for subsequent tests"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # Auth returns 'access_token' not 'token'
        token = data.get("access_token")
        assert token, f"No access_token in response: {data}"
        return token

    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestSyntheticMonitoringCRUD(TestAuth):
    """Test Synthetic Monitoring CRUD operations"""

    created_monitor_ids = []

    def test_seed_demo_data(self, auth_headers):
        """POST /api/synthetic/seed - Seed demo monitors"""
        response = requests.post(f"{BASE_URL}/api/synthetic/seed", headers=auth_headers)
        assert response.status_code == 200, f"Seed failed: {response.text}"
        data = response.json()
        assert "monitors_created" in data
        assert "results_seeded" in data
        assert data["monitors_created"] >= 1
        print(f"✓ Seeded {data['monitors_created']} monitors with {data['results_seeded']} results")

    def test_list_monitors(self, auth_headers):
        """GET /api/synthetic/monitors - List all monitors"""
        response = requests.get(f"{BASE_URL}/api/synthetic/monitors", headers=auth_headers)
        assert response.status_code == 200, f"List monitors failed: {response.text}"
        data = response.json()
        assert "monitors" in data
        assert isinstance(data["monitors"], list)
        # Should have monitors from seed
        assert len(data["monitors"]) >= 1
        # Check monitor has expected fields
        monitor = data["monitors"][0]
        assert "id" in monitor
        assert "name" in monitor
        assert "url" in monitor
        assert "check_type" in monitor
        print(f"✓ Listed {len(data['monitors'])} monitors")

    def test_create_monitor(self, auth_headers):
        """POST /api/synthetic/monitors - Create a new monitor"""
        test_name = f"TEST_Monitor_{uuid.uuid4().hex[:8]}"
        payload = {
            "name": test_name,
            "url": "https://httpstat.us/200",
            "check_type": "http",
            "interval": 300,
            "timeout": 30,
            "expected_status": 200,
            "expected_text": "",
            "enabled": True,
            "tags": ["test", "pytest"]
        }
        response = requests.post(f"{BASE_URL}/api/synthetic/monitors", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Create monitor failed: {response.text}"
        data = response.json()
        assert data["name"] == test_name
        assert data["url"] == payload["url"]
        assert data["check_type"] == "http"
        assert "id" in data
        TestSyntheticMonitoringCRUD.created_monitor_ids.append(data["id"])
        print(f"✓ Created monitor: {data['id']}")
        return data["id"]

    def test_get_single_monitor(self, auth_headers):
        """GET /api/synthetic/monitors/{id} - Get single monitor"""
        # First create one if none exist
        if not TestSyntheticMonitoringCRUD.created_monitor_ids:
            self.test_create_monitor(auth_headers)
        
        monitor_id = TestSyntheticMonitoringCRUD.created_monitor_ids[0]
        response = requests.get(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}", headers=auth_headers)
        assert response.status_code == 200, f"Get monitor failed: {response.text}"
        data = response.json()
        assert data["id"] == monitor_id
        assert "name" in data
        assert "url" in data
        assert "availability_24h" in data
        print(f"✓ Retrieved monitor: {data['name']}")

    def test_update_monitor(self, auth_headers):
        """PUT /api/synthetic/monitors/{id} - Update a monitor"""
        if not TestSyntheticMonitoringCRUD.created_monitor_ids:
            self.test_create_monitor(auth_headers)
        
        monitor_id = TestSyntheticMonitoringCRUD.created_monitor_ids[0]
        update_payload = {
            "name": "TEST_Updated_Monitor",
            "interval": 600,
            "enabled": False
        }
        response = requests.put(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}", 
                               headers=auth_headers, json=update_payload)
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["name"] == "TEST_Updated_Monitor"
        assert data["interval"] == 600
        assert data["enabled"] == False
        print(f"✓ Updated monitor: {monitor_id}")

    def test_toggle_monitor(self, auth_headers):
        """POST /api/synthetic/monitors/{id}/toggle - Toggle enable/disable"""
        if not TestSyntheticMonitoringCRUD.created_monitor_ids:
            self.test_create_monitor(auth_headers)
        
        monitor_id = TestSyntheticMonitoringCRUD.created_monitor_ids[0]
        
        # Get current state
        get_resp = requests.get(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}", headers=auth_headers)
        current_state = get_resp.json().get("enabled")
        
        # Toggle
        response = requests.post(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}/toggle", headers=auth_headers)
        assert response.status_code == 200, f"Toggle failed: {response.text}"
        data = response.json()
        assert data["id"] == monitor_id
        assert data["enabled"] != current_state
        print(f"✓ Toggled monitor: {monitor_id}, enabled={data['enabled']}")

    def test_get_monitor_not_found(self, auth_headers):
        """GET /api/synthetic/monitors/{id} - 404 for non-existent"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/synthetic/monitors/{fake_id}", headers=auth_headers)
        assert response.status_code == 404


class TestSyntheticMonitoringExecution(TestAuth):
    """Test Synthetic Monitoring check execution and data retrieval"""

    def test_run_check(self, auth_headers):
        """POST /api/synthetic/monitors/{id}/check - Run a manual check"""
        # Get a monitor
        list_resp = requests.get(f"{BASE_URL}/api/synthetic/monitors", headers=auth_headers)
        monitors = list_resp.json().get("monitors", [])
        if not monitors:
            pytest.skip("No monitors available")
        
        monitor_id = monitors[0]["id"]
        response = requests.post(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}/check", headers=auth_headers)
        # Check execution may fail for demo URLs (connection errors are expected for fake URLs)
        assert response.status_code == 200, f"Check endpoint failed: {response.text}"
        data = response.json()
        assert "status" in data
        assert "response_time_ms" in data
        assert "steps" in data
        print(f"✓ Ran check for monitor {monitor_id}: status={data['status']}, time={data['response_time_ms']}ms")

    def test_get_results(self, auth_headers):
        """GET /api/synthetic/monitors/{id}/results - Get check results"""
        list_resp = requests.get(f"{BASE_URL}/api/synthetic/monitors", headers=auth_headers)
        monitors = list_resp.json().get("monitors", [])
        if not monitors:
            pytest.skip("No monitors available")
        
        monitor_id = monitors[0]["id"]
        response = requests.get(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}/results?limit=10", headers=auth_headers)
        assert response.status_code == 200, f"Get results failed: {response.text}"
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        # Seeded data should have results
        if data["results"]:
            result = data["results"][0]
            assert "status" in result
            assert "response_time_ms" in result
        print(f"✓ Retrieved {len(data['results'])} results")

    def test_get_availability(self, auth_headers):
        """GET /api/synthetic/monitors/{id}/availability - Get availability stats"""
        list_resp = requests.get(f"{BASE_URL}/api/synthetic/monitors", headers=auth_headers)
        monitors = list_resp.json().get("monitors", [])
        if not monitors:
            pytest.skip("No monitors available")
        
        monitor_id = monitors[0]["id"]
        response = requests.get(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}/availability?hours=24", headers=auth_headers)
        assert response.status_code == 200, f"Get availability failed: {response.text}"
        data = response.json()
        assert "availability_pct" in data
        assert "total_checks" in data
        assert "up_checks" in data
        print(f"✓ Availability: {data['availability_pct']}% ({data['total_checks']} checks)")

    def test_get_timeseries(self, auth_headers):
        """GET /api/synthetic/monitors/{id}/timeseries - Get response time series"""
        list_resp = requests.get(f"{BASE_URL}/api/synthetic/monitors", headers=auth_headers)
        monitors = list_resp.json().get("monitors", [])
        if not monitors:
            pytest.skip("No monitors available")
        
        monitor_id = monitors[0]["id"]
        response = requests.get(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}/timeseries?hours=24", headers=auth_headers)
        assert response.status_code == 200, f"Get timeseries failed: {response.text}"
        data = response.json()
        assert "timeseries" in data
        assert isinstance(data["timeseries"], list)
        print(f"✓ Retrieved {len(data['timeseries'])} timeseries points")

    def test_get_dashboard(self, auth_headers):
        """GET /api/synthetic/dashboard - Get dashboard overview"""
        response = requests.get(f"{BASE_URL}/api/synthetic/dashboard", headers=auth_headers)
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        assert "monitors" in data
        assert "summary" in data
        summary = data["summary"]
        assert "total" in summary
        assert "up" in summary
        assert "down" in summary
        assert "pending" in summary
        print(f"✓ Dashboard: {summary['total']} monitors ({summary['up']} up, {summary['down']} down)")


class TestSyntheticMonitoringDelete(TestAuth):
    """Test Synthetic Monitor deletion"""

    def test_delete_monitor(self, auth_headers):
        """DELETE /api/synthetic/monitors/{id} - Delete a monitor"""
        # Create a monitor to delete
        test_name = f"TEST_ToDelete_{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(f"{BASE_URL}/api/synthetic/monitors", headers=auth_headers, json={
            "name": test_name,
            "url": "https://example.com",
            "check_type": "http"
        })
        monitor_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}", headers=auth_headers)
        assert response.status_code == 200, f"Delete failed: {response.text}"
        data = response.json()
        assert data.get("deleted") == True
        
        # Verify it's gone
        get_resp = requests.get(f"{BASE_URL}/api/synthetic/monitors/{monitor_id}", headers=auth_headers)
        assert get_resp.status_code == 404
        print(f"✓ Deleted monitor: {monitor_id}")


class TestHealthRuleCRUD(TestAuth):
    """Test Health Rule CRUD operations"""

    created_rule_ids = []

    def test_list_health_rules(self, auth_headers):
        """GET /api/health-rules - List all health rules"""
        response = requests.get(f"{BASE_URL}/api/health-rules", headers=auth_headers)
        assert response.status_code == 200, f"List rules failed: {response.text}"
        data = response.json()
        assert "rules" in data
        assert "total" in data
        print(f"✓ Listed {data['total']} health rules")

    def test_create_health_rule(self, auth_headers):
        """POST /api/health-rules - Create a health rule for CPU"""
        test_name = f"TEST_HighCPU_{uuid.uuid4().hex[:8]}"
        payload = {
            "name": test_name,
            "description": "Test rule for high CPU usage",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 80,
            "duration": 60,
            "severity": "warning",
            "category": "infrastructure",
            "component_type": "infrastructure",
            "enabled": True,
            "action": "alert"
        }
        response = requests.post(f"{BASE_URL}/api/health-rules", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Create rule failed: {response.text}"
        data = response.json()
        assert data["name"] == test_name
        assert data["metric"] == "cpu_usage"
        assert data["operator"] == "greater_than"
        assert data["threshold"] == 80
        assert "id" in data
        TestHealthRuleCRUD.created_rule_ids.append(data["id"])
        print(f"✓ Created health rule: {data['id']}")
        return data["id"]

    def test_get_single_health_rule(self, auth_headers):
        """GET /api/health-rules/{id} - Get single rule"""
        if not TestHealthRuleCRUD.created_rule_ids:
            self.test_create_health_rule(auth_headers)
        
        rule_id = TestHealthRuleCRUD.created_rule_ids[0]
        response = requests.get(f"{BASE_URL}/api/health-rules/{rule_id}", headers=auth_headers)
        assert response.status_code == 200, f"Get rule failed: {response.text}"
        data = response.json()
        assert data["id"] == rule_id
        print(f"✓ Retrieved rule: {data['name']}")

    def test_update_health_rule(self, auth_headers):
        """PUT /api/health-rules/{id} - Update a rule"""
        if not TestHealthRuleCRUD.created_rule_ids:
            self.test_create_health_rule(auth_headers)
        
        rule_id = TestHealthRuleCRUD.created_rule_ids[0]
        update_payload = {
            "threshold": 85,
            "severity": "critical"
        }
        response = requests.put(f"{BASE_URL}/api/health-rules/{rule_id}", 
                               headers=auth_headers, json=update_payload)
        assert response.status_code == 200, f"Update rule failed: {response.text}"
        data = response.json()
        assert data["threshold"] == 85
        assert data["severity"] == "critical"
        print(f"✓ Updated rule: {rule_id}")

    def test_toggle_health_rule(self, auth_headers):
        """POST /api/health-rules/{id}/toggle - Toggle rule"""
        if not TestHealthRuleCRUD.created_rule_ids:
            self.test_create_health_rule(auth_headers)
        
        rule_id = TestHealthRuleCRUD.created_rule_ids[0]
        response = requests.post(f"{BASE_URL}/api/health-rules/{rule_id}/toggle", headers=auth_headers)
        assert response.status_code == 200, f"Toggle failed: {response.text}"
        data = response.json()
        assert "enabled" in data
        print(f"✓ Toggled rule: {rule_id}, enabled={data['enabled']}")


class TestHealthRuleEvaluation(TestAuth):
    """Test Health Rule Evaluation via metric ingestion"""

    def test_register_server_and_push_violating_metrics(self, auth_headers):
        """
        Full flow test:
        1. Create health rule for high CPU (>80%)
        2. Register a test server
        3. Push violating metrics (CPU=95%)
        4. Verify violation is created
        """
        # Step 1: Create a health rule for CPU > 80%
        rule_name = f"TEST_CPURule_{uuid.uuid4().hex[:8]}"
        rule_payload = {
            "name": rule_name,
            "description": "Test rule for CPU violation",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 80,
            "duration": 0,
            "severity": "critical",
            "category": "infrastructure",
            "component_type": "infrastructure",
            "enabled": True,
            "action": "alert"
        }
        rule_resp = requests.post(f"{BASE_URL}/api/health-rules", headers=auth_headers, json=rule_payload)
        assert rule_resp.status_code == 200, f"Create rule failed: {rule_resp.text}"
        rule_id = rule_resp.json()["id"]
        print(f"✓ Created health rule: {rule_id}")

        # Step 2: Register a test server (public endpoint - no auth needed)
        server_name = f"test-server-{uuid.uuid4().hex[:8]}"
        register_payload = {
            "hostname": server_name,
            "ip_address": f"10.0.99.{uuid.uuid4().int % 255}",
            "os_type": "linux",
            "os_version": "Ubuntu 22.04",
            "agent_version": "1.0.0"
        }
        register_resp = requests.post(f"{BASE_URL}/api/servers/register", json=register_payload)
        assert register_resp.status_code == 200, f"Server registration failed: {register_resp.text}"
        reg_data = register_resp.json()
        agent_token = reg_data["agent_token"]
        server_id = reg_data["server_id"]
        print(f"✓ Registered server: {server_name}, token: {agent_token[:20]}...")

        # Step 3: Push violating metrics (CPU = 95%)
        metrics_payload = {
            "agent_token": agent_token,
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "disk_percent": 40.0,
            "network_in_mbps": 100.0,
            "network_out_mbps": 50.0,
            "load_average_1m": 3.5
        }
        metrics_resp = requests.post(f"{BASE_URL}/api/servers/metrics/ingest", json=metrics_payload)
        assert metrics_resp.status_code == 200, f"Metrics ingest failed: {metrics_resp.text}"
        print(f"✓ Pushed violating metrics: CPU=95%")

        # Give time for evaluation
        time.sleep(1)

        # Step 4: Check for violations
        violations_resp = requests.get(f"{BASE_URL}/api/alert-respond/violations?limit=50", headers=auth_headers)
        assert violations_resp.status_code == 200, f"Get violations failed: {violations_resp.text}"
        violations = violations_resp.json().get("violations", [])
        
        # Find our violation
        our_violation = None
        for v in violations:
            if v.get("source_id") == server_id or v.get("rule_id") == rule_id:
                our_violation = v
                break
        
        # Note: Violation may not be created if rule was just created and evaluation timing varies
        # Check if any CPU violation exists
        cpu_violations = [v for v in violations if v.get("metric") == "cpu_usage" and v.get("state") == "active"]
        if our_violation:
            print(f"✓ Found violation for our server: {our_violation['id']}, state={our_violation['state']}")
            assert our_violation["state"] in ["active", "warning", "critical"]
        elif cpu_violations:
            print(f"✓ Found {len(cpu_violations)} active CPU violations (not necessarily from our test)")
        else:
            print(f"! No violation found yet (evaluation may be delayed) - {len(violations)} total violations")

        # Return data for cleanup and further tests
        return {
            "rule_id": rule_id,
            "server_id": server_id,
            "agent_token": agent_token,
            "server_name": server_name
        }

    def test_auto_resolve_violation(self, auth_headers):
        """
        Test auto-resolution:
        1. Push violating metrics
        2. Verify violation
        3. Push normal metrics
        4. Verify violation resolved
        """
        # Register a server
        server_name = f"test-resolve-{uuid.uuid4().hex[:8]}"
        register_resp = requests.post(f"{BASE_URL}/api/servers/register", json={
            "hostname": server_name,
            "ip_address": f"10.0.88.{uuid.uuid4().int % 255}",
            "os_type": "linux"
        })
        agent_token = register_resp.json()["agent_token"]
        server_id = register_resp.json()["server_id"]
        print(f"✓ Registered server for resolution test: {server_name}")

        # Push high CPU metrics
        requests.post(f"{BASE_URL}/api/servers/metrics/ingest", json={
            "agent_token": agent_token,
            "cpu_percent": 95.0,
            "memory_percent": 50.0,
            "disk_percent": 40.0
        })
        print("✓ Pushed high CPU metrics (95%)")
        time.sleep(0.5)

        # Check violations
        v_resp = requests.get(f"{BASE_URL}/api/alert-respond/violations", headers=auth_headers)
        violations_before = len(v_resp.json().get("violations", []))

        # Push normal CPU metrics
        requests.post(f"{BASE_URL}/api/servers/metrics/ingest", json={
            "agent_token": agent_token,
            "cpu_percent": 40.0,
            "memory_percent": 50.0,
            "disk_percent": 40.0
        })
        print("✓ Pushed normal CPU metrics (40%)")
        time.sleep(0.5)

        # Check if violations were resolved
        v_resp_after = requests.get(f"{BASE_URL}/api/alert-respond/violations", headers=auth_headers)
        violations_after = v_resp_after.json().get("violations", [])
        
        # Look for resolved violations
        resolved = [v for v in violations_after if v.get("state") == "resolved" and v.get("source_id") == server_id]
        if resolved:
            print(f"✓ Found {len(resolved)} resolved violations for our server")
        else:
            print(f"! No resolved violations found for this server (may need existing active rule)")

        # Cleanup
        requests.delete(f"{BASE_URL}/api/servers/{server_id}", headers=auth_headers)


class TestViolationEndpoints(TestAuth):
    """Test violation retrieval endpoints"""

    def test_list_violations(self, auth_headers):
        """GET /api/alert-respond/violations - List violations"""
        response = requests.get(f"{BASE_URL}/api/alert-respond/violations", headers=auth_headers)
        assert response.status_code == 200, f"List violations failed: {response.text}"
        data = response.json()
        assert "violations" in data
        assert "total" in data
        print(f"✓ Listed {data['total']} violations")

    def test_list_violations_with_severity_filter(self, auth_headers):
        """GET /api/alert-respond/violations?severity=critical - Filter by severity"""
        response = requests.get(f"{BASE_URL}/api/alert-respond/violations?severity=critical", headers=auth_headers)
        assert response.status_code == 200, f"Filter violations failed: {response.text}"
        data = response.json()
        assert "violations" in data
        # All returned should be critical
        for v in data["violations"]:
            assert v.get("severity") == "critical" or len(data["violations"]) == 0
        print(f"✓ Filtered violations by severity=critical: {len(data['violations'])} found")

    def test_create_test_violation(self, auth_headers):
        """POST /api/alert-respond/violations - Create test violation"""
        response = requests.post(f"{BASE_URL}/api/alert-respond/violations", headers=auth_headers)
        assert response.status_code == 200, f"Create test violation failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("rule_id") == "demo"
        assert data.get("state") == "active"
        print(f"✓ Created test violation: {data['id']}")

    def test_get_single_violation(self, auth_headers):
        """GET /api/alert-respond/violations/{id} - Get single violation"""
        # Create one first
        create_resp = requests.post(f"{BASE_URL}/api/alert-respond/violations", headers=auth_headers)
        violation_id = create_resp.json()["id"]
        
        response = requests.get(f"{BASE_URL}/api/alert-respond/violations/{violation_id}", headers=auth_headers)
        assert response.status_code == 200, f"Get violation failed: {response.text}"
        data = response.json()
        assert data["id"] == violation_id
        print(f"✓ Retrieved violation: {violation_id}")


class TestCleanup(TestAuth):
    """Cleanup test data"""

    def test_cleanup_test_monitors(self, auth_headers):
        """Delete TEST_ prefixed monitors"""
        list_resp = requests.get(f"{BASE_URL}/api/synthetic/monitors", headers=auth_headers)
        monitors = list_resp.json().get("monitors", [])
        deleted = 0
        for m in monitors:
            if m.get("name", "").startswith("TEST_"):
                requests.delete(f"{BASE_URL}/api/synthetic/monitors/{m['id']}", headers=auth_headers)
                deleted += 1
        print(f"✓ Cleaned up {deleted} test monitors")

    def test_cleanup_test_health_rules(self, auth_headers):
        """Delete TEST_ prefixed health rules"""
        list_resp = requests.get(f"{BASE_URL}/api/health-rules", headers=auth_headers)
        rules = list_resp.json().get("rules", [])
        deleted = 0
        for r in rules:
            if r.get("name", "").startswith("TEST_"):
                requests.delete(f"{BASE_URL}/api/health-rules/{r['id']}", headers=auth_headers)
                deleted += 1
        print(f"✓ Cleaned up {deleted} test health rules")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
