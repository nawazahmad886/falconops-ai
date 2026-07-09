"""
FalconOps AI - Event Analyzer API Tests
Tests for AI-powered event/alert analysis feature
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"
VIEWER_EMAIL = "test@falconapps.com"
VIEWER_PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestEventAnalyzerPublicEndpoints:
    """Test public endpoints that don't require authentication"""
    
    def test_sample_format_endpoint(self):
        """GET /api/events/sample-format - should return expected file format documentation"""
        response = requests.get(f"{BASE_URL}/api/events/sample-format")
        assert response.status_code == 200
        
        data = response.json()
        assert "description" in data
        assert "supported_formats" in data
        assert ".xlsx" in data["supported_formats"]
        assert ".xls" in data["supported_formats"]
        assert ".csv" in data["supported_formats"]
        assert "max_file_size" in data
        assert "required_columns" in data
        assert "timestamp" in data["required_columns"]
        assert "service" in data["required_columns"]
        assert "alert" in data["required_columns"]
        assert "severity" in data["required_columns"]
        assert "optional_columns" in data
        assert "sample_data" in data
        assert len(data["sample_data"]) > 0
        assert "column_aliases" in data
        print("✓ GET /api/events/sample-format - PASSED")


class TestEventAnalyzerAuthentication:
    """Test authentication requirements for event analyzer endpoints"""
    
    def test_uploads_requires_auth(self):
        """GET /api/events/uploads - should require authentication"""
        response = requests.get(f"{BASE_URL}/api/events/uploads")
        assert response.status_code == 401 or response.status_code == 403
        print("✓ GET /api/events/uploads requires auth - PASSED")
    
    def test_analyses_requires_auth(self):
        """GET /api/events/analyses - should require authentication"""
        response = requests.get(f"{BASE_URL}/api/events/analyses")
        assert response.status_code == 401 or response.status_code == 403
        print("✓ GET /api/events/analyses requires auth - PASSED")
    
    def test_upload_requires_auth(self):
        """POST /api/events/upload - should require authentication"""
        csv_content = "timestamp,service,alert,severity\n2025-01-01 10:00:00,test-service,test-alert,info"
        files = {'file': ('test.csv', csv_content, 'text/csv')}
        response = requests.post(f"{BASE_URL}/api/events/upload", files=files)
        assert response.status_code == 401 or response.status_code == 403
        print("✓ POST /api/events/upload requires auth - PASSED")


