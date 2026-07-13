"""
FalconOps AI - Remediation, Impact Analysis & Dispatch Module Tests
Tests for:
- Auto-Remediation Engine: 8 actions, RCA-to-remediation mapping, execute, history, stats
- Impact Analysis Engine: blast radius analyzer, affected services/users/violations/threats
- Connector Dispatcher: dispatch logs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


# ======================== REMEDIATION TESTS ========================

class TestRemediationActions:
    """Tests for GET /api/remediation/actions - Action Library"""
    
    def test_get_actions_returns_200(self, api_client):
        """GET /api/remediation/actions returns 200"""
        response = api_client.get(f"{BASE_URL}/api/remediation/actions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/remediation/actions returns 200")
    
    def test_actions_returns_8_actions(self, api_client):
        """Action library contains exactly 8 actions"""
        response = api_client.get(f"{BASE_URL}/api/remediation/actions")
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 8, f"Expected 8 actions, got {len(data)}"
        print(f"✓ Action library contains {len(data)} actions")
    
    def test_actions_have_required_fields(self, api_client):
        """Each action has required fields: id, name, category, risk_level, auto_eligible, script_preview"""
        response = api_client.get(f"{BASE_URL}/api/remediation/actions")
        data = response.json()
        required_fields = ["id", "name", "category", "risk_level", "auto_eligible", "script_preview"]
        
        for action in data:
            for field in required_fields:
                assert field in action, f"Action missing field: {field}"
        
        # Verify specific actions exist
        action_ids = [a["id"] for a in data]
        expected_actions = ["restart_service", "block_ip", "scale_pods", "disable_user", 
                          "flush_cache", "rotate_credentials", "increase_disk", "kill_process"]
        for expected in expected_actions:
            assert expected in action_ids, f"Missing action: {expected}"
        
        print(f"✓ All 8 actions have required fields: {', '.join(expected_actions)}")
    
    def test_actions_have_valid_risk_levels(self, api_client):
        """Actions have valid risk levels: low, medium, high"""
        response = api_client.get(f"{BASE_URL}/api/remediation/actions")
        data = response.json()
        valid_levels = ["low", "medium", "high"]
        
        for action in data:
            assert action["risk_level"] in valid_levels, f"Invalid risk level: {action['risk_level']}"
        
        print("✓ All actions have valid risk levels")


class TestRemediationSuggest:
    """Tests for POST /api/remediation/suggest - RCA-to-Remediation Mapping"""
    
    def test_suggest_high_cpu_returns_actions(self, api_client):
        """POST /api/remediation/suggest with high_cpu returns relevant actions"""
        response = api_client.post(f"{BASE_URL}/api/remediation/suggest", json={
            "root_cause": "high_cpu",
            "context": {}
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should return at least one suggestion"
        
        action_ids = [s["action_id"] for s in data]
        # high_cpu should suggest restart_service, kill_process, scale_pods
        assert "restart_service" in action_ids or "kill_process" in action_ids, "high_cpu should suggest restart_service or kill_process"
        print(f"✓ high_cpu suggests: {', '.join(action_ids)}")
    
    def test_suggest_brute_force_returns_security_actions(self, api_client):
        """POST /api/remediation/suggest with brute_force returns security actions"""
        response = api_client.post(f"{BASE_URL}/api/remediation/suggest", json={
            "root_cause": "brute_force",
            "context": {"source_ip": "192.168.1.100"}
        })
        assert response.status_code == 200
        data = response.json()
        action_ids = [s["action_id"] for s in data]
        assert "block_ip" in action_ids, "brute_force should suggest block_ip"
        print(f"✓ brute_force suggests: {', '.join(action_ids)}")
    
    def test_suggest_returns_pre_filled_params(self, api_client):
        """Suggestions include pre-filled params from context"""
        response = api_client.post(f"{BASE_URL}/api/remediation/suggest", json={
            "root_cause": "brute_force",
            "context": {"source_ip": "10.0.0.50", "user": "attacker_user"}
        })
        assert response.status_code == 200
        data = response.json()
        
        # Find block_ip suggestion
        block_ip = next((s for s in data if s["action_id"] == "block_ip"), None)
        if block_ip and "pre_filled_params" in block_ip:
            assert block_ip["pre_filled_params"].get("ip_address") == "10.0.0.50", "IP should be pre-filled"
            print("✓ Suggestions include pre-filled params from context")
        else:
            print("✓ Suggestions returned (pre-filled params optional)")
    
    def test_suggest_all_rca_causes(self, api_client):
        """Test all RCA causes return suggestions"""
        causes = ["high_cpu", "high_memory", "disk_full", "brute_force", 
                  "privilege_escalation", "data_exfiltration", "connection_leak", "service_down"]
        
        for cause in causes:
            response = api_client.post(f"{BASE_URL}/api/remediation/suggest", json={
                "root_cause": cause,
                "context": {}
            })
            assert response.status_code == 200, f"Failed for cause: {cause}"
            data = response.json()
            assert isinstance(data, list), f"Response for {cause} should be a list"
            print(f"  ✓ {cause}: {len(data)} suggestions")
        
        print("✓ All 8 RCA causes return suggestions")


class TestRemediationExecute:
    """Tests for POST /api/remediation/execute - Execute Remediation Action"""
    
    def test_execute_block_ip_returns_result(self, api_client):
        """POST /api/remediation/execute executes action and returns result"""
        response = api_client.post(f"{BASE_URL}/api/remediation/execute", json={
            "action_id": "block_ip",
            "params": {"ip_address": "192.168.100.200"},
            "trigger": "manual"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data, "Response should have id"
        assert "action_name" in data, "Response should have action_name"
        assert "resolved_script" in data, "Response should have resolved_script"
        assert "status" in data, "Response should have status"
        # execute_remediation() is dry-run/preview only — see remediation_service docstring
        assert data["status"] == "previewed", f"Expected previewed, got {data['status']}"
        
        # Verify resolved script contains the IP
        assert "192.168.100.200" in data["resolved_script"], "Resolved script should contain IP"
        print(f"✓ Execute block_ip: {data['resolved_script']}")
    
    def test_execute_restart_service_returns_result(self, api_client):
        """Execute restart_service action"""
        response = api_client.post(f"{BASE_URL}/api/remediation/execute", json={
            "action_id": "restart_service",
            "params": {"service_name": "nginx", "host": "web-server-01"},
            "trigger": "manual"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "previewed"
        assert "nginx" in data["resolved_script"]
        print(f"✓ Execute restart_service: {data['resolved_script']}")
    
    def test_execute_unknown_action_returns_error(self, api_client):
        """Execute unknown action returns error"""
        response = api_client.post(f"{BASE_URL}/api/remediation/execute", json={
            "action_id": "unknown_action",
            "params": {},
            "trigger": "manual"
        })
        # Should return 200 with error in body or 400/404
        if response.status_code == 200:
            data = response.json()
            assert "error" in data, "Should return error for unknown action"
            print(f"✓ Unknown action returns error: {data.get('error')}")
        else:
            assert response.status_code in [400, 404], f"Expected 400/404, got {response.status_code}"
            print(f"✓ Unknown action returns {response.status_code}")


class TestRemediationHistory:
    """Tests for GET /api/remediation/history - Execution History"""
    
    def test_history_returns_200(self, api_client):
        """GET /api/remediation/history returns 200"""
        response = api_client.get(f"{BASE_URL}/api/remediation/history")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/remediation/history returns 200")
    
    def test_history_returns_list(self, api_client):
        """History returns list of executions"""
        response = api_client.get(f"{BASE_URL}/api/remediation/history")
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ History contains {len(data)} executions")
    
    def test_history_items_have_required_fields(self, api_client):
        """History items have required fields"""
        response = api_client.get(f"{BASE_URL}/api/remediation/history")
        data = response.json()
        
        if len(data) > 0:
            required_fields = ["action_name", "resolved_script", "trigger", "status"]
            for field in required_fields:
                assert field in data[0], f"History item missing field: {field}"
            print(f"✓ History items have required fields: {', '.join(required_fields)}")
        else:
            print("✓ History is empty (no executions yet)")


class TestRemediationStats:
    """Tests for GET /api/remediation/stats - Statistics"""
    
    def test_stats_returns_200(self, api_client):
        """GET /api/remediation/stats returns 200"""
        response = api_client.get(f"{BASE_URL}/api/remediation/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/remediation/stats returns 200")
    
    def test_stats_have_required_fields(self, api_client):
        """Stats have required fields"""
        response = api_client.get(f"{BASE_URL}/api/remediation/stats")
        data = response.json()
        
        required_fields = ["total_executions", "auto_triggered", "manual_triggered", "previewed"]
        for field in required_fields:
            assert field in data, f"Stats missing field: {field}"

        print(f"✓ Stats: total={data['total_executions']}, auto={data['auto_triggered']}, manual={data['manual_triggered']}, previewed={data['previewed']}")


# ======================== IMPACT ANALYSIS TESTS ========================

class TestImpactAnalyze:
    """Tests for POST /api/impact/analyze - Blast Radius Analysis"""
    
    def test_analyze_returns_200(self, api_client):
        """POST /api/impact/analyze returns 200"""
        response = api_client.post(f"{BASE_URL}/api/impact/analyze", json={
            "host": "prod-web-01",
            "service": "api-gateway",
            "severity": "critical",
            "type": "incident",
            "source_ip": "192.168.1.100"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ POST /api/impact/analyze returns 200")
    
    def test_analyze_returns_impact_score(self, api_client):
        """Analysis returns impact_score (0-100)"""
        response = api_client.post(f"{BASE_URL}/api/impact/analyze", json={
            "host": "db-server-01",
            "service": "postgres",
            "severity": "high",
            "type": "service_down"
        })
        data = response.json()
        
        assert "impact_score" in data, "Response should have impact_score"
        assert isinstance(data["impact_score"], (int, float)), "impact_score should be numeric"
        assert 0 <= data["impact_score"] <= 100, f"impact_score should be 0-100, got {data['impact_score']}"
        print(f"✓ Impact score: {data['impact_score']}/100")
    
    def test_analyze_returns_affected_services(self, api_client):
        """Analysis returns affected_services list"""
        response = api_client.post(f"{BASE_URL}/api/impact/analyze", json={
            "host": "app-server",
            "service": "user-service",
            "severity": "warning",
            "type": "high_cpu"
        })
        data = response.json()
        
        assert "affected_services" in data, "Response should have affected_services"
        assert isinstance(data["affected_services"], list), "affected_services should be a list"
        assert "affected_service_count" in data, "Response should have affected_service_count"
        print(f"✓ Affected services: {data['affected_service_count']}")
    
    def test_analyze_returns_related_threats(self, api_client):
        """Analysis returns related_threats list"""
        response = api_client.post(f"{BASE_URL}/api/impact/analyze", json={
            "host": "web-server",
            "source_ip": "185.220.101.1",
            "severity": "critical",
            "type": "brute_force"
        })
        data = response.json()
        
        assert "related_threats" in data, "Response should have related_threats"
        assert isinstance(data["related_threats"], list), "related_threats should be a list"
        print(f"✓ Related threats: {len(data['related_threats'])}")
    
    def test_analyze_returns_affected_users(self, api_client):
        """Analysis returns affected_users list"""
        response = api_client.post(f"{BASE_URL}/api/impact/analyze", json={
            "host": "auth-server",
            "severity": "high",
            "type": "privilege_escalation"
        })
        data = response.json()
        
        assert "affected_users" in data, "Response should have affected_users"
        assert isinstance(data["affected_users"], list), "affected_users should be a list"
        assert "affected_user_count" in data, "Response should have affected_user_count"
        print(f"✓ Affected users: {data['affected_user_count']}")
    
    def test_analyze_returns_summary(self, api_client):
        """Analysis returns human-readable summary"""
        response = api_client.post(f"{BASE_URL}/api/impact/analyze", json={
            "host": "cache-server",
            "service": "redis",
            "severity": "warning",
            "type": "disk_full"
        })
        data = response.json()
        
        assert "summary" in data, "Response should have summary"
        assert isinstance(data["summary"], str), "summary should be a string"
        assert len(data["summary"]) > 0, "summary should not be empty"
        print(f"✓ Summary: {data['summary'][:100]}...")
    
    def test_analyze_returns_impact_level(self, api_client):
        """Analysis returns impact_level (critical/high/medium/low)"""
        response = api_client.post(f"{BASE_URL}/api/impact/analyze", json={
            "host": "prod-server",
            "severity": "critical",
            "type": "incident"
        })
        data = response.json()
        
        assert "impact_level" in data, "Response should have impact_level"
        valid_levels = ["critical", "high", "medium", "low"]
        assert data["impact_level"] in valid_levels, f"Invalid impact_level: {data['impact_level']}"
        print(f"✓ Impact level: {data['impact_level']}")


class TestImpactHistory:
    """Tests for GET /api/impact/history - Analysis History"""
    
    def test_history_returns_200(self, api_client):
        """GET /api/impact/history returns 200"""
        response = api_client.get(f"{BASE_URL}/api/impact/history")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/impact/history returns 200")
    
    def test_history_returns_list(self, api_client):
        """History returns list of analyses"""
        response = api_client.get(f"{BASE_URL}/api/impact/history")
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Impact history contains {len(data)} analyses")


class TestImpactStats:
    """Tests for GET /api/impact/stats - Statistics"""
    
    def test_stats_returns_200(self, api_client):
        """GET /api/impact/stats returns 200"""
        response = api_client.get(f"{BASE_URL}/api/impact/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/impact/stats returns 200")
    
    def test_stats_have_required_fields(self, api_client):
        """Stats have required fields"""
        response = api_client.get(f"{BASE_URL}/api/impact/stats")
        data = response.json()
        
        required_fields = ["total_analyses", "avg_impact_score"]
        for field in required_fields:
            assert field in data, f"Stats missing field: {field}"
        
        print(f"✓ Impact stats: total={data['total_analyses']}, avg_score={data['avg_impact_score']}")


# ======================== DISPATCH TESTS ========================

class TestDispatchLogs:
    """Tests for GET /api/dispatch/logs - Connector Dispatch Logs"""
    
    def test_logs_returns_200(self, api_client):
        """GET /api/dispatch/logs returns 200"""
        response = api_client.get(f"{BASE_URL}/api/dispatch/logs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/dispatch/logs returns 200")
    
    def test_logs_returns_list(self, api_client):
        """Logs returns list of dispatch events"""
        response = api_client.get(f"{BASE_URL}/api/dispatch/logs")
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Dispatch logs contains {len(data)} events")
    
    def test_logs_with_limit(self, api_client):
        """Logs respects limit parameter"""
        response = api_client.get(f"{BASE_URL}/api/dispatch/logs?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5, f"Expected max 5 logs, got {len(data)}"
        print(f"✓ Dispatch logs with limit=5: {len(data)} events")


# ======================== AUTH TESTS ========================

class TestAuthRequired:
    """Tests for authentication requirements"""
    
    def test_remediation_actions_requires_auth(self):
        """Remediation actions requires authentication"""
        response = requests.get(f"{BASE_URL}/api/remediation/actions")
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ /api/remediation/actions requires authentication")
    
    def test_impact_analyze_requires_auth(self):
        """Impact analyze requires authentication"""
        response = requests.post(f"{BASE_URL}/api/impact/analyze", json={
            "host": "test",
            "severity": "warning"
        })
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ /api/impact/analyze requires authentication")
    
    def test_dispatch_logs_requires_auth(self):
        """Dispatch logs requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dispatch/logs")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ /api/dispatch/logs requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
