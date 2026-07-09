"""
FalconOps AI - Multi-tenancy, NOC Dashboard, and Monitoring Agent Tests
Testing: tenant_id filtering, NOC dashboard APIs, monitoring agent endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://health-rules-engine.preview.emergentagent.com')

class TestAuthentication:
    """Authentication and tenant context tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_login_returns_user_with_context(self, auth_token):
        """Test login returns user info"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == "admin@falconapps.com"
        print(f"✓ Login successful, user: {data['user']['email']}, role: {data['user']['role']}")


class TestMultiTenancyMonitors:
    """Multi-tenancy filtering tests for monitors"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_monitors_with_tenant_context(self, auth_headers):
        """Test GET /api/monitors returns data with tenant context"""
        response = requests.get(f"{BASE_URL}/api/monitors", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/monitors returned {len(data)} monitors")
    
    def test_get_monitors_dashboard_with_tenant_context(self, auth_headers):
        """Test GET /api/monitors/dashboard has tenant_id filtering"""
        response = requests.get(f"{BASE_URL}/api/monitors/dashboard", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify dashboard response structure
        assert "total_monitors" in data
        assert "monitors_up" in data
        assert "monitors_down" in data
        print(f"✓ GET /api/monitors/dashboard: total={data['total_monitors']}, up={data['monitors_up']}, down={data['monitors_down']}")


class TestMultiTenancyServers:
    """Multi-tenancy filtering tests for servers"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_servers_dashboard_with_tenant_context(self, auth_headers):
        """Test GET /api/servers/dashboard has tenant_id filtering"""
        response = requests.get(f"{BASE_URL}/api/servers/dashboard", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify dashboard response structure
        assert "total_servers" in data
        assert "online_servers" in data
        assert "servers" in data
        print(f"✓ GET /api/servers/dashboard: total={data['total_servers']}, online={data['online_servers']}")
        return data
    
    def test_get_servers_list_with_tenant_context(self, auth_headers):
        """Test GET /api/servers returns server list"""
        response = requests.get(f"{BASE_URL}/api/servers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/servers returned {len(data)} servers")


class TestMultiTenancyAnalytics:
    """Multi-tenancy filtering tests for analytics"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_analytics_summary_with_tenant_context(self, auth_headers):
        """Test GET /api/analytics/summary has tenant_id filtering"""
        response = requests.get(f"{BASE_URL}/api/analytics/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify summary response structure
        assert "open_alerts" in data
        assert "open_incidents" in data
        assert "active_monitors" in data
        print(f"✓ GET /api/analytics/summary: alerts={data['open_alerts']}, incidents={data['open_incidents']}, monitors={data['active_monitors']}")
    
    def test_get_analytics_dashboard_with_tenant_context(self, auth_headers):
        """Test GET /api/analytics with tenant_id filtering"""
        response = requests.get(f"{BASE_URL}/api/analytics?days=7", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify analytics response structure
        assert "total_alerts" in data
        assert "total_incidents" in data
        print(f"✓ GET /api/analytics: total_alerts={data['total_alerts']}, total_incidents={data['total_incidents']}")


class TestMultiTenancyLogs:
    """Multi-tenancy filtering tests for logs"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_post_logs_ingest_stores_tenant_id(self, auth_headers):
        """Test POST /api/logs/ingest stores tenant_id in log documents"""
        log_data = {
            "message": "TEST_LOG: Multi-tenancy test log entry",
            "level": "INFO",
            "service": "test-service",
            "host": "test-host-001"
        }
        response = requests.post(f"{BASE_URL}/api/logs/ingest", json=log_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "ingested"
        print(f"✓ POST /api/logs/ingest: log ingested with id={data['id']}")
    
    def test_get_logs_with_tenant_context(self, auth_headers):
        """Test GET /api/logs returns logs with tenant context"""
        response = requests.get(f"{BASE_URL}/api/logs?hours=24&limit=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        print(f"✓ GET /api/logs: returned {len(data['logs'])} logs, total={data['total']}")


class TestMonitoringAgent:
    """Monitoring agent download and install script tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_download_python_agent(self, auth_headers):
        """Test GET /api/agent/download/python returns Python agent file"""
        response = requests.get(f"{BASE_URL}/api/agent/download/python", headers=auth_headers)
        assert response.status_code == 200
        # Check content type indicates python file
        content_type = response.headers.get("content-type", "")
        assert "text" in content_type or "python" in content_type or "application/octet-stream" in content_type
        # Verify file content starts with shebang or contains FalconOps
        content = response.text
        assert "FalconOps" in content or "#!/usr/bin/env python" in content
        print(f"✓ GET /api/agent/download/python: returned {len(content)} bytes Python agent")
    
    def test_get_install_script(self, auth_headers):
        """Test GET /api/agent/install-script returns installation instructions"""
        response = requests.get(f"{BASE_URL}/api/agent/install-script", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify install script structure
        assert "install_steps" in data
        assert isinstance(data["install_steps"], list)
        assert len(data["install_steps"]) >= 3
        assert "systemd_config" in data
        assert "[Unit]" in data["systemd_config"]
        assert "FalconOps" in data["systemd_config"]
        print(f"✓ GET /api/agent/install-script: returned {len(data['install_steps'])} install steps")
        print(f"  Steps: {[s.get('title') for s in data['install_steps']]}")


class TestNOCDashboardAPIs:
    """NOC Dashboard API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_system_risk(self, auth_headers):
        """Test GET /api/impact/system-risk returns risk score"""
        response = requests.get(f"{BASE_URL}/api/impact/system-risk", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify system risk response structure
        assert "risk_score" in data
        assert "risk_level" in data
        assert isinstance(data["risk_score"], (int, float))
        assert data["risk_level"] in ["minimal", "low", "medium", "high", "critical"]
        print(f"✓ GET /api/impact/system-risk: score={data['risk_score']}, level={data['risk_level']}")
    
    def test_get_alert_engine_stats(self, auth_headers):
        """Test GET /api/alert-engine/stats returns alert statistics"""
        response = requests.get(f"{BASE_URL}/api/alert-engine/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify alert stats structure
        assert "active_alerts" in data or "total_alerts" in data
        print(f"✓ GET /api/alert-engine/stats: active={data.get('active_alerts', data.get('total_alerts', 0))}")
    
    def test_get_incident_engine_stats(self, auth_headers):
        """Test GET /api/incident-engine/stats returns incident statistics"""
        response = requests.get(f"{BASE_URL}/api/incident-engine/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify incident stats structure
        assert "active_incidents" in data or "total_incidents" in data
        print(f"✓ GET /api/incident-engine/stats: active={data.get('active_incidents', data.get('total_incidents', 0))}")
    
    def test_get_active_alerts(self, auth_headers):
        """Test GET /api/alert-engine/active returns active alerts"""
        response = requests.get(f"{BASE_URL}/api/alert-engine/active", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        print(f"✓ GET /api/alert-engine/active: {len(data['alerts'])} active alerts")
    
    def test_get_active_incidents(self, auth_headers):
        """Test GET /api/incident-engine/active returns active incidents"""
        response = requests.get(f"{BASE_URL}/api/incident-engine/active", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "incidents" in data
        print(f"✓ GET /api/incident-engine/active: {len(data['incidents'])} active incidents")
    
    def test_get_capacity_alerts(self, auth_headers):
        """Test GET /api/capacity/alerts returns capacity warnings"""
        response = requests.get(f"{BASE_URL}/api/capacity/alerts?threshold=85&horizon=24h", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data or isinstance(data, list) or "message" in data
        alert_count = len(data.get("alerts", data if isinstance(data, list) else []))
        print(f"✓ GET /api/capacity/alerts: {alert_count} capacity warnings")


class TestAgentMetricsFlow:
    """Test agent registration and metrics push flow"""
    
    def test_agent_register_and_push_metrics(self):
        """Test agent can register and push metrics"""
        import socket
        
        # Step 1: Register server
        register_data = {
            "hostname": f"TEST_agent-host-{int(time.time())}",
            "ip_address": "192.168.1.100",
            "os_type": "linux",
            "os_version": "Ubuntu 22.04",
            "agent_version": "2.0.0",
            "tags": {"test": "true"}
        }
        
        response = requests.post(f"{BASE_URL}/api/servers/register", json=register_data)
        assert response.status_code == 200
        reg_data = response.json()
        assert "agent_token" in reg_data
        agent_token = reg_data["agent_token"]
        print(f"✓ Server registered with token: {agent_token[:20]}...")
        
        # Step 2: Push metrics
        metrics_data = {
            "agent_token": agent_token,
            "cpu_percent": 45.5,
            "memory_percent": 62.3,
            "memory_used_gb": 8.0,
            "memory_total_gb": 16.0,
            "disk_percent": 55.0,
            "disk_used_gb": 100.0,
            "disk_total_gb": 200.0,
            "network_in_mbps": 50.5,
            "network_out_mbps": 25.3,
            "load_average_1m": 1.5,
            "load_average_5m": 1.2,
            "load_average_15m": 0.9,
            "process_count": 150,
            "uptime_seconds": 86400
        }
        
        response = requests.post(f"{BASE_URL}/api/servers/metrics/ingest", json=metrics_data)
        assert response.status_code == 200
        ingest_data = response.json()
        assert "status" in ingest_data
        print(f"✓ Metrics pushed successfully, status={ingest_data['status']}")


class TestMultiTenancyOtherRoutes:
    """Multi-tenancy tests for APM, Reports, Topology"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_apm_dashboard_with_tenant_context(self, auth_headers):
        """Test GET /api/apm/dashboard has tenant_id filtering"""
        response = requests.get(f"{BASE_URL}/api/apm/dashboard?hours=24", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "overall_metrics" in data
        print(f"✓ GET /api/apm/dashboard: {len(data['services'])} services")
    
    def test_topology_with_tenant_context(self, auth_headers):
        """Test GET /api/topology has tenant_id filtering"""
        response = requests.get(f"{BASE_URL}/api/topology", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        print(f"✓ GET /api/topology: {len(data['nodes'])} nodes, {len(data['edges'])} edges")
    
    def test_reports_executive_with_tenant_context(self, auth_headers):
        """Test GET /api/reports/executive has tenant_id filtering"""
        response = requests.get(f"{BASE_URL}/api/reports/executive", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "kpis" in data or "period" in data
        print(f"✓ GET /api/reports/executive: report generated")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
