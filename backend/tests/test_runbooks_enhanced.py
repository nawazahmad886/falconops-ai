"""
FalconOps AI - Enhanced Runbook Automation Engine Tests
Tests for:
- 17 action types (7 new: ssh_command, database_query, kubernetes, script, set_variable, loop, parallel)
- 14 templates (9 new including DB backup, SSL check, K8s rollout)
- Cron-based scheduled execution with 13 presets
- Schedule set/remove endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@falconapps.com"
TEST_PASSWORD = "Admin@123"


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


class TestEnhancedActionTypes:
    """Tests for 17 action types (7 new)"""
    
    def test_get_action_types_count(self, auth_headers):
        """Test GET /api/runbooks/action-types returns 17 action types"""
        response = requests.get(f"{BASE_URL}/api/runbooks/action-types", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "action_types" in data
        action_types = data["action_types"]
        assert len(action_types) == 17, f"Expected 17 action types, got {len(action_types)}"
        print(f"Found {len(action_types)} action types")
    
    def test_original_action_types_present(self, auth_headers):
        """Test original 10 action types are present"""
        response = requests.get(f"{BASE_URL}/api/runbooks/action-types", headers=auth_headers)
        action_types = response.json()["action_types"]
        action_ids = [a["id"] for a in action_types]
        
        original_types = [
            "http_request", "shell_command", "notification", "delay",
            "condition", "webhook", "log_message", "metric_check",
            "service_restart", "approval"
        ]
        for action_id in original_types:
            assert action_id in action_ids, f"Original action type '{action_id}' not found"
        print("All 10 original action types present")
    
    def test_new_action_types_present(self, auth_headers):
        """Test 7 new action types are present"""
        response = requests.get(f"{BASE_URL}/api/runbooks/action-types", headers=auth_headers)
        action_types = response.json()["action_types"]
        action_ids = [a["id"] for a in action_types]
        
        new_types = [
            "ssh_command", "database_query", "kubernetes", 
            "script", "set_variable", "loop", "parallel"
        ]
        for action_id in new_types:
            assert action_id in action_ids, f"New action type '{action_id}' not found"
        print("All 7 new action types present: ssh_command, database_query, kubernetes, script, set_variable, loop, parallel")
    
    def test_action_type_structure(self, auth_headers):
        """Test action type structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/runbooks/action-types", headers=auth_headers)
        action_types = response.json()["action_types"]
        
        for action in action_types:
            assert "id" in action
            assert "name" in action
            assert "description" in action
            assert "icon" in action


