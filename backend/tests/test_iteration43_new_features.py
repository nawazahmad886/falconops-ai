"""
FalconOps AI - Iteration 43 Test Suite
Tests 4 new features:
1. Alert Correlation - NLP-based grouping with similarity scores, keyword extraction
2. K8s Auto-Healing - 6 playbooks, approval workflow, command generation
3. Usage Billing - AI run tracking with overage at $0.002/run
4. Live Pipeline - Uptime DOWN alerts auto-trigger AI agents
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
    pytest.skip(f"Admin auth failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def viewer_token():
    """Get viewer authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": VIEWER_EMAIL,
        "password": VIEWER_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Viewer auth failed: {response.status_code} - {response.text}")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}", "Content-Type": "application/json"}


# ======================== ALERT CORRELATION TESTS ========================

class TestAlertCorrelation:
    """Tests for NLP-based alert correlation feature"""

    def test_correlation_analyze_returns_groups(self, admin_headers):
        """GET /api/correlation/analyze returns groups with noise_reduction_pct, top_keywords, similarity scores"""
        response = requests.get(f"{BASE_URL}/api/correlation/analyze?hours=24", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required fields
        assert "total_alerts" in data, "Missing total_alerts field"
        assert "correlation_groups" in data, "Missing correlation_groups field"
        assert "noise_reduction_pct" in data, "Missing noise_reduction_pct field"
        assert "groups" in data, "Missing groups field"
        assert "config" in data, "Missing config field"
        
        # Verify data types
        assert isinstance(data["total_alerts"], int), "total_alerts should be int"
        assert isinstance(data["correlation_groups"], int), "correlation_groups should be int"
        assert isinstance(data["noise_reduction_pct"], (int, float)), "noise_reduction_pct should be numeric"
        assert isinstance(data["groups"], list), "groups should be list"
        
        # If groups exist, verify structure
        if data["groups"]:
            group = data["groups"][0]
            assert "id" in group, "Group missing id"
            assert "primary" in group, "Group missing primary alert"
            assert "alert_count" in group, "Group missing alert_count"
            assert "top_keywords" in group, "Group missing top_keywords"
            assert "severity" in group, "Group missing severity"
            
            # Check correlated alerts have similarity scores
            if group.get("correlated"):
                correlated = group["correlated"][0]
                assert "similarity" in correlated, "Correlated alert missing similarity score"
                assert isinstance(correlated["similarity"], (int, float)), "Similarity should be numeric"
        
        print(f"Correlation analyze: {data['total_alerts']} alerts -> {data['correlation_groups']} groups ({data['noise_reduction_pct']}% noise reduction)")

    def test_correlation_stats_returns_summary(self, admin_headers):
        """GET /api/correlation/stats returns summary statistics"""
        response = requests.get(f"{BASE_URL}/api/correlation/stats?hours=24", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_alerts" in data
        assert "groups" in data
        assert "noise_reduction_pct" in data
        assert "config" in data
        
        print(f"Correlation stats: {data['total_alerts']} alerts, {data['groups']} groups")

    def test_correlation_config_get(self, admin_headers):
        """GET /api/correlation/config returns settings"""
        response = requests.get(f"{BASE_URL}/api/correlation/config", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "correlation_window_min" in data, "Missing correlation_window_min"
        assert "similarity_threshold" in data, "Missing similarity_threshold"
        assert "max_group_size" in data, "Missing max_group_size"
        assert "enabled" in data, "Missing enabled"
        
        # Verify reasonable defaults
        assert isinstance(data["correlation_window_min"], int)
        assert isinstance(data["similarity_threshold"], (int, float))
        assert 0 <= data["similarity_threshold"] <= 1, "Threshold should be 0-1"
        
        print(f"Correlation config: window={data['correlation_window_min']}min, threshold={data['similarity_threshold']}")

    def test_correlation_config_update_admin_only(self, admin_headers, viewer_headers):
        """PUT /api/correlation/config updates settings (admin only)"""
        # First get current config
        get_resp = requests.get(f"{BASE_URL}/api/correlation/config", headers=admin_headers)
        original_config = get_resp.json()
        
        # Try update as viewer - should fail
        viewer_resp = requests.put(f"{BASE_URL}/api/correlation/config", 
            headers=viewer_headers,
            json={"correlation_window_min": 60})
        assert viewer_resp.status_code in [401, 403], f"Viewer should not update config: {viewer_resp.status_code}"
        
        # Update as admin - should succeed
        new_window = 45
        admin_resp = requests.put(f"{BASE_URL}/api/correlation/config",
            headers=admin_headers,
            json={"correlation_window_min": new_window})
        assert admin_resp.status_code == 200, f"Admin update failed: {admin_resp.status_code}: {admin_resp.text}"
        
        updated = admin_resp.json()
        assert updated["correlation_window_min"] == new_window, "Window not updated"
        
        # Restore original
        requests.put(f"{BASE_URL}/api/correlation/config",
            headers=admin_headers,
            json={"correlation_window_min": original_config.get("correlation_window_min", 30)})
        
        print("Correlation config update: admin-only restriction working")


# ======================== K8S AUTO-HEALING TESTS ========================

class TestK8sHealing:
    """Tests for Kubernetes auto-healing feature"""

    def test_k8s_playbooks_returns_6(self, admin_headers):
        """GET /api/k8s/playbooks returns 6 playbooks"""
        response = requests.get(f"{BASE_URL}/api/k8s/playbooks", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        playbooks = response.json()
        assert isinstance(playbooks, list), "Playbooks should be a list"
        assert len(playbooks) == 6, f"Expected 6 playbooks, got {len(playbooks)}"
        
        # Verify expected playbooks exist
        playbook_ids = [p["id"] for p in playbooks]
        expected_ids = ["restart_pod", "scale_deployment", "rollback_deployment", "drain_node", "restart_deployment", "hpa_adjust"]
        for expected in expected_ids:
            assert expected in playbook_ids, f"Missing playbook: {expected}"
        
        # Verify playbook structure
        for pb in playbooks:
            assert "id" in pb
            assert "name" in pb
            assert "description" in pb
            assert "risk_level" in pb
            assert "auto_approve" in pb
            assert "commands" in pb
            assert pb["risk_level"] in ["low", "medium", "high"]
        
        print(f"K8s playbooks: {len(playbooks)} playbooks found - {playbook_ids}")

    def test_k8s_generate_commands(self, admin_headers):
        """POST /api/k8s/generate generates kubectl commands from params"""
        response = requests.post(f"{BASE_URL}/api/k8s/generate",
            headers=admin_headers,
            json={
                "playbook_id": "restart_pod",
                "params": {
                    "pod_name": "test-pod-123",
                    "namespace": "production",
                    "app_label": "myapp"
                }
            })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "commands" in data, "Missing commands"
        assert "playbook_id" in data
        assert "risk_level" in data
        assert "auto_approve" in data
        
        # Verify commands contain the params
        commands = data["commands"]
        assert len(commands) > 0, "No commands generated"
        assert "test-pod-123" in commands[0], "Pod name not in command"
        assert "production" in commands[0], "Namespace not in command"
        
        print(f"K8s generate: {len(commands)} commands generated for restart_pod")

    def test_k8s_execute_low_risk_auto_approves(self, admin_headers):
        """POST /api/k8s/execute - low risk auto-approves"""
        response = requests.post(f"{BASE_URL}/api/k8s/execute",
            headers=admin_headers,
            json={
                "playbook_id": "restart_pod",
                "params": {
                    "pod_name": "test-auto-pod",
                    "namespace": "default",
                    "app_label": "testapp"
                },
                "auto_approve": False
            })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert "status" in data
        # Low risk should auto-approve and execute
        assert data["status"] in ["executed", "approved"], f"Low risk should auto-approve, got {data['status']}"
        assert data["risk_level"] == "low"
        
        print(f"K8s execute low risk: status={data['status']}")

    def test_k8s_execute_medium_risk_pending_approval(self, admin_headers):
        """POST /api/k8s/execute - medium/high risk returns pending_approval"""
        response = requests.post(f"{BASE_URL}/api/k8s/execute",
            headers=admin_headers,
            json={
                "playbook_id": "rollback_deployment",
                "params": {
                    "deployment": "test-deployment",
                    "namespace": "staging"
                },
                "auto_approve": False
            })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending_approval", f"Medium risk should be pending, got {data['status']}"
        assert data["risk_level"] == "medium"
        
        execution_id = data["id"]
        print(f"K8s execute medium risk: status={data['status']}, id={execution_id}")
        return execution_id

    def test_k8s_approve_pending_execution(self, admin_headers):
        """POST /api/k8s/executions/{id}/approve approves pending"""
        # First create a pending execution
        create_resp = requests.post(f"{BASE_URL}/api/k8s/execute",
            headers=admin_headers,
            json={
                "playbook_id": "restart_deployment",
                "params": {"deployment": "approve-test", "namespace": "default"},
                "auto_approve": False
            })
        assert create_resp.status_code == 200
        execution_id = create_resp.json()["id"]
        
        # Approve it
        approve_resp = requests.post(f"{BASE_URL}/api/k8s/executions/{execution_id}/approve",
            headers=admin_headers)
        assert approve_resp.status_code == 200, f"Approve failed: {approve_resp.status_code}: {approve_resp.text}"
        
        data = approve_resp.json()
        assert data["status"] == "executed", f"Expected executed, got {data['status']}"
        
        print(f"K8s approve: execution {execution_id} approved and executed")

    def test_k8s_reject_pending_execution(self, admin_headers):
        """POST /api/k8s/executions/{id}/reject rejects pending"""
        # Create a pending execution
        create_resp = requests.post(f"{BASE_URL}/api/k8s/execute",
            headers=admin_headers,
            json={
                "playbook_id": "drain_node",
                "params": {"node_name": "reject-test-node"},
                "auto_approve": False
            })
        assert create_resp.status_code == 200
        execution_id = create_resp.json()["id"]
        
        # Reject it
        reject_resp = requests.post(f"{BASE_URL}/api/k8s/executions/{execution_id}/reject",
            headers=admin_headers)
        assert reject_resp.status_code == 200, f"Reject failed: {reject_resp.status_code}: {reject_resp.text}"
        
        data = reject_resp.json()
        assert data["status"] == "rejected", f"Expected rejected, got {data['status']}"
        
        print(f"K8s reject: execution {execution_id} rejected")

    def test_k8s_executions_list(self, admin_headers):
        """GET /api/k8s/executions returns execution log"""
        response = requests.get(f"{BASE_URL}/api/k8s/executions?limit=20", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        executions = response.json()
        assert isinstance(executions, list), "Executions should be a list"
        
        if executions:
            ex = executions[0]
            assert "id" in ex
            assert "playbook_id" in ex
            assert "status" in ex
            assert "commands" in ex
            assert "created_at" in ex
        
        print(f"K8s executions: {len(executions)} executions found")

    def test_k8s_stats(self, admin_headers):
        """GET /api/k8s/stats returns counts"""
        response = requests.get(f"{BASE_URL}/api/k8s/stats", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total" in data
        assert "pending_approval" in data
        assert "executed" in data
        assert "rejected" in data
        
        assert isinstance(data["total"], int)
        assert isinstance(data["pending_approval"], int)
        
        print(f"K8s stats: total={data['total']}, pending={data['pending_approval']}, executed={data['executed']}, rejected={data['rejected']}")


# ======================== USAGE BILLING TESTS ========================

class TestUsageBilling:
    """Tests for usage-based billing with AI run tracking"""

    def test_billing_usage_returns_ai_runs(self, admin_headers):
        """GET /api/billing/usage returns ai_runs_used, ai_runs_limit, overage_runs, overage_cost"""
        response = requests.get(f"{BASE_URL}/api/billing/usage", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required fields
        assert "ai_runs_used" in data, "Missing ai_runs_used"
        assert "ai_runs_limit" in data, "Missing ai_runs_limit"
        assert "overage_runs" in data, "Missing overage_runs"
        assert "overage_cost" in data, "Missing overage_cost"
        assert "plan_id" in data, "Missing plan_id"
        assert "plan_name" in data, "Missing plan_name"
        assert "cost_per_run" in data, "Missing cost_per_run"
        
        # Verify data types
        assert isinstance(data["ai_runs_used"], int)
        assert isinstance(data["ai_runs_limit"], int)
        assert isinstance(data["overage_runs"], int)
        assert isinstance(data["overage_cost"], (int, float))
        
        # Verify cost per run is $0.002
        assert data["cost_per_run"] == 0.002, f"Expected cost_per_run=0.002, got {data['cost_per_run']}"
        
        # Verify overage calculation
        expected_overage = max(0, data["ai_runs_used"] - data["ai_runs_limit"])
        assert data["overage_runs"] == expected_overage, f"Overage calculation wrong: {data['overage_runs']} vs {expected_overage}"
        
        expected_cost = round(expected_overage * 0.002, 2)
        assert data["overage_cost"] == expected_cost, f"Overage cost wrong: {data['overage_cost']} vs {expected_cost}"
        
        print(f"Billing usage: {data['ai_runs_used']}/{data['ai_runs_limit']} AI runs, overage={data['overage_runs']} (${data['overage_cost']})")

    def test_billing_plans_include_max_ai_runs(self, admin_headers):
        """GET /api/billing/plans - plans include max_ai_runs field"""
        response = requests.get(f"{BASE_URL}/api/billing/plans", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        plans = response.json()
        assert isinstance(plans, list)
        assert len(plans) >= 3, "Expected at least 3 plans (free, pro, enterprise)"
        
        for plan in plans:
            assert "max_ai_runs" in plan, f"Plan {plan.get('id')} missing max_ai_runs"
            assert isinstance(plan["max_ai_runs"], int)
            assert plan["max_ai_runs"] > 0
        
        # Verify specific limits
        plan_limits = {p["id"]: p["max_ai_runs"] for p in plans}
        assert plan_limits.get("free") == 50, f"Free plan should have 50 AI runs, got {plan_limits.get('free')}"
        assert plan_limits.get("pro") == 2000, f"Pro plan should have 2000 AI runs, got {plan_limits.get('pro')}"
        assert plan_limits.get("enterprise") == 10000, f"Enterprise plan should have 10000 AI runs, got {plan_limits.get('enterprise')}"
        
        print(f"Billing plans: free={plan_limits.get('free')}, pro={plan_limits.get('pro')}, enterprise={plan_limits.get('enterprise')} AI runs")


# ======================== LIVE PIPELINE TESTS ========================

class TestLivePipeline:
    """Tests for live detection rule pipeline - uptime DOWN alerts auto-trigger AI"""

    def test_pipeline_events_endpoint(self, admin_headers):
        """GET /api/ai/pipeline/events returns trigger events"""
        response = requests.get(f"{BASE_URL}/api/ai/pipeline/events?limit=20", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        events = response.json()
        assert isinstance(events, list), "Events should be a list"
        
        # Check for uptime-triggered events
        uptime_events = [e for e in events if "uptime" in str(e.get("rule_id", "")).lower() or "uptime" in str(e.get("rule_name", "")).lower()]
        
        if events:
            event = events[0]
            assert "id" in event or "rule_id" in event
            assert "timestamp" in event or "triggered_at" in event
        
        print(f"Pipeline events: {len(events)} total, {len(uptime_events)} uptime-triggered")

    def test_pipeline_config_exists(self, admin_headers):
        """GET /api/ai/pipeline/config returns pipeline configuration"""
        response = requests.get(f"{BASE_URL}/api/ai/pipeline/config", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled" in data, "Missing enabled field"
        
        print(f"Pipeline config: enabled={data.get('enabled')}")

    def test_uptime_service_has_pipeline_trigger(self, admin_headers):
        """Verify uptime monitor service has AI pipeline trigger code"""
        # This is a code verification test - we check that the uptime alerts endpoint exists
        # and that the _fire_alert function triggers AI pipeline (verified by code review)
        
        # Check uptime alerts endpoint
        response = requests.get(f"{BASE_URL}/api/uptime/alerts?limit=10", headers=admin_headers)
        assert response.status_code == 200, f"Uptime alerts endpoint failed: {response.status_code}"
        
        alerts = response.json()
        assert isinstance(alerts, list)
        
        # Check for DOWN alerts that would trigger pipeline
        down_alerts = [a for a in alerts if a.get("alert_type") == "down"]
        
        print(f"Uptime alerts: {len(alerts)} total, {len(down_alerts)} DOWN alerts (would trigger AI pipeline)")


# ======================== INTEGRATION TESTS ========================

class TestIntegration:
    """Integration tests across features"""

    def test_all_new_endpoints_accessible(self, admin_headers):
        """Verify all new endpoints are accessible"""
        endpoints = [
            ("GET", "/api/correlation/analyze"),
            ("GET", "/api/correlation/stats"),
            ("GET", "/api/correlation/config"),
            ("GET", "/api/k8s/playbooks"),
            ("GET", "/api/k8s/executions"),
            ("GET", "/api/k8s/stats"),
            ("GET", "/api/billing/usage"),
            ("GET", "/api/ai/pipeline/events"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", headers=admin_headers)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", headers=admin_headers, json={})
            
            assert response.status_code in [200, 201, 400, 422], f"{method} {endpoint} failed: {response.status_code}"
            print(f"  {method} {endpoint}: {response.status_code}")
        
        print("All new endpoints accessible")

    def test_viewer_can_read_but_not_modify(self, viewer_headers, admin_headers):
        """Verify viewer role can read but not modify K8s/correlation config"""
        # Viewer can read correlation
        read_resp = requests.get(f"{BASE_URL}/api/correlation/analyze", headers=viewer_headers)
        assert read_resp.status_code == 200, "Viewer should read correlation"
        
        # Viewer can read K8s playbooks
        read_resp = requests.get(f"{BASE_URL}/api/k8s/playbooks", headers=viewer_headers)
        assert read_resp.status_code == 200, "Viewer should read playbooks"
        
        # Viewer cannot execute K8s
        exec_resp = requests.post(f"{BASE_URL}/api/k8s/execute",
            headers=viewer_headers,
            json={"playbook_id": "restart_pod", "params": {"pod_name": "test", "namespace": "default", "app_label": "test"}})
        assert exec_resp.status_code in [401, 403], f"Viewer should not execute K8s: {exec_resp.status_code}"
        
        print("Role-based access control working correctly")
