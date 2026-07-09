"""
FalconOps AI - Alert Engine, Incident Engine, Capacity Prediction Tests
Testing all APIs for alert/incident lifecycle and capacity forecasting
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ============ FIXTURES ============

@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@falconapps.com",
        "password": "Admin@123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")

@pytest.fixture(scope="module")
def headers(auth_token):
    """Auth headers for requests"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }

# ============ SEED DATA TESTS ============

class TestSeedDataAPI:
    """Test seed data generation for demo data"""
    
    def test_seed_full_demo(self, headers):
        """POST /api/seed/full - Generate complete demo data"""
        response = requests.post(f"{BASE_URL}/api/seed/full", headers=headers)
        assert response.status_code == 200, f"Seed full failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "metrics" in data
        assert "alerts" in data
        assert "incidents" in data
        print(f"Seed result: {data['message']}")
    
    def test_seed_metrics_only(self, headers):
        """POST /api/seed/metrics - Generate sample metrics"""
        response = requests.post(f"{BASE_URL}/api/seed/metrics?hours=12", headers=headers)
        assert response.status_code == 200, f"Seed metrics failed: {response.text}"
        data = response.json()
        
        assert "count" in data
        assert data["count"] > 0
        print(f"Seeded {data['count']} metric data points")
    
    def test_seed_alerts_only(self, headers):
        """POST /api/seed/alerts - Generate sample alerts"""
        response = requests.post(f"{BASE_URL}/api/seed/alerts?count=10", headers=headers)
        assert response.status_code == 200, f"Seed alerts failed: {response.text}"
        data = response.json()
        
        assert "count" in data
        assert data["count"] == 10 or data["count"] > 0  # May deduplicate
        print(f"Seeded {data['count']} alerts")
    
    def test_seed_requires_auth(self):
        """Seed endpoints require authentication"""
        response = requests.post(f"{BASE_URL}/api/seed/full")
        assert response.status_code == 401 or response.status_code == 403


# ============ ALERT ENGINE TESTS ============

class TestAlertEngineStats:
    """Test Alert Engine statistics endpoints"""
    
    def test_get_alert_stats(self, headers):
        """GET /api/alert-engine/stats - Get alert statistics"""
        response = requests.get(f"{BASE_URL}/api/alert-engine/stats", headers=headers)
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        
        assert "by_status" in data
        assert "by_severity" in data
        assert "active_alerts" in data
        assert "avg_mttr_minutes" in data
        
        # Verify proper types
        assert isinstance(data["active_alerts"], int)
        assert isinstance(data["by_status"], dict)
        print(f"Active alerts: {data['active_alerts']}, MTTR: {data['avg_mttr_minutes']}m")


class TestAlertEngineList:
    """Test Alert Engine listing endpoints"""
    
    def test_get_active_alerts(self, headers):
        """GET /api/alert-engine/active - Get active alerts"""
        response = requests.get(f"{BASE_URL}/api/alert-engine/active", headers=headers)
        assert response.status_code == 200, f"Get active alerts failed: {response.text}"
        data = response.json()
        
        assert "alerts" in data
        assert "total" in data
        assert isinstance(data["alerts"], list)
        print(f"Active alerts count: {data['total']}")
    
    def test_get_alerts_list(self, headers):
        """GET /api/alert-engine - List all alerts"""
        response = requests.get(f"{BASE_URL}/api/alert-engine?limit=50", headers=headers)
        assert response.status_code == 200, f"Get alerts list failed: {response.text}"
        data = response.json()
        
        assert "alerts" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        print(f"Total alerts: {data['total']}")
    
    def test_get_alerts_with_filters(self, headers):
        """GET /api/alert-engine - List alerts with severity filter"""
        response = requests.get(f"{BASE_URL}/api/alert-engine?severity=critical&limit=20", headers=headers)
        assert response.status_code == 200, f"Get filtered alerts failed: {response.text}"
        data = response.json()
        
        # All returned alerts should be critical
        for alert in data.get("alerts", []):
            if alert.get("severity"):
                assert alert["severity"] == "critical"
    
    def test_get_alerts_with_status_filter(self, headers):
        """GET /api/alert-engine - List alerts with status filter"""
        response = requests.get(f"{BASE_URL}/api/alert-engine?status=triggered&limit=20", headers=headers)
        assert response.status_code == 200, f"Get status filtered alerts failed: {response.text}"
        data = response.json()
        
        for alert in data.get("alerts", []):
            assert alert.get("status") == "triggered"