class TestEnhancedTemplates:
    """Tests for 14 templates (9 new)"""
    
    def test_get_templates_count(self, auth_headers):
        """Test GET /api/runbooks/templates returns 14 templates"""
        response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) == 14, f"Expected 14 templates, got {len(templates)}"
        print(f"Found {len(templates)} templates")
    
    def test_original_templates_present(self, auth_headers):
        """Test original 5 templates are present"""
        response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        templates = response.json()["templates"]
        template_names = [t["name"] for t in templates]
        
        original_templates = [
            "High CPU Remediation",
            "Disk Space Cleanup",
            "Service Health Check",
            "Incident Response Workflow",
            "Deployment Validation"
        ]
        for name in original_templates:
            assert name in template_names, f"Original template '{name}' not found"
        print("All 5 original templates present")
    
    def test_new_templates_present(self, auth_headers):
        """Test 9 new templates are present"""
        response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        templates = response.json()["templates"]
        template_names = [t["name"] for t in templates]
        
        new_templates = [
            "Memory Leak Detection",
            "SSL Certificate Check",
            "Outage Response",
            "Kubernetes Rollout",
            "Database Backup",
            "Database Maintenance",
            "Security Vulnerability Scan",
            "Access Audit",
            "Network Health Check"
        ]
        for name in new_templates:
            assert name in template_names, f"New template '{name}' not found"
        print("All 9 new templates present")
    
    def test_template_categories(self, auth_headers):
        """Test templates cover all categories"""
        response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        templates = response.json()["templates"]
        categories = set(t["category"] for t in templates)
        
        expected_categories = {"infrastructure", "monitoring", "incident", "deployment", "database", "security", "network"}
        for cat in expected_categories:
            assert cat in categories, f"Category '{cat}' not covered by templates"
        print(f"Templates cover categories: {categories}")
    
    def test_template_structure(self, auth_headers):
        """Test template structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/runbooks/templates", headers=auth_headers)
        templates = response.json()["templates"]
        
        for template in templates:
            assert "id" in template
            assert "name" in template
            assert "description" in template
            assert "category" in template
            assert "steps" in template
            assert len(template["steps"]) > 0


class TestSchedulePresets:
    """Tests for cron schedule presets"""
    
    def test_get_schedule_presets_count(self, auth_headers):
        """Test GET /api/runbooks/schedules/presets returns 13 presets"""
        response = requests.get(f"{BASE_URL}/api/runbooks/schedules/presets", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        presets = data["presets"]
        assert len(presets) == 13, f"Expected 13 presets, got {len(presets)}"
        print(f"Found {len(presets)} schedule presets")
    
    def test_preset_structure(self, auth_headers):
        """Test preset structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/runbooks/schedules/presets", headers=auth_headers)
        presets = response.json()["presets"]
        
        for preset in presets:
            assert "name" in preset
            assert "cron" in preset
            assert "description" in preset
    
    def test_common_presets_present(self, auth_headers):
        """Test common schedule presets are present"""
        response = requests.get(f"{BASE_URL}/api/runbooks/schedules/presets", headers=auth_headers)
        presets = response.json()["presets"]
        preset_names = [p["name"] for p in presets]
        
        expected_presets = [
            "Every minute", "Every 5 minutes", "Every 15 minutes",
            "Every hour", "Daily at midnight", "Weekly (Monday)", "Monthly (1st)"
        ]
        for name in expected_presets:
            assert name in preset_names, f"Preset '{name}' not found"
        print("Common schedule presets present")


class TestScheduledRunbooks:
    """Tests for scheduled runbooks endpoint"""
    
    def test_get_scheduled_runbooks(self, auth_headers):
        """Test GET /api/runbooks/scheduled returns scheduled runbooks list"""
        response = requests.get(f"{BASE_URL}/api/runbooks/scheduled", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "scheduled_runbooks" in data
        assert "total" in data
        print(f"Found {data['total']} scheduled runbooks")
    
    def test_scheduled_runbook_structure(self, auth_headers):
        """Test scheduled runbook has schedule field"""
        response = requests.get(f"{BASE_URL}/api/runbooks/scheduled", headers=auth_headers)
        data = response.json()
        
        if data["total"] > 0:
            runbook = data["scheduled_runbooks"][0]
            assert "schedule" in runbook
            assert runbook["schedule"]["enabled"] == True
            assert "cron_expression" in runbook["schedule"]
            assert "timezone" in runbook["schedule"]
            print(f"Scheduled runbook '{runbook['name']}' has cron: {runbook['schedule']['cron_expression']}")


class TestScheduleManagement:
    """Tests for schedule set/remove endpoints"""
    
    def test_set_schedule(self, auth_headers):
        """Test POST /api/runbooks/{id}/schedule sets schedule"""
        # Create a test runbook
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_Schedule_{unique_id}",
            "description": "Test scheduling",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{"name": "Test", "action_type": "log_message", "config": {"message": "test"}}]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        assert create_response.status_code == 200
        runbook_id = create_response.json()["id"]
        
        try:
            # Set schedule
            schedule_data = {
                "enabled": True,
                "cron_expression": "0 * * * *",
                "timezone": "UTC"
            }
            response = requests.post(
                f"{BASE_URL}/api/runbooks/{runbook_id}/schedule",
                json=schedule_data,
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["message"] == "Schedule updated"
            assert data["runbook_id"] == runbook_id
            assert data["schedule"]["enabled"] == True
            assert data["schedule"]["cron_expression"] == "0 * * * *"
            assert "next_run" in data["schedule"]
            
            print(f"Schedule set successfully: {data['schedule']['cron_expression']}")
            
            # Verify schedule is set on runbook
            get_response = requests.get(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
            runbook = get_response.json()
            assert runbook["schedule"] is not None
            assert runbook["schedule"]["enabled"] == True
            
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
    
    def test_remove_schedule(self, auth_headers):
        """Test DELETE /api/runbooks/{id}/schedule removes schedule"""
        # Create a test runbook with schedule
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_RemoveSchedule_{unique_id}",
            "description": "Test schedule removal",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{"name": "Test", "action_type": "log_message", "config": {"message": "test"}}]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        try:
            # Set schedule first
            schedule_data = {"enabled": True, "cron_expression": "*/30 * * * *", "timezone": "UTC"}
            requests.post(f"{BASE_URL}/api/runbooks/{runbook_id}/schedule", json=schedule_data, headers=auth_headers)
            
            # Remove schedule
            response = requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}/schedule", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            
            assert data["message"] == "Schedule removed"
            assert data["runbook_id"] == runbook_id
            
            # Verify schedule is removed
            get_response = requests.get(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
            runbook = get_response.json()
            assert runbook["schedule"] is None
            
            print("Schedule removed successfully")
            
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)


