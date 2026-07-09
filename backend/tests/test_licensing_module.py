"""
FalconOps AI - Licensing Module Tests
Tests for license generation, validation, activation, and download features
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"
VIEWER_EMAIL = "test@falconapps.com"
VIEWER_PASSWORD = "testpass123"


class TestLicensingModule:
    """Licensing API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.admin_token = None
        self.viewer_token = None
        self.generated_license_key = None
    
    def get_admin_token(self):
        """Get admin authentication token"""
        if self.admin_token:
            return self.admin_token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.admin_token = response.json().get("access_token")
            return self.admin_token
        pytest.skip("Admin authentication failed")
    
    def get_viewer_token(self):
        """Get viewer authentication token"""
        if self.viewer_token:
            return self.viewer_token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": VIEWER_EMAIL,
            "password": VIEWER_PASSWORD
        })
        if response.status_code == 200:
            self.viewer_token = response.json().get("access_token")
            return self.viewer_token
        pytest.skip("Viewer authentication failed")
    
    def get_admin_headers(self):
        """Get headers with admin token"""
        token = self.get_admin_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_viewer_headers(self):
        """Get headers with viewer token"""
        token = self.get_viewer_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    # ==================== LICENSE PLANS TESTS ====================
    
    def test_get_license_plans_public(self):
        """GET /api/licenses/plans - should return available license plans (public endpoint)"""
        response = self.session.get(f"{BASE_URL}/api/licenses/plans")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "plans" in data, "Response should contain 'plans' key"
        
        plans = data["plans"]
        assert "trial" in plans, "Should have trial plan"
        assert "standard" in plans, "Should have standard plan"
        assert "professional" in plans, "Should have professional plan"
        assert "enterprise" in plans, "Should have enterprise plan"
        
        # Verify trial plan structure
        trial = plans["trial"]
        assert trial["name"] == "Trial"
        assert trial["valid_days"] == 14
        assert trial["max_users"] == 3
        assert trial["max_servers"] == 5
        assert trial["max_monitors"] == 10
        
        print("✓ GET /api/licenses/plans - PASSED (4 plans returned)")
    
    # ==================== LICENSE GENERATION TESTS ====================
    
    def test_generate_license_admin_only(self):
        """POST /api/licenses/generate - should require admin access"""
        # Test without auth
        response = self.session.post(f"{BASE_URL}/api/licenses/generate", json={
            "organization": "Test Org",
            "customer_email": "test@test.com",
            "license_type": "standard"
        })
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        # Test with viewer (non-admin)
        response = self.session.post(
            f"{BASE_URL}/api/licenses/generate",
            headers=self.get_viewer_headers(),
            json={
                "organization": "Test Org",
                "customer_email": "test@test.com",
                "license_type": "standard"
            }
        )
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        
        print("✓ POST /api/licenses/generate - PASSED (requires admin)")
    
    def test_generate_license_success(self):
        """POST /api/licenses/generate - should generate a new license key (admin)"""
        response = self.session.post(
            f"{BASE_URL}/api/licenses/generate",
            headers=self.get_admin_headers(),
            json={
                "organization": "TEST_Acme Corporation",
                "customer_email": "test@acme.com",
                "license_type": "standard",
                "valid_days": 365
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "license_key" in data, "Response should contain license_key"
        assert "license_id" in data, "Response should contain license_id"
        assert data["organization"] == "TEST_Acme Corporation"
        assert data["customer_email"] == "test@acme.com"
        assert data["type"] == "standard"
        assert "expires_at" in data
        assert "features" in data
        
        # Store for later tests
        self.generated_license_key = data["license_key"]
        
        print(f"✓ POST /api/licenses/generate - PASSED (license generated)")
    
    def test_generate_license_invalid_type(self):
        """POST /api/licenses/generate - should reject invalid license type"""
        response = self.session.post(
            f"{BASE_URL}/api/licenses/generate",
            headers=self.get_admin_headers(),
            json={
                "organization": "Test Org",
                "customer_email": "test@test.com",
                "license_type": "invalid_type"
            }
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid type, got {response.status_code}"
        print("✓ POST /api/licenses/generate - PASSED (rejects invalid type)")
    
    def test_generate_license_all_types(self):
        """POST /api/licenses/generate - should generate all license types"""
        license_types = ["trial", "standard", "professional", "enterprise"]
        
        for license_type in license_types:
            response = self.session.post(
                f"{BASE_URL}/api/licenses/generate",
                headers=self.get_admin_headers(),
                json={
                    "organization": f"TEST_{license_type.upper()} Org",
                    "customer_email": f"test_{license_type}@test.com",
                    "license_type": license_type
                }
            )
            
            assert response.status_code == 200, f"Failed to generate {license_type} license: {response.text}"
            data = response.json()
            assert data["type"] == license_type
        
        print(f"✓ POST /api/licenses/generate - PASSED (all 4 types generated)")
    
    # ==================== LICENSE VALIDATION TESTS ====================
    
    def test_validate_license_success(self):
        """POST /api/licenses/validate - should validate a valid license key"""
        # First generate a license
        gen_response = self.session.post(
            f"{BASE_URL}/api/licenses/generate",
            headers=self.get_admin_headers(),
            json={
                "organization": "TEST_Validation Org",
                "customer_email": "validate@test.com",
                "license_type": "professional"
            }
        )
        assert gen_response.status_code == 200
        license_key = gen_response.json()["license_key"]
        
        # Validate the license
        response = self.session.post(
            f"{BASE_URL}/api/licenses/validate",
            json={"license_key": license_key}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("valid") == True, "License should be valid"
        assert data["organization"] == "TEST_Validation Org"
        assert data["type"] == "professional"
        assert "days_remaining" in data
        assert data["days_remaining"] > 0
        assert "features" in data
        
        print("✓ POST /api/licenses/validate - PASSED (valid license)")
    
    def test_validate_license_invalid(self):
        """POST /api/licenses/validate - should reject invalid license key"""
        response = self.session.post(
            f"{BASE_URL}/api/licenses/validate",
            json={"license_key": "invalid_license_key_12345"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("valid") == False, "Invalid license should return valid=False"
        assert "error" in data
        
        print("✓ POST /api/licenses/validate - PASSED (rejects invalid)")
    
    # ==================== LICENSE ACTIVATION TESTS ====================
    
    def test_activate_license_admin_only(self):
        """POST /api/licenses/activate - should require admin access"""
        # Test without auth
        response = self.session.post(f"{BASE_URL}/api/licenses/activate", json={
            "license_key": "test_key"
        })
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        # Test with viewer
        response = self.session.post(
            f"{BASE_URL}/api/licenses/activate",
            headers=self.get_viewer_headers(),
            json={"license_key": "test_key"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        
        print("✓ POST /api/licenses/activate - PASSED (requires admin)")
    
    def test_activate_license_success(self):
        """POST /api/licenses/activate - should activate a valid license"""
        # First generate a license
        gen_response = self.session.post(
            f"{BASE_URL}/api/licenses/generate",
            headers=self.get_admin_headers(),
            json={
                "organization": "TEST_Activation Org",
                "customer_email": "activate@test.com",
                "license_type": "enterprise"
            }
        )
        assert gen_response.status_code == 200
        license_key = gen_response.json()["license_key"]
        
        # Activate the license
        response = self.session.post(
            f"{BASE_URL}/api/licenses/activate",
            headers=self.get_admin_headers(),
            json={"license_key": license_key}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Activation should succeed"
        
        print("✓ POST /api/licenses/activate - PASSED (license activated)")
    
    def test_activate_license_invalid(self):
        """POST /api/licenses/activate - should reject invalid license"""
        response = self.session.post(
            f"{BASE_URL}/api/licenses/activate",
            headers=self.get_admin_headers(),
            json={"license_key": "invalid_license_key_12345"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid license, got {response.status_code}"
        
        print("✓ POST /api/licenses/activate - PASSED (rejects invalid)")
    
    # ==================== CURRENT LICENSE TESTS ====================
    
    def test_get_current_license_auth_required(self):
        """GET /api/licenses/current - should require authentication"""
        response = self.session.get(f"{BASE_URL}/api/licenses/current")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        print("✓ GET /api/licenses/current - PASSED (requires auth)")
    
    def test_get_current_license_success(self):
        """GET /api/licenses/current - should return current active license"""
        response = self.session.get(
            f"{BASE_URL}/api/licenses/current",
            headers=self.get_admin_headers()
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Either active license or no license message
        assert "active" in data or "message" in data
        
        if data.get("active"):
            assert "license" in data
            license_info = data["license"]
            assert "organization" in license_info
            assert "type" in license_info
            assert "expires_at" in license_info
            print("✓ GET /api/licenses/current - PASSED (active license found)")
        else:
            print("✓ GET /api/licenses/current - PASSED (no active license)")
    
    # ==================== LICENSE REVOKE TESTS ====================
    
    def test_revoke_license_admin_only(self):
        """DELETE /api/licenses/revoke - should require admin access"""
        # Test without auth
        response = self.session.delete(f"{BASE_URL}/api/licenses/revoke")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        # Test with viewer
        response = self.session.delete(
            f"{BASE_URL}/api/licenses/revoke",
            headers=self.get_viewer_headers()
        )
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        
        print("✓ DELETE /api/licenses/revoke - PASSED (requires admin)")
    
    def test_revoke_license_success(self):
        """DELETE /api/licenses/revoke - should revoke current license"""
        # First activate a license
        gen_response = self.session.post(
            f"{BASE_URL}/api/licenses/generate",
            headers=self.get_admin_headers(),
            json={
                "organization": "TEST_Revoke Org",
                "customer_email": "revoke@test.com",
                "license_type": "trial"
            }
        )
        assert gen_response.status_code == 200
        license_key = gen_response.json()["license_key"]
        
        # Activate it
        self.session.post(
            f"{BASE_URL}/api/licenses/activate",
            headers=self.get_admin_headers(),
            json={"license_key": license_key}
        )
        
        # Revoke it
        response = self.session.delete(
            f"{BASE_URL}/api/licenses/revoke",
            headers=self.get_admin_headers()
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        
        # Verify no active license
        current_response = self.session.get(
            f"{BASE_URL}/api/licenses/current",
            headers=self.get_admin_headers()
        )
        current_data = current_response.json()
        assert current_data.get("active") == False or "message" in current_data
        
        print("✓ DELETE /api/licenses/revoke - PASSED (license revoked)")
    
    # ==================== LICENSE RECORDS TESTS ====================
    
    def test_get_license_records_admin_only(self):
        """GET /api/licenses/records - should require admin access"""
        # Test without auth
        response = self.session.get(f"{BASE_URL}/api/licenses/records")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        # Test with viewer
        response = self.session.get(
            f"{BASE_URL}/api/licenses/records",
            headers=self.get_viewer_headers()
        )
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        
        print("✓ GET /api/licenses/records - PASSED (requires admin)")
    
    def test_get_license_records_success(self):
        """GET /api/licenses/records - should list generated licenses"""
        response = self.session.get(
            f"{BASE_URL}/api/licenses/records",
            headers=self.get_admin_headers()
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "records" in data
        assert "total" in data
        assert isinstance(data["records"], list)
        
        # Should have records from previous tests
        if len(data["records"]) > 0:
            record = data["records"][0]
            assert "organization" in record
            assert "type" in record
            assert "customer_email" in record
            assert "expires_at" in record
            assert "created_at" in record
        
        print(f"✓ GET /api/licenses/records - PASSED ({data['total']} records)")
    
    # ==================== DOWNLOAD TESTS ====================
    
    def test_download_source_admin_only(self):
        """GET /api/licenses/download/source - should require admin access"""
        # Test without auth
        response = self.session.get(f"{BASE_URL}/api/licenses/download/source")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        # Test with viewer
        response = self.session.get(
            f"{BASE_URL}/api/licenses/download/source",
            headers=self.get_viewer_headers()
        )
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        
        print("✓ GET /api/licenses/download/source - PASSED (requires admin)")
    
    def test_download_source_success(self):
        """GET /api/licenses/download/source - should download tar.gz file"""
        response = self.session.get(
            f"{BASE_URL}/api/licenses/download/source?include_docker=true",
            headers={"Authorization": f"Bearer {self.get_admin_token()}"},
            stream=True
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "gzip" in content_type or "application/octet-stream" in content_type or "application/x-gzip" in content_type, f"Expected gzip content type, got {content_type}"
        
        # Check content disposition
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disposition
        assert ".tar.gz" in content_disposition
        
        # Verify it's a valid file (has content)
        content_length = 0
        for chunk in response.iter_content(chunk_size=8192):
            content_length += len(chunk)
            if content_length > 1000:  # Just verify it has substantial content
                break
        
        assert content_length > 1000, "Download should have substantial content"
        
        print("✓ GET /api/licenses/download/source - PASSED (tar.gz downloaded)")
    
    def test_download_agent_admin_only(self):
        """GET /api/licenses/download/agent - should require admin access"""
        # Test without auth
        response = self.session.get(f"{BASE_URL}/api/licenses/download/agent")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        # Test with viewer
        response = self.session.get(
            f"{BASE_URL}/api/licenses/download/agent",
            headers=self.get_viewer_headers()
        )
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        
        print("✓ GET /api/licenses/download/agent - PASSED (requires admin)")
    
    def test_download_agent_success(self):
        """GET /api/licenses/download/agent - should download agent script"""
        response = self.session.get(
            f"{BASE_URL}/api/licenses/download/agent",
            headers={"Authorization": f"Bearer {self.get_admin_token()}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "python" in content_type or "text" in content_type or "octet-stream" in content_type, f"Expected python/text content type, got {content_type}"
        
        # Check content disposition
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "falconops_agent.py" in content_disposition
        
        # Verify content is Python code
        content = response.text
        assert "import" in content or "def " in content, "Should be Python code"
        
        print("✓ GET /api/licenses/download/agent - PASSED (agent downloaded)")
    
    # ==================== FEATURE ACCESS TESTS ====================
    
    def test_check_feature_access_auth_required(self):
        """GET /api/licenses/features/{feature} - should require authentication"""
        response = self.session.get(f"{BASE_URL}/api/licenses/features/monitoring")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        print("✓ GET /api/licenses/features/{feature} - PASSED (requires auth)")
    
    def test_check_feature_access_success(self):
        """GET /api/licenses/features/{feature} - should check feature access"""
        # First activate a license with known features
        gen_response = self.session.post(
            f"{BASE_URL}/api/licenses/generate",
            headers=self.get_admin_headers(),
            json={
                "organization": "TEST_Feature Check Org",
                "customer_email": "feature@test.com",
                "license_type": "enterprise"
            }
        )
        assert gen_response.status_code == 200
        license_key = gen_response.json()["license_key"]
        
        # Activate it
        self.session.post(
            f"{BASE_URL}/api/licenses/activate",
            headers=self.get_admin_headers(),
            json={"license_key": license_key}
        )
        
        # Check feature access
        response = self.session.get(
            f"{BASE_URL}/api/licenses/features/ai_copilot",
            headers=self.get_admin_headers()
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "feature" in data
        assert "available" in data
        assert data["feature"] == "ai_copilot"
        # Enterprise should have ai_copilot
        assert data["available"] == True, "Enterprise license should have ai_copilot feature"
        
        print("✓ GET /api/licenses/features/{feature} - PASSED (feature check works)")
    
    def test_check_feature_no_license(self):
        """GET /api/licenses/features/{feature} - should handle no active license"""
        # First revoke any active license
        self.session.delete(
            f"{BASE_URL}/api/licenses/revoke",
            headers=self.get_admin_headers()
        )
        
        # Check feature access
        response = self.session.get(
            f"{BASE_URL}/api/licenses/features/monitoring",
            headers=self.get_admin_headers()
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["available"] == False
        assert "reason" in data or "No active license" in str(data)
        
        print("✓ GET /api/licenses/features/{feature} - PASSED (handles no license)")


# Cleanup test data
class TestCleanup:
    """Cleanup test-created data"""
    
    def test_cleanup_license_records(self):
        """Clean up TEST_ prefixed license records"""
        session = requests.Session()
        
        # Login as admin
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip("Could not authenticate for cleanup")
        
        token = response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Revoke any active license
        session.delete(f"{BASE_URL}/api/licenses/revoke", headers=headers)
        
        print("✓ Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
