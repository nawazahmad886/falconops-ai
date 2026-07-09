"""
FalconOps AI - Health Rules API Tests
Tests for Health Rule management endpoints at /api/health-rules
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://health-rules-engine.preview.emergentagent.com')


class TestHealthRulesAuth:
    """Authentication tests for health rules endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_token):
        self.client = api_client
        self.token = auth_token
        self.headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_get_health_rules_requires_auth(self, api_client):
        """GET /api/health-rules requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/health-rules")
        assert response.status_code == 401
    
    def test_create_health_rule_requires_auth(self, api_client):
        """POST /api/health-rules requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/health-rules", json={
            "name": "Test Rule",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 80
        })
        assert response.status_code == 401


class TestHealthRulesMetadata:
    """Tests for health rules metadata endpoints (operators, metrics, categories, templates)"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_token):
        self.client = api_client
        self.token = auth_token
        self.headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_get_operators_returns_8_operators(self):
        """GET /api/health-rules/operators returns 8 operators including BETWEEN and NOT BETWEEN"""
        response = self.client.get(f"{BASE_URL}/api/health-rules/operators", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "operators" in data
        operators = data["operators"]
        assert len(operators) == 8
        
        # Verify all required operators exist
        operator_ids = [op["id"] for op in operators]
        assert "greater_than" in operator_ids
        assert "less_than" in operator_ids
        assert "equals" in operator_ids
        assert "not_equals" in operator_ids
        assert "greater_than_or_equal" in operator_ids
        assert "less_than_or_equal" in operator_ids
        assert "between" in operator_ids
        assert "not_between" in operator_ids
        
        # Check BETWEEN has correct symbol
        between_op = next(op for op in operators if op["id"] == "between")
        assert between_op["symbol"] == "BETWEEN"
        
    def test_get_metrics_returns_metrics_across_4_categories(self):
        """GET /api/health-rules/metrics returns metrics across infrastructure, application, database, network"""
        response = self.client.get(f"{BASE_URL}/api/health-rules/metrics", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "metrics" in data
        metrics = data["metrics"]
        
        # Should have at least 20 metrics
        assert len(metrics) >= 20
        
        # Check all 4 categories present
        categories = set(m["category"] for m in metrics)
        assert "infrastructure" in categories
        assert "application" in categories
        assert "database" in categories
        assert "network" in categories
        
        # Check specific metrics exist
        metric_ids = [m["id"] for m in metrics]
        assert "cpu_usage" in metric_ids
        assert "memory_usage" in metric_ids
        assert "response_time" in metric_ids
        assert "error_rate" in metric_ids
        assert "active_sessions" in metric_ids
        assert "cache_hit_ratio" in metric_ids
        assert "network_in" in metric_ids
    
    def test_get_categories_returns_6_categories(self):
        """GET /api/health-rules/categories returns 6 categories"""
        response = self.client.get(f"{BASE_URL}/api/health-rules/categories", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data
        categories = data["categories"]
        assert len(categories) == 6
        
        category_ids = [c["id"] for c in categories]
        assert "infrastructure" in category_ids
        assert "application" in category_ids
        assert "database" in category_ids
        assert "network" in category_ids
        assert "security" in category_ids
        assert "custom" in category_ids
    
    def test_get_templates_returns_8_templates(self):
        """GET /api/health-rules/templates returns 8 templates"""
        response = self.client.get(f"{BASE_URL}/api/health-rules/templates", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) == 8
        
        template_ids = [t["id"] for t in templates]
        assert "high_cpu" in template_ids
        assert "critical_cpu" in template_ids
        assert "high_memory" in template_ids
        assert "disk_space_low" in template_ids
        assert "disk_space_critical" in template_ids
        assert "slow_response" in template_ids
        assert "high_error_rate" in template_ids
        assert "service_unavailable" in template_ids


class TestHealthRulesCRUD:
    """Tests for health rules CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_token):
        self.client = api_client
        self.token = auth_token
        self.headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        self.created_rule_ids = []
    
    def teardown_method(self, method):
        """Cleanup test-created rules after each test"""
        for rule_id in self.created_rule_ids:
            try:
                self.client.delete(f"{BASE_URL}/api/health-rules/{rule_id}", headers=self.headers)
            except:
                pass
    
    def test_get_health_rules_list(self):
        """GET /api/health-rules returns list of rules"""
        response = self.client.get(f"{BASE_URL}/api/health-rules", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "rules" in data
        assert "total" in data
        assert isinstance(data["rules"], list)
    
    def test_create_simple_health_rule(self):
        """POST /api/health-rules creates a simple rule"""
        rule_data = {
            "name": "TEST_Simple CPU Rule",
            "description": "Test rule for high CPU",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 80,
            "duration": 300,
            "severity": "warning",
            "category": "infrastructure",
            "component_type": "infrastructure",
            "action": "alert"
        }
        
        response = self.client.post(f"{BASE_URL}/api/health-rules", headers=self.headers, json=rule_data)
        assert response.status_code == 200
        
        data = response.json()
        self.created_rule_ids.append(data["id"])
        
        assert data["name"] == rule_data["name"]
        assert data["metric"] == rule_data["metric"]
        assert data["operator"] == rule_data["operator"]
        assert data["threshold"] == rule_data["threshold"]
        assert data["severity"] == rule_data["severity"]
        assert data["enabled"] == True  # Default
    
    def test_create_rule_with_compound_conditions(self):
        """POST /api/health-rules creates rule with AND/OR conditions"""
        rule_data = {
            "name": "TEST_Compound Rule",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 80,
            "conditions": [
                {"metric": "memory_usage", "operator": "greater_than", "threshold": 70, "logic": "AND"},
                {"metric": "disk_usage", "operator": "greater_than", "threshold": 85, "logic": "OR"}
            ],
            "severity": "critical",
            "category": "infrastructure",
            "action": "email"
        }
        
        response = self.client.post(f"{BASE_URL}/api/health-rules", headers=self.headers, json=rule_data)
        assert response.status_code == 200
        
        data = response.json()
        self.created_rule_ids.append(data["id"])
        
        assert len(data["conditions"]) == 2
        assert data["conditions"][0]["logic"] == "AND"
        assert data["conditions"][1]["logic"] == "OR"
    
    def test_create_rule_with_between_operator(self):
        """POST /api/health-rules creates rule with BETWEEN operator and threshold_max"""
        rule_data = {
            "name": "TEST_Between Rule",
            "metric": "cpu_usage",
            "operator": "between",
            "threshold": 50,
            "threshold_max": 80,
            "severity": "info",
            "category": "infrastructure"
        }
        
        response = self.client.post(f"{BASE_URL}/api/health-rules", headers=self.headers, json=rule_data)
        assert response.status_code == 200
        
        data = response.json()
        self.created_rule_ids.append(data["id"])
        
        assert data["operator"] == "between"
        assert data["threshold"] == 50
        assert data["threshold_max"] == 80
    
    def test_update_health_rule(self):
        """PUT /api/health-rules/{id} updates rule"""
        # First create a rule
        rule_data = {
            "name": "TEST_To Update",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 70,
            "severity": "warning"
        }
        create_response = self.client.post(f"{BASE_URL}/api/health-rules", headers=self.headers, json=rule_data)
        assert create_response.status_code == 200
        rule_id = create_response.json()["id"]
        self.created_rule_ids.append(rule_id)
        
        # Update the rule
        update_data = {
            "name": "TEST_Updated Rule",
            "threshold": 85
        }
        update_response = self.client.put(f"{BASE_URL}/api/health-rules/{rule_id}", headers=self.headers, json=update_data)
        assert update_response.status_code == 200
        
        data = update_response.json()
        assert data["name"] == "TEST_Updated Rule"
        assert data["threshold"] == 85
        assert data["updated_at"] is not None
    
    def test_delete_health_rule(self):
        """DELETE /api/health-rules/{id} deletes rule"""
        # Create a rule
        rule_data = {
            "name": "TEST_To Delete",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 70
        }
        create_response = self.client.post(f"{BASE_URL}/api/health-rules", headers=self.headers, json=rule_data)
        assert create_response.status_code == 200
        rule_id = create_response.json()["id"]
        
        # Delete it
        delete_response = self.client.delete(f"{BASE_URL}/api/health-rules/{rule_id}", headers=self.headers)
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Rule deleted"
        
        # Verify it's gone
        get_response = self.client.get(f"{BASE_URL}/api/health-rules/{rule_id}", headers=self.headers)
        assert get_response.status_code == 404
    
    def test_toggle_health_rule(self):
        """POST /api/health-rules/{id}/toggle toggles enabled status"""
        # Create a rule (enabled by default)
        rule_data = {
            "name": "TEST_To Toggle",
            "metric": "cpu_usage",
            "operator": "greater_than",
            "threshold": 70,
            "enabled": True
        }
        create_response = self.client.post(f"{BASE_URL}/api/health-rules", headers=self.headers, json=rule_data)
        assert create_response.status_code == 200
        rule_id = create_response.json()["id"]
        self.created_rule_ids.append(rule_id)
        
        # Toggle off
        toggle_response = self.client.post(f"{BASE_URL}/api/health-rules/{rule_id}/toggle", headers=self.headers)
        assert toggle_response.status_code == 200
        assert toggle_response.json()["enabled"] == False
        
        # Toggle back on
        toggle_response2 = self.client.post(f"{BASE_URL}/api/health-rules/{rule_id}/toggle", headers=self.headers)
        assert toggle_response2.status_code == 200
        assert toggle_response2.json()["enabled"] == True


class TestHealthRulesTemplates:
    """Tests for creating rules from templates"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_token):
        self.client = api_client
        self.token = auth_token
        self.headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        self.created_rule_ids = []
    
    def teardown_method(self, method):
        """Cleanup test-created rules"""
        for rule_id in self.created_rule_ids:
            try:
                self.client.delete(f"{BASE_URL}/api/health-rules/{rule_id}", headers=self.headers)
            except:
                pass
    
    def test_create_from_template_high_cpu(self):
        """POST /api/health-rules/from-template/high_cpu creates rule from template"""
        response = self.client.post(f"{BASE_URL}/api/health-rules/from-template/high_cpu", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        self.created_rule_ids.append(data["id"])
        
        assert data["name"] == "High CPU Usage"
        assert data["metric"] == "cpu_usage"
        assert data["operator"] == "greater_than"
        assert data["threshold"] == 85
        assert data["severity"] == "warning"
        assert data["category"] == "infrastructure"
    
    def test_create_from_invalid_template_returns_404(self):
        """POST /api/health-rules/from-template/{invalid} returns 404"""
        response = self.client.post(f"{BASE_URL}/api/health-rules/from-template/invalid_template", headers=self.headers)
        assert response.status_code == 404


class TestHealthRulesStats:
    """Tests for health rules statistics"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_token):
        self.client = api_client
        self.headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_get_stats_returns_statistics(self):
        """GET /api/health-rules/stats returns rule statistics"""
        response = self.client.get(f"{BASE_URL}/api/health-rules/stats", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "total_rules" in data
        assert "enabled_rules" in data
        assert "disabled_rules" in data
        assert "by_category" in data
        assert "by_severity" in data


class TestHealthRulesEvaluate:
    """Tests for rule evaluation endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_token):
        self.client = api_client
        self.headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_evaluate_metrics_against_rules(self):
        """POST /api/health-rules/evaluate evaluates metrics against enabled rules"""
        eval_data = {
            "metrics": {
                "cpu_usage": 95,
                "memory_usage": 80,
                "active_sessions": 150,
                "cache_hit_ratio": 85
            },
            "service": "test-service",
            "host": "test-host"
        }
        
        response = self.client.post(f"{BASE_URL}/api/health-rules/evaluate", headers=self.headers, json=eval_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "evaluated_at" in data
        assert "rules_evaluated" in data
        assert "violations" in data
        assert "alerts_to_trigger" in data
        assert isinstance(data["violations"], list)


# ============== FIXTURES ==============

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@falconapps.com",
        "password": "Admin@123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")
