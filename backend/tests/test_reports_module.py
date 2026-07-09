"""
FalconOps AI - Enterprise Reports Module Tests
Tests for Executive Reports, SLA Reports, Incident Analytics, Team Performance, and Export functionality
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestReportsModule:
    """Test suite for Enterprise Reports Module"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - login and get auth token"""
        self.admin_email = "admin@falconapps.com"
        self.admin_password = "Admin@123"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    # ==================== Executive Report Tests ====================
    
    def test_executive_report_basic(self):
        """Test GET /api/reports/executive - basic request"""
        response = self.session.get(f"{BASE_URL}/api/reports/executive")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "period" in data, "Response should contain 'period'"
        assert "kpis" in data, "Response should contain 'kpis'"
        assert "sla_summary" in data, "Response should contain 'sla_summary'"
        assert "generated_at" in data, "Response should contain 'generated_at'"
        
        # Verify KPIs structure
        kpis = data["kpis"]
        assert "total_incidents" in kpis
        assert "resolution_rate" in kpis
        assert "avg_mttr_minutes" in kpis
        assert "open_incidents" in kpis
        assert "critical_incidents" in kpis
        
        print(f"✓ Executive Report - Total Incidents: {kpis['total_incidents']}, Resolution Rate: {kpis['resolution_rate']}%")
    
    def test_executive_report_with_date_range(self):
        """Test GET /api/reports/executive with date range parameters"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        response = self.session.get(
            f"{BASE_URL}/api/reports/executive",
            params={"start_date": start_date, "end_date": end_date}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify date range is reflected
        assert data["period"]["start_date"] == start_date
        assert data["period"]["end_date"] == end_date
        
        print(f"✓ Executive Report with date range: {start_date} to {end_date}")
    
    def test_executive_report_with_ai_summary(self):
        """Test GET /api/reports/executive with AI summary enabled"""
        response = self.session.get(
            f"{BASE_URL}/api/reports/executive",
            params={"include_ai_summary": "true"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # AI summary should be present
        assert "ai_summary" in data, "AI summary should be included when requested"
        assert data["ai_summary"] is not None, "AI summary should not be None"
        assert len(data["ai_summary"]) > 0, "AI summary should have content"
        
        print(f"✓ Executive Report with AI Summary - Length: {len(data['ai_summary'])} chars")
        print(f"  AI Summary Preview: {data['ai_summary'][:200]}...")
    
    def test_executive_report_incident_trends(self):
        """Test that executive report includes incident trends"""
        response = self.session.get(f"{BASE_URL}/api/reports/executive")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "incident_trends" in data, "Response should contain incident_trends"
        # Trends should be a list
        assert isinstance(data["incident_trends"], list)
        
        print(f"✓ Executive Report - Incident Trends: {len(data['incident_trends'])} data points")
    
    def test_executive_report_category_breakdown(self):
        """Test that executive report includes category breakdown"""
        response = self.session.get(f"{BASE_URL}/api/reports/executive")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "category_breakdown" in data, "Response should contain category_breakdown"
        assert isinstance(data["category_breakdown"], list)
        
        print(f"✓ Executive Report - Categories: {len(data['category_breakdown'])} categories")
    
    def test_executive_report_team_performance(self):
        """Test that executive report includes team performance"""
        response = self.session.get(f"{BASE_URL}/api/reports/executive")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "team_performance" in data, "Response should contain team_performance"
        assert isinstance(data["team_performance"], list)
        
        print(f"✓ Executive Report - Teams: {len(data['team_performance'])} teams")
    
    # ==================== SLA Report Tests ====================
    
    def test_sla_report_basic(self):
        """Test GET /api/reports/sla - basic request"""
        response = self.session.get(f"{BASE_URL}/api/reports/sla")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "period" in data
        assert "summary" in data
        assert "service_breakdown" in data
        assert "availability_trend" in data
        assert "generated_at" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "overall_availability" in summary
        assert "sla_compliance" in summary
        assert "total_services" in summary
        
        print(f"✓ SLA Report - Availability: {summary['overall_availability']}%, Compliance: {summary['sla_compliance']}%")
    
    def test_sla_report_with_date_range(self):
        """Test GET /api/reports/sla with date range"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = self.session.get(
            f"{BASE_URL}/api/reports/sla",
            params={"start_date": start_date, "end_date": end_date}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["period"]["start_date"] == start_date
        assert data["period"]["end_date"] == end_date
        
        print(f"✓ SLA Report with date range: {start_date} to {end_date}")
    
    def test_sla_report_service_breakdown(self):
        """Test SLA report service breakdown structure"""
        response = self.session.get(f"{BASE_URL}/api/reports/sla")
        
        assert response.status_code == 200
        data = response.json()
        
        service_breakdown = data.get("service_breakdown", [])
        if service_breakdown:
            # Verify service breakdown structure
            service = service_breakdown[0]
            assert "service_name" in service
            assert "availability_percent" in service
            assert "sla_target" in service
            assert "sla_met" in service
            assert "avg_latency_ms" in service
            
            print(f"✓ SLA Report - {len(service_breakdown)} services in breakdown")
        else:
            print("✓ SLA Report - No services in breakdown (empty data)")
    
    # ==================== Incident Analytics Tests ====================
    
    def test_incident_analytics_basic(self):
        """Test GET /api/reports/incidents - basic request"""
        response = self.session.get(f"{BASE_URL}/api/reports/incidents")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "period" in data
        assert "summary" in data
        assert "mttr_stats" in data
        assert "severity_breakdown" in data
        assert "daily_trend" in data
        assert "hourly_distribution" in data
        assert "recent_incidents" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "total_incidents" in summary
        assert "resolved_incidents" in summary
        assert "open_incidents" in summary
        assert "critical_incidents" in summary
        
        print(f"✓ Incident Analytics - Total: {summary['total_incidents']}, Critical: {summary['critical_incidents']}")
    
    def test_incident_analytics_mttr_stats(self):
        """Test incident analytics MTTR statistics"""
        response = self.session.get(f"{BASE_URL}/api/reports/incidents")
        
        assert response.status_code == 200
        data = response.json()
        
        mttr_stats = data.get("mttr_stats", {})
        assert "average_minutes" in mttr_stats
        assert "min_minutes" in mttr_stats
        assert "max_minutes" in mttr_stats
        
        print(f"✓ Incident Analytics - MTTR: Avg={mttr_stats['average_minutes']}m, Min={mttr_stats['min_minutes']}m, Max={mttr_stats['max_minutes']}m")
    
    def test_incident_analytics_severity_breakdown(self):
        """Test incident analytics severity breakdown"""
        response = self.session.get(f"{BASE_URL}/api/reports/incidents")
        
        assert response.status_code == 200
        data = response.json()
        
        severity_breakdown = data.get("severity_breakdown", [])
        assert isinstance(severity_breakdown, list)
        
        # Should have severity levels
        severities = [s["severity"] for s in severity_breakdown]
        print(f"✓ Incident Analytics - Severity levels: {severities}")
    
    def test_incident_analytics_hourly_distribution(self):
        """Test incident analytics hourly distribution"""
        response = self.session.get(f"{BASE_URL}/api/reports/incidents")
        
        assert response.status_code == 200
        data = response.json()
        
        hourly = data.get("hourly_distribution", [])
        assert isinstance(hourly, list)
        # Should have 24 hours
        assert len(hourly) == 24, f"Expected 24 hours, got {len(hourly)}"
        
        print(f"✓ Incident Analytics - Hourly distribution: {len(hourly)} hours")
    
    def test_incident_analytics_recent_incidents(self):
        """Test incident analytics recent incidents with AI analysis flag"""
        response = self.session.get(f"{BASE_URL}/api/reports/incidents")
        
        assert response.status_code == 200
        data = response.json()
        
        recent = data.get("recent_incidents", [])
        if recent:
            incident = recent[0]
            assert "id" in incident
            assert "title" in incident
            assert "severity" in incident
            assert "status" in incident
            assert "has_ai_analysis" in incident
            
            print(f"✓ Incident Analytics - Recent incidents: {len(recent)}, First has AI: {incident['has_ai_analysis']}")
        else:
            print("✓ Incident Analytics - No recent incidents")
    
    # ==================== Team Performance Tests ====================
    
    def test_team_performance_basic(self):
        """Test GET /api/reports/team-performance - basic request"""
        response = self.session.get(f"{BASE_URL}/api/reports/team-performance")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "period" in data
        assert "summary" in data
        assert "team_breakdown" in data
        assert "generated_at" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "total_teams" in summary
        assert "total_incidents" in summary
        assert "overall_resolution_rate" in summary
        
        print(f"✓ Team Performance - Teams: {summary['total_teams']}, Resolution Rate: {summary['overall_resolution_rate']}%")
    
    def test_team_performance_breakdown_structure(self):
        """Test team performance breakdown structure"""
        response = self.session.get(f"{BASE_URL}/api/reports/team-performance")
        
        assert response.status_code == 200
        data = response.json()
        
        team_breakdown = data.get("team_breakdown", [])
        if team_breakdown:
            team = team_breakdown[0]
            assert "team" in team
            assert "total_incidents" in team
            assert "resolved" in team
            assert "open" in team
            assert "critical" in team
            assert "resolution_rate" in team
            assert "avg_mttr_minutes" in team
            assert "workload_percentage" in team
            
            print(f"✓ Team Performance - {len(team_breakdown)} teams, Top team: {team['team']}")
        else:
            print("✓ Team Performance - No teams in breakdown")
    
    # ==================== Export Tests ====================
    
    def test_export_pdf_executive(self):
        """Test GET /api/reports/export/pdf for executive report"""
        response = self.session.get(
            f"{BASE_URL}/api/reports/export/pdf",
            params={"report_type": "executive"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify PDF content type
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got {content_type}"
        
        # Verify content disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert ".pdf" in content_disp
        
        # Verify PDF content (starts with %PDF)
        assert response.content[:4] == b'%PDF', "Response should be valid PDF"
        
        print(f"✓ PDF Export (Executive) - Size: {len(response.content)} bytes")
    
    def test_export_pdf_sla(self):
        """Test GET /api/reports/export/pdf for SLA report"""
        response = self.session.get(
            f"{BASE_URL}/api/reports/export/pdf",
            params={"report_type": "sla"}
        )
        
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        
        print(f"✓ PDF Export (SLA) - Size: {len(response.content)} bytes")
    
    def test_export_pdf_incidents(self):
        """Test GET /api/reports/export/pdf for incidents report"""
        response = self.session.get(
            f"{BASE_URL}/api/reports/export/pdf",
            params={"report_type": "incidents"}
        )
        
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        
        print(f"✓ PDF Export (Incidents) - Size: {len(response.content)} bytes")
    
    def test_export_excel_executive(self):
        """Test GET /api/reports/export/excel for executive report"""
        response = self.session.get(
            f"{BASE_URL}/api/reports/export/excel",
            params={"report_type": "executive"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify Excel content type
        content_type = response.headers.get("content-type", "")
        assert "spreadsheet" in content_type or "excel" in content_type.lower() or "openxml" in content_type, f"Expected Excel content type, got {content_type}"
        
        # Verify content disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert ".xlsx" in content_disp
        
        # Verify Excel content (starts with PK for ZIP-based xlsx)
        assert response.content[:2] == b'PK', "Response should be valid XLSX (ZIP format)"
        
        print(f"✓ Excel Export (Executive) - Size: {len(response.content)} bytes")
    
    def test_export_excel_sla(self):
        """Test GET /api/reports/export/excel for SLA report"""
        response = self.session.get(
            f"{BASE_URL}/api/reports/export/excel",
            params={"report_type": "sla"}
        )
        
        assert response.status_code == 200
        assert response.content[:2] == b'PK'
        
        print(f"✓ Excel Export (SLA) - Size: {len(response.content)} bytes")
    
    def test_export_excel_incidents(self):
        """Test GET /api/reports/export/excel for incidents report"""
        response = self.session.get(
            f"{BASE_URL}/api/reports/export/excel",
            params={"report_type": "incidents"}
        )
        
        assert response.status_code == 200
        assert response.content[:2] == b'PK'
        
        print(f"✓ Excel Export (Incidents) - Size: {len(response.content)} bytes")
    
    def test_export_with_date_range(self):
        """Test export with date range parameters"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        response = self.session.get(
            f"{BASE_URL}/api/reports/export/pdf",
            params={
                "report_type": "executive",
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        
        print(f"✓ PDF Export with date range: {start_date} to {end_date}")
    
    # ==================== Authentication Tests ====================
    
    def test_reports_require_auth(self):
        """Test that reports endpoints require authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        endpoints = [
            "/api/reports/executive",
            "/api/reports/sla",
            "/api/reports/incidents",
            "/api/reports/team-performance",
            "/api/reports/export/pdf",
            "/api/reports/export/excel"
        ]
        
        for endpoint in endpoints:
            response = no_auth_session.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"Expected 401/403 for {endpoint}, got {response.status_code}"
        
        print(f"✓ All {len(endpoints)} report endpoints require authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
