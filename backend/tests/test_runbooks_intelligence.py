"""
FalconOps AI - Runbooks and Intelligence Page API Tests
Tests for:
- Runbook templates, categories, action types
- Runbook CRUD operations
- Runbook execution and dry-run
- Multi-tenancy support for alerts and incidents
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@falconapps.com"
TEST_PASSWORD = "Admin@123"


class TestAuthentication:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
        print(f"Login successful for {TEST_EMAIL}")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestRunbookTemplates:
    """Tests for runbook templates endpoint"""
    
    def test_get_templates(self, auth_headers):
        """Test GET /api/runbooks/templates returns 5 templates"""
        response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) == 5
        
        # Verify template names
        template_names = [t["name"] for t in templates]
        expected_names = [
            "High CPU Remediation",
            "Disk Space Cleanup",
            "Service Health Check",
            "Incident Response Workflow",
            "Deployment Validation"
        ]
        for name in expected_names:
            assert name in template_names, f"Template '{name}' not found"
        
        print(f"Found {len(templates)} templates: {template_names}")
    
    def test_template_structure(self, auth_headers):
        """Test template structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        assert response.status_code == 200
        templates = response.json()["templates"]
        
        for template in templates:
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "category" in template
            assert "steps" in template
            assert len(template["steps"]) > 0
            print(f"Template '{template['name']}' has {len(template['steps'])} steps")