class TestEventAnalyzerFileUpload:
    """Test file upload functionality"""
    
    def test_upload_csv_file(self, auth_headers):
        """POST /api/events/upload - should accept and parse CSV files"""
        csv_content = """timestamp,service,alert,severity,host
2025-01-15 10:01:00,payment-api,Database connection timeout,critical,payment-pod-1
2025-01-15 10:02:00,checkout-api,API response latency high,warning,checkout-pod-2
2025-01-15 10:03:00,payment-api,Database connection timeout,critical,payment-pod-1
2025-01-15 10:04:00,user-service,Memory usage high,warning,user-pod-1
2025-01-15 10:05:00,payment-api,Connection pool exhausted,critical,payment-pod-1"""
        
        files = {'file': ('test_events.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/events/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "upload_id" in data
        assert data.get("total_events") == 5
        assert "columns_detected" in data
        assert "timestamp" in data["columns_detected"]
        assert "service" in data["columns_detected"]
        assert "alert" in data["columns_detected"]
        assert "severity" in data["columns_detected"]
        print(f"✓ POST /api/events/upload CSV - PASSED (upload_id: {data['upload_id']})")
    
    def test_upload_invalid_file_type(self, auth_headers):
        """POST /api/events/upload - should reject invalid file types"""
        files = {'file': ('test.txt', 'invalid content', 'text/plain')}
        response = requests.post(
            f"{BASE_URL}/api/events/upload",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print("✓ POST /api/events/upload rejects invalid file type - PASSED")


class TestEventAnalyzerAnalysis:
    """Test event analysis functionality"""
    
    @pytest.fixture(scope="class")
    def uploaded_file(self, auth_headers):
        """Upload a test file for analysis"""
        csv_content = """timestamp,service,alert,severity,host
2025-01-15 10:01:00,payment-api,Database connection timeout,critical,payment-pod-1
2025-01-15 10:02:00,checkout-api,API response latency high,warning,checkout-pod-2
2025-01-15 10:03:00,payment-api,Database connection timeout,critical,payment-pod-1
2025-01-15 10:04:00,user-service,Memory usage high,warning,user-pod-1
2025-01-15 10:05:00,payment-api,Connection pool exhausted,critical,payment-pod-1
2025-01-15 10:06:00,checkout-api,API response latency high,warning,checkout-pod-3
2025-01-15 10:07:00,payment-api,Database connection timeout,critical,payment-pod-2
2025-01-15 10:08:00,notification-service,Queue backlog,info,notification-pod-1
2025-01-15 10:09:00,payment-api,Database connection timeout,critical,payment-pod-1
2025-01-15 10:10:00,user-service,Memory usage high,warning,user-pod-2"""
        
        files = {'file': ('analysis_test.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/events/upload",
            headers=auth_headers,
            files=files
        )
        
        if response.status_code == 200:
            return response.json()
        pytest.skip("File upload failed")
    
    def test_analyze_uploaded_events(self, auth_headers, uploaded_file):
        """POST /api/events/analyze/{upload_id} - should perform AI analysis on uploaded events"""
        upload_id = uploaded_file["upload_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/events/analyze/{upload_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "analysis_id" in data
        assert "patterns" in data
        assert "clusters" in data
        assert "ai_analysis" in data
        assert "summary" in data
        
        # Verify patterns structure
        patterns = data["patterns"]
        assert "total_events" in patterns
        assert "severity_distribution" in patterns
        assert "alert_frequency" in patterns
        assert "service_frequency" in patterns
        
        # Verify summary structure
        summary = data["summary"]
        assert "status" in summary
        assert "health_score" in summary
        assert "total_events" in summary
        assert "critical_count" in summary
        assert "warning_count" in summary
        
        print(f"✓ POST /api/events/analyze/{upload_id} - PASSED (analysis_id: {data['analysis_id']})")
    
    def test_analyze_nonexistent_upload(self, auth_headers):
        """POST /api/events/analyze/{upload_id} - should return 404 for nonexistent upload"""
        response = requests.post(
            f"{BASE_URL}/api/events/analyze/nonexistent-id-12345",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        print("✓ POST /api/events/analyze returns 404 for nonexistent upload - PASSED")
    
    def test_get_analysis_result(self, auth_headers, uploaded_file):
        """GET /api/events/analysis/{analysis_id} - should retrieve analysis results"""
        upload_id = uploaded_file["upload_id"]
        
        # First perform analysis
        analyze_response = requests.post(
            f"{BASE_URL}/api/events/analyze/{upload_id}",
            headers=auth_headers
        )
        
        if analyze_response.status_code != 200:
            pytest.skip("Analysis failed")
        
        analysis_id = analyze_response.json()["analysis_id"]
        
        # Get analysis result
        response = requests.get(
            f"{BASE_URL}/api/events/analysis/{analysis_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "patterns" in data or "ai_analysis" in data
        print(f"✓ GET /api/events/analysis/{analysis_id} - PASSED")
    
    def test_get_nonexistent_analysis(self, auth_headers):
        """GET /api/events/analysis/{analysis_id} - should return 404 for nonexistent analysis"""
        response = requests.get(
            f"{BASE_URL}/api/events/analysis/nonexistent-analysis-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        print("✓ GET /api/events/analysis returns 404 for nonexistent analysis - PASSED")


class TestEventAnalyzerListEndpoints:
    """Test list endpoints for uploads and analyses"""
    
    def test_list_uploads(self, auth_headers):
        """GET /api/events/uploads - should list all uploads"""
        response = requests.get(
            f"{BASE_URL}/api/events/uploads",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "uploads" in data
        assert "total" in data
        assert isinstance(data["uploads"], list)
        print(f"✓ GET /api/events/uploads - PASSED (total: {data['total']})")
    
    def test_list_uploads_with_pagination(self, auth_headers):
        """GET /api/events/uploads - should support pagination"""
        response = requests.get(
            f"{BASE_URL}/api/events/uploads?skip=0&limit=5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "skip" in data
        assert "limit" in data
        assert data["skip"] == 0
        assert data["limit"] == 5
        print("✓ GET /api/events/uploads with pagination - PASSED")
    
    def test_list_analyses(self, auth_headers):
        """GET /api/events/analyses - should list all analyses"""
        response = requests.get(
            f"{BASE_URL}/api/events/analyses",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "analyses" in data
        assert "total" in data
        assert isinstance(data["analyses"], list)
        print(f"✓ GET /api/events/analyses - PASSED (total: {data['total']})")


class TestEventAnalyzerDelete:
    """Test delete functionality"""
    
    def test_delete_upload(self, auth_headers):
        """DELETE /api/events/upload/{upload_id} - should delete upload and analysis"""
        # First upload a file
        csv_content = """timestamp,service,alert,severity
2025-01-15 10:01:00,test-service,test-alert,info"""
        
        files = {'file': ('delete_test.csv', csv_content, 'text/csv')}
        upload_response = requests.post(
            f"{BASE_URL}/api/events/upload",
            headers=auth_headers,
            files=files
        )
        
        if upload_response.status_code != 200:
            pytest.skip("Upload failed")
        
        upload_id = upload_response.json()["upload_id"]
        
        # Delete the upload
        response = requests.delete(
            f"{BASE_URL}/api/events/upload/{upload_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        print(f"✓ DELETE /api/events/upload/{upload_id} - PASSED")
    
    def test_delete_nonexistent_upload(self, auth_headers):
        """DELETE /api/events/upload/{upload_id} - should return 404 for nonexistent upload"""
        response = requests.delete(
            f"{BASE_URL}/api/events/upload/nonexistent-upload-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        print("✓ DELETE /api/events/upload returns 404 for nonexistent upload - PASSED")


class TestEventAnalyzerQuickAnalyze:
    """Test quick analyze endpoint"""
    
    def test_quick_analyze(self, auth_headers):
        """POST /api/events/quick-analyze - should upload and analyze in one call"""
        csv_content = """timestamp,service,alert,severity,host
2025-01-15 10:01:00,payment-api,Database connection timeout,critical,payment-pod-1
2025-01-15 10:02:00,checkout-api,API response latency high,warning,checkout-pod-2
2025-01-15 10:03:00,payment-api,Database connection timeout,critical,payment-pod-1"""
        
        files = {'file': ('quick_test.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/events/quick-analyze",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "filename" in data
        assert "total_events" in data
        assert data["total_events"] == 3
        assert "patterns" in data
        assert "clusters" in data
        assert "ai_analysis" in data
        assert "summary" in data
        print("✓ POST /api/events/quick-analyze - PASSED")
    
    def test_quick_analyze_invalid_file(self, auth_headers):
        """POST /api/events/quick-analyze - should reject invalid file types"""
        files = {'file': ('test.txt', 'invalid content', 'text/plain')}
        response = requests.post(
            f"{BASE_URL}/api/events/quick-analyze",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400
        print("✓ POST /api/events/quick-analyze rejects invalid file - PASSED")


class TestEventAnalyzerReport:
    """Test report endpoint"""
    
    @pytest.fixture(scope="class")
    def analysis_result(self, auth_headers):
        """Create an analysis for report testing"""
        # Upload file
        csv_content = """timestamp,service,alert,severity,host
2025-01-15 10:01:00,payment-api,Database connection timeout,critical,payment-pod-1
2025-01-15 10:02:00,checkout-api,API response latency high,warning,checkout-pod-2
2025-01-15 10:03:00,payment-api,Database connection timeout,critical,payment-pod-1"""
        
        files = {'file': ('report_test.csv', csv_content, 'text/csv')}
        upload_response = requests.post(
            f"{BASE_URL}/api/events/upload",
            headers=auth_headers,
            files=files
        )
        
        if upload_response.status_code != 200:
            pytest.skip("Upload failed")
        
        upload_id = upload_response.json()["upload_id"]
        
        # Analyze
        analyze_response = requests.post(
            f"{BASE_URL}/api/events/analyze/{upload_id}",
            headers=auth_headers
        )
        
        if analyze_response.status_code != 200:
            pytest.skip("Analysis failed")
        
        return analyze_response.json()
    
    def test_get_report_data(self, auth_headers, analysis_result):
        """GET /api/events/report/{analysis_id} - should get report-formatted data"""
        analysis_id = analysis_result["analysis_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/events/report/{analysis_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("report_type") == "event_analysis"
        assert "analysis_id" in data
        assert "generated_at" in data
        assert "summary" in data
        assert "charts_data" in data
        
        # Verify charts data structure
        charts = data["charts_data"]
        assert "severity_pie" in charts
        assert "alert_bar" in charts
        assert "service_bar" in charts
        
        print(f"✓ GET /api/events/report/{analysis_id} - PASSED")
    
    def test_get_report_nonexistent_analysis(self, auth_headers):
        """GET /api/events/report/{analysis_id} - should return 404 for nonexistent analysis"""
        response = requests.get(
            f"{BASE_URL}/api/events/report/nonexistent-analysis-id",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        print("✓ GET /api/events/report returns 404 for nonexistent analysis - PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
