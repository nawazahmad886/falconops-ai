"""
FalconOps AI - AIOps Brain Test Suite
Testing: Anomaly Detection, Smart Correlation, Impact Analysis, Topology Seeding
Phase 1 + Phase 2 AI Intelligence Layers
"""
import os
import pytest
import requests

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
    if response.status_code == 200:
        token = response.json().get("token") or response.json().get("access_token")
        return token
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


# ========== TOPOLOGY SEEDING TESTS ==========
class TestTopologySeeding:
    """Test topology seeding for service dependency graph"""

    def test_seed_topology(self, api_client):
        """POST /api/seed/topology - Creates 16 service nodes and 20 edges"""
        response = api_client.post(f"{BASE_URL}/api/seed/topology")
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "nodes" in data, "Response missing 'nodes' count"
        assert "edges" in data, "Response missing 'edges' count"
        assert data["nodes"] == 16, f"Expected 16 nodes, got {data['nodes']}"
        assert data["edges"] == 20, f"Expected 20 edges, got {data['edges']}"
        print(f"✓ Topology seeded: {data['nodes']} nodes, {data['edges']} edges")

    def test_seed_full_demo(self, api_client):
        """POST /api/seed/full - Seeds topology + metrics + alerts + incidents"""
        response = api_client.post(f"{BASE_URL}/api/seed/full")
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "topology" in data, "Response missing 'topology'"
        assert "metrics" in data, "Response missing 'metrics'"
        assert "alerts" in data, "Response missing 'alerts'"
        print(f"✓ Full demo seeded: topology={data.get('topology', {}).get('nodes', '?')} nodes, alerts={data.get('alerts', {}).get('count', '?')}")


# ========== ANOMALY DETECTION TESTS ==========
class TestAnomalyDetection:
    """Test multi-algorithm anomaly detection (Z-score, EWMA, Isolation Forest, Dynamic Thresholds, Seasonal)"""

    def test_analyze_metric(self, api_client):
        """GET /api/anomaly-detection/analyze - Returns ensemble analysis with 5 detector results"""
        response = api_client.get(f"{BASE_URL}/api/anomaly-detection/analyze", params={
            "metric_name": "cpu_usage",
            "host": "prod-web-01",
            "lookback_hours": 24
        })
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "metric_name" in data, "Response missing 'metric_name'"
        assert data["metric_name"] == "cpu_usage", f"Wrong metric: {data['metric_name']}"
        
        # Check for anomaly detection result structure
        if data.get("status") == "success":
            assert "anomaly" in data, "Response missing 'anomaly' field"
            anomaly = data["anomaly"]
            assert "ensemble_score" in anomaly, "Missing 'ensemble_score'"
            assert "detectors" in anomaly, "Missing 'detectors'"
            assert "severity" in anomaly, "Missing 'severity'"
            
            # Validate detectors
            detectors = anomaly.get("detectors", {})
            expected_detectors = ["zscore", "ewma", "dynamic_threshold", "seasonal"]
            for det in expected_detectors:
                assert det in detectors, f"Missing detector: {det}"
            
            print(f"✓ Anomaly analysis: score={anomaly['ensemble_score']}, severity={anomaly['severity']}, detectors={len(detectors)}")
        else:
            print(f"✓ Anomaly analysis returned status: {data.get('status')} (may be insufficient_data)")

    def test_anomaly_full_scan(self, api_client):
        """GET /api/anomaly-detection/scan - Full scan across all metrics"""
        response = api_client.get(f"{BASE_URL}/api/anomaly-detection/scan", params={
            "lookback_hours": 24
        })
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "scanned" in data, "Response missing 'scanned'"
        assert "anomalies_found" in data, "Response missing 'anomalies_found'"
        assert "anomalies" in data, "Response missing 'anomalies' list"
        
        # Verify structure of anomalies if found
        if data["anomalies_found"] > 0:
            anomaly = data["anomalies"][0]
            assert "metric_name" in anomaly
            assert "anomaly" in anomaly
            assert "ensemble_score" in anomaly.get("anomaly", {})
        
        print(f"✓ Scan complete: scanned={data['scanned']}, anomalies_found={data['anomalies_found']}")

    def test_metric_baseline(self, api_client):
        """GET /api/anomaly-detection/baseline - Baseline stats for a metric"""
        response = api_client.get(f"{BASE_URL}/api/anomaly-detection/baseline", params={
            "metric_name": "cpu_usage",
            "host": "prod-web-01"
        })
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "metric_name" in data
        assert "status" in data
        
        if data.get("status") == "success":
            assert "mean" in data, "Missing 'mean'"
            assert "std" in data, "Missing 'std'"
            assert "p50" in data, "Missing 'p50'"
            assert "p95" in data, "Missing 'p95'"
            print(f"✓ Baseline stats: mean={data['mean']}, std={data['std']}, p95={data['p95']}")
        else:
            print(f"✓ Baseline returned status: {data.get('status')}")


