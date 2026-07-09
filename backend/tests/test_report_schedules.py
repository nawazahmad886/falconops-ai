"""
FalconOps AI - Report Scheduler API Tests
Tests for automated report scheduling CRUD and execution endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestReportSchedulerAuth:
    """Authentication and authorization tests for scheduler endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Get auth token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
    def test_list_schedules_without_auth(self):
        """GET /api/report-schedules without auth should return 401/403"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/report-schedules")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthenticated GET /api/report-schedules returns 401/403")
        
    def test_create_schedule_without_auth(self):
        """POST /api/report-schedules without auth should return 401/403"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(f"{BASE_URL}/api/report-schedules", json={
            "name": "Test Schedule",
            "frequency": "weekly"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthenticated POST /api/report-schedules returns 401/403")


class TestReportSchedulerCRUD:
    """CRUD operations tests for report schedules"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Get auth token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.created_schedule_ids = []
    
    def teardown_method(self, method):
        """Clean up created schedules after each test"""
        for schedule_id in self.created_schedule_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/report-schedules/{schedule_id}")
            except:
                pass
    
    # --- List Schedules ---
    def test_list_schedules_returns_200(self):
        """GET /api/report-schedules returns 200 with schedules array"""
        response = self.session.get(f"{BASE_URL}/api/report-schedules")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "schedules" in data, "Response should contain 'schedules' key"
        assert isinstance(data["schedules"], list), "'schedules' should be a list"
        print(f"✓ GET /api/report-schedules returns 200 with {len(data['schedules'])} schedules")
    
    # --- Create Schedule ---
    def test_create_schedule_minimal(self):
        """POST /api/report-schedules with minimal data creates schedule"""
        unique_name = f"TEST_Schedule_{uuid.uuid4().hex[:8]}"
        payload = {"name": unique_name}
        response = self.session.post(f"{BASE_URL}/api/report-schedules", json=payload)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data, "Response should contain 'id'"
        assert data["name"] == unique_name, "Name should match"
        assert data["frequency"] == "weekly", "Default frequency should be 'weekly'"
        assert data["enabled"] == True, "Default enabled should be True"
        self.created_schedule_ids.append(data["id"])
        print(f"✓ POST /api/report-schedules creates schedule with id={data['id']}")
        
    def test_create_schedule_full_payload(self):
        """POST /api/report-schedules with full data creates schedule"""
        unique_name = f"TEST_Full_Schedule_{uuid.uuid4().hex[:8]}"
        payload = {
            "name": unique_name,
            "frequency": "daily",
            "day_of_week": "mon",
            "day_of_month": 15,
            "hour": 9,
            "format": "excel",
            "recipients": ["cto@test.com", "noc@test.com"],
            "email_subject": "Daily FalconOps Report",
            "branding": {"company": "Test Corp", "title": "Daily Report", "footer": "Confidential"},
            "enabled": True
        }
        response = self.session.post(f"{BASE_URL}/api/report-schedules", json=payload)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["name"] == unique_name
        assert data["frequency"] == "daily"
        assert data["hour"] == 9
        assert data["format"] == "excel"
        assert data["recipients"] == ["cto@test.com", "noc@test.com"]
        assert data["branding"]["company"] == "Test Corp"
        self.created_schedule_ids.append(data["id"])
        print(f"✓ POST /api/report-schedules with full payload creates schedule correctly")
        
    def test_create_schedule_weekly(self):
        """POST /api/report-schedules with weekly frequency"""
        unique_name = f"TEST_Weekly_{uuid.uuid4().hex[:8]}"
        payload = {
            "name": unique_name,
            "frequency": "weekly",
            "day_of_week": "fri",
            "hour": 17,
            "format": "pdf"
        }
        response = self.session.post(f"{BASE_URL}/api/report-schedules", json=payload)
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["frequency"] == "weekly"
        assert data["day_of_week"] == "fri"
        self.created_schedule_ids.append(data["id"])
        print(f"✓ Weekly schedule created with day_of_week='fri'")
        
    def test_create_schedule_monthly(self):
        """POST /api/report-schedules with monthly frequency"""
        unique_name = f"TEST_Monthly_{uuid.uuid4().hex[:8]}"
        payload = {
            "name": unique_name,
            "frequency": "monthly",
            "day_of_month": 1,
            "hour": 6,
            "format": "pdf"
        }
        response = self.session.post(f"{BASE_URL}/api/report-schedules", json=payload)
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["frequency"] == "monthly"
        assert data["day_of_month"] == 1
        self.created_schedule_ids.append(data["id"])
        print(f"✓ Monthly schedule created with day_of_month=1")
    
    # --- Update Schedule ---
    def test_update_schedule_enabled(self):
        """PUT /api/report-schedules/{id} can toggle enabled"""
        # Create schedule first
        unique_name = f"TEST_Toggle_{uuid.uuid4().hex[:8]}"
        create_response = self.session.post(f"{BASE_URL}/api/report-schedules", json={"name": unique_name})
        schedule_id = create_response.json()["id"]
        self.created_schedule_ids.append(schedule_id)
        
        # Disable schedule
        update_response = self.session.put(f"{BASE_URL}/api/report-schedules/{schedule_id}", json={"enabled": False})
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}"
        data = update_response.json()
        assert data["enabled"] == False, "Schedule should be disabled"
        
        # Re-enable schedule
        update_response2 = self.session.put(f"{BASE_URL}/api/report-schedules/{schedule_id}", json={"enabled": True})
        assert update_response2.status_code == 200
        assert update_response2.json()["enabled"] == True
        print(f"✓ PUT /api/report-schedules/{schedule_id} toggles enabled correctly")
        
    def test_update_schedule_fields(self):
        """PUT /api/report-schedules/{id} updates multiple fields"""
        # Create schedule first
        unique_name = f"TEST_Update_{uuid.uuid4().hex[:8]}"
        create_response = self.session.post(f"{BASE_URL}/api/report-schedules", json={"name": unique_name})
        schedule_id = create_response.json()["id"]
        self.created_schedule_ids.append(schedule_id)
        
        # Update fields
        update_payload = {
            "name": f"Updated_{unique_name}",
            "frequency": "monthly",
            "day_of_month": 10,
            "hour": 14,
            "format": "excel"
        }
        update_response = self.session.put(f"{BASE_URL}/api/report-schedules/{schedule_id}", json=update_payload)
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["frequency"] == "monthly"
        assert data["day_of_month"] == 10
        assert data["hour"] == 14
        assert data["format"] == "excel"
        print(f"✓ PUT /api/report-schedules/{schedule_id} updates multiple fields")
        
    def test_update_nonexistent_schedule(self):
        """PUT /api/report-schedules/{id} returns 404 for non-existent schedule"""
        fake_id = str(uuid.uuid4())
        response = self.session.put(f"{BASE_URL}/api/report-schedules/{fake_id}", json={"enabled": False})
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ PUT /api/report-schedules/{fake_id} returns 404")
    
    # --- Delete Schedule ---
    def test_delete_schedule(self):
        """DELETE /api/report-schedules/{id} deletes schedule"""
        # Create schedule first
        unique_name = f"TEST_Delete_{uuid.uuid4().hex[:8]}"
        create_response = self.session.post(f"{BASE_URL}/api/report-schedules", json={"name": unique_name})
        schedule_id = create_response.json()["id"]
        
        # Delete it
        delete_response = self.session.delete(f"{BASE_URL}/api/report-schedules/{schedule_id}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        data = delete_response.json()
        assert data["deleted"] == True
        
        # Verify it's gone - check list
        list_response = self.session.get(f"{BASE_URL}/api/report-schedules")
        schedules = list_response.json()["schedules"]
        schedule_ids = [s["id"] for s in schedules]
        assert schedule_id not in schedule_ids, "Deleted schedule should not be in list"
        print(f"✓ DELETE /api/report-schedules/{schedule_id} removes schedule")
        
    def test_delete_nonexistent_schedule(self):
        """DELETE /api/report-schedules/{id} returns 404 for non-existent schedule"""
        fake_id = str(uuid.uuid4())
        response = self.session.delete(f"{BASE_URL}/api/report-schedules/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ DELETE /api/report-schedules/{fake_id} returns 404")


class TestReportSchedulerExecution:
    """Tests for manual execution and logs endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Get auth token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.created_schedule_ids = []
    
    def teardown_method(self, method):
        for schedule_id in self.created_schedule_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/report-schedules/{schedule_id}")
            except:
                pass
    
    def test_run_schedule_now(self):
        """POST /api/report-schedules/{id}/run triggers execution"""
        # Create schedule first
        unique_name = f"TEST_Run_{uuid.uuid4().hex[:8]}"
        create_response = self.session.post(f"{BASE_URL}/api/report-schedules", json={
            "name": unique_name,
            "recipients": ["test@example.com"]
        })
        schedule_id = create_response.json()["id"]
        self.created_schedule_ids.append(schedule_id)
        
        # Run it
        run_response = self.session.post(f"{BASE_URL}/api/report-schedules/{schedule_id}/run")
        assert run_response.status_code == 200, f"Expected 200, got {run_response.status_code}: {run_response.text}"
        data = run_response.json()
        assert "status" in data, "Response should have 'status'"
        assert data["status"] == "executed"
        print(f"✓ POST /api/report-schedules/{schedule_id}/run executes schedule")
        
    def test_get_schedule_logs(self):
        """GET /api/report-schedules/{id}/logs returns execution logs"""
        # Create and run schedule
        unique_name = f"TEST_Logs_{uuid.uuid4().hex[:8]}"
        create_response = self.session.post(f"{BASE_URL}/api/report-schedules", json={"name": unique_name})
        schedule_id = create_response.json()["id"]
        self.created_schedule_ids.append(schedule_id)
        
        # Run it first to create a log
        self.session.post(f"{BASE_URL}/api/report-schedules/{schedule_id}/run")
        
        # Get logs
        logs_response = self.session.get(f"{BASE_URL}/api/report-schedules/{schedule_id}/logs")
        assert logs_response.status_code == 200, f"Expected 200, got {logs_response.status_code}"
        data = logs_response.json()
        assert "logs" in data, "Response should have 'logs'"
        assert isinstance(data["logs"], list), "'logs' should be a list"
        print(f"✓ GET /api/report-schedules/{schedule_id}/logs returns logs array (count: {len(data['logs'])})")


