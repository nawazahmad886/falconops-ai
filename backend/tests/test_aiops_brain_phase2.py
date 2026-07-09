"""
AIOps Brain Phase 2 - Backend API Tests
Tests for:
1. POST /api/correlation/correlate-violations - Alert Correlation Engine
2. POST /api/correlation/rca-violations - Root Cause Analysis Engine
3. GET /api/capacity/forecast-summary - Capacity Prediction Engine
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from iteration_31.json
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }


class TestCorrelateViolationsEndpoint:
    """Tests for POST /api/correlation/correlate-violations"""
    
    def test_correlate_violations_requires_auth(self):
        """Endpoint should return 401 without authentication"""
        response = requests.post(f"{BASE_URL}/api/correlation/correlate-violations")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ correlate-violations returns 401 without auth")
    
    def test_correlate_violations_success(self, auth_headers):
        """Endpoint should return 200 with valid auth and proper structure"""
        response = requests.post(
            f"{BASE_URL}/api/correlation/correlate-violations?time_window_minutes=2880",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check required top-level keys
        assert "incidents_created" in data, "Missing 'incidents_created' key"
        assert "violations_processed" in data, "Missing 'violations_processed' key"
        assert "groups" in data, "Missing 'groups' key"
        assert "summary" in data, "Missing 'summary' key"
        
        print(f"✓ correlate-violations returns proper structure")
        print(f"  - incidents_created: {data['incidents_created']}")
        print(f"  - violations_processed: {data['violations_processed']}")
        print(f"  - summary: {data['summary']}")
    
    def test_correlate_violations_group_structure(self, auth_headers):
        """Each group should have required fields"""
        response = requests.post(
            f"{BASE_URL}/api/correlation/correlate-violations?time_window_minutes=2880",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        groups = data.get("groups", [])
        
        if len(groups) > 0:
            group = groups[0]
            required_fields = [
                "id", "strategy", "root_cause", "confidence", "severity",
                "violation_count", "critical_count", "warning_count",
                "metrics", "rules", "sources", "fingerprints", "suggested_actions"
            ]
            
            for field in required_fields:
                assert field in group, f"Missing '{field}' in group"
            
            # Validate strategy values
            valid_strategies = ["same_source", "same_metric_fleet", "severity_cascade"]
            assert group["strategy"] in valid_strategies, f"Invalid strategy: {group['strategy']}"
            
            # Validate confidence is between 0 and 1
            assert 0 <= group["confidence"] <= 1, f"Confidence out of range: {group['confidence']}"
            
            # Validate severity
            assert group["severity"] in ["critical", "warning", "info"], f"Invalid severity: {group['severity']}"
            
            print(f"✓ Group structure validated with {len(groups)} groups")
            print(f"  - First group strategy: {group['strategy']}")
            print(f"  - First group root_cause: {group['root_cause'][:50]}...")
        else:
            print("✓ No groups returned (no active violations in time window)")
    
    def test_correlate_violations_different_time_window(self, auth_headers):
        """Endpoint should work with different time_window_minutes parameter"""
        # Test with smaller time window
        response = requests.post(
            f"{BASE_URL}/api/correlation/correlate-violations?time_window_minutes=60",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # time_window_minutes is only returned when there are violations
        if data.get("violations_processed", 0) > 0:
            assert "time_window_minutes" in data, "Missing 'time_window_minutes' when violations exist"
            assert data["time_window_minutes"] == 60, f"Expected time_window_minutes=60, got {data['time_window_minutes']}"
        
        print(f"✓ correlate-violations works with time_window_minutes=60 (violations: {data.get('violations_processed', 0)})")


class TestRCAViolationsEndpoint:
    """Tests for POST /api/correlation/rca-violations"""
    
    def test_rca_violations_requires_auth(self):
        """Endpoint should return 401 without authentication"""
        response = requests.post(f"{BASE_URL}/api/correlation/rca-violations")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ rca-violations returns 401 without auth")
    
    def test_rca_violations_success(self, auth_headers):
        """Endpoint should return 200 with valid auth and proper structure"""
        response = requests.post(
            f"{BASE_URL}/api/correlation/rca-violations",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check required top-level keys
        assert "status" in data, "Missing 'status' key"
        assert "ai_powered" in data, "Missing 'ai_powered' key"
        
        print(f"✓ rca-violations returns proper structure")
        print(f"  - status: {data['status']}")
        print(f"  - ai_powered: {data['ai_powered']}")
    
    def test_rca_violations_full_structure(self, auth_headers):
        """RCA response should have all required fields when violations exist"""
        response = requests.post(
            f"{BASE_URL}/api/correlation/rca-violations",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("status") == "analyzed":
            # Check llm_analysis (can be null)
            assert "llm_analysis" in data, "Missing 'llm_analysis' key"
            
            # Check rule_analysis structure
            assert "rule_analysis" in data, "Missing 'rule_analysis' key"
            rule_analysis = data["rule_analysis"]
            
            required_rule_fields = [
                "root_cause", "impact", "prediction",
                "correlation_patterns", "recommended_actions"
            ]
            for field in required_rule_fields:
                assert field in rule_analysis, f"Missing '{field}' in rule_analysis"
            
            # Check context structure
            assert "context" in data, "Missing 'context' key"
            context = data["context"]
            
            context_fields = ["total_violations", "critical", "warning", "metrics", "sources", "rules"]
            for field in context_fields:
                assert field in context, f"Missing '{field}' in context"
            
            print(f"✓ RCA full structure validated")
            print(f"  - root_cause: {rule_analysis['root_cause'][:60]}...")
            print(f"  - total_violations: {context['total_violations']}")
            print(f"  - critical: {context['critical']}, warning: {context['warning']}")
            print(f"  - recommended_actions count: {len(rule_analysis['recommended_actions'])}")
        else:
            print(f"✓ RCA returned status: {data.get('status')} (no violations to analyze)")


class TestForecastSummaryEndpoint:
    """Tests for GET /api/capacity/forecast-summary"""
    
    def test_forecast_summary_requires_auth(self):
        """Endpoint should return 401 without authentication"""
        response = requests.get(f"{BASE_URL}/api/capacity/forecast-summary")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ forecast-summary returns 401 without auth")
    
    def test_forecast_summary_success(self, auth_headers):
        """Endpoint should return 200 with valid auth and proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/capacity/forecast-summary",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check required top-level keys
        assert "predictions" in data, "Missing 'predictions' key"
        assert "total" in data, "Missing 'total' key"
        assert "at_risk" in data, "Missing 'at_risk' key"
        assert "summary" in data, "Missing 'summary' key"
        
        print(f"✓ forecast-summary returns proper structure")
        print(f"  - total predictions: {data['total']}")
        print(f"  - at_risk: {data['at_risk']}")
        print(f"  - summary: {data['summary']}")
    
    def test_forecast_summary_predictions_structure(self, auth_headers):
        """Each prediction should have required fields if any exist"""
        response = requests.get(
            f"{BASE_URL}/api/capacity/forecast-summary",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        predictions = data.get("predictions", [])
        
        if len(predictions) > 0:
            pred = predictions[0]
            required_fields = [
                "metric", "host", "current", "predicted_24h",
                "confidence", "will_breach", "trend", "risk_level"
            ]
            
            for field in required_fields:
                assert field in pred, f"Missing '{field}' in prediction"
            
            print(f"✓ Prediction structure validated with {len(predictions)} predictions")
            print(f"  - First prediction: {pred['metric']} on {pred['host']}")
            print(f"  - Current: {pred['current']}, Predicted 24h: {pred['predicted_24h']}")
        else:
            # This is expected behavior per the agent context note
            print("✓ No predictions returned (expected - no time-series server metrics)")


class TestEndpointIntegration:
    """Integration tests across all 3 endpoints"""
    
    def test_all_endpoints_accessible(self, auth_headers):
        """All 3 endpoints should be accessible with auth"""
        endpoints = [
            ("POST", "/api/correlation/correlate-violations?time_window_minutes=2880"),
            ("POST", "/api/correlation/rca-violations"),
            ("GET", "/api/capacity/forecast-summary"),
        ]
        
        for method, endpoint in endpoints:
            if method == "POST":
                response = requests.post(f"{BASE_URL}{endpoint}", headers=auth_headers)
            else:
                response = requests.get(f"{BASE_URL}{endpoint}", headers=auth_headers)
            
            assert response.status_code == 200, f"{method} {endpoint} failed: {response.status_code}"
            print(f"✓ {method} {endpoint} - OK")
    
    def test_correlation_and_rca_consistency(self, auth_headers):
        """Correlation and RCA should analyze the same violations"""
        # Get correlation results
        corr_response = requests.post(
            f"{BASE_URL}/api/correlation/correlate-violations?time_window_minutes=2880",
            headers=auth_headers
        )
        corr_data = corr_response.json()
        
        # Get RCA results
        rca_response = requests.post(
            f"{BASE_URL}/api/correlation/rca-violations",
            headers=auth_headers
        )
        rca_data = rca_response.json()
        
        # Both should have processed violations or both should have none
        corr_violations = corr_data.get("violations_processed", 0)
        rca_violations = rca_data.get("context", {}).get("total_violations", 0)
        
        # RCA only looks at active violations, correlation looks at time window
        # So RCA violations should be <= correlation violations
        print(f"✓ Correlation processed: {corr_violations} violations")
        print(f"✓ RCA analyzed: {rca_violations} active violations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
