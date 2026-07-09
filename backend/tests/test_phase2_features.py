"""
FalconOps AI - Phase 2 Features Test Suite
Tests for Health Rules API, Metrics API, Wallboard, and Runbook Edit functionality
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://health-rules-engine.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


class TestAuthentication:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful: {data['user']['email']}")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Authentication failed")


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


# ==================== HEALTH RULES API TESTS ====================

class TestHealthRulesAPI:
    """Health Rules API endpoint tests"""
    
    def test_get_health_rule_templates(self, auth_headers):
        """Test GET /api/health-rules/templates"""
        response = requests.get(f"{BASE_URL}/api/health-rules/templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) > 0
        # Verify template structure
        template = templates[0]
        assert "id" in template
        assert "name" in template
        assert "metric" in template
        assert "operator" in template
        assert "threshold" in template
        print(f"✓ Found {len(templates)} health rule templates")
    
    def test_get_health_rule_categories(self, auth_headers):
        """Test GET /api/health-rules/categories"""
        response = requests.get(f"{BASE_URL}/api/health-rules/categories", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        categories = data["categories"]
        assert len(categories) > 0
        # Verify expected categories
        category_ids = [c["id"] for c in categories]
        assert "infrastructure" in category_ids
        assert "application" in category_ids
        print(f"✓ Found {len(categories)} categories: {category_ids}")
    
    def test_get_health_rule_metrics(self, auth_headers):
        """Test GET /api/health-rules/metrics"""
        response = requests.get(f"{BASE_URL}/api/health-rules/metrics", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        metrics = data["metrics"]
        assert len(metrics) > 0
        # Verify metric structure
        metric = metrics[0]
        assert "id" in metric
        assert "name" in metric
        assert "unit" in metric
        print(f"✓ Found {len(metrics)} metric types")
    
    def test_get_health_rule_operators(self, auth_headers):
        """Test GET /api/health-rules/operators"""
        response = requests.get(f"{BASE_URL}/api/health-rules/operators", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "operators" in data
        operators = data["operators"]
        assert len(operators) > 0
        # Verify expected operators
        operator_ids = [o["id"] for o in operators]
        assert "greater_than" in operator_ids
        assert "less_than" in operator_ids
        print(f"✓ Found {len(operators)} operators: {operator_ids}")
    
    def test_create_health_rule(self, auth_headers):
        """Test POST /api/health-rules - Create a new health rule"""
        rule_data = {
            "name": "TEST_High CPU Alert",
            "description": "Test rule for high CPU usage",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 80.0,
            "duration": 300,
            "severity": "warning",
            "category": "infrastructure",
            "enabled": True
        }
        response = requests.post(f"{BASE_URL}/api/health-rules", json=rule_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == rule_data["name"]
        assert data["metric"] == rule_data["metric"]
        assert data["threshold"] == rule_data["threshold"]
        print(f"✓ Created health rule: {data['id']}")
        return data["id"]
    
    def test_get_health_rules_list(self, auth_headers):
        """Test GET /api/health-rules - List all rules"""
        response = requests.get(f"{BASE_URL}/api/health-rules", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "total" in data
        print(f"✓ Found {data['total']} health rules")
    
    def test_get_health_rule_stats(self, auth_headers):
        """Test GET /api/health-rules/stats"""
        response = requests.get(f"{BASE_URL}/api/health-rules/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_rules" in data
        assert "enabled_rules" in data
        print(f"✓ Health rule stats: {data['total_rules']} total, {data['enabled_rules']} enabled")


# ==================== METRICS API TESTS ====================

class TestMetricsAPI:
    """Metrics API endpoint tests"""
    
    def test_ingest_single_metric(self, auth_headers):
        """Test POST /api/metrics - Ingest single metric"""
        metric_data = {
            "name": "test_cpu_usage",
            "value": 75.5,
            "unit": "%",
            "service": "test-service",
            "host": "test-host-01",
            "tags": {"env": "test", "region": "us-east"}
        }
        response = requests.post(f"{BASE_URL}/api/metrics", json=metric_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == metric_data["name"]
        assert data["value"] == metric_data["value"]
        print(f"✓ Ingested metric: {data['id']}")
    
    def test_ingest_batch_metrics(self, auth_headers):
        """Test POST /api/metrics/batch - Ingest multiple metrics"""
        batch_data = {
            "metrics": [
                {"name": "test_memory_usage", "value": 60.0, "unit": "%", "service": "test-service"},
                {"name": "test_disk_usage", "value": 45.0, "unit": "%", "service": "test-service"},
                {"name": "test_network_in", "value": 100.5, "unit": "MB/s", "service": "test-service"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/metrics/batch", json=batch_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "ingested" in data
        assert data["ingested"] == 3
        print(f"✓ Batch ingested {data['ingested']} metrics")
    
    def test_query_metrics(self, auth_headers):
        """Test POST /api/metrics/query - Query metrics with aggregation"""
        query_data = {
            "name": "test_cpu_usage",
            "aggregation": "avg",
            "resolution": "5m"
        }
        response = requests.post(f"{BASE_URL}/api/metrics/query", json=query_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "aggregation" in data
        print(f"✓ Query metrics response: {data.get('data_points', 0)} data points")
    
    def test_get_latest_metrics(self, auth_headers):
        """Test GET /api/metrics/latest"""
        response = requests.get(f"{BASE_URL}/api/metrics/latest", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        print(f"✓ Found {len(data['metrics'])} latest metrics")
    
    def test_get_metric_names(self, auth_headers):
        """Test GET /api/metrics/names"""
        response = requests.get(f"{BASE_URL}/api/metrics/names", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "names" in data
        print(f"✓ Found {len(data['names'])} unique metric names")
    
    def test_get_metric_stats(self, auth_headers):
        """Test GET /api/metrics/stats"""
        response = requests.get(f"{BASE_URL}/api/metrics/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_data_points" in data
        assert "unique_metrics" in data
        print(f"✓ Metric stats: {data['total_data_points']} data points, {data['unique_metrics']} unique metrics")


# ==================== RUNBOOKS API TESTS ====================

class TestRunbooksAPI:
    """Runbooks API endpoint tests"""
    
    def test_get_runbooks_list(self, auth_headers):
        """Test GET /api/runbooks"""
        response = requests.get(f"{BASE_URL}/api/runbooks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} runbooks")
    
    def test_get_runbook_templates(self, auth_headers):
        """Test GET /api/runbooks/templates"""
        response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        print(f"✓ Found {len(data['templates'])} runbook templates")
    
    def test_get_runbook_categories(self, auth_headers):
        """Test GET /api/runbooks/categories"""
        response = requests.get(f"{BASE_URL}/api/runbooks/categories", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        print(f"✓ Found {len(data['categories'])} runbook categories")
    
    def test_get_runbook_action_types(self, auth_headers):
        """Test GET /api/runbooks/action-types"""
        response = requests.get(f"{BASE_URL}/api/runbooks/action-types", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "action_types" in data
        action_types = data["action_types"]
        # Verify expected action types for Visual Workflow Builder
        action_ids = [a["id"] for a in action_types]
        expected_types = ["http_request", "shell_command", "ssh_command", "database_query", "notification"]
        for expected in expected_types:
            assert expected in action_ids, f"Missing action type: {expected}"
        print(f"✓ Found {len(action_types)} action types including: {action_ids[:5]}...")
    
    def test_get_runbook_stats(self, auth_headers):
        """Test GET /api/runbooks/stats/summary"""
        response = requests.get(f"{BASE_URL}/api/runbooks/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_runbooks" in data
        print(f"✓ Runbook stats: {data['total_runbooks']} total runbooks")
    
    def test_get_scheduled_runbooks(self, auth_headers):
        """Test GET /api/runbooks/scheduled"""
        response = requests.get(f"{BASE_URL}/api/runbooks/scheduled", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "scheduled_runbooks" in data
        print(f"✓ Found {len(data['scheduled_runbooks'])} scheduled runbooks")
    
    def test_get_schedule_presets(self, auth_headers):
        """Test GET /api/runbooks/schedules/presets"""
        response = requests.get(f"{BASE_URL}/api/runbooks/schedules/presets", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        print(f"✓ Found {len(data['presets'])} schedule presets")
    
    def test_create_runbook(self, auth_headers):
        """Test POST /api/runbooks - Create runbook with steps"""
        runbook_data = {
            "name": "TEST_CPU Remediation Runbook",
            "description": "Test runbook for CPU remediation",
            "service": "test-service",
            "category": "infrastructure",
            "auto_execute": False,
            "tags": ["test", "cpu"],
            "steps": [
                {
                    "name": "Check CPU Usage",
                    "action_type": "shell_command",
                    "config": {"command": "top -bn1 | head -5"},
                    "continue_on_failure": False
                },
                {
                    "name": "Send Notification",
                    "action_type": "notification",
                    "config": {"channel": "log", "message": "CPU check completed"},
                    "continue_on_failure": True
                }
            ]
        }
        response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == runbook_data["name"]
        assert len(data["steps"]) == 2
        print(f"✓ Created runbook: {data['id']} with {len(data['steps'])} steps")
        return data["id"]
    
    def test_update_runbook(self, auth_headers):
        """Test PUT /api/runbooks/{id} - Update runbook (Edit functionality)"""
        # First create a runbook
        create_data = {
            "name": "TEST_Runbook for Update",
            "description": "Original description",
            "service": "test-service",
            "category": "general",
            "steps": [{"name": "Step 1", "action_type": "shell_command", "config": {"command": "echo test"}}]
        }
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=create_data, headers=auth_headers)
        assert create_response.status_code == 200
        runbook_id = create_response.json()["id"]
        
        # Update the runbook
        update_data = {
            "name": "TEST_Runbook Updated",
            "description": "Updated description",
            "service": "test-service",
            "category": "infrastructure",
            "steps": [
                {"name": "Updated Step 1", "action_type": "http_request", "config": {"method": "GET", "url": "http://example.com"}},
                {"name": "New Step 2", "action_type": "delay", "config": {"seconds": 5}}
            ]
        }
        response = requests.put(f"{BASE_URL}/api/runbooks/{runbook_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert len(data["steps"]) == 2
        print(f"✓ Updated runbook: {runbook_id} with new steps")


# ==================== ALERTS & INCIDENTS API TESTS ====================

class TestAlertsIncidentsAPI:
    """Alerts and Incidents API tests for Wallboard data"""
    
    def test_get_alerts(self, auth_headers):
        """Test GET /api/alerts"""
        response = requests.get(f"{BASE_URL}/api/alerts?status=open&limit=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} open alerts")
    
    def test_get_incidents(self, auth_headers):
        """Test GET /api/incidents"""
        response = requests.get(f"{BASE_URL}/api/incidents?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} incidents")
    
    def test_get_analytics_summary(self, auth_headers):
        """Test GET /api/analytics/summary - Used by Wallboard"""
        response = requests.get(f"{BASE_URL}/api/analytics/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Wallboard uses these fields
        print(f"✓ Analytics summary retrieved for Wallboard")


# ==================== CLEANUP ====================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_health_rules(self, auth_headers):
        """Clean up TEST_ prefixed health rules"""
        response = requests.get(f"{BASE_URL}/api/health-rules", headers=auth_headers)
        if response.status_code == 200:
            rules = response.json().get("rules", [])
            deleted = 0
            for rule in rules:
                if rule.get("name", "").startswith("TEST_"):
                    del_response = requests.delete(f"{BASE_URL}/api/health-rules/{rule['id']}", headers=auth_headers)
                    if del_response.status_code == 200:
                        deleted += 1
            print(f"✓ Cleaned up {deleted} test health rules")
    
    def test_cleanup_test_runbooks(self, auth_headers):
        """Clean up TEST_ prefixed runbooks"""
        response = requests.get(f"{BASE_URL}/api/runbooks", headers=auth_headers)
        if response.status_code == 200:
            runbooks = response.json()
            deleted = 0
            for runbook in runbooks:
                if runbook.get("name", "").startswith("TEST_"):
                    del_response = requests.delete(f"{BASE_URL}/api/runbooks/{runbook['id']}", headers=auth_headers)
                    if del_response.status_code == 200:
                        deleted += 1
            print(f"✓ Cleaned up {deleted} test runbooks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
