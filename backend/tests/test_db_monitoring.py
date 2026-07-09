"""
FalconOps AI - Database Monitoring Module Tests (Iteration 22)
Tests for DB instance management, metrics ingestion, slow queries, locks, alert rules, and dashboard
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@falconapps.com"
TEST_PASSWORD = "Admin@123"


class TestDBMonitoringAuth:
    """Test authentication requirements for DB monitoring endpoints"""
    
    def test_instances_requires_auth(self):
        """GET /api/db-monitoring/instances requires authentication"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/instances")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: GET /api/db-monitoring/instances requires auth")
    
    def test_dashboard_overview_requires_auth(self):
        """GET /api/db-monitoring/dashboard-overview requires authentication"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/dashboard-overview")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: GET /api/db-monitoring/dashboard-overview requires auth")
    
    def test_alert_rules_requires_auth(self):
        """GET /api/db-monitoring/alert-rules requires authentication"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/alert-rules")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: GET /api/db-monitoring/alert-rules requires auth")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for authenticated tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        token = data.get("token") or data.get("access_token")
        print(f"AUTH: Got token successfully")
        return token
    pytest.skip(f"Authentication failed: {response.status_code}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestDBInstancesAPI:
    """Test DB instance management endpoints"""
    
    def test_list_instances(self, auth_headers):
        """GET /api/db-monitoring/instances - should return seeded instances"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "instances" in data, "Response should contain 'instances' key"
        instances = data["instances"]
        assert isinstance(instances, list), "instances should be a list"
        assert len(instances) >= 3, f"Expected at least 3 seeded instances, got {len(instances)}"
        
        # Verify instance structure
        if instances:
            inst = instances[0]
            assert "id" in inst, "Instance should have 'id'"
            assert "name" in inst, "Instance should have 'name'"
            assert "db_type" in inst, "Instance should have 'db_type'"
            assert "host" in inst, "Instance should have 'host'"
            assert "port" in inst, "Instance should have 'port'"
        print(f"PASS: GET /api/db-monitoring/instances returned {len(instances)} instances")
        return instances
    
    def test_create_instance(self, auth_headers):
        """POST /api/db-monitoring/instances - create a new DB instance"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "name": f"TEST_DB_{test_id}",
            "db_type": "postgres",
            "host": "test-db-host.local",
            "port": 5432,
            "database": "test_db",
            "environment": "development",
            "tags": {"team": "testing"}
        }
        response = requests.post(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers, json=payload)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        data = response.json()
        assert "id" in data, "Response should contain instance id"
        assert data["name"] == payload["name"], "Name should match"
        assert data["db_type"] == "postgres", "DB type should be postgres"
        assert data["status"] == "registered", "Status should be 'registered'"
        print(f"PASS: POST /api/db-monitoring/instances created instance {data['id'][:8]}")
        return data["id"]
    
    def test_delete_instance(self, auth_headers):
        """DELETE /api/db-monitoring/instances/{id} - delete instance"""
        # First create an instance to delete
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "name": f"TEST_DELETE_{test_id}",
            "db_type": "mysql",
            "host": "to-delete.local",
            "port": 3306
        }
        create_res = requests.post(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers, json=payload)
        assert create_res.status_code in [200, 201]
        instance_id = create_res.json()["id"]
        
        # Delete the instance
        response = requests.delete(f"{BASE_URL}/api/db-monitoring/instances/{instance_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("deleted") == True, "Response should confirm deletion"
        print(f"PASS: DELETE /api/db-monitoring/instances/{instance_id[:8]} successful")
    
    def test_delete_nonexistent_instance(self, auth_headers):
        """DELETE /api/db-monitoring/instances/{non-existent-id} - should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/db-monitoring/instances/{fake_id}", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: DELETE non-existent instance returns 404")


class TestMetricsIngestion:
    """Test metrics ingestion endpoint (no auth required)"""
    
    def test_ingest_metrics(self, auth_headers):
        """POST /api/db-monitoring/metrics/ingest - ingest metrics"""
        # First get an instance ID
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers)
        instances = list_res.json().get("instances", [])
        if not instances:
            pytest.skip("No instances available for metrics ingestion test")
        instance_id = instances[0]["id"]
        
        payload = {
            "instance_id": instance_id,
            "metrics": {
                "active_sessions": 45,
                "cpu_usage": 65.5,
                "memory_usage": 78.2,
                "tps": 1200,
                "cache_hit_ratio": 98.5,
                "database_size_mb": 5120
            },
            "slow_queries": [
                {
                    "pid": 12345,
                    "user": "app_user",
                    "query": "SELECT * FROM large_table WHERE status = 'pending'",
                    "duration_ms": 5500,
                    "fingerprint": "select_large_table_status"
                }
            ],
            "locks": [
                {
                    "blocked_pid": 1001,
                    "blocking_pid": 1002,
                    "blocked_user": "app_user",
                    "blocking_user": "admin_user",
                    "blocked_query": "UPDATE orders SET status='shipped'",
                    "blocking_query": "UPDATE orders SET status='pending'",
                    "lock_type": "row_exclusive",
                    "wait_time_ms": 2500
                }
            ]
        }
        response = requests.post(f"{BASE_URL}/api/db-monitoring/metrics/ingest", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", "Response status should be 'ok'"
        assert data.get("metrics_stored") == True, "Metrics should be stored"
        assert data.get("slow_queries_count") == 1, "Should have 1 slow query"
        assert data.get("locks_count") == 1, "Should have 1 lock"
        print(f"PASS: POST /api/db-monitoring/metrics/ingest successful - {data.get('alerts_fired', 0)} alerts fired")


class TestDashboardAPIs:
    """Test dashboard data endpoints"""
    
    def test_dashboard_overview(self, auth_headers):
        """GET /api/db-monitoring/dashboard-overview - overview with all instances"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/dashboard-overview", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "instances" in data, "Response should contain 'instances'"
        assert "summary" in data, "Response should contain 'summary'"
        
        summary = data["summary"]
        assert "total_instances" in summary, "Summary should have total_instances"
        assert "active_instances" in summary, "Summary should have active_instances"
        assert "avg_health_score" in summary, "Summary should have avg_health_score"
        assert "total_slow_queries_1h" in summary, "Summary should have total_slow_queries_1h"
        assert "total_locks_1h" in summary, "Summary should have total_locks_1h"
        
        # Each instance should have health_score and current_metrics
        for inst in data["instances"]:
            assert "health_score" in inst, f"Instance {inst.get('name')} should have health_score"
            assert "current_metrics" in inst, f"Instance {inst.get('name')} should have current_metrics"
        
        print(f"PASS: Dashboard overview - {summary['total_instances']} instances, avg health: {summary['avg_health_score']}")
    
    def test_instance_dashboard(self, auth_headers):
        """GET /api/db-monitoring/dashboard/{instance_id} - detailed instance dashboard"""
        # Get an instance ID first
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers)
        instances = list_res.json().get("instances", [])
        if not instances:
            pytest.skip("No instances available for dashboard test")
        instance_id = instances[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/db-monitoring/dashboard/{instance_id}?hours=24", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "instance" in data, "Response should contain 'instance'"
        assert "current" in data, "Response should contain 'current' metrics"
        assert "metrics_history" in data, "Response should contain 'metrics_history'"
        assert "slow_queries" in data, "Response should contain 'slow_queries'"
        assert "locks" in data, "Response should contain 'locks'"
        assert "alerts" in data, "Response should contain 'alerts'"
        assert "period_hours" in data, "Response should contain 'period_hours'"
        
        inst_data = data["instance"]
        assert inst_data["id"] == instance_id, "Instance ID should match"
        
        print(f"PASS: Dashboard for {inst_data['name']} - {len(data['metrics_history'])} metrics, {len(data['slow_queries'])} slow queries, {len(data['locks'])} locks")
    
    def test_dashboard_nonexistent_instance(self, auth_headers):
        """GET /api/db-monitoring/dashboard/{non-existent} - should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/db-monitoring/dashboard/{fake_id}", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Dashboard for non-existent instance returns 404")


class TestSlowQueriesAPI:
    """Test slow queries endpoints"""
    
    def test_get_slow_queries(self, auth_headers):
        """GET /api/db-monitoring/slow-queries/{instance_id} - get slow queries"""
        # Get an instance ID
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers)
        instances = list_res.json().get("instances", [])
        if not instances:
            pytest.skip("No instances available")
        instance_id = instances[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/db-monitoring/slow-queries/{instance_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "slow_queries" in data, "Response should contain 'slow_queries'"
        assert "total" in data, "Response should contain 'total'"
        
        slow_queries = data["slow_queries"]
        if slow_queries:
            sq = slow_queries[0]
            assert "query" in sq or "duration_ms" in sq, "Slow query should have query or duration"
        
        print(f"PASS: GET /api/db-monitoring/slow-queries returned {data['total']} queries")
    
    def test_get_top_queries(self, auth_headers):
        """GET /api/db-monitoring/top-queries/{instance_id} - get aggregated top queries"""
        # Get an instance ID
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers)
        instances = list_res.json().get("instances", [])
        if not instances:
            pytest.skip("No instances available")
        instance_id = instances[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/db-monitoring/top-queries/{instance_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "top_queries" in data, "Response should contain 'top_queries'"
        
        top_queries = data["top_queries"]
        if top_queries:
            tq = top_queries[0]
            assert "fingerprint" in tq, "Top query should have fingerprint"
            assert "total_executions" in tq, "Top query should have total_executions"
            assert "avg_duration_ms" in tq, "Top query should have avg_duration_ms"
        
        print(f"PASS: GET /api/db-monitoring/top-queries returned {len(top_queries)} aggregated queries")


class TestLocksAPI:
    """Test locks/blocking sessions endpoints"""
    
    def test_get_locks(self, auth_headers):
        """GET /api/db-monitoring/locks/{instance_id} - get locks"""
        # Get an instance ID
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers)
        instances = list_res.json().get("instances", [])
        if not instances:
            pytest.skip("No instances available")
        instance_id = instances[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/db-monitoring/locks/{instance_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "locks" in data, "Response should contain 'locks'"
        assert "total" in data, "Response should contain 'total'"
        
        locks = data["locks"]
        if locks:
            lk = locks[0]
            # Lock should have either blocked/blocking PIDs or other lock info
            assert any(k in lk for k in ["blocked_pid", "blocking_pid", "lock_type", "wait_time_ms"]), "Lock should have lock info"
        
        print(f"PASS: GET /api/db-monitoring/locks returned {data['total']} locks")


class TestAlertRulesAPI:
    """Test alert rules CRUD"""
    
    def test_list_alert_rules(self, auth_headers):
        """GET /api/db-monitoring/alert-rules - should return default rules"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/alert-rules", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "rules" in data, "Response should contain 'rules'"
        rules = data["rules"]
        assert isinstance(rules, list), "rules should be a list"
        assert len(rules) >= 5, f"Expected at least 5 default rules, got {len(rules)}"
        
        # Verify rule structure
        if rules:
            rule = rules[0]
            assert "id" in rule, "Rule should have 'id'"
            assert "name" in rule, "Rule should have 'name'"
            assert "metric" in rule, "Rule should have 'metric'"
            assert "threshold" in rule, "Rule should have 'threshold'"
            assert "operator" in rule, "Rule should have 'operator'"
        
        print(f"PASS: GET /api/db-monitoring/alert-rules returned {len(rules)} rules")
    
    def test_create_alert_rule(self, auth_headers):
        """POST /api/db-monitoring/alert-rules - create a new alert rule"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "name": f"TEST_Rule_{test_id}",
            "metric": "cpu_usage",
            "operator": "gt",
            "threshold": 95.0,
            "severity": "critical",
            "enabled": True
        }
        response = requests.post(f"{BASE_URL}/api/db-monitoring/alert-rules", headers=auth_headers, json=payload)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        data = response.json()
        assert "id" in data, "Response should contain rule id"
        assert data["name"] == payload["name"], "Name should match"
        assert data["metric"] == "cpu_usage", "Metric should be cpu_usage"
        assert data["threshold"] == 95.0, "Threshold should be 95.0"
        print(f"PASS: POST /api/db-monitoring/alert-rules created rule {data['id'][:8]}")
        return data["id"]
    
    def test_delete_alert_rule(self, auth_headers):
        """DELETE /api/db-monitoring/alert-rules/{id} - delete an alert rule"""
        # First create a rule to delete
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "name": f"TEST_DELETE_Rule_{test_id}",
            "metric": "memory_usage",
            "operator": "gt",
            "threshold": 99.0,
            "severity": "warning"
        }
        create_res = requests.post(f"{BASE_URL}/api/db-monitoring/alert-rules", headers=auth_headers, json=payload)
        assert create_res.status_code in [200, 201]
        rule_id = create_res.json()["id"]
        
        # Delete the rule
        response = requests.delete(f"{BASE_URL}/api/db-monitoring/alert-rules/{rule_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("deleted") == True, "Response should confirm deletion"
        print(f"PASS: DELETE /api/db-monitoring/alert-rules/{rule_id[:8]} successful")
    
    def test_delete_nonexistent_rule(self, auth_headers):
        """DELETE /api/db-monitoring/alert-rules/{non-existent} - should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/db-monitoring/alert-rules/{fake_id}", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: DELETE non-existent rule returns 404")


class TestCleanup:
    """Cleanup test data after tests"""
    
    def test_cleanup_test_instances(self, auth_headers):
        """Cleanup: Remove TEST_ prefixed instances"""
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers)
        instances = list_res.json().get("instances", [])
        deleted = 0
        for inst in instances:
            if inst.get("name", "").startswith("TEST_"):
                del_res = requests.delete(f"{BASE_URL}/api/db-monitoring/instances/{inst['id']}", headers=auth_headers)
                if del_res.status_code == 200:
                    deleted += 1
        print(f"CLEANUP: Removed {deleted} TEST_ instances")
    
    def test_cleanup_test_alert_rules(self, auth_headers):
        """Cleanup: Remove TEST_ prefixed alert rules"""
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/alert-rules", headers=auth_headers)
        rules = list_res.json().get("rules", [])
        deleted = 0
        for rule in rules:
            if rule.get("name", "").startswith("TEST_"):
                del_res = requests.delete(f"{BASE_URL}/api/db-monitoring/alert-rules/{rule['id']}", headers=auth_headers)
                if del_res.status_code == 200:
                    deleted += 1
        print(f"CLEANUP: Removed {deleted} TEST_ alert rules")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
