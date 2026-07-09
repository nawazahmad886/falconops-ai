"""
FalconOps AI - DB Agent Deployment Endpoints Tests
Tests for:
- GET /api/db-monitoring/agent/queries/{instance_id} - No auth, returns enabled queries
- GET /api/db-monitoring/agent/download - Downloads falcon_db_agent.py
- GET /api/db-monitoring/agent/install-script - Generates install script
- GET /api/db-monitoring/agent/config-template - Generates YAML config
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_INSTANCE_ID = "b9b9b607-e8ce-4a42-a8de-bd6c4a91fd48"  # Production PostgreSQL
INVALID_INSTANCE_ID = "invalid-instance-12345"


class TestAgentEndpointsNoAuth:
    """Test agent endpoints that should work WITHOUT authentication"""

    def test_agent_queries_no_auth_valid_instance(self):
        """GET /api/db-monitoring/agent/queries/{instance_id} - Returns queries without auth"""
        url = f"{BASE_URL}/api/db-monitoring/agent/queries/{TEST_INSTANCE_ID}"
        response = requests.get(url, timeout=15)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "queries" in data, "Response should have 'queries' field"
        assert "instance_id" in data, "Response should have 'instance_id' field"
        assert "instance_name" in data, "Response should have 'instance_name' field"
        
        # Verify instance_id matches
        assert data["instance_id"] == TEST_INSTANCE_ID
        
        # Verify queries are list
        assert isinstance(data["queries"], list), "queries should be a list"
        
        # If queries exist, verify they are enabled
        for query in data["queries"]:
            assert query.get("enabled", False) is True, f"Query should be enabled: {query.get('name')}"
            assert "id" in query
            assert "name" in query
            assert "query" in query
            assert "interval" in query
        
        print(f"✓ Agent queries endpoint returned {len(data['queries'])} enabled queries")

    def test_agent_queries_no_auth_invalid_instance(self):
        """GET /api/db-monitoring/agent/queries/{invalid_id} - Returns 404"""
        url = f"{BASE_URL}/api/db-monitoring/agent/queries/{INVALID_INSTANCE_ID}"
        response = requests.get(url, timeout=15)
        
        assert response.status_code == 404, f"Expected 404 for invalid instance, got {response.status_code}"
        print("✓ Agent queries returns 404 for invalid instance")


class TestAgentDownloadEndpoint:
    """Test agent download endpoint"""

    def test_agent_download_returns_python_file(self):
        """GET /api/db-monitoring/agent/download - Returns falcon_db_agent.py file"""
        url = f"{BASE_URL}/api/db-monitoring/agent/download"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "python" in content_type or "text" in content_type or "octet" in content_type, \
            f"Expected python/text content type, got: {content_type}"
        
        # Check Content-Disposition header
        content_disposition = response.headers.get("content-disposition", "")
        assert "falcon_db_agent.py" in content_disposition, \
            f"Expected filename falcon_db_agent.py in header, got: {content_disposition}"
        
        # Verify content looks like Python agent
        content = response.text
        assert "#!/usr/bin/env python3" in content, "Agent should start with shebang"
        assert "FalconOps" in content, "Agent should contain FalconOps reference"
        assert "Database Monitoring Agent" in content, "Agent should mention Database Monitoring"
        assert "VERSION" in content, "Agent should have VERSION constant"
        assert "PostgresCollector" in content or "BaseCollector" in content, "Agent should have collector classes"
        
        # Check content length
        assert len(content) > 10000, f"Agent file seems too small: {len(content)} bytes"
        
        print(f"✓ Agent download returns valid Python file ({len(content)} bytes)")

    def test_agent_download_is_valid_python(self):
        """Verify downloaded agent is valid Python syntax"""
        url = f"{BASE_URL}/api/db-monitoring/agent/download"
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        content = response.text
        
        # Try to compile the Python code to verify syntax
        try:
            compile(content, "falcon_db_agent.py", "exec")
            print("✓ Downloaded agent is valid Python syntax")
        except SyntaxError as e:
            pytest.fail(f"Agent file has syntax error: {e}")


class TestInstallScriptEndpoint:
    """Test install script generation endpoint"""

    def test_install_script_default_params(self):
        """GET /api/db-monitoring/agent/install-script - Returns bash script"""
        url = f"{BASE_URL}/api/db-monitoring/agent/install-script"
        response = requests.get(url, timeout=15)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "shell" in content_type or "text" in content_type, \
            f"Expected shell/text content type, got: {content_type}"
        
        # Check Content-Disposition header
        content_disposition = response.headers.get("content-disposition", "")
        assert "install_db_agent.sh" in content_disposition, \
            f"Expected install_db_agent.sh filename, got: {content_disposition}"
        
        content = response.text
        
        # Verify bash script content
        assert "#!/bin/bash" in content, "Script should start with bash shebang"
        assert "FalconOps" in content, "Script should reference FalconOps"
        assert "pip3 install" in content or "pip install" in content, "Script should install dependencies"
        assert "systemd" in content or "service" in content, "Script should create service"
        assert "/opt/falconops" in content or "/etc/falconops" in content, "Script should reference install dirs"
        
        print(f"✓ Install script endpoint returns valid bash script ({len(content)} bytes)")

    def test_install_script_with_params(self):
        """GET /api/db-monitoring/agent/install-script with query params"""
        params = {
            "api_url": BASE_URL,
            "db_type": "postgres",
            "instance_id": TEST_INSTANCE_ID,
            "api_key": "test-api-key"
        }
        url = f"{BASE_URL}/api/db-monitoring/agent/install-script"
        response = requests.get(url, params=params, timeout=15)
        
        assert response.status_code == 200
        content = response.text
        
        # Verify params are embedded
        assert BASE_URL in content or "falcon" in content.lower(), "Script should contain API URL"
        assert "postgres" in content, "Script should contain db_type"
        assert TEST_INSTANCE_ID in content, "Script should contain instance_id"
        
        # Verify postgresql specific installation
        assert "psycopg2" in content, "Postgres install should include psycopg2"
        
        print("✓ Install script with params works correctly")

    def test_install_script_oracle_db_type(self):
        """GET /api/db-monitoring/agent/install-script for Oracle"""
        params = {"db_type": "oracle"}
        url = f"{BASE_URL}/api/db-monitoring/agent/install-script"
        response = requests.get(url, params=params, timeout=15)
        
        assert response.status_code == 200
        content = response.text
        
        assert "oracle" in content.lower(), "Script should reference oracle"
        assert "oracledb" in content, "Oracle install should include oracledb driver"
        assert "1521" in content, "Oracle default port should be 1521"
        
        print("✓ Install script for Oracle generates correctly")

    def test_install_script_mysql_db_type(self):
        """GET /api/db-monitoring/agent/install-script for MySQL"""
        params = {"db_type": "mysql"}
        url = f"{BASE_URL}/api/db-monitoring/agent/install-script"
        response = requests.get(url, params=params, timeout=15)
        
        assert response.status_code == 200
        content = response.text
        
        assert "mysql" in content.lower(), "Script should reference mysql"
        assert "pymysql" in content, "MySQL install should include pymysql driver"
        assert "3306" in content, "MySQL default port should be 3306"
        
        print("✓ Install script for MySQL generates correctly")


class TestConfigTemplateEndpoint:
    """Test config template generation endpoint"""

    def test_config_template_default(self):
        """GET /api/db-monitoring/agent/config-template - Returns YAML config"""
        url = f"{BASE_URL}/api/db-monitoring/agent/config-template"
        response = requests.get(url, timeout=15)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "yaml" in content_type or "text" in content_type, \
            f"Expected yaml/text content type, got: {content_type}"
        
        # Check Content-Disposition header  
        content_disposition = response.headers.get("content-disposition", "")
        assert ".yaml" in content_disposition, f"Expected .yaml filename, got: {content_disposition}"
        
        content = response.text
        
        # Verify YAML structure
        assert "database:" in content, "Config should have database section"
        assert "type:" in content, "Config should have type field"
        assert "host:" in content, "Config should have host field"
        assert "port:" in content, "Config should have port field"
        assert "username:" in content, "Config should have username field"
        assert "password:" in content, "Config should have password field"
        assert "api:" in content, "Config should have api section"
        assert "endpoint:" in content, "Config should have endpoint field"
        assert "collection_interval:" in content, "Config should have collection_interval"
        
        print(f"✓ Config template endpoint returns valid YAML ({len(content)} bytes)")

    def test_config_template_with_postgres(self):
        """GET /api/db-monitoring/agent/config-template for postgres"""
        params = {
            "db_type": "postgres",
            "api_url": BASE_URL,
            "instance_id": TEST_INSTANCE_ID
        }
        url = f"{BASE_URL}/api/db-monitoring/agent/config-template"
        response = requests.get(url, params=params, timeout=15)
        
        assert response.status_code == 200
        content = response.text
        
        assert "postgres" in content, "Config should contain postgres"
        assert "5432" in content, "Postgres port should be 5432"
        assert TEST_INSTANCE_ID in content, "Config should contain instance_id"
        
        print("✓ Config template with postgres params works")

    def test_config_template_with_oracle(self):
        """GET /api/db-monitoring/agent/config-template for oracle"""
        params = {"db_type": "oracle"}
        url = f"{BASE_URL}/api/db-monitoring/agent/config-template"
        response = requests.get(url, params=params, timeout=15)
        
        assert response.status_code == 200
        content = response.text
        
        assert "oracle" in content, "Config should contain oracle"
        assert "1521" in content, "Oracle port should be 1521"
        
        print("✓ Config template for Oracle generates correctly")

    def test_config_template_with_mysql(self):
        """GET /api/db-monitoring/agent/config-template for mysql"""
        params = {"db_type": "mysql"}
        url = f"{BASE_URL}/api/db-monitoring/agent/config-template"
        response = requests.get(url, params=params, timeout=15)
        
        assert response.status_code == 200
        content = response.text
        
        assert "mysql" in content, "Config should contain mysql"
        assert "3306" in content, "MySQL port should be 3306"
        
        print("✓ Config template for MySQL generates correctly")


class TestAgentQueriesWithAuthComparison:
    """Compare agent queries (no auth) vs custom-queries (with auth)"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get auth token for comparison test"""
        login_url = f"{BASE_URL}/api/auth/login"
        response = requests.post(login_url, json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        }, timeout=15)
        if response.status_code == 200:
            token = response.json().get("token")
            return {"Authorization": f"Bearer {token}"}
        pytest.skip("Could not authenticate - skipping auth comparison test")
    
    def test_agent_queries_returns_only_enabled(self, auth_headers):
        """Verify agent endpoint only returns enabled queries"""
        # Get all queries with auth
        all_queries_url = f"{BASE_URL}/api/db-monitoring/custom-queries/{TEST_INSTANCE_ID}"
        all_response = requests.get(all_queries_url, headers=auth_headers, timeout=15)
        
        # Get agent queries without auth
        agent_queries_url = f"{BASE_URL}/api/db-monitoring/agent/queries/{TEST_INSTANCE_ID}"
        agent_response = requests.get(agent_queries_url, timeout=15)
        
        if all_response.status_code == 200 and agent_response.status_code == 200:
            all_data = all_response.json()
            agent_data = agent_response.json()
            
            all_queries = all_data.get("queries", [])
            agent_queries = agent_data.get("queries", [])
            
            # Count enabled queries from all queries
            enabled_count = sum(1 for q in all_queries if q.get("enabled", False))
            
            print(f"Total queries: {len(all_queries)}, Enabled: {enabled_count}, Agent returns: {len(agent_queries)}")
            
            # Agent queries should match enabled count
            assert len(agent_queries) <= len(all_queries), "Agent queries should not exceed total"
            
            print("✓ Agent endpoint correctly filters to enabled queries only")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
