"""
FalconOps AI - Alert Ingestion and Knowledge Base API Tests
Tests for webhook-based alert ingestion, knowledge base, and AI learning features
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://health-rules-engine.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Get auth headers for admin"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestWebhookManagement:
    """Tests for webhook CRUD operations"""
    
    def test_list_webhooks(self, auth_headers):
        """GET /api/ingest/webhooks - list all webhooks"""
        response = requests.get(f"{BASE_URL}/api/ingest/webhooks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "webhooks" in data
        assert isinstance(data["webhooks"], list)
    
    def test_create_webhook(self, auth_headers):
        """POST /api/ingest/webhooks - create new webhook"""
        payload = {
            "name": "TEST_Datadog Alerts",
            "source_type": "datadog",
            "enabled": True,
            "auto_analyze": True,
            "analyze_threshold": 15
        }
        response = requests.post(
            f"{BASE_URL}/api/ingest/webhooks",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "webhook_id" in data
        assert "webhook_url" in data
        assert data["name"] == "TEST_Datadog Alerts"
        
        # Store webhook_id for cleanup
        TestWebhookManagement.test_webhook_id = data["webhook_id"]
    
    def test_get_webhook_details(self, auth_headers):
        """GET /api/ingest/webhooks/{id} - get webhook details"""
        webhook_id = getattr(TestWebhookManagement, 'test_webhook_id', None)
        if not webhook_id:
            pytest.skip("No test webhook created")
        
        response = requests.get(
            f"{BASE_URL}/api/ingest/webhooks/{webhook_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == webhook_id
        assert data["name"] == "TEST_Datadog Alerts"
        assert data["source_type"] == "datadog"
    
    def test_delete_webhook(self, auth_headers):
        """DELETE /api/ingest/webhooks/{id} - delete webhook"""
        webhook_id = getattr(TestWebhookManagement, 'test_webhook_id', None)
        if not webhook_id:
            pytest.skip("No test webhook created")
        
        response = requests.delete(
            f"{BASE_URL}/api/ingest/webhooks/{webhook_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify deletion
        response = requests.get(
            f"{BASE_URL}/api/ingest/webhooks/{webhook_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_delete_nonexistent_webhook(self, auth_headers):
        """DELETE /api/ingest/webhooks/{id} - returns 404 for nonexistent"""
        response = requests.delete(
            f"{BASE_URL}/api/ingest/webhooks/nonexistent-id",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestWebhookAlertIngestion:
    """Tests for webhook-based alert ingestion (no auth required)"""
    
    @pytest.fixture(scope="class")
    def test_webhook(self, auth_headers):
        """Create a test webhook for alert ingestion tests"""
        payload = {
            "name": "TEST_Ingestion Webhook",
            "source_type": "prometheus",
            "enabled": True,
            "auto_analyze": False,
            "analyze_threshold": 100
        }
        response = requests.post(
            f"{BASE_URL}/api/ingest/webhooks",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        webhook_id = response.json()["webhook_id"]
        yield webhook_id
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/ingest/webhooks/{webhook_id}", headers=auth_headers)
    
    def test_receive_single_alert_no_auth(self, test_webhook):
        """POST /api/ingest/webhook/{id} - receive alert without auth"""
        payload = {
            "service": "test-service",
            "alert": "TEST_High CPU usage",
            "severity": "warning",
            "host": "test-host-1",
            "source": "prometheus"
        }
        response = requests.post(
            f"{BASE_URL}/api/ingest/webhook/{test_webhook}",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "alert_id" in data
        assert data["message"] == "Alert received"
    
    def test_receive_batch_alerts_no_auth(self, test_webhook):
        """POST /api/ingest/webhook/{id}/batch - receive batch alerts without auth"""
        payload = {
            "alerts": [
                {"service": "test-service-1", "alert": "TEST_Memory spike", "severity": "warning"},
                {"service": "test-service-2", "alert": "TEST_Disk full", "severity": "critical"},
                {"service": "test-service-3", "alert": "TEST_Network latency", "severity": "info"}
            ],
            "source": "prometheus"
        }
        response = requests.post(
            f"{BASE_URL}/api/ingest/webhook/{test_webhook}/batch",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["received"] == 3
    
    def test_receive_alert_invalid_webhook(self):
        """POST /api/ingest/webhook/{id} - returns 404 for invalid webhook"""
        payload = {
            "service": "test-service",
            "alert": "TEST_Alert",
            "severity": "warning"
        }
        response = requests.post(
            f"{BASE_URL}/api/ingest/webhook/invalid-webhook-id",
            json=payload
        )
        assert response.status_code == 404


class TestIngestedAlerts:
    """Tests for ingested alerts management"""
    
    def test_list_ingested_alerts(self, auth_headers):
        """GET /api/ingest/alerts - list ingested alerts"""
        response = requests.get(f"{BASE_URL}/api/ingest/alerts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
    
    def test_list_alerts_with_filters(self, auth_headers):
        """GET /api/ingest/alerts - list with filters"""
        response = requests.get(
            f"{BASE_URL}/api/ingest/alerts?severity=critical&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        # All returned alerts should be critical
        for alert in data["alerts"]:
            assert alert["severity"] == "critical"
    
    def test_list_alerts_requires_auth(self):
        """GET /api/ingest/alerts - requires authentication"""
        response = requests.get(f"{BASE_URL}/api/ingest/alerts")
        assert response.status_code == 401


class TestIngestionStats:
    """Tests for ingestion statistics"""
    
    def test_get_ingestion_stats(self, auth_headers):
        """GET /api/ingest/stats - get ingestion statistics"""
        response = requests.get(f"{BASE_URL}/api/ingest/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_alerts" in data
        assert "analyzed" in data
        assert "unanalyzed" in data
        assert "by_source" in data
        assert "by_severity" in data
        assert "webhooks" in data
    
    def test_stats_requires_auth(self):
        """GET /api/ingest/stats - requires authentication"""
        response = requests.get(f"{BASE_URL}/api/ingest/stats")
        assert response.status_code == 401


class TestKnowledgeBase:
    """Tests for knowledge base and AI learning"""
    
    def test_get_knowledge_stats(self, auth_headers):
        """GET /api/ingest/knowledge/stats - get knowledge base stats"""
        response = requests.get(f"{BASE_URL}/api/ingest/knowledge/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_patterns" in data
        assert "total_occurrences" in data
        assert "total_successes" in data
        assert "verified_patterns" in data
        assert "avg_confidence" in data
        assert "top_patterns" in data
        assert "learning_score" in data
    
    def test_list_knowledge_patterns(self, auth_headers):
        """GET /api/ingest/knowledge/patterns - list learned patterns"""
        response = requests.get(f"{BASE_URL}/api/ingest/knowledge/patterns", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "patterns" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
    
    def test_knowledge_stats_requires_auth(self):
        """GET /api/ingest/knowledge/stats - requires authentication"""
        response = requests.get(f"{BASE_URL}/api/ingest/knowledge/stats")
        assert response.status_code == 401
    
    def test_learn_from_resolution_invalid_incident(self, auth_headers):
        """POST /api/ingest/learn - returns 404 for invalid incident"""
        payload = {
            "incident_id": "nonexistent-incident-id",
            "root_cause": "Test root cause",
            "resolution": "Test resolution",
            "helpful": True
        }
        response = requests.post(
            f"{BASE_URL}/api/ingest/learn",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 404


class TestAnalyzeIngestedAlerts:
    """Tests for analyzing ingested alerts"""
    
    def test_analyze_alerts_no_alerts(self, auth_headers):
        """POST /api/ingest/alerts/analyze - handles no alerts gracefully"""
        # This should return a message about no alerts found
        response = requests.post(
            f"{BASE_URL}/api/ingest/alerts/analyze?time_range_hours=1",
            headers=auth_headers
        )
        # Either 200 with success=false or actual analysis
        assert response.status_code == 200
        data = response.json()
        # If no unanalyzed alerts, should return appropriate message
        if not data.get("success"):
            assert "message" in data
    
    def test_analyze_requires_auth(self):
        """POST /api/ingest/alerts/analyze - requires authentication"""
        response = requests.post(f"{BASE_URL}/api/ingest/alerts/analyze")
        assert response.status_code == 401


class TestDirectAlertIngestion:
    """Tests for authenticated direct alert ingestion"""
    
    def test_ingest_single_alert_authenticated(self, auth_headers):
        """POST /api/ingest/alert - ingest single alert with auth"""
        payload = {
            "service": "TEST_direct-service",
            "alert": "TEST_Direct alert ingestion",
            "severity": "info",
            "host": "direct-host-1"
        }
        response = requests.post(
            f"{BASE_URL}/api/ingest/alert",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "alert_id" in data
    
    def test_ingest_batch_alerts_authenticated(self, auth_headers):
        """POST /api/ingest/alerts/batch - ingest batch alerts with auth"""
        payload = {
            "alerts": [
                {"service": "TEST_batch-service-1", "alert": "TEST_Batch alert 1", "severity": "warning"},
                {"service": "TEST_batch-service-2", "alert": "TEST_Batch alert 2", "severity": "info"}
            ],
            "source": "api"
        }
        response = requests.post(
            f"{BASE_URL}/api/ingest/alerts/batch",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["received"] == 2
    
    def test_direct_ingestion_requires_auth(self):
        """POST /api/ingest/alert - requires authentication"""
        payload = {
            "service": "test-service",
            "alert": "Test alert",
            "severity": "info"
        }
        response = requests.post(f"{BASE_URL}/api/ingest/alert", json=payload)
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
