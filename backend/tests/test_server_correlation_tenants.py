"""
FalconOps AI - Server Monitoring, AI Correlation, and Multi-Tenancy Tests
Tests for iteration 7 features: Server Monitoring Module, AI Correlation Engine, Multi-Tenancy
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestServerMonitoringModule:
    """Server Monitoring API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_server_dashboard(self):
        """Test GET /api/servers/dashboard - Server monitoring dashboard"""
        response = requests.get(f"{BASE_URL}/api/servers/dashboard", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify dashboard structure
        assert "total_servers" in data
        assert "online_servers" in data
        assert "offline_servers" in data
        assert "warning_servers" in data
        assert "critical_servers" in data
        assert "avg_cpu" in data
        assert "avg_memory" in data
        assert "avg_disk" in data
        assert "servers" in data
        
        # Verify we have 5 demo servers
        assert data["total_servers"] == 5
        assert isinstance(data["servers"], list)
        print(f"✓ Server Dashboard: {data['total_servers']} servers, {data['online_servers']} online, {data['warning_servers']} warning")
    
    def test_server_list(self):
        """Test GET /api/servers - List all servers"""
        response = requests.get(f"{BASE_URL}/api/servers", headers=self.headers)
        assert response.status_code == 200
        servers = response.json()
        
        assert isinstance(servers, list)
        assert len(servers) >= 5  # Demo servers
        
        # Verify server structure
        server = servers[0]
        assert "id" in server
        assert "hostname" in server
        assert "ip_address" in server
        assert "status" in server
        assert "cpu_usage" in server
        assert "memory_usage" in server
        assert "disk_usage" in server
        print(f"✓ Server List: {len(servers)} servers found")
    
    def test_server_details(self):
        """Test GET /api/servers/{server_id} - Get single server"""
        # First get a server ID
        response = requests.get(f"{BASE_URL}/api/servers", headers=self.headers)
        servers = response.json()
        server_id = servers[0]["id"]
        
        # Get server details
        response = requests.get(f"{BASE_URL}/api/servers/{server_id}", headers=self.headers)
        assert response.status_code == 200
        server = response.json()
        
        assert server["id"] == server_id
        assert "hostname" in server
        assert "os_type" in server
        print(f"✓ Server Details: {server['hostname']} ({server['status']})")
    
    def test_server_metrics_history(self):
        """Test GET /api/servers/{server_id}/metrics - Get server metrics history"""
        # First get a server ID
        response = requests.get(f"{BASE_URL}/api/servers", headers=self.headers)
        servers = response.json()
        server_id = servers[0]["id"]
        
        # Get metrics history
        response = requests.get(f"{BASE_URL}/api/servers/{server_id}/metrics?hours=24", headers=self.headers)
        assert response.status_code == 200
        metrics = response.json()
        
        assert isinstance(metrics, list)
        if len(metrics) > 0:
            metric = metrics[0]
            assert "cpu_percent" in metric
            assert "memory_percent" in metric
            assert "disk_percent" in metric
            assert "timestamp" in metric
        print(f"✓ Server Metrics History: {len(metrics)} data points")
    
    def test_server_metrics_ingestion(self):
        """Test POST /api/servers/metrics/ingest - Ingest server metrics"""
        # Get a server's agent token
        response = requests.get(f"{BASE_URL}/api/servers", headers=self.headers)
        servers = response.json()
        agent_token = servers[0]["agent_token"]
        
        # Ingest metrics
        response = requests.post(f"{BASE_URL}/api/servers/metrics/ingest", json={
            "agent_token": agent_token,
            "cpu_percent": 55.5,
            "memory_percent": 65.2,
            "disk_percent": 40.0,
            "network_in_mbps": 100.5,
            "network_out_mbps": 50.2,
            "load_average_1m": 2.5,
            "process_count": 150,
            "uptime_seconds": 86400
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Metrics ingested successfully"
        assert "status" in data
        print(f"✓ Metrics Ingestion: status={data['status']}")
    
    def test_server_simulate(self):
        """Test POST /api/servers/simulate - Simulate server metrics"""
        response = requests.post(f"{BASE_URL}/api/servers/simulate", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "Simulation complete" in data["message"]
        print(f"✓ Server Simulation: {data['message']}")
    
    def test_server_alert_rules_list(self):
        """Test GET /api/servers/rules/alerts - List alert rules"""
        response = requests.get(f"{BASE_URL}/api/servers/rules/alerts", headers=self.headers)
        assert response.status_code == 200
        rules = response.json()
        
        assert isinstance(rules, list)
        print(f"✓ Alert Rules List: {len(rules)} rules")
    
    def test_server_alert_rule_create_delete(self):
        """Test POST/DELETE /api/servers/rules/alerts - Create and delete alert rule"""
        # Create rule
        rule_name = f"TEST_High_CPU_Alert_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/servers/rules/alerts", headers=self.headers, json={
            "name": rule_name,
            "metric": "cpu",
            "operator": "gt",
            "threshold": 90,
            "severity": "critical"
        })
        assert response.status_code == 200
        rule = response.json()
        
        assert rule["name"] == rule_name
        assert rule["metric"] == "cpu"
        assert rule["threshold"] == 90
        rule_id = rule["id"]
        print(f"✓ Alert Rule Created: {rule_name}")
        
        # Delete rule
        response = requests.delete(f"{BASE_URL}/api/servers/rules/alerts/{rule_id}", headers=self.headers)
        assert response.status_code == 200
        print(f"✓ Alert Rule Deleted: {rule_id}")


class TestAICorrelationEngine:
    """AI Correlation Engine API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_correlation_rules(self):
        """Test GET /api/correlation/rules - Get all correlation rules"""
        response = requests.get(f"{BASE_URL}/api/correlation/rules", headers=self.headers)
        assert response.status_code == 200
        rules = response.json()
        
        assert isinstance(rules, list)
        assert len(rules) == 7  # 7 predefined rules
        
        # Verify rule structure
        rule_names = [r["name"] for r in rules]
        assert "Resource Saturation" in rule_names
        assert "Database Connection Pool Exhaustion" in rule_names
        assert "Network Connectivity Issues" in rule_names
        assert "Disk Space Critical" in rule_names
        assert "SSL Certificate Expiry" in rule_names
        assert "Application Error Spike" in rule_names
        assert "Cascading Failure" in rule_names
        
        # Verify rule has required fields
        rule = rules[0]
        assert "id" in rule
        assert "name" in rule
        assert "description" in rule
        assert "conditions" in rule
        assert "root_cause" in rule
        assert "suggested_actions" in rule
        assert "severity" in rule
        print(f"✓ Correlation Rules: {len(rules)} rules found")
    
    def test_correlation_stats(self):
        """Test GET /api/correlation/stats - Get correlation statistics"""
        response = requests.get(f"{BASE_URL}/api/correlation/stats", headers=self.headers)
        assert response.status_code == 200
        stats = response.json()
        
        assert "total_incidents" in stats
        assert "rule_based_incidents" in stats
        assert "auto_grouped_incidents" in stats
        assert "correlation_rules_count" in stats
        assert "rules" in stats
        
        assert stats["correlation_rules_count"] == 7
        print(f"✓ Correlation Stats: {stats['total_incidents']} incidents, {stats['correlation_rules_count']} rules")
    
    def test_correlation_run(self):
        """Test POST /api/correlation/run - Trigger correlation cycle"""
        response = requests.post(f"{BASE_URL}/api/correlation/run", headers=self.headers)
        assert response.status_code == 200
        result = response.json()
        
        assert "success" in result
        assert result["success"] == True
        assert "incidents_created" in result
        print(f"✓ Correlation Run: success={result['success']}, incidents_created={result['incidents_created']}")


class TestMultiTenancy:
    """Multi-Tenancy API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_tenant_list(self):
        """Test GET /api/tenants - List all tenants"""
        response = requests.get(f"{BASE_URL}/api/tenants", headers=self.headers)
        assert response.status_code == 200
        tenants = response.json()
        
        assert isinstance(tenants, list)
        print(f"✓ Tenant List: {len(tenants)} tenants")
    
    def test_tenant_create_and_delete(self):
        """Test POST/DELETE /api/tenants - Create and delete tenant"""
        # Create tenant
        tenant_name = f"TEST_Tenant_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/tenants", headers=self.headers, json={
            "name": tenant_name,
            "domain": "testdomain.com",
            "contact_email": "contact@testdomain.com",
            "plan": "professional",
            "max_users": 20,
            "max_servers": 100,
            "max_monitors": 200
        })
        assert response.status_code == 200
        tenant = response.json()
        
        assert tenant["name"] == tenant_name
        assert tenant["plan"] == "professional"
        assert tenant["max_users"] == 20
        assert tenant["status"] == "active"
        tenant_id = tenant["id"]
        print(f"✓ Tenant Created: {tenant_name}")
        
        # Get tenant details
        response = requests.get(f"{BASE_URL}/api/tenants/{tenant_id}", headers=self.headers)
        assert response.status_code == 200
        tenant_details = response.json()
        assert tenant_details["name"] == tenant_name
        print(f"✓ Tenant Details Retrieved: {tenant_id}")
        
        # Delete tenant
        response = requests.delete(f"{BASE_URL}/api/tenants/{tenant_id}", headers=self.headers)
        assert response.status_code == 200
        print(f"✓ Tenant Deleted: {tenant_id}")
    
    def test_tenant_stats(self):
        """Test GET /api/tenants/{tenant_id}/stats - Get tenant statistics"""
        # First create a tenant
        tenant_name = f"TEST_Stats_Tenant_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/tenants", headers=self.headers, json={
            "name": tenant_name,
            "plan": "starter"
        })
        tenant_id = response.json()["id"]
        
        # Get stats
        response = requests.get(f"{BASE_URL}/api/tenants/{tenant_id}/stats", headers=self.headers)
        assert response.status_code == 200
        stats = response.json()
        
        assert "tenant_id" in stats
        assert "usage" in stats
        assert "health" in stats
        assert "status" in stats
        print(f"✓ Tenant Stats: {stats['tenant_name']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tenants/{tenant_id}", headers=self.headers)


class TestServerRegistration:
    """Server Registration API tests (public endpoint)"""
    
    def test_server_register(self):
        """Test POST /api/servers/register - Register new server"""
        hostname = f"test-server-{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/servers/register", json={
            "hostname": hostname,
            "ip_address": f"192.168.1.{uuid.uuid4().int % 255}",
            "os_type": "linux",
            "os_version": "Ubuntu 22.04",
            "agent_version": "1.0.0"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "server_id" in data
        assert "agent_token" in data
        assert data["agent_token"].startswith("fop_srv_")
        print(f"✓ Server Registered: {hostname}, token={data['agent_token'][:20]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