class TestNewActionTypeExecution:
    """Tests for executing runbooks with new action types"""
    
    def test_execute_ssh_command(self, auth_headers):
        """Test executing runbook with ssh_command action (simulated)"""
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_SSH_{unique_id}",
            "description": "Test SSH command",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{
                "name": "SSH Test",
                "action_type": "ssh_command",
                "config": {"host": "test.example.com", "username": "admin", "command": "ls -la"}
            }]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/runbooks/{runbook_id}/execute",
                json={"variables": {}, "trigger_source": "manual"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] == True
            assert data["steps_completed"] == 1
            assert data["step_results"][0]["action_type"] == "ssh_command"
            assert data["step_results"][0]["status"] == "success"
            assert data["step_results"][0]["output"]["simulated"] == True
            
            print("SSH command executed (simulated) successfully")
            
        finally:
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
    
    def test_execute_kubernetes_action(self, auth_headers):
        """Test executing runbook with kubernetes action (simulated)"""
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_K8s_{unique_id}",
            "description": "Test Kubernetes action",
            "service": "test-service",
            "category": "deployment",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{
                "name": "K8s Get Pods",
                "action_type": "kubernetes",
                "config": {"action": "get", "resource_type": "pods", "namespace": "default"}
            }]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/runbooks/{runbook_id}/execute",
                json={"variables": {}, "trigger_source": "manual"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] == True
            assert data["step_results"][0]["action_type"] == "kubernetes"
            assert data["step_results"][0]["status"] == "success"
            assert "kubectl" in data["step_results"][0]["output"]["command"]
            
            print("Kubernetes action executed (simulated) successfully")
            
        finally:
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
    
    def test_execute_database_query(self, auth_headers):
        """Test executing runbook with database_query action (simulated)"""
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_DB_{unique_id}",
            "description": "Test database query",
            "service": "test-service",
            "category": "database",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{
                "name": "DB Query",
                "action_type": "database_query",
                "config": {"database_type": "mongodb", "database": "test_db", "query": "db.test.find()"}
            }]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/runbooks/{runbook_id}/execute",
                json={"variables": {}, "trigger_source": "manual"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] == True
            assert data["step_results"][0]["action_type"] == "database_query"
            assert data["step_results"][0]["status"] == "success"
            assert data["step_results"][0]["output"]["simulated"] == True
            
            print("Database query executed (simulated) successfully")
            
        finally:
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
    
    def test_execute_script_action(self, auth_headers):
        """Test executing runbook with script action (simulated)"""
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_Script_{unique_id}",
            "description": "Test script execution",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{
                "name": "Run Script",
                "action_type": "script",
                "config": {"script_type": "bash", "script": "echo 'Hello World'"}
            }]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/runbooks/{runbook_id}/execute",
                json={"variables": {}, "trigger_source": "manual"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] == True
            assert data["step_results"][0]["action_type"] == "script"
            assert data["step_results"][0]["status"] == "success"
            
            print("Script action executed (simulated) successfully")
            
        finally:
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
    
    def test_execute_set_variable(self, auth_headers):
        """Test executing runbook with set_variable action"""
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_SetVar_{unique_id}",
            "description": "Test set variable",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{
                "name": "Set Variable",
                "action_type": "set_variable",
                "config": {"name": "test_var", "value": "test_value"}
            }]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/runbooks/{runbook_id}/execute",
                json={"variables": {}, "trigger_source": "manual"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] == True
            assert data["step_results"][0]["action_type"] == "set_variable"
            assert data["step_results"][0]["status"] == "success"
            assert data["step_results"][0]["output"]["variable_name"] == "test_var"
            assert data["step_results"][0]["output"]["variable_value"] == "test_value"
            
            print("Set variable action executed successfully")
            
        finally:
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
    
    def test_execute_loop_action(self, auth_headers):
        """Test executing runbook with loop action"""
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_Loop_{unique_id}",
            "description": "Test loop action",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{
                "name": "Loop Test",
                "action_type": "loop",
                "config": {"items": ["item1", "item2", "item3"], "max_iterations": 10}
            }]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/runbooks/{runbook_id}/execute",
                json={"variables": {}, "trigger_source": "manual"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] == True
            assert data["step_results"][0]["action_type"] == "loop"
            assert data["step_results"][0]["status"] == "success"
            assert data["step_results"][0]["output"]["iterations_completed"] == 3
            
            print("Loop action executed successfully")
            
        finally:
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)
    
    def test_execute_parallel_action(self, auth_headers):
        """Test executing runbook with parallel action (simulated)"""
        unique_id = str(uuid.uuid4())[:8]
        runbook_data = {
            "name": f"TEST_Parallel_{unique_id}",
            "description": "Test parallel action",
            "service": "test-service",
            "category": "general",
            "auto_execute": False,
            "tags": ["test"],
            "steps": [{
                "name": "Parallel Test",
                "action_type": "parallel",
                "config": {
                    "actions": [
                        {"action_type": "log_message", "config": {"message": "Action 1"}},
                        {"action_type": "log_message", "config": {"message": "Action 2"}}
                    ]
                }
            }]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/runbooks", json=runbook_data, headers=auth_headers)
        runbook_id = create_response.json()["id"]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/runbooks/{runbook_id}/execute",
                json={"variables": {}, "trigger_source": "manual"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] == True
            assert data["step_results"][0]["action_type"] == "parallel"
            assert data["step_results"][0]["status"] == "success"
            assert data["step_results"][0]["output"]["parallel_actions"] == 2
            
            print("Parallel action executed (simulated) successfully")
            
        finally:
            requests.delete(f"{BASE_URL}/api/runbooks/{runbook_id}", headers=auth_headers)


class TestRunbookStats:
    """Tests for runbook statistics"""
    
    def test_get_stats_summary(self, auth_headers):
        """Test GET /api/runbooks/stats/summary returns statistics"""
        response = requests.get(f"{BASE_URL}/api/runbooks/stats/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "total_runbooks" in data
        assert "total_executions" in data
        assert "successful_executions" in data
        assert "failed_executions" in data
        assert "success_rate" in data
        assert "auto_execute_enabled" in data
        assert "recent_executions" in data
        
        print(f"Stats: {data['total_runbooks']} runbooks, {data['total_executions']} executions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