class TestPDFExportEnhanced:
    """Tests for enhanced PDF export with new charts"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
    def test_get_analysis_id(self):
        """Get an analysis_id from existing uploads"""
        response = self.session.get(f"{BASE_URL}/api/events/uploads")
        assert response.status_code == 200
        data = response.json()
        uploads = data.get("uploads", [])
        analyzed = [u for u in uploads if u.get("status") == "analyzed" and u.get("analysis_id")]
        assert len(analyzed) > 0, "Need at least one analyzed upload for PDF test"
        self.analysis_id = analyzed[0]["analysis_id"]
        print(f"✓ Found analyzed upload with analysis_id={self.analysis_id[:8]}...")
        return self.analysis_id
        
    def test_pdf_export_enhanced_charts(self):
        """GET /api/events/export/{analysis_id}/pdf returns PDF with enhanced charts"""
        # Get analysis_id
        response = self.session.get(f"{BASE_URL}/api/events/uploads")
        uploads = response.json().get("uploads", [])
        analyzed = [u for u in uploads if u.get("status") == "analyzed" and u.get("analysis_id")]
        if not analyzed:
            pytest.skip("No analyzed uploads available for PDF test")
        analysis_id = analyzed[0]["analysis_id"]
        
        # Export PDF
        pdf_response = self.session.get(f"{BASE_URL}/api/events/export/{analysis_id}/pdf")
        assert pdf_response.status_code == 200, f"Expected 200, got {pdf_response.status_code}"
        content_type = pdf_response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"
        
        # Check file starts with PDF magic bytes
        content = pdf_response.content
        assert content[:4] == b'%PDF', "PDF should start with %PDF magic bytes"
        
        # Enhanced PDF should be larger due to new charts (heatmap, timeline, donut pie)
        # Previously was ~5KB min, now should be larger with more charts
        file_size = len(content)
        assert file_size > 10000, f"Enhanced PDF should be >10KB, got {file_size} bytes"
        print(f"✓ PDF export returns valid PDF with size {file_size} bytes (enhanced charts)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