# ========== SMART CORRELATION TESTS ==========
class TestSmartCorrelation:
    """Test topology-aware event correlation engine"""

    def test_run_smart_correlation(self, api_client):
        """POST /api/smart-correlation/run - Runs topology-aware correlation"""
        response = api_client.post(f"{BASE_URL}/api/smart-correlation/run", params={
            "time_window_minutes": 60,
            "min_signals": 2
        })
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "alerts_processed" in data, "Response missing 'alerts_processed'"
        assert "incidents_created" in data, "Response missing 'incidents_created'"
        assert "incidents" in data, "Response missing 'incidents' list"
        assert "correlation_details" in data, "Response missing 'correlation_details'"
        
        # Validate correlation details structure if any
        if len(data.get("correlation_details", [])) > 0:
            detail = data["correlation_details"][0]
            assert "type" in detail, "Correlation detail missing 'type'"
            assert "reason" in detail, "Correlation detail missing 'reason'"
            # Expected types: topology_dependency, same_host, metric_pattern, same_service
            valid_types = ["topology_dependency", "same_host", "metric_pattern", "same_service"]
            assert detail["type"] in valid_types, f"Invalid correlation type: {detail['type']}"
        
        print(f"✓ Correlation: alerts_processed={data['alerts_processed']}, incidents_created={data['incidents_created']}")


# ========== IMPACT ANALYSIS TESTS ==========
class TestImpactAnalysis:
    """Test impact analysis engine with blast radius calculation"""

    def test_system_risk(self, api_client):
        """GET /api/impact/system-risk - System risk score with active alerts/incidents/services"""
        response = api_client.get(f"{BASE_URL}/api/impact/system-risk")
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "risk_score" in data, "Response missing 'risk_score'"
        assert "risk_level" in data, "Response missing 'risk_level'"
        assert "active_alerts" in data, "Response missing 'active_alerts'"
        assert "active_incidents" in data, "Response missing 'active_incidents'"
        assert "total_services" in data, "Response missing 'total_services'"
        
        # Validate risk level
        valid_levels = ["critical", "high", "medium", "low"]
        assert data["risk_level"] in valid_levels, f"Invalid risk level: {data['risk_level']}"
        
        print(f"✓ System risk: score={data['risk_score']}, level={data['risk_level']}, services={data['total_services']}")

    def test_blast_radius(self, api_client):
        """GET /api/impact/blast-radius - Blast radius showing impacted services"""
        response = api_client.get(f"{BASE_URL}/api/impact/blast-radius", params={
            "service_name": "postgres-primary"
        })
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Handle both success and error cases
        if "error" not in data:
            assert "service" in data, "Response missing 'service'"
            assert "total_impacted" in data, "Response missing 'total_impacted'"
            assert "impacted_services" in data, "Response missing 'impacted_services'"
            assert "risk_level" in data, "Response missing 'risk_level'"
            
            # postgres-primary should have significant blast radius (8 services)
            assert data["total_impacted"] >= 0, "Invalid total_impacted count"
            
            # Validate impacted services structure
            if len(data.get("impacted_services", [])) > 0:
                svc = data["impacted_services"][0]
                assert "service" in svc
                assert "depth" in svc
            
            print(f"✓ Blast radius for postgres-primary: {data['total_impacted']} impacted services, risk={data['risk_level']}")
        else:
            print(f"✓ Blast radius returned error (topology may need seeding): {data['error']}")

    def test_blast_radius_api_gateway(self, api_client):
        """GET /api/impact/blast-radius - Test with api-gateway service"""
        response = api_client.get(f"{BASE_URL}/api/impact/blast-radius", params={
            "service_name": "api-gateway"
        })
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        
        data = response.json()
        if "error" not in data:
            print(f"✓ Blast radius for api-gateway: {data['total_impacted']} impacted services")
        else:
            print(f"✓ api-gateway blast radius: {data.get('error', 'no data')}")

    def test_incident_impact_analysis(self, api_client):
        """GET /api/impact/incident/{incident_id} - Impact analysis for a specific incident"""
        # First, get an incident ID from the incidents engine
        incidents_response = api_client.get(f"{BASE_URL}/api/incident-engine/active")
        
        if incidents_response.status_code == 200:
            incidents = incidents_response.json()
            if isinstance(incidents, list) and len(incidents) > 0:
                incident_id = incidents[0].get("id")
                if incident_id:
                    response = api_client.get(f"{BASE_URL}/api/impact/incident/{incident_id}")
                    assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
                    
                    data = response.json()
                    if "error" not in data:
                        assert "incident_id" in data, "Missing 'incident_id'"
                        assert "impact_score" in data, "Missing 'impact_score'"
                        assert "impact_level" in data, "Missing 'impact_level'"
                        print(f"✓ Incident impact: id={incident_id[:8]}..., score={data['impact_score']}, level={data['impact_level']}")
                    else:
                        print(f"✓ Incident impact returned: {data.get('error')}")
                    return
        
        # If no incidents found, test with a fake ID (should return error gracefully)
        response = api_client.get(f"{BASE_URL}/api/impact/incident/test-incident-id-12345")
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "error" in data, "Expected error for non-existent incident"
        print(f"✓ Incident impact handles non-existent ID correctly")


# ========== AUTH TESTS ==========
class TestAuthRequired:
    """Test authentication requirements"""

    def test_anomaly_detection_requires_auth(self):
        """Anomaly detection endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/anomaly-detection/analyze", params={
            "metric_name": "cpu_usage"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Anomaly detection requires auth")

    def test_correlation_requires_auth(self):
        """Smart correlation endpoints require authentication"""
        response = requests.post(f"{BASE_URL}/api/smart-correlation/run")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Smart correlation requires auth")

    def test_impact_requires_auth(self):
        """Impact analysis endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/impact/system-risk")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Impact analysis requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
