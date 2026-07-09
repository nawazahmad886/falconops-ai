"""
Test Health Rule Analytics API - Iteration 31
Tests the /api/events/health-rule-analytics endpoint for:
- Summary with total_violations, active_violations, resolved_violations, total_critical, total_warning, resolution_rate, distinct_rules_triggered
- rule_analytics array with rule_name, fingerprints, critical_count, warning_count, total_violations, resolved_count, resolution_rate, distinct_sources
- Each fingerprint entry with fingerprint hash, source_id, source_name, severity, state, value, timestamp
- chart_data with rule_name, critical, warning, info counts per rule
- severity_distribution with critical, warning, info totals
- Authentication requirement (401 without token)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthRuleAnalyticsAuth:
    """Test authentication requirements"""
    
    def test_endpoint_requires_auth(self):
        """Endpoint should return 401 without authentication"""
        response = requests.get(f"{BASE_URL}/api/events/health-rule-analytics")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print("PASS: Endpoint requires authentication (401 without token)")


class TestHealthRuleAnalytics:
    """Test health rule analytics endpoint with authentication"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@falconapps.com", "password": "Admin@123"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_endpoint_returns_200_with_auth(self):
        """Endpoint should return 200 with valid authentication"""
        response = requests.get(
            f"{BASE_URL}/api/events/health-rule-analytics",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Endpoint returns 200 with valid auth")
    
    def test_response_has_required_top_level_keys(self):
        """Response should have summary, rule_analytics, chart_data, severity_distribution"""
        response = requests.get(
            f"{BASE_URL}/api/events/health-rule-analytics",
            headers=self.headers
        )
        data = response.json()
        
        required_keys = ["summary", "rule_analytics", "chart_data", "severity_distribution"]
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"
        print(f"PASS: Response has all required top-level keys: {required_keys}")
    
    def test_summary_has_required_fields(self):
        """Summary should have all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/events/health-rule-analytics",
            headers=self.headers
        )
        data = response.json()
        summary = data.get("summary", {})
        
        required_fields = [
            "total_violations",
            "active_violations", 
            "resolved_violations",
            "total_critical",
            "total_warning",
            "resolution_rate",
            "distinct_rules_triggered"
        ]
        
        for field in required_fields:
            assert field in summary, f"Summary missing required field: {field}"
            assert summary[field] is not None, f"Summary field {field} is None"
        
        # Verify types
        assert isinstance(summary["total_violations"], int), "total_violations should be int"
        assert isinstance(summary["active_violations"], int), "active_violations should be int"
        assert isinstance(summary["resolved_violations"], int), "resolved_violations should be int"
        assert isinstance(summary["total_critical"], int), "total_critical should be int"
        assert isinstance(summary["total_warning"], int), "total_warning should be int"
        assert isinstance(summary["resolution_rate"], (int, float)), "resolution_rate should be numeric"
        assert isinstance(summary["distinct_rules_triggered"], int), "distinct_rules_triggered should be int"
        
        print(f"PASS: Summary has all required fields with correct types")
        print(f"  - total_violations: {summary['total_violations']}")
        print(f"  - active_violations: {summary['active_violations']}")
        print(f"  - resolved_violations: {summary['resolved_violations']}")
        print(f"  - total_critical: {summary['total_critical']}")
        print(f"  - total_warning: {summary['total_warning']}")
        print(f"  - resolution_rate: {summary['resolution_rate']}%")
        print(f"  - distinct_rules_triggered: {summary['distinct_rules_triggered']}")
    
    def test_rule_analytics_structure(self):
        """rule_analytics should be array with required fields per rule"""
        response = requests.get(
            f"{BASE_URL}/api/events/health-rule-analytics",
            headers=self.headers
        )
        data = response.json()
        rule_analytics = data.get("rule_analytics", [])
        
        assert isinstance(rule_analytics, list), "rule_analytics should be a list"
        assert len(rule_analytics) > 0, "rule_analytics should have at least one rule"
        
        required_fields = [
            "rule_name",
            "fingerprints",
            "critical_count",
            "warning_count",
            "total_violations",
            "resolved_count",
            "resolution_rate",
            "distinct_sources"
        ]
        
        for rule in rule_analytics:
            for field in required_fields:
                assert field in rule, f"Rule missing required field: {field}"
            
            # Verify types
            assert isinstance(rule["rule_name"], str), "rule_name should be string"
            assert isinstance(rule["fingerprints"], list), "fingerprints should be list"
            assert isinstance(rule["critical_count"], int), "critical_count should be int"
            assert isinstance(rule["warning_count"], int), "warning_count should be int"
            assert isinstance(rule["total_violations"], int), "total_violations should be int"
            assert isinstance(rule["resolved_count"], int), "resolved_count should be int"
            assert isinstance(rule["resolution_rate"], (int, float)), "resolution_rate should be numeric"
            assert isinstance(rule["distinct_sources"], int), "distinct_sources should be int"
        
        print(f"PASS: rule_analytics has {len(rule_analytics)} rules with correct structure")
        for rule in rule_analytics[:3]:
            print(f"  - {rule['rule_name']}: {rule['total_violations']} violations ({rule['critical_count']} critical, {rule['warning_count']} warning)")
    
    def test_fingerprint_structure(self):
        """Each fingerprint entry should have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/events/health-rule-analytics",
            headers=self.headers
        )
        data = response.json()
        rule_analytics = data.get("rule_analytics", [])
        
        # Find a rule with fingerprints
        rule_with_fps = None
        for rule in rule_analytics:
            if rule.get("fingerprints") and len(rule["fingerprints"]) > 0:
                rule_with_fps = rule
                break
        
        assert rule_with_fps is not None, "No rules with fingerprints found"
        
        required_fp_fields = [
            "fingerprint",
            "source_id",
            "source_name",
            "severity",
            "state",
            "value",
            "timestamp"
        ]
        
        for fp in rule_with_fps["fingerprints"]:
            for field in required_fp_fields:
                assert field in fp, f"Fingerprint missing required field: {field}"
            
            # Verify fingerprint is a hash string
            assert isinstance(fp["fingerprint"], str), "fingerprint should be string"
            assert len(fp["fingerprint"]) > 0, "fingerprint should not be empty"
            
            # Verify severity is valid
            assert fp["severity"] in ["critical", "warning", "info"], f"Invalid severity: {fp['severity']}"
            
            # Verify state is valid
            assert fp["state"] in ["active", "resolved", "critical", "warning"], f"Invalid state: {fp['state']}"
        
        print(f"PASS: Fingerprints have correct structure")
        print(f"  - Sample fingerprint: {rule_with_fps['fingerprints'][0]['fingerprint']}")
        print(f"  - Sample severity: {rule_with_fps['fingerprints'][0]['severity']}")
        print(f"  - Sample state: {rule_with_fps['fingerprints'][0]['state']}")
    
    def test_chart_data_structure(self):
        """chart_data should have rule_name, critical, warning, info counts"""
        response = requests.get(
            f"{BASE_URL}/api/events/health-rule-analytics",
            headers=self.headers
        )
        data = response.json()
        chart_data = data.get("chart_data", [])
        
        assert isinstance(chart_data, list), "chart_data should be a list"
        assert len(chart_data) > 0, "chart_data should have at least one entry"
        
        required_fields = ["rule_name", "critical", "warning", "info"]
        
        for entry in chart_data:
            for field in required_fields:
                assert field in entry, f"chart_data entry missing field: {field}"
            
            assert isinstance(entry["rule_name"], str), "rule_name should be string"
            assert isinstance(entry["critical"], int), "critical should be int"
            assert isinstance(entry["warning"], int), "warning should be int"
            assert isinstance(entry["info"], int), "info should be int"
        
        print(f"PASS: chart_data has {len(chart_data)} entries with correct structure")
        for entry in chart_data[:3]:
            print(f"  - {entry['rule_name']}: critical={entry['critical']}, warning={entry['warning']}, info={entry['info']}")
    
    def test_severity_distribution_structure(self):
        """severity_distribution should have critical, warning, info totals"""
        response = requests.get(
            f"{BASE_URL}/api/events/health-rule-analytics",
            headers=self.headers
        )
        data = response.json()
        severity_dist = data.get("severity_distribution", {})
        
        required_fields = ["critical", "warning", "info"]
        
        for field in required_fields:
            assert field in severity_dist, f"severity_distribution missing field: {field}"
            assert isinstance(severity_dist[field], int), f"{field} should be int"
        
        print(f"PASS: severity_distribution has correct structure")
        print(f"  - critical: {severity_dist['critical']}")
        print(f"  - warning: {severity_dist['warning']}")
        print(f"  - info: {severity_dist['info']}")
    
    def test_data_consistency(self):
        """Verify data consistency between summary and rule_analytics"""
        response = requests.get(
            f"{BASE_URL}/api/events/health-rule-analytics",
            headers=self.headers
        )
        data = response.json()
        summary = data.get("summary", {})
        rule_analytics = data.get("rule_analytics", [])
        severity_dist = data.get("severity_distribution", {})
        
        # Sum of violations from rules should match total
        total_from_rules = sum(r["total_violations"] for r in rule_analytics)
        assert total_from_rules == summary["total_violations"], \
            f"Total violations mismatch: summary={summary['total_violations']}, rules sum={total_from_rules}"
        
        # Severity distribution should match summary
        assert severity_dist["critical"] == summary["total_critical"], \
            f"Critical count mismatch: dist={severity_dist['critical']}, summary={summary['total_critical']}"
        assert severity_dist["warning"] == summary["total_warning"], \
            f"Warning count mismatch: dist={severity_dist['warning']}, summary={summary['total_warning']}"
        
        # Number of rules should match distinct_rules_triggered
        assert len(rule_analytics) == summary["distinct_rules_triggered"], \
            f"Rules count mismatch: analytics={len(rule_analytics)}, summary={summary['distinct_rules_triggered']}"
        
        print("PASS: Data consistency verified")
        print(f"  - Total violations: {summary['total_violations']} (matches rule sum)")
        print(f"  - Critical: {severity_dist['critical']} (matches summary)")
        print(f"  - Warning: {severity_dist['warning']} (matches summary)")
        print(f"  - Distinct rules: {len(rule_analytics)} (matches summary)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
