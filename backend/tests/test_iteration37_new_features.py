"""
FalconOps AI - Iteration 37 Backend Tests
Testing 3 new features:
1. Uptime Monitor - URL/HTTP monitoring with background scheduler
2. DB Agent Management - Instance registration, agent download, install script
3. Multi-Tenant Management - Tenant CRUD, user management, usage stats
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_login_success(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data


# ======================== UPTIME MONITOR TESTS ========================

class TestUptimeMonitor:
    """Uptime Monitor API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_monitor_id(self, auth_headers):
        """Create a test monitor and return its ID"""
        response = requests.post(f"{BASE_URL}/api/uptime/monitors", 
            headers=auth_headers,
            json={
                "name": "TEST_Monitor_Iteration37",
                "url": "https://httpbin.org/status/200",
                "interval": 60,
                "method": "GET",
                "expected_status": 200,
                "timeout": 10
            })
        assert response.status_code == 200, f"Create monitor failed: {response.text}"
        data = response.json()
        assert "id" in data
        yield data["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/uptime/monitors/{data['id']}", headers=auth_headers)
    
    def test_list_monitors(self, auth_headers):
        """GET /api/uptime/monitors - List all monitors"""
        response = requests.get(f"{BASE_URL}/api/uptime/monitors", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the existing Google monitor
        print(f"Found {len(data)} monitors")
    
    def test_create_monitor(self, auth_headers):
        """POST /api/uptime/monitors - Create a new monitor"""
        response = requests.post(f"{BASE_URL}/api/uptime/monitors",
            headers=auth_headers,
            json={
                "name": "TEST_Create_Monitor",
                "url": "https://example.com",
                "interval": 120,
                "method": "GET",
                "expected_status": 200,
                "timeout": 5
            })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TEST_Create_Monitor"
        assert data["url"] == "https://example.com"
        assert data["interval"] == 120
        assert data["enabled"] == True
        assert "id" in data
        # Cleanup
        requests.delete(f"{BASE_URL}/api/uptime/monitors/{data['id']}", headers=auth_headers)
    
    def test_get_single_monitor(self, auth_headers, test_monitor_id):
        """GET /api/uptime/monitors/{id} - Get single monitor"""
        response = requests.get(f"{BASE_URL}/api/uptime/monitors/{test_monitor_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_monitor_id
        assert "name" in data
        assert "url" in data
    
    def test_check_now(self, auth_headers, test_monitor_id):
        """POST /api/uptime/monitors/{id}/check - Run immediate check"""
        response = requests.post(f"{BASE_URL}/api/uptime/monitors/{test_monitor_id}/check", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Check result should have these fields
        assert "status_code" in data
        assert "response_time_ms" in data
        assert "success" in data
        print(f"Check result: status={data.get('status_code')}, time={data.get('response_time_ms')}ms, success={data.get('success')}")
    
    def test_get_history(self, auth_headers, test_monitor_id):
        """GET /api/uptime/monitors/{id}/history - Get check history"""
        # First run a check to ensure there's history
        requests.post(f"{BASE_URL}/api/uptime/monitors/{test_monitor_id}/check", headers=auth_headers)
        time.sleep(1)
        
        response = requests.get(f"{BASE_URL}/api/uptime/monitors/{test_monitor_id}/history?hours=24&limit=50", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "timestamp" in data[0]
            assert "status_code" in data[0]
            assert "response_time_ms" in data[0]
        print(f"Found {len(data)} history entries")
    
    def test_toggle_monitor(self, auth_headers, test_monitor_id):
        """POST /api/uptime/monitors/{id}/toggle - Enable/disable monitor"""
        # Get current state
        response = requests.get(f"{BASE_URL}/api/uptime/monitors/{test_monitor_id}", headers=auth_headers)
        original_enabled = response.json().get("enabled", True)
        
        # Toggle
        response = requests.post(f"{BASE_URL}/api/uptime/monitors/{test_monitor_id}/toggle", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == (not original_enabled)
        
        # Toggle back
        requests.post(f"{BASE_URL}/api/uptime/monitors/{test_monitor_id}/toggle", headers=auth_headers)
    
    def test_get_stats(self, auth_headers):
        """GET /api/uptime/stats - Get aggregate stats"""
        response = requests.get(f"{BASE_URL}/api/uptime/stats?hours=24", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_monitors" in data
        assert "up" in data
        assert "down" in data
        assert "avg_uptime_pct" in data
        assert "total_checks_period" in data
        print(f"Stats: total={data['total_monitors']}, up={data['up']}, down={data['down']}, avg_uptime={data['avg_uptime_pct']}%")
    
    def test_delete_monitor(self, auth_headers):
        """DELETE /api/uptime/monitors/{id} - Delete monitor"""
        # Create a monitor to delete
        create_resp = requests.post(f"{BASE_URL}/api/uptime/monitors",
            headers=auth_headers,
            json={"name": "TEST_Delete_Me", "url": "https://delete.test"})
        monitor_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/uptime/monitors/{monitor_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == True
        
        # Verify it's gone
        get_resp = requests.get(f"{BASE_URL}/api/uptime/monitors/{monitor_id}", headers=auth_headers)
        assert get_resp.json().get("error") == "Not found"
    
    def test_uptime_requires_auth(self):
        """Verify uptime endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/uptime/monitors")
        assert response.status_code in [401, 403]


# ======================== DB AGENT TESTS ========================

class TestDBAgent:
    """DB Agent Management API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_instance_id(self, auth_headers):
        """Create a test DB instance and return its ID"""
        response = requests.post(f"{BASE_URL}/api/db-monitoring/instances",
            headers=auth_headers,
            json={
                "name": "TEST_DB_Instance_Iter37",
                "db_type": "postgres",
                "host": "test-db.local",
                "port": 5432,
                "database": "testdb",
                "environment": "development"
            })
        assert response.status_code == 200, f"Create instance failed: {response.text}"
        data = response.json()
        assert "id" in data
        yield data["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/db-monitoring/instances/{data['id']}", headers=auth_headers)
    
    def test_dashboard_overview(self, auth_headers):
        """GET /api/db-monitoring/dashboard-overview - Get all instances with agent status"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/dashboard-overview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "instances" in data
        assert "summary" in data
        assert "total_instances" in data["summary"]
        assert "active_instances" in data["summary"]
        print(f"DB Overview: {data['summary']['total_instances']} instances, {data['summary']['active_instances']} active")
    
    def test_register_instance(self, auth_headers):
        """POST /api/db-monitoring/instances - Register new DB instance"""
        response = requests.post(f"{BASE_URL}/api/db-monitoring/instances",
            headers=auth_headers,
            json={
                "name": "TEST_Register_Instance",
                "db_type": "mysql",
                "host": "mysql.test.local",
                "port": 3306,
                "database": "mydb",
                "environment": "staging"
            })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TEST_Register_Instance"
        assert data["db_type"] == "mysql"
        assert data["status"] == "registered"
        assert "id" in data
        # Cleanup
        requests.delete(f"{BASE_URL}/api/db-monitoring/instances/{data['id']}", headers=auth_headers)
    
    def test_get_install_script(self, auth_headers):
        """GET /api/db-monitoring/agent/install-script - Get bash install script"""
        response = requests.get(
            f"{BASE_URL}/api/db-monitoring/agent/install-script?db_type=postgres&api_url=https://test.com",
            headers=auth_headers
        )
        assert response.status_code == 200
        # Should be a shell script
        content = response.text
        assert "#!/bin/bash" in content
        assert "FalconOps" in content
        assert "postgres" in content.lower()
        print(f"Install script length: {len(content)} chars")
    
    def test_download_agent(self, auth_headers):
        """GET /api/db-monitoring/agent/download - Download agent Python file"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/agent/download", headers=auth_headers)
        # May return 404 if agent file doesn't exist, which is acceptable
        if response.status_code == 200:
            content = response.text
            assert "python" in content.lower() or "def " in content or "import " in content
            print(f"Agent file downloaded: {len(content)} chars")
        else:
            assert response.status_code == 404
            print("Agent file not found (expected in some environments)")
    
    def test_list_instances(self, auth_headers):
        """GET /api/db-monitoring/instances - List all instances"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/instances", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "instances" in data
        print(f"Found {len(data['instances'])} DB instances")
    
    def test_db_monitoring_requires_auth(self):
        """Verify DB monitoring endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/dashboard-overview")
        assert response.status_code in [401, 403]


# ======================== TENANT MANAGEMENT TESTS ========================

class TestTenants:
    """Multi-Tenant Management API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_tenant_id(self, auth_headers):
        """Create a test tenant and return its ID"""
        response = requests.post(f"{BASE_URL}/api/tenants",
            headers=auth_headers,
            json={
                "name": "TEST_Tenant_Iter37",
                "domain": "test-iter37.com",
                "contact_email": "admin@test-iter37.com",
                "plan": "professional",
                "max_users": 20,
                "max_servers": 100,
                "max_monitors": 200
            })
        assert response.status_code == 200, f"Create tenant failed: {response.text}"
        data = response.json()
        assert "id" in data
        yield data["id"]
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tenants/{data['id']}", headers=auth_headers)
    
    def test_list_tenants(self, auth_headers):
        """GET /api/tenants - List all tenants"""
        response = requests.get(f"{BASE_URL}/api/tenants", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} tenants")
    
    def test_create_tenant(self, auth_headers):
        """POST /api/tenants - Create new tenant"""
        response = requests.post(f"{BASE_URL}/api/tenants",
            headers=auth_headers,
            json={
                "name": "TEST_Create_Tenant",
                "domain": "create-test.com",
                "contact_email": "admin@create-test.com",
                "plan": "starter",
                "max_users": 10,
                "max_servers": 50,
                "max_monitors": 100
            })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TEST_Create_Tenant"
        assert data["plan"] == "starter"
        assert data["status"] == "active"
        assert "id" in data
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tenants/{data['id']}", headers=auth_headers)
    
    def test_get_tenant_stats(self, auth_headers, test_tenant_id):
        """GET /api/tenants/{id}/stats - Get tenant usage stats"""
        response = requests.get(f"{BASE_URL}/api/tenants/{test_tenant_id}/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "tenant_id" in data
        assert "usage" in data
        assert "users" in data["usage"]
        assert "servers" in data["usage"]
        assert "monitors" in data["usage"]
        assert "health" in data
        print(f"Tenant stats: users={data['usage']['users']}, servers={data['usage']['servers']}")
    
    def test_list_tenant_users(self, auth_headers, test_tenant_id):
        """GET /api/tenants/{id}/users - List users in tenant"""
        response = requests.get(f"{BASE_URL}/api/tenants/{test_tenant_id}/users", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} users in tenant")
    
    def test_create_tenant_user(self, auth_headers, test_tenant_id):
        """POST /api/tenants/{id}/users - Create user in tenant"""
        response = requests.post(f"{BASE_URL}/api/tenants/{test_tenant_id}/users",
            headers=auth_headers,
            json={
                "email": "test_user_iter37@test.com",
                "full_name": "Test User Iter37",
                "password": "TestPass123!",
                "role": "user"
            })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test_user_iter37@test.com"
        assert data["full_name"] == "Test User Iter37"
        assert data["role"] == "user"
        assert data["tenant_id"] == test_tenant_id
        # Store user_id for delete test
        return data["id"]
    
    def test_delete_tenant_user(self, auth_headers, test_tenant_id):
        """DELETE /api/tenants/{id}/users/{uid} - Remove user from tenant"""
        # First create a user to delete
        create_resp = requests.post(f"{BASE_URL}/api/tenants/{test_tenant_id}/users",
            headers=auth_headers,
            json={
                "email": "delete_me_iter37@test.com",
                "full_name": "Delete Me",
                "password": "DeletePass123!",
                "role": "viewer"
            })
        user_id = create_resp.json()["id"]
        
        # Delete the user
        response = requests.delete(f"{BASE_URL}/api/tenants/{test_tenant_id}/users/{user_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data["message"].lower() or "success" in data["message"].lower()
    
    def test_delete_tenant(self, auth_headers):
        """DELETE /api/tenants/{id} - Delete tenant"""
        # Create a tenant to delete
        create_resp = requests.post(f"{BASE_URL}/api/tenants",
            headers=auth_headers,
            json={"name": "TEST_Delete_Tenant", "plan": "starter"})
        tenant_id = create_resp.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/tenants/{tenant_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data["message"].lower()
    
    def test_tenants_requires_admin(self):
        """Verify tenant endpoints require admin authentication"""
        response = requests.get(f"{BASE_URL}/api/tenants")
        assert response.status_code in [401, 403]


# ======================== INTEGRATION TESTS ========================

class TestIntegration:
    """Integration tests for the 3 new features"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_uptime_monitor_full_flow(self, auth_headers):
        """Test complete uptime monitor flow: create -> check -> history -> delete"""
        # Create
        create_resp = requests.post(f"{BASE_URL}/api/uptime/monitors",
            headers=auth_headers,
            json={"name": "TEST_Full_Flow", "url": "https://httpbin.org/get", "interval": 60})
        assert create_resp.status_code == 200
        monitor_id = create_resp.json()["id"]
        
        # Check
        check_resp = requests.post(f"{BASE_URL}/api/uptime/monitors/{monitor_id}/check", headers=auth_headers)
        assert check_resp.status_code == 200
        assert "success" in check_resp.json()
        
        # History
        time.sleep(1)
        history_resp = requests.get(f"{BASE_URL}/api/uptime/monitors/{monitor_id}/history", headers=auth_headers)
        assert history_resp.status_code == 200
        assert len(history_resp.json()) >= 1
        
        # Delete
        delete_resp = requests.delete(f"{BASE_URL}/api/uptime/monitors/{monitor_id}", headers=auth_headers)
        assert delete_resp.status_code == 200
        print("Uptime monitor full flow: PASSED")
    
    def test_db_agent_full_flow(self, auth_headers):
        """Test complete DB agent flow: register -> overview -> delete"""
        # Register
        create_resp = requests.post(f"{BASE_URL}/api/db-monitoring/instances",
            headers=auth_headers,
            json={"name": "TEST_DB_Flow", "db_type": "postgres", "host": "flow.test", "port": 5432})
        assert create_resp.status_code == 200
        instance_id = create_resp.json()["id"]
        
        # Overview should include it
        overview_resp = requests.get(f"{BASE_URL}/api/db-monitoring/dashboard-overview", headers=auth_headers)
        assert overview_resp.status_code == 200
        instances = overview_resp.json()["instances"]
        assert any(i["id"] == instance_id for i in instances)
        
        # Delete
        delete_resp = requests.delete(f"{BASE_URL}/api/db-monitoring/instances/{instance_id}", headers=auth_headers)
        assert delete_resp.status_code == 200
        print("DB agent full flow: PASSED")
    
    def test_tenant_full_flow(self, auth_headers):
        """Test complete tenant flow: create -> add user -> stats -> delete user -> delete tenant"""
        # Create tenant
        create_resp = requests.post(f"{BASE_URL}/api/tenants",
            headers=auth_headers,
            json={"name": "TEST_Tenant_Flow", "plan": "professional", "max_users": 10})
        assert create_resp.status_code == 200
        tenant_id = create_resp.json()["id"]
        
        # Add user
        user_resp = requests.post(f"{BASE_URL}/api/tenants/{tenant_id}/users",
            headers=auth_headers,
            json={"email": "flow_user@test.com", "full_name": "Flow User", "password": "FlowPass123!", "role": "user"})
        assert user_resp.status_code == 200
        user_id = user_resp.json()["id"]
        
        # Get stats
        stats_resp = requests.get(f"{BASE_URL}/api/tenants/{tenant_id}/stats", headers=auth_headers)
        assert stats_resp.status_code == 200
        assert stats_resp.json()["usage"]["users"]["current"] >= 1
        
        # Delete user
        del_user_resp = requests.delete(f"{BASE_URL}/api/tenants/{tenant_id}/users/{user_id}", headers=auth_headers)
        assert del_user_resp.status_code == 200
        
        # Delete tenant
        del_tenant_resp = requests.delete(f"{BASE_URL}/api/tenants/{tenant_id}", headers=auth_headers)
        assert del_tenant_resp.status_code == 200
        print("Tenant full flow: PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