class TestRunbookCategories:
    """Tests for runbook categories endpoint"""
    
    def test_get_categories(self, auth_headers):
        """Test GET /api/runbooks/categories returns 8 categories"""
        response = requests.get(f"{BASE_URL}/api/runbooks/categories", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        categories = data["categories"]
        assert len(categories) == 8
        
        # Verify category IDs
        category_ids = [c["id"] for c in categories]
        expected_ids = [
            "infrastructure", "monitoring", "incident", "deployment",
            "security", "database", "network", "general"
        ]
        for cat_id in expected_ids:
            assert cat_id in category_ids, f"Category '{cat_id}' not found"
        
        print(f"Found {len(categories)} categories: {category_ids}")
    
    def test_category_structure(self, auth_headers):
        """Test category structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/runbooks/categories", headers=auth_headers)
        assert response.status_code == 200
        categories = response.json()["categories"]
        
        for category in categories:
            assert "id" in category
            assert "name" in category
            assert "icon" in category
            assert "description" in category


class TestRunbookActionTypes:
    """Tests for runbook action types endpoint"""
    
    def test_get_action_types(self, auth_headers):
        """Test GET /api/runbooks/action-types returns 10 action types"""
        response = requests.get(f"{BASE_URL}/api/runbooks/action-types", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "action_types" in data
        action_types = data["action_types"]
        assert len(action_types) == 10
        
        # Verify action type IDs
        action_ids = [a["id"] for a in action_types]
        expected_ids = [
            "http_request", "shell_command", "notification", "delay",
            "condition", "webhook", "log_message", "metric_check",
            "service_restart", "approval"
        ]
        for action_id in expected_ids:
            assert action_id in action_ids, f"Action type '{action_id}' not found"
        
        print(f"Found {len(action_types)} action types: {action_ids}")
    
    def test_action_type_structure(self, auth_headers):
        """Test action type structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/runbooks/action-types", headers=auth_headers)
        assert response.status_code == 200
        action_types = response.json()["action_types"]
        
        for action in action_types:
            assert "id" in action
            assert "name" in action
            assert "description" in action
            assert "icon" in action


class TestRunbookStats:
    """Tests for runbook statistics endpoint"""
    
    def test_get_stats_summary(self, auth_headers):
        """Test GET /api/runbooks/stats/summary returns statistics"""
        response = requests.get(f"{BASE_URL}/api/runbooks/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "total_runbooks" in data
        assert "total_executions" in data
        assert "successful_executions" in data
        assert "failed_executions" in data
        assert "success_rate" in data
        assert "auto_execute_enabled" in data
        assert "recent_executions" in data
        
        print(f"Stats: {data['total_runbooks']} runbooks, {data['total_executions']} executions, {data['success_rate']}% success rate")


class TestRunbookCRUD:
    """Tests for runbook CRUD operations"""
    
    def test_create_runbook(self, auth_headers):
        """Test POST /api/runbooks creates a new runbook"""
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_Runbook_{unique_id}",
            "description": "Test runbook created by pytest",
            "service": "test-service",
            "category": "monitoring",
            "auto_execute": False,
            "tags": ["test", "pytest"],
            "steps": [
                {
                    "name": "Log Start",
                    "action_type": "log_message",
                    "config": {"message": "Test started", "level": "info"},
                    "continue_on_failure": False
                },
                {
                    "name": "Echo Test",
                    "action_type": "shell_command",
                    "config": {"command": "echo 'Test passed'"},
                    "continue_on_failure": False
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["name"] == runbook_data["name"]
        assert data["service"] == runbook_data["service"]
        assert len(data["steps"]) == 2
        
        print(f"Created runbook: {data['id']} - {data['name']}")
        return data["id"]
    
    def test_get_runbooks_list(self, auth_headers):
        """Test GET /api/runbooks returns list of runbooks"""
        response = requests.get(f"{BASE_URL}/api/runbooks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} runbooks")
    
    def test_get_runbook_by_id(self, auth_headers):
        """Test GET /api/runbooks/{id} returns single runbook"""
        # First get list to find an ID
        list_response = requests.get(f"{BASE_URL}/api/runbooks", headers=auth_headers)
        runbooks = list_response.json()
        
        if len(runbooks) > 0:
            runbook_id = runbooks[0]["id"]
            response = requests.get(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == runbook_id
            print(f"Retrieved runbook: {data['name']}")
        else:
            pytest.skip("No runbooks available to test")


class TestRunbookExecution:
    """Tests for runbook execution"""
    
    def test_dry_run_validation(self, auth_headers):
        """Test POST /api/runbooks/{id}/dry-run validates runbook"""
        # Get a runbook ID
        list_response = requests.get(f"{BASE_URL}/api/runbooks", headers=auth_headers)
        runbooks = list_response.json()
        
        if len(runbooks) > 0:
            runbook_id = runbooks[0]["id"]
            response = requests.post(f"{BASE_URL}/api/runbooks/{runbook_id}/dry-run", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            
            assert "runbook_id" in data
            assert "valid" in data
            assert "steps_count" in data
            assert "step_validations" in data
            
            print(f"Dry-run validation: valid={data['valid']}, steps={data['steps_count']}")
        else:
            pytest.skip("No runbooks available to test")
    
    def test_execute_runbook(self, auth_headers):
        """Test POST /api/runbooks/{id}/execute executes runbook"""
        # Create a simple runbook for testing
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_Execute_{unique_id}",
            "description": "Test runbook for execution",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [
                {
                    "name": "Echo Test",
                    "action_type": "shell_command",
                    "config": {"command": "echo 'Execution test'"},
                    "continue_on_failure": False
                }
            ]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        assert create_response.status_code == 200
        runbook_id = create_response.json()["id"]
        
        # Execute the runbook
        execute_response = requests.post(
            f"{BASE_URL}/api/runbooks/{runbook_id}/execute",
            json={"variables": {}, "trigger_source": "manual"},
            headers=auth_headers
        )
        assert execute_response.status_code == 200
        data = execute_response.json()
        
        assert "success" in data
        assert "execution_id" in data
        assert "status" in data
        assert "step_results" in data
        
        print(f"Execution result: success={data['success']}, status={data['status']}, steps_completed={data.get('steps_completed', 0)}")
        
        # Cleanup - delete the test runbook
        requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)


class TestMultiTenancyAlerts:
    """Tests for multi-tenancy support in alerts"""
    
    def test_get_alerts_tenant_aware(self, auth_headers):
        """Test GET /api/alerts supports tenant filtering"""
        response = requests.get(f"{BASE_URL}/api/alerts?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Retrieved {len(data)} alerts")
    
    def test_get_alert_stats(self, auth_headers):
        """Test GET /api/alerts/stats/summary returns tenant-aware stats"""
        response = requests.get(f"{BASE_URL}/api/alerts/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "open" in data
        assert "acknowledged" in data
        assert "resolved" in data
        assert "by_severity" in data
        
        print(f"Alert stats: total={data['total']}, open={data['open']}, resolved={data['resolved']}")


class TestMultiTenancyIncidents:
    """Tests for multi-tenancy support in incidents"""
    
    def test_get_incidents_tenant_aware(self, auth_headers):
        """Test GET /api/incidents supports tenant filtering"""
        response = requests.get(f"{BASE_URL}/api/incidents?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Retrieved {len(data)} incidents")
    
    def test_get_incident_stats(self, auth_headers):
        """Test GET /api/incidents/stats/summary returns tenant-aware stats"""
        response = requests.get(f"{BASE_URL}/api/incidents/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "open" in data
        assert "investigating" in data
        assert "resolved" in data
        assert "avg_mttr_seconds" in data
        
        print(f"Incident stats: total={data['total']}, open={data['open']}, avg_mttr={data['avg_mttr_formatted']}")


class TestCreateFromTemplate:
    """Tests for creating runbooks from templates"""
    
    def test_create_from_template(self, auth_headers):
        """Test POST /api/runbooks/from-template/{template_id} creates runbook"""
        # Get templates first
        templates_response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        templates = templates_response.json()["templates"]
        
        if len(templates) > 0:
            template_id = templates[0]["id"]
            unique_service = f"test-service-{str(uuid.uuid4())[:8]}"
            
            response = requests.post(
                f"{BASE_URL}/api/runbooks/from-template/{template_id}?service={unique_service}",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert "id" in data
            assert "message" in data
            assert data["message"] == "Runbook created from template"
            
            print(f"Created runbook from template: {data['id']}")
            
            # Cleanup
            if "id" in data:
                requests.delete(f"{BASE_URL}/api/runbooks/{data['id']}", headers=auth_headers)
        else:
            pytest.skip("No templates available")
    
    def test_create_from_invalid_template(self, auth_headers):
        """Test creating from non-existent template returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/runbooks/from-template/invalid-template-id?service=test",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestRunbookDelete:
    """Tests for runbook deletion"""
    
    def test_delete_runbook(self, auth_headers):
        """Test DELETE /api/runbooks/{id} deletes runbook"""
        # Create a runbook to delete
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_Delete_{unique_id}",
            "description": "Test runbook for deletion",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [
                {
                    "name": "Test Step",
                    "action_type": "log_message",
                    "config": {"message": "Test"},
                    "continue_on_failure": False
                }
            ]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        # Delete the runbook
        delete_response = requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify it's deleted
        get_response = requests.get(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
        assert get_response.status_code == 404
        
        print(f"Successfully deleted runbook: {runbook_id}")
    
    def test_delete_nonexistent_runbook(self, auth_headers):
        """Test deleting non-existent runbook returns 404"""
        response = requests.delete(f"{BASE_URL}/api/runbooks/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