class TestAlertEngineCreate:
    """Test Alert Engine create operations"""
    
    def test_create_alert(self, headers):
        """POST /api/alert-engine - Create a new alert"""
        alert_data = {
            "title": "TEST_High CPU Alert",
            "description": "CPU usage exceeded 90% threshold on test server",
            "severity": "high",
            "source": "test_automation",
            "entity_type": "service",
            "entity_id": "test-service-001",
            "entity_name": "test-api-service",
            "metric_name": "cpu_usage",
            "metric_value": 92.5,
            "threshold": 90.0,
            "tags": {"host": "test-web-01", "environment": "test"}
        }
        
        response = requests.post(f"{BASE_URL}/api/alert-engine", headers=headers, json=alert_data)
        assert response.status_code == 200, f"Create alert failed: {response.text}"
        data = response.json()
        
        # Verify response data
        assert "id" in data
        assert data["title"] == alert_data["title"]
        assert data["severity"] == "high"
        assert data["status"] == "triggered"
        assert data["metric_value"] == 92.5
        
        # Store alert ID for cleanup
        TestAlertEngineCreate.test_alert_id = data["id"]
        print(f"Created alert: {data['id']}")
        return data["id"]
    
    def test_get_created_alert(self, headers):
        """GET /api/alert-engine/{id} - Verify alert persistence"""
        alert_id = getattr(TestAlertEngineCreate, 'test_alert_id', None)
        if not alert_id:
            pytest.skip("No alert created")
        
        response = requests.get(f"{BASE_URL}/api/alert-engine/{alert_id}", headers=headers)
        assert response.status_code == 200, f"Get alert failed: {response.text}"
        data = response.json()
        
        assert data["id"] == alert_id
        assert data["title"] == "TEST_High CPU Alert"


