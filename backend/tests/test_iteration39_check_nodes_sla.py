"""
FalconOps AI - Iteration 39 Backend Tests
Testing 4 NEW features:
1. Distributed Check Node architecture (register, heartbeat, config pull, result push)
2. SLA Dashboard (overview, monitor SLA, breach detection, incident timeline)
3. WhatsApp alert channel (simulation mode)
4. Existing uptime monitors still working
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


class TestAuth:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for authenticated requests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ======================== CHECK NODES TESTS ========================

class TestCheckNodesNoAuth:
    """Check Node endpoints that don't require auth (for external nodes)"""
    
    def test_register_node(self):
        """POST /api/check-nodes/register - Register a new check node (no auth)"""
        node_data = {
            "name": f"TEST_node_{uuid.uuid4().hex[:8]}",
            "region": "us-east",
            "ip": f"10.0.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}",
            "version": "1.0.0",
            "capabilities": ["http", "https", "tcp"]
        }
        response = requests.post(f"{BASE_URL}/api/check-nodes/register", json=node_data)
        assert response.status_code == 200, f"Register failed: {response.text}"
        data = response.json()
        assert "id" in data, "No id in response"
        assert data["name"] == node_data["name"]
        assert data["region"] == node_data["region"]
        assert data["status"] == "online"
        return data["id"]
    
    def test_register_node_different_region(self):
        """Register node in different region"""
        node_data = {
            "name": f"TEST_node_eu_{uuid.uuid4().hex[:8]}",
            "region": "eu-west",
            "ip": f"10.1.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}",
            "version": "1.0.0"
        }
        response = requests.post(f"{BASE_URL}/api/check-nodes/register", json=node_data)
        assert response.status_code == 200
        data = response.json()
        assert data["region"] == "eu-west"
    
    def test_heartbeat(self):
        """POST /api/check-nodes/{id}/heartbeat - Node heartbeat (no auth)"""
        # First register a node
        node_data = {
            "name": f"TEST_heartbeat_node_{uuid.uuid4().hex[:8]}",
            "region": "us-west",
            "ip": f"10.2.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"
        }
        reg_response = requests.post(f"{BASE_URL}/api/check-nodes/register", json=node_data)
        assert reg_response.status_code == 200
        node_id = reg_response.json()["id"]
        
        # Send heartbeat
        hb_response = requests.post(f"{BASE_URL}/api/check-nodes/{node_id}/heartbeat", json={
            "metrics": {"cpu": 45.2, "memory": 62.1, "checks_per_min": 10}
        })
        assert hb_response.status_code == 200
        data = hb_response.json()
        assert data["status"] == "ok"
    
    def test_get_monitors_for_node(self):
        """GET /api/check-nodes/{id}/monitors - Get monitors for node's region (no auth)"""
        # Register a node
        node_data = {
            "name": f"TEST_config_node_{uuid.uuid4().hex[:8]}",
            "region": "us-east",
            "ip": f"10.3.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"
        }
        reg_response = requests.post(f"{BASE_URL}/api/check-nodes/register", json=node_data)
        assert reg_response.status_code == 200
        node_id = reg_response.json()["id"]
        
        # Get monitors for this node
        response = requests.get(f"{BASE_URL}/api/check-nodes/{node_id}/monitors")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Expected list of monitors"
    
    def test_submit_check_result(self):
        """POST /api/check-nodes/{id}/results - Submit check result (no auth)"""
        # Register a node
        node_data = {
            "name": f"TEST_result_node_{uuid.uuid4().hex[:8]}",
            "region": "us-east",
            "ip": f"10.4.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"
        }
        reg_response = requests.post(f"{BASE_URL}/api/check-nodes/register", json=node_data)
        assert reg_response.status_code == 200
        node_id = reg_response.json()["id"]
        
        # Submit a check result
        result_data = {
            "monitor_id": "test-monitor-123",
            "url": "https://example.com",
            "region": "us-east",
            "status_code": 200,
            "response_time_ms": 150.5,
            "success": True,
            "error": None
        }
        response = requests.post(f"{BASE_URL}/api/check-nodes/{node_id}/results", json=result_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "check_id" in data


class TestCheckNodesAuth:
    """Check Node endpoints that require authentication"""
    
    def test_list_nodes(self, auth_headers):
        """GET /api/check-nodes - List all check nodes (requires auth)"""
        response = requests.get(f"{BASE_URL}/api/check-nodes", headers=auth_headers)
        assert response.status_code == 200, f"List nodes failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of nodes"
        # Should have at least one node from previous tests
        print(f"Found {len(data)} check nodes")
    
    def test_list_nodes_filter_by_region(self, auth_headers):
        """GET /api/check-nodes?region=us-east - Filter nodes by region"""
        response = requests.get(f"{BASE_URL}/api/check-nodes?region=us-east", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for node in data:
            assert node["region"] == "us-east"
    
    def test_get_node_stats(self, auth_headers):
        """GET /api/check-nodes/stats - Get node statistics (requires auth)"""
        response = requests.get(f"{BASE_URL}/api/check-nodes/stats", headers=auth_headers)
        assert response.status_code == 200, f"Stats failed: {response.text}"
        data = response.json()
        assert "total_nodes" in data
        assert "online" in data
        assert "offline" in data
        assert "total_checks" in data
        assert "by_region" in data
        print(f"Node stats: {data['total_nodes']} total, {data['online']} online")
    
    def test_delete_node(self, auth_headers):
        """DELETE /api/check-nodes/{id} - Delete a node (admin only)"""
        # First register a node to delete
        node_data = {
            "name": f"TEST_delete_node_{uuid.uuid4().hex[:8]}",
            "region": "ap-southeast",
            "ip": f"10.5.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"
        }
        reg_response = requests.post(f"{BASE_URL}/api/check-nodes/register", json=node_data)
        assert reg_response.status_code == 200
        node_id = reg_response.json()["id"]
        
        # Delete the node
        del_response = requests.delete(f"{BASE_URL}/api/check-nodes/{node_id}", headers=auth_headers)
        assert del_response.status_code == 200
        data = del_response.json()
        assert data["deleted"] == True
        
        # Verify node is gone from list
        list_response = requests.get(f"{BASE_URL}/api/check-nodes", headers=auth_headers)
        nodes = list_response.json()
        node_ids = [n["id"] for n in nodes]
        assert node_id not in node_ids, "Node should be deleted"


# ======================== SLA DASHBOARD TESTS ========================

class TestSLADashboard:
    """SLA Dashboard endpoint tests"""
    
    def test_get_sla_overview(self, auth_headers):
        """GET /api/sla/overview - Get SLA compliance summary"""
        response = requests.get(f"{BASE_URL}/api/sla/overview?months=1", headers=auth_headers)
        assert response.status_code == 200, f"SLA overview failed: {response.text}"
        data = response.json()
        assert "total_monitors" in data
        assert "compliant" in data
        assert "breached" in data
        assert "compliance_rate" in data
        assert "monitors" in data
        assert "targets_available" in data
        print(f"SLA Overview: {data['total_monitors']} monitors, {data['compliance_rate']}% compliance")
    
    def test_get_sla_overview_multiple_months(self, auth_headers):
        """GET /api/sla/overview?months=3 - Get SLA overview for 3 months"""
        response = requests.get(f"{BASE_URL}/api/sla/overview?months=3", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "monitors" in data
    
    def test_get_monitor_sla(self, auth_headers):
        """GET /api/sla/monitor/{id} - Get monthly SLA breakdown for a monitor"""
        # First get a monitor ID from overview
        overview_response = requests.get(f"{BASE_URL}/api/sla/overview", headers=auth_headers)
        assert overview_response.status_code == 200
        overview = overview_response.json()
        
        if overview["monitors"]:
            monitor_id = overview["monitors"][0]["monitor_id"]
            
            # Get SLA details for this monitor
            response = requests.get(f"{BASE_URL}/api/sla/monitor/{monitor_id}?months=3", headers=auth_headers)
            assert response.status_code == 200, f"Monitor SLA failed: {response.text}"
            data = response.json()
            assert "monitor_id" in data
            assert "monitor_name" in data
            assert "sla_target" in data
            assert "overall_uptime_pct" in data
            assert "overall_compliant" in data
            assert "monthly" in data
            
            # Check monthly breakdown structure
            if data["monthly"]:
                month = data["monthly"][0]
                assert "month" in month
                assert "uptime_pct" in month
                assert "target_pct" in month
                assert "breached" in month
                assert "remaining_budget_min" in month
                print(f"Monitor {data['monitor_name']}: {data['overall_uptime_pct']}% uptime")
        else:
            pytest.skip("No monitors available for SLA testing")
    
    def test_set_sla_target(self, auth_headers):
        """POST /api/sla/target - Set SLA target for a monitor"""
        # Get a monitor ID
        overview_response = requests.get(f"{BASE_URL}/api/sla/overview", headers=auth_headers)
        assert overview_response.status_code == 200
        overview = overview_response.json()
        
        if overview["monitors"]:
            monitor_id = overview["monitors"][0]["monitor_id"]
            
            # Set SLA target
            response = requests.post(f"{BASE_URL}/api/sla/target", headers=auth_headers, json={
                "monitor_id": monitor_id,
                "target": "99.9"
            })
            assert response.status_code == 200, f"Set target failed: {response.text}"
            data = response.json()
            assert data["monitor_id"] == monitor_id
            assert data["sla_target"] == "99.9"
        else:
            pytest.skip("No monitors available")
    
    def test_get_incident_timeline(self, auth_headers):
        """GET /api/sla/incidents/{id} - Get incident timeline for a monitor"""
        # Get a monitor ID
        overview_response = requests.get(f"{BASE_URL}/api/sla/overview", headers=auth_headers)
        assert overview_response.status_code == 200
        overview = overview_response.json()
        
        if overview["monitors"]:
            monitor_id = overview["monitors"][0]["monitor_id"]
            
            # Get incidents
            response = requests.get(f"{BASE_URL}/api/sla/incidents/{monitor_id}?days=30", headers=auth_headers)
            assert response.status_code == 200, f"Incidents failed: {response.text}"
            data = response.json()
            assert isinstance(data, list), "Expected list of incidents"
            print(f"Found {len(data)} incidents for monitor")
        else:
            pytest.skip("No monitors available")
    
    def test_sla_targets_available(self, auth_headers):
        """Verify SLA targets are available in overview"""
        response = requests.get(f"{BASE_URL}/api/sla/overview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        targets = data.get("targets_available", [])
        assert len(targets) > 0, "Should have SLA targets available"
        
        # Check target structure
        target_ids = [t["id"] for t in targets]
        assert "99.9" in target_ids, "Should have 99.9% target"
        assert "99.99" in target_ids, "Should have 99.99% target"


# ======================== WHATSAPP CHANNEL TESTS ========================

class TestWhatsAppChannel:
    """WhatsApp alert channel tests (simulation mode)"""
    
    def test_create_monitor_with_whatsapp_channel(self, auth_headers):
        """Create a monitor with WhatsApp alert channel"""
        monitor_data = {
            "name": f"TEST_whatsapp_monitor_{uuid.uuid4().hex[:8]}",
            "url": "https://httpstat.us/200",
            "interval": 60,
            "method": "GET",
            "expected_status": 200,
            "timeout": 10,
            "regions": ["us-east"],
            "consecutive_failures": 2,
            "alert_channels": [
                {"type": "whatsapp", "to_number": "+966501234567"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/uptime/monitors", headers=auth_headers, json=monitor_data)
        assert response.status_code == 200, f"Create monitor failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["alert_channels"][0]["type"] == "whatsapp"
        assert data["alert_channels"][0]["to_number"] == "+966501234567"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/uptime/monitors/{data['id']}", headers=auth_headers)
    
    def test_update_monitor_add_whatsapp(self, auth_headers):
        """Update existing monitor to add WhatsApp channel"""
        # Create a basic monitor
        monitor_data = {
            "name": f"TEST_update_whatsapp_{uuid.uuid4().hex[:8]}",
            "url": "https://httpstat.us/200",
            "interval": 60,
            "regions": ["us-east"]
        }
        create_response = requests.post(f"{BASE_URL}/api/uptime/monitors", headers=auth_headers, json=monitor_data)
        assert create_response.status_code == 200
        monitor_id = create_response.json()["id"]
        
        # Update to add WhatsApp channel
        update_response = requests.put(f"{BASE_URL}/api/uptime/monitors/{monitor_id}", headers=auth_headers, json={
            "alert_channels": [
                {"type": "whatsapp", "to_number": "+966509876543"}
            ]
        })
        assert update_response.status_code == 200
        data = update_response.json()
        assert len(data["alert_channels"]) == 1
        assert data["alert_channels"][0]["type"] == "whatsapp"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/uptime/monitors/{monitor_id}", headers=auth_headers)


# ======================== EXISTING FEATURES TESTS ========================

class TestExistingFeatures:
    """Verify existing features still work"""
    
    def test_uptime_monitors_list(self, auth_headers):
        """GET /api/uptime/monitors - List uptime monitors"""
        response = requests.get(f"{BASE_URL}/api/uptime/monitors", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} uptime monitors")
    
    def test_uptime_stats(self, auth_headers):
        """GET /api/uptime/stats - Get uptime statistics"""
        response = requests.get(f"{BASE_URL}/api/uptime/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_monitors" in data
        assert "up" in data
        assert "down" in data
    
    def test_regions_list(self, auth_headers):
        """GET /api/uptime/regions - List available regions"""
        response = requests.get(f"{BASE_URL}/api/uptime/regions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 5, "Should have at least 5 regions"
        region_ids = [r["id"] for r in data]
        assert "us-east" in region_ids
        assert "eu-west" in region_ids
        assert "me-south" in region_ids
    
    def test_alerts_list(self, auth_headers):
        """GET /api/uptime/alerts - List alert history"""
        response = requests.get(f"{BASE_URL}/api/uptime/alerts?limit=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_billing_plans(self, auth_headers):
        """GET /api/billing/plans - List billing plans"""
        response = requests.get(f"{BASE_URL}/api/billing/plans", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3, "Should have at least 3 plans"


# ======================== CLEANUP ========================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_nodes(self, auth_headers):
        """Remove TEST_ prefixed nodes"""
        response = requests.get(f"{BASE_URL}/api/check-nodes", headers=auth_headers)
        if response.status_code == 200:
            nodes = response.json()
            for node in nodes:
                if node.get("name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/check-nodes/{node['id']}", headers=auth_headers)
            print(f"Cleaned up test nodes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
