"""
FalconOps AI - Event Export API Tests
Tests for Excel and PDF export endpoints with branding support
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@falconapps.com"
TEST_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def valid_analysis_id(auth_headers):
    """Get a valid analysis_id from an analyzed upload"""
    response = requests.get(f"{BASE_URL}/api/events/uploads", headers=auth_headers)
    assert response.status_code == 200, f"Failed to get uploads: {response.text}"
    
    uploads = response.json().get("uploads", [])
    # Find an upload with status='analyzed'
    for upload in uploads:
        if upload.get("status") == "analyzed" and upload.get("analysis_id"):
            return upload["analysis_id"]
    
    pytest.skip("No analyzed uploads available for export testing")


class TestExcelExport:
    """Excel export endpoint tests"""

    def test_excel_export_basic(self, auth_headers, valid_analysis_id):
        """Test basic Excel export returns xlsx file"""
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/excel",
            headers=auth_headers
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Excel export failed: {response.text}"
        
        # Content-type assertion
        assert "spreadsheetml" in response.headers.get("Content-Type", ""), \
            f"Expected xlsx content type, got: {response.headers.get('Content-Type')}"
        
        # Content-disposition assertion
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, "Expected attachment disposition"
        assert ".xlsx" in content_disp, "Expected xlsx extension in filename"
        
        # Data assertion - file should have content
        assert len(response.content) > 0, "Excel file should have content"
        
        # Validate it's a valid xlsx file (starts with PK signature for zip)
        assert response.content[:2] == b'PK', "Excel file should be a valid zip/xlsx file"

    def test_excel_export_with_branding(self, auth_headers, valid_analysis_id):
        """Test Excel export with branding query params"""
        params = {
            "company": "TestCorp Inc",
            "title": "Weekly Analysis Report",
            "footer": "Confidential - Internal Use Only"
        }
        
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/excel",
            headers=auth_headers,
            params=params
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Excel export with branding failed: {response.text}"
        
        # Content-type assertion
        assert "spreadsheetml" in response.headers.get("Content-Type", "")
        
        # File should be generated
        assert len(response.content) > 0

    def test_excel_export_404_invalid_analysis(self, auth_headers):
        """Test Excel export returns 404 for non-existent analysis_id"""
        response = requests.get(
            f"{BASE_URL}/api/events/export/nonexistent-analysis-id/excel",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_excel_export_requires_auth(self, valid_analysis_id):
        """Test Excel export requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/excel"
        )
        
        assert response.status_code in [401, 403]


class TestPDFExport:
    """PDF export endpoint tests"""

    def test_pdf_export_basic(self, auth_headers, valid_analysis_id):
        """Test basic PDF export returns pdf file"""
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/pdf",
            headers=auth_headers
        )
        
        # Status code assertion
        assert response.status_code == 200, f"PDF export failed: {response.text}"
        
        # Content-type assertion
        assert "application/pdf" in response.headers.get("Content-Type", ""), \
            f"Expected pdf content type, got: {response.headers.get('Content-Type')}"
        
        # Content-disposition assertion
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, "Expected attachment disposition"
        assert ".pdf" in content_disp, "Expected pdf extension in filename"
        
        # Data assertion - file should have content
        assert len(response.content) > 0, "PDF file should have content"
        
        # Validate it's a valid PDF file (starts with %PDF)
        assert response.content[:4] == b'%PDF', "PDF file should start with %PDF signature"

    def test_pdf_export_with_branding(self, auth_headers, valid_analysis_id):
        """Test PDF export with branding query params"""
        params = {
            "company": "TestCorp Inc",
            "title": "Weekly Analysis Report",
            "footer": "Confidential - Internal Use Only"
        }
        
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/pdf",
            headers=auth_headers,
            params=params
        )
        
        # Status code assertion
        assert response.status_code == 200, f"PDF export with branding failed: {response.text}"
        
        # Content-type assertion
        assert "application/pdf" in response.headers.get("Content-Type", "")
        
        # File should be generated
        assert len(response.content) > 0
        
        # Validate PDF signature
        assert response.content[:4] == b'%PDF'

    def test_pdf_export_404_invalid_analysis(self, auth_headers):
        """Test PDF export returns 404 for non-existent analysis_id"""
        response = requests.get(
            f"{BASE_URL}/api/events/export/nonexistent-analysis-id/pdf",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_pdf_export_requires_auth(self, valid_analysis_id):
        """Test PDF export requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/pdf"
        )
        
        assert response.status_code in [401, 403]


class TestExportEndpointValidation:
    """Additional validation tests for export endpoints"""

    def test_excel_file_size_reasonable(self, auth_headers, valid_analysis_id):
        """Test that Excel file size is reasonable (not empty, not too large)"""
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/excel",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        file_size = len(response.content)
        
        # File should be at least 5KB for a valid report
        assert file_size > 5000, f"Excel file too small: {file_size} bytes"
        
        # File should not exceed 50MB
        assert file_size < 50 * 1024 * 1024, f"Excel file too large: {file_size} bytes"

    def test_pdf_file_size_reasonable(self, auth_headers, valid_analysis_id):
        """Test that PDF file size is reasonable (not empty, not too large)"""
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/pdf",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        file_size = len(response.content)
        
        # File should be at least 5KB for a valid report
        assert file_size > 5000, f"PDF file too small: {file_size} bytes"
        
        # File should not exceed 50MB
        assert file_size < 50 * 1024 * 1024, f"PDF file too large: {file_size} bytes"

    def test_branding_with_special_characters(self, auth_headers, valid_analysis_id):
        """Test export handles special characters in branding"""
        params = {
            "company": "Test & Co. <Special>",
            "title": "Report: Q1 2026 Analysis",
            "footer": "© 2026 - All Rights Reserved"
        }
        
        # Excel should handle special chars
        excel_response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/excel",
            headers=auth_headers,
            params=params
        )
        assert excel_response.status_code == 200
        
        # PDF should handle special chars
        pdf_response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/pdf",
            headers=auth_headers,
            params=params
        )
        assert pdf_response.status_code == 200

    def test_partial_branding(self, auth_headers, valid_analysis_id):
        """Test export works with only some branding fields"""
        # Only company
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/excel",
            headers=auth_headers,
            params={"company": "TestCorp"}
        )
        assert response.status_code == 200
        
        # Only title
        response = requests.get(
            f"{BASE_URL}/api/events/export/{valid_analysis_id}/pdf",
            headers=auth_headers,
            params={"title": "Custom Report Title"}
        )
        assert response.status_code == 200