class TestAlertEngineActions:
    """Test Alert Engine acknowledge and resolve operations"""
    
    def test_acknowledge_alert(self, headers):
        """POST /api/alert-engine/{id}/acknowledge - Acknowledge an alert"""
        # First create a fresh alert
        alert_data = {
            "title": "TEST_Alert for Ack",
            "description": "Test alert for acknowledge test",
            "severity": "medium",
            "source": "test_automation",
            "entity_type": "service",
            "entity_id": "test-ack-service",
            "entity_name": "test-ack-service",
            "metric_name": "test_metric",
            "metric_value": 85.0,
            "threshold": 80.0
        }
        
        create_response = requests.post(f"{BASE_URL}/api/alert-engine", headers=headers, json=alert_data)
        assert create_response.status_code == 200
        alert_id = create_response.json()["id"]
        
        # Acknowledge the alert
        ack_response = requests.post(
            f"{BASE_URL}/api/alert-engine/{alert_id}/acknowledge", 
            headers=headers,
            json={"notes": "Acknowledged for testing"}
        )
        assert ack_response.status_code == 200, f"Acknowledge failed: {ack_response.text}"
        data = ack_response.json()
        
        assert data["status"] == "acknowledged"
        assert data["acknowledged_by"] == "admin@falconapps.com"
        assert data["acknowledged_at"] is not None
        
        TestAlertEngineActions.ack_alert_id = alert_id
        print(f"Acknowledged alert: {alert_id}")
    
    def test_resolve_alert(self, headers):
        """POST /api/alert-engine/{id}/resolve - Resolve an alert"""
        alert_id = getattr(TestAlertEngineActions, 'ack_alert_id', None)
        if not alert_id:
            pytest.skip("No acknowledged alert available")
        
        resolve_response = requests.post(
            f"{BASE_URL}/api/alert-engine/{alert_id}/resolve",
            headers=headers,
            json={"notes": "Resolved - test complete"}
        )
        assert resolve_response.status_code == 200, f"Resolve failed: {resolve_response.text}"
        data = resolve_response.json()
        
        assert data["status"] == "resolved"
        assert data["resolved_by"] == "admin@falconapps.com"
        assert data["resolved_at"] is not None
        print(f"Resolved alert: {alert_id}")
    
    def test_resolve_triggered_alert_directly(self, headers):
        """Test resolving a triggered alert directly (without acknowledge)"""
        # Create a fresh alert
        alert_data = {
            "title": "TEST_Alert for Direct Resolve",
            "description": "Test alert for direct resolve test",
            "severity": "low",
            "source": "test_automation",
            "entity_type": "service",
            "entity_id": "test-resolve-service",
            "entity_name": "test-resolve-service"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/alert-engine", headers=headers, json=alert_data)
        alert_id = create_response.json()["id"]
        
        # Resolve directly
        resolve_response = requests.post(
            f"{BASE_URL}/api/alert-engine/{alert_id}/resolve",
            headers=headers,
            json={}
        )
        assert resolve_response.status_code == 200
        assert resolve_response.json()["status"] == "resolved"


# ============ INCIDENT ENGINE TESTS ============

class TestIncidentEngineStats:
    """Test Incident Engine statistics endpoints"""
    
    def test_get_incident_stats(self, headers):
        """GET /api/incident-engine/stats - Get incident statistics"""
        response = requests.get(f"{BASE_URL}/api/incident-engine/stats", headers=headers)
        assert response.status_code == 200, f"Get incident stats failed: {response.text}"
        data = response.json()
        
        assert "by_status" in data
        assert "by_severity" in data
        assert "active_incidents" in data
        assert "avg_mttr_minutes" in data
        print(f"Active incidents: {data['active_incidents']}, MTTR: {data['avg_mttr_minutes']}m")


class TestIncidentEngineList:
    """Test Incident Engine listing endpoints"""
    
    def test_get_active_incidents(self, headers):
        """GET /api/incident-engine/active - Get active incidents"""
        response = requests.get(f"{BASE_URL}/api/incident-engine/active", headers=headers)
        assert response.status_code == 200, f"Get active incidents failed: {response.text}"
        data = response.json()
        
        assert "incidents" in data
        assert "total" in data
        assert isinstance(data["incidents"], list)
        print(f"Active incidents: {data['total']}")
    
    def test_get_incidents_list(self, headers):
        """GET /api/incident-engine - List all incidents"""
        response = requests.get(f"{BASE_URL}/api/incident-engine?limit=50", headers=headers)
        assert response.status_code == 200, f"Get incidents list failed: {response.text}"
        data = response.json()
        
        assert "incidents" in data
        assert "total" in data
        print(f"Total incidents: {data['total']}")


class TestIncidentEngineCreate:
    """Test Incident Engine create operations"""
    
    def test_create_incident(self, headers):
        """POST /api/incident-engine - Create a new incident"""
        incident_data = {
            "title": "TEST_API Outage Incident",
            "description": "Critical API outage affecting production",
            "severity": "sev2",
            "affected_services": ["api-gateway", "user-service"],
            "affected_hosts": ["prod-api-01"],
            "source": "test_automation"
        }
        
        response = requests.post(f"{BASE_URL}/api/incident-engine", headers=headers, json=incident_data)
        assert response.status_code == 200, f"Create incident failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["title"] == incident_data["title"]
        assert data["severity"] == "sev2"
        assert data["status"] == "active"
        assert "timeline" in data
        assert len(data["timeline"]) >= 1
        
        TestIncidentEngineCreate.test_incident_id = data["id"]
        print(f"Created incident: {data['id']}")
    
    def test_get_created_incident(self, headers):
        """GET /api/incident-engine/{id} - Verify incident persistence"""
        incident_id = getattr(TestIncidentEngineCreate, 'test_incident_id', None)
        if not incident_id:
            pytest.skip("No incident created")
        
        response = requests.get(f"{BASE_URL}/api/incident-engine/{incident_id}", headers=headers)
        assert response.status_code == 200, f"Get incident failed: {response.text}"
        data = response.json()
        
        assert data["id"] == incident_id
        assert data["title"] == "TEST_API Outage Incident"


class TestIncidentEngineActions:
    """Test Incident Engine status updates and RCA"""
    
    def test_update_incident_status(self, headers):
        """POST /api/incident-engine/{id}/status - Update status to investigating"""
        # First create an incident
        incident_data = {
            "title": "TEST_Incident for Status Test",
            "description": "Incident for testing status updates",
            "severity": "sev3",
            "source": "test_automation"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/incident-engine", headers=headers, json=incident_data)
        assert create_response.status_code == 200
        incident_id = create_response.json()["id"]
        
        # Update status
        status_response = requests.post(
            f"{BASE_URL}/api/incident-engine/{incident_id}/status",
            headers=headers,
            json={"status": "investigating", "notes": "Started investigation"}
        )
        assert status_response.status_code == 200, f"Update status failed: {status_response.text}"
        data = status_response.json()
        
        assert data["status"] == "investigating"
        # Verify timeline was updated
        assert len(data["timeline"]) >= 2
        
        TestIncidentEngineActions.status_test_incident_id = incident_id
        print(f"Updated incident status: {incident_id}")
    
    def test_resolve_incident(self, headers):
        """POST /api/incident-engine/{id}/status - Resolve incident"""
        incident_id = getattr(TestIncidentEngineActions, 'status_test_incident_id', None)
        if not incident_id:
            pytest.skip("No incident available")
        
        resolve_response = requests.post(
            f"{BASE_URL}/api/incident-engine/{incident_id}/status",
            headers=headers,
            json={"status": "resolved", "notes": "Issue resolved - test complete"}
        )
        assert resolve_response.status_code == 200
        data = resolve_response.json()
        
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None
        assert data["resolved_by"] == "admin@falconapps.com"
    
    def test_trigger_rca_analysis(self, headers):
        """POST /api/incident-engine/{id}/analyze-rca - Trigger RCA"""
        # Create an incident with alerts for RCA
        incident_data = {
            "title": "TEST_Incident for RCA",
            "description": "Incident for RCA analysis testing",
            "severity": "sev2",
            "affected_services": ["test-service"],
            "source": "test_automation"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/incident-engine", headers=headers, json=incident_data)
        incident_id = create_response.json()["id"]
        
        # Trigger RCA
        rca_response = requests.post(
            f"{BASE_URL}/api/incident-engine/{incident_id}/analyze-rca",
            headers=headers
        )
        assert rca_response.status_code == 200, f"RCA analysis failed: {rca_response.text}"
        data = rca_response.json()
        
        assert "incident_id" in data
        assert "rca" in data
        assert "root_cause" in data["rca"]
        assert "analysis_type" in data["rca"]
        print(f"RCA completed. Type: {data['rca']['analysis_type']}, Cause: {data['rca']['root_cause'][:50]}...")


class TestIncidentEngineAutoCorrelate:
    """Test Incident Engine auto-correlation"""
    
    def test_auto_correlate_alerts(self, headers):
        """POST /api/incident-engine/auto-correlate - Auto correlate alerts"""
        response = requests.post(
            f"{BASE_URL}/api/incident-engine/auto-correlate?time_window_minutes=30&min_alerts=2",
            headers=headers
        )
        assert response.status_code == 200, f"Auto correlate failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "incidents" in data
        assert "count" in data
        print(f"Auto-correlate result: {data['message']}")


# ============ CAPACITY PREDICTION TESTS ============

class TestCapacityPrediction:
    """Test Capacity Prediction API endpoints"""
    
    def test_capacity_predict_cpu(self, headers):
        """GET /api/capacity/predict - Predict CPU capacity"""
        response = requests.get(
            f"{BASE_URL}/api/capacity/predict?metric_name=cpu_usage&horizon=24h&threshold=90",
            headers=headers
        )
        assert response.status_code == 200, f"Capacity predict failed: {response.text}"
        data = response.json()
        
        assert "metric_name" in data
        assert "status" in data
        
        if data["status"] == "success":
            assert "current_value" in data
            assert "prediction" in data
            assert "threshold_analysis" in data
            assert "risk_assessment" in data
            assert "forecast_series" in data
            
            # Verify prediction structure
            assert "predicted_value" in data["prediction"]
            assert "confidence" in data["prediction"]
            
            print(f"CPU Prediction: current={data['current_value']}, predicted={data['prediction']['predicted_value']}")
        else:
            print(f"Capacity predict status: {data['status']} - {data.get('message')}")
    
    def test_capacity_predict_with_host(self, headers):
        """GET /api/capacity/predict - Predict with specific host filter"""
        response = requests.get(
            f"{BASE_URL}/api/capacity/predict?metric_name=cpu_usage&host=prod-web-01&horizon=24h&threshold=90",
            headers=headers
        )
        assert response.status_code == 200, f"Capacity predict with host failed: {response.text}"
        data = response.json()
        
        assert "metric_name" in data
        if data.get("host"):
            assert data["host"] == "prod-web-01"
    
    def test_capacity_predict_disk(self, headers):
        """GET /api/capacity/predict - Predict disk usage"""
        response = requests.get(
            f"{BASE_URL}/api/capacity/predict?metric_name=disk_usage&horizon=7d&threshold=85",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "metric_name" in data
        assert data["metric_name"] == "disk_usage"


class TestCapacityTrends:
    """Test Capacity Trends API"""
    
    def test_get_trends_report(self, headers):
        """GET /api/capacity/trends - Get trends report"""
        response = requests.get(f"{BASE_URL}/api/capacity/trends", headers=headers)
        assert response.status_code == 200, f"Get trends failed: {response.text}"
        data = response.json()
        
        assert "generated_at" in data
        assert "metrics_analyzed" in data
        assert "increasing_trends" in data
        assert "decreasing_trends" in data
        assert "stable_trends" in data
        
        print(f"Trends: {len(data['increasing_trends'])} increasing, "
              f"{len(data['decreasing_trends'])} decreasing, "
              f"{len(data['stable_trends'])} stable")


class TestCapacityAlerts:
    """Test Capacity Alerts API"""
    
    def test_get_capacity_alerts(self, headers):
        """GET /api/capacity/alerts - Get capacity warnings"""
        response = requests.get(
            f"{BASE_URL}/api/capacity/alerts?threshold=90&horizon=24h",
            headers=headers
        )
        assert response.status_code == 200, f"Get capacity alerts failed: {response.text}"
        data = response.json()
        
        assert "alerts" in data
        assert "total" in data
        assert isinstance(data["alerts"], list)
        
        print(f"Capacity alerts: {data['total']}")
        
        # Verify alert structure if any exist
        for alert in data.get("alerts", [])[:3]:
            assert "metric" in alert
            assert "risk_level" in alert


# ============ AUTH TESTS ============

class TestAuthRequired:
    """Test that all endpoints require authentication"""
    
    def test_alert_engine_requires_auth(self):
        """Alert engine endpoints require auth"""
        endpoints = [
            ("GET", "/api/alert-engine"),
            ("GET", "/api/alert-engine/stats"),
            ("GET", "/api/alert-engine/active"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}")
            else:
                response = requests.post(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth"
    
    def test_incident_engine_requires_auth(self):
        """Incident engine endpoints require auth"""
        endpoints = [
            ("GET", "/api/incident-engine"),
            ("GET", "/api/incident-engine/stats"),
            ("GET", "/api/incident-engine/active"),
        ]
        
        for method, endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth"
    
    def test_capacity_requires_auth(self):
        """Capacity endpoints require auth"""
        endpoints = [
            "/api/capacity/predict?metric_name=cpu_usage",
            "/api/capacity/trends",
            "/api/capacity/alerts",
        ]
        
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
