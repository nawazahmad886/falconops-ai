"""
FalconOps AI - Download Page & Licensing API Tests
Tests for: /api/licenses/download/agent, /api/licenses/download/db-agent, 
           /api/licenses/download/agents-info, /api/licenses/download/source,
           /api/licenses/plans, /api/licenses/current, /api/licenses/records,
           /api/licenses/validate, /api/licenses/generate, /api/licenses/activate
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDownloadEndpoints:
    """Tests for agent and source download endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("access_token")
        assert self.token, "No access_token in login response"
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_download_server_agent(self):
        """GET /api/licenses/download/agent - Download server monitoring agent"""
        response = requests.get(f"{BASE_URL}/api/licenses/download/agent", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "text/x-python" in response.headers.get("content-type", ""), "Expected Python file content type"
        assert len(response.content) > 1000, "Agent file should be substantial"
        assert b"psutil" in response.content or b"falcon" in response.content.lower(), "Agent should contain expected code"
        print(f"✓ Server agent downloaded: {len(response.content)} bytes")
    
    def test_download_db_agent(self):
        """GET /api/licenses/download/db-agent - Download database monitoring agent"""
        response = requests.get(f"{BASE_URL}/api/licenses/download/db-agent", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "text/x-python" in response.headers.get("content-type", ""), "Expected Python file content type"
        assert len(response.content) > 5000, "DB Agent file should be substantial"
        assert b"database" in response.content.lower() or b"postgresql" in response.content.lower() or b"mysql" in response.content.lower(), "DB Agent should contain database-related code"
        print(f"✓ DB agent downloaded: {len(response.content)} bytes")
    
    def test_agents_info(self):
        """GET /api/licenses/download/agents-info - Get info about available agents"""
        response = requests.get(f"{BASE_URL}/api/licenses/download/agents-info", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "agents" in data, "Response should contain 'agents' key"
        agents = data["agents"]
        assert len(agents) >= 2, f"Expected at least 2 agents, got {len(agents)}"
        
        # Check server agent info
        server_agent = next((a for a in agents if a["id"] == "server-agent"), None)
        assert server_agent is not None, "Server agent not found in agents list"
        assert server_agent["available"] == True, "Server agent should be available"
        assert server_agent["download_url"] == "/api/licenses/download/agent"
        
        # Check DB agent info
        db_agent = next((a for a in agents if a["id"] == "db-agent"), None)
        assert db_agent is not None, "DB agent not found in agents list"
        assert db_agent["available"] == True, "DB agent should be available"
        assert db_agent["download_url"] == "/api/licenses/download/db-agent"
        
        print(f"✓ Agents info returned {len(agents)} agents")
    
    def test_download_source_package(self):
        """GET /api/licenses/download/source - Download full enterprise source package"""
        response = requests.get(
            f"{BASE_URL}/api/licenses/download/source?include_docker=true", 
            headers=self.headers,
            stream=True
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "application/gzip" in response.headers.get("content-type", ""), "Expected gzip content type"
        
        # Check content-disposition header for filename
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp, "Should have attachment disposition"
        assert ".tar.gz" in content_disp, "Filename should be .tar.gz"
        
        # Read first chunk to verify it's a valid gzip
        first_chunk = next(response.iter_content(chunk_size=1024))
        assert first_chunk[:2] == b'\x1f\x8b', "Should be valid gzip file (magic bytes)"
        
        print(f"✓ Source package download started successfully")
    
    def test_download_agent_requires_admin(self):
        """Agent download should require admin role"""
        # Try without auth
        response = requests.get(f"{BASE_URL}/api/licenses/download/agent")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Agent download requires authentication")


class TestLicensingEndpoints:
    """Tests for license management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("access_token")
        assert self.token, "No access_token in login response"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_get_license_plans(self):
        """GET /api/licenses/plans - Get available license plans"""
        response = requests.get(f"{BASE_URL}/api/licenses/plans", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "plans" in data, "Response should contain 'plans' key"
        plans = data["plans"]
        
        # Check expected plan types exist
        expected_types = ["trial", "standard", "professional", "enterprise"]
        for plan_type in expected_types:
            assert plan_type in plans, f"Plan type '{plan_type}' should exist"
            plan = plans[plan_type]
            assert "name" in plan, f"Plan {plan_type} should have 'name'"
            assert "max_users" in plan, f"Plan {plan_type} should have 'max_users'"
            assert "max_servers" in plan, f"Plan {plan_type} should have 'max_servers'"
            assert "valid_days" in plan, f"Plan {plan_type} should have 'valid_days'"
        
        print(f"✓ License plans returned: {list(plans.keys())}")
    
    def test_get_current_license(self):
        """GET /api/licenses/current - Get current active license"""
        response = requests.get(f"{BASE_URL}/api/licenses/current", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Either active=True with license data, or active=False with message
        assert "active" in data, "Response should contain 'active' key"
        print(f"✓ Current license status: active={data.get('active')}")
    
    def test_get_license_records(self):
        """GET /api/licenses/records - Get license records (admin only)"""
        response = requests.get(f"{BASE_URL}/api/licenses/records", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "records" in data, "Response should contain 'records' key"
        assert "total" in data, "Response should contain 'total' key"
        print(f"✓ License records: {data.get('total')} total records")
    
    def test_generate_license(self):
        """POST /api/licenses/generate - Generate a new license key"""
        payload = {
            "organization": "TEST_TestOrg",
            "customer_email": "test@testorg.com",
            "license_type": "trial",
            "valid_days": 14
        }
        response = requests.post(f"{BASE_URL}/api/licenses/generate", headers=self.headers, json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Generation should succeed"
        assert "license_key" in data, "Response should contain 'license_key'"
        assert "license_id" in data, "Response should contain 'license_id'"
        assert data.get("organization") == "TEST_TestOrg"
        assert data.get("type") == "trial"
        
        # Store for validation test
        self.generated_license_key = data["license_key"]
        print(f"✓ License generated: {data['license_key'][:20]}...")
        
        # Test validation of generated license
        validate_response = requests.post(
            f"{BASE_URL}/api/licenses/validate",
            headers=self.headers,
            json={"license_key": data["license_key"]}
        )
        assert validate_response.status_code == 200, f"Validation failed: {validate_response.text}"
        validate_data = validate_response.json()
        assert validate_data.get("valid") == True, "Generated license should be valid"
        print(f"✓ Generated license validated successfully")
    
    def test_validate_invalid_license(self):
        """POST /api/licenses/validate - Validate an invalid license key"""
        response = requests.post(
            f"{BASE_URL}/api/licenses/validate",
            headers=self.headers,
            json={"license_key": "INVALID-LICENSE-KEY-12345"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("valid") == False, "Invalid license should not be valid"
        print("✓ Invalid license correctly rejected")


class TestDownloadPageIntegration:
    """Integration tests for Download page functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_full_download_workflow(self):
        """Test complete download workflow: agents-info -> download agent"""
        # 1. Get agents info
        info_response = requests.get(f"{BASE_URL}/api/licenses/download/agents-info", headers=self.headers)
        assert info_response.status_code == 200
        agents = info_response.json()["agents"]
        
        # 2. Download each available agent
        for agent in agents:
            if agent["available"]:
                download_url = f"{BASE_URL}{agent['download_url']}"
                download_response = requests.get(download_url, headers=self.headers)
                assert download_response.status_code == 200, f"Failed to download {agent['name']}"
                print(f"✓ Downloaded {agent['name']}: {len(download_response.content)} bytes")
    
    def test_license_generate_validate_flow(self):
        """Test license generation and validation flow"""
        # 1. Get plans
        plans_response = requests.get(f"{BASE_URL}/api/licenses/plans", headers=self.headers)
        assert plans_response.status_code == 200
        plans = plans_response.json()["plans"]
        
        # 2. Generate license for each plan type
        for plan_type in ["trial", "standard"]:
            if plan_type in plans:
                gen_response = requests.post(
                    f"{BASE_URL}/api/licenses/generate",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json={
                        "organization": f"TEST_Org_{plan_type}",
                        "customer_email": f"test_{plan_type}@example.com",
                        "license_type": plan_type
                    }
                )
                assert gen_response.status_code == 200, f"Failed to generate {plan_type} license"
                license_key = gen_response.json()["license_key"]
                
                # 3. Validate the generated license
                val_response = requests.post(
                    f"{BASE_URL}/api/licenses/validate",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json={"license_key": license_key}
                )
                assert val_response.status_code == 200
                assert val_response.json()["valid"] == True
                print(f"✓ {plan_type} license generated and validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
