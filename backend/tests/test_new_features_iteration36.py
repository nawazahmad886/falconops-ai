"""
FalconOps AI - Iteration 36 Backend Tests
Testing: RBAC, SOC Live Feed, AWS Connectors, Kafka Pipeline, Query Analyzer
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


class TestSetup:
    """Setup and authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestRBAC(TestSetup):
    """RBAC Module Tests - Roles, Permissions, Audit Logs"""
    
    def test_get_roles_returns_default_roles(self, auth_headers):
        """GET /api/rbac/roles should return 4 default roles"""
        response = requests.get(f"{BASE_URL}/api/rbac/roles", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        roles = response.json()
        assert isinstance(roles, list), "Roles should be a list"
        assert len(roles) >= 4, f"Expected at least 4 default roles, got {len(roles)}"
        
        # Verify default role IDs exist
        role_ids = [r.get("role_id") for r in roles]
        for expected_role in ["admin", "security_analyst", "devops", "viewer"]:
            assert expected_role in role_ids, f"Missing default role: {expected_role}"
        
        # Verify role structure
        admin_role = next((r for r in roles if r.get("role_id") == "admin"), None)
        assert admin_role is not None
        assert "name" in admin_role
        assert "permissions" in admin_role
        assert isinstance(admin_role["permissions"], list)
        print(f"✓ Found {len(roles)} roles including all 4 defaults")
    
    def test_get_permissions_returns_all_permissions(self, auth_headers):
        """GET /api/rbac/permissions should return 26 permissions"""
        response = requests.get(f"{BASE_URL}/api/rbac/permissions", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        permissions = response.json()
        assert isinstance(permissions, list), "Permissions should be a list"
        assert len(permissions) >= 26, f"Expected at least 26 permissions, got {len(permissions)}"
        
        # Verify permission structure
        for perm in permissions[:5]:
            assert "key" in perm, "Permission should have 'key'"
            assert "description" in perm, "Permission should have 'description'"
        print(f"✓ Found {len(permissions)} permissions")
    
    def test_create_custom_role(self, auth_headers):
        """POST /api/rbac/roles should create a new custom role"""
        role_data = {
            "role_id": "test_custom_role",
            "name": "Test Custom Role",
            "description": "A test role for iteration 36",
            "permissions": ["dashboard.view", "monitors.view", "alerts.view"]
        }
        response = requests.post(f"{BASE_URL}/api/rbac/roles", json=role_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert result.get("role_id") == "test_custom_role"
        assert result.get("name") == "Test Custom Role"
        assert "permissions" in result
        assert result.get("is_system") == False
        print(f"✓ Created custom role: {result.get('name')}")
    
    def test_get_single_role(self, auth_headers):
        """GET /api/rbac/roles/{role_id} should return specific role"""
        response = requests.get(f"{BASE_URL}/api/rbac/roles/admin", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        role = response.json()
        assert role.get("role_id") == "admin"
        assert role.get("name") == "Administrator"
        assert len(role.get("permissions", [])) > 20, "Admin should have many permissions"
        print(f"✓ Retrieved admin role with {len(role.get('permissions', []))} permissions")
    
    def test_get_audit_logs(self, auth_headers):
        """GET /api/rbac/audit should return audit logs"""
        response = requests.get(f"{BASE_URL}/api/rbac/audit?limit=50", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert "logs" in result, "Response should have 'logs'"
        assert "total" in result, "Response should have 'total'"
        assert isinstance(result["logs"], list)
        print(f"✓ Retrieved {len(result['logs'])} audit logs (total: {result['total']})")
    
    def test_get_audit_stats(self, auth_headers):
        """GET /api/rbac/audit/stats should return audit statistics"""
        response = requests.get(f"{BASE_URL}/api/rbac/audit/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        stats = response.json()
        assert "total_events" in stats, "Stats should have 'total_events'"
        assert "top_users" in stats, "Stats should have 'top_users'"
        assert "top_actions" in stats, "Stats should have 'top_actions'"
        print(f"✓ Audit stats: {stats['total_events']} total events")
    
    def test_check_permission(self, auth_headers):
        """GET /api/rbac/check-permission should check user permission"""
        response = requests.get(f"{BASE_URL}/api/rbac/check-permission?permission=dashboard.view", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert "permission" in result
        assert "granted" in result
        assert result["permission"] == "dashboard.view"
        print(f"✓ Permission check: dashboard.view = {result['granted']}")


class TestSOCLiveFeed(TestSetup):
    """SOC Live Feed Module Tests"""
    
    def test_get_soc_feed(self, auth_headers):
        """GET /api/soc/feed should return recent feed items"""
        response = requests.get(f"{BASE_URL}/api/soc/feed?limit=30", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        feed = response.json()
        assert isinstance(feed, list), "Feed should be a list"
        print(f"✓ SOC feed returned {len(feed)} items")
    
    def test_get_soc_stats(self, auth_headers):
        """GET /api/soc/stats should return connected clients count"""
        response = requests.get(f"{BASE_URL}/api/soc/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        stats = response.json()
        assert "connected_clients" in stats, "Stats should have 'connected_clients'"
        assert "status" in stats, "Stats should have 'status'"
        assert stats["status"] == "active"
        print(f"✓ SOC stats: {stats['connected_clients']} connected clients, status={stats['status']}")


class TestAWSConnectors(TestSetup):
    """AWS Connectors Module Tests - CloudTrail & VPC Flow Logs"""
    
    def test_get_connectors_list(self, auth_headers):
        """GET /api/aws/connectors should return 2 connectors"""
        response = requests.get(f"{BASE_URL}/api/aws/connectors", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert "connectors" in result, "Response should have 'connectors'"
        connectors = result["connectors"]
        assert len(connectors) == 2, f"Expected 2 connectors, got {len(connectors)}"
        
        # Verify connector types
        types = [c.get("type") for c in connectors]
        assert "cloudtrail" in types, "Missing cloudtrail connector"
        assert "vpc_flowlogs" in types, "Missing vpc_flowlogs connector"
        
        # Verify connector structure
        for conn in connectors:
            assert "id" in conn
            assert "name" in conn
            assert "type" in conn
            assert "enabled" in conn
            assert "region" in conn
            assert "status" in conn
        print(f"✓ Found {len(connectors)} AWS connectors: {types}")
    
    def test_configure_cloudtrail_connector(self, auth_headers):
        """POST /api/aws/connectors should configure CloudTrail connector"""
        config = {
            "connector_type": "cloudtrail",
            "aws_region": "us-east-1",
            "aws_access_key": "",
            "aws_secret_key": "",
            "enabled": True
        }
        response = requests.post(f"{BASE_URL}/api/aws/connectors", json=config, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert "message" in result
        assert "enabled" in result
        print(f"✓ Configured CloudTrail connector: {result['message']}")
    
    def test_get_cloudtrail_events(self, auth_headers):
        """GET /api/aws/events/cloudtrail should return simulated CloudTrail events"""
        response = requests.get(f"{BASE_URL}/api/aws/events/cloudtrail?limit=20", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        events = response.json()
        assert isinstance(events, list), "Events should be a list"
        
        # Verify event structure if events exist
        if len(events) > 0:
            event = events[0]
            assert "message" in event or "event_name" in event
            assert "severity" in event
            assert "timestamp" in event
        print(f"✓ CloudTrail returned {len(events)} simulated events")
    
    def test_get_vpc_flow_events(self, auth_headers):
        """GET /api/aws/events/vpc should return simulated VPC Flow Log events"""
        response = requests.get(f"{BASE_URL}/api/aws/events/vpc?limit=20", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        events = response.json()
        assert isinstance(events, list), "Events should be a list"
        
        # Verify event structure if events exist
        if len(events) > 0:
            event = events[0]
            assert "message" in event or "source_ip" in event
            assert "severity" in event
        print(f"✓ VPC Flow Logs returned {len(events)} simulated events")
    
    def test_fetch_all_aws_events(self, auth_headers):
        """POST /api/aws/fetch should ingest from all enabled connectors"""
        response = requests.post(f"{BASE_URL}/api/aws/fetch", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        # Result should contain info about fetched events
        print(f"✓ AWS fetch completed: {result}")


class TestKafkaPipeline(TestSetup):
    """Kafka Pipeline Module Tests - Event Streaming with MongoDB Fallback"""
    
    def test_get_kafka_stats(self, auth_headers):
        """GET /api/kafka/stats should return pipeline stats with mode='mongodb_fallback'"""
        response = requests.get(f"{BASE_URL}/api/kafka/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        stats = response.json()
        
        # Verify required fields
        assert "mode" in stats, "Stats should have 'mode'"
        assert stats["mode"] == "mongodb_fallback", f"Expected mongodb_fallback mode, got {stats['mode']}"
        assert "total_events" in stats, "Stats should have 'total_events'"
        assert "topics" in stats, "Stats should have 'topics'"
        
        # Verify topics structure
        topics = stats.get("topics", {})
        assert isinstance(topics, dict), "Topics should be a dict"
        print(f"✓ Kafka stats: mode={stats['mode']}, total_events={stats['total_events']}, topics={len(topics)}")
    
    def test_produce_event_to_pipeline(self, auth_headers):
        """POST /api/kafka/produce should send an event to the pipeline"""
        event_data = {
            "topic": "security_events",
            "event": {
                "type": "test_event",
                "message": "Test event from iteration 36",
                "severity": "info",
                "source": "pytest",
                "timestamp": "2026-01-15T10:00:00Z"
            }
        }
        response = requests.post(f"{BASE_URL}/api/kafka/produce", json=event_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        assert "sent" in result, "Response should have 'sent'"
        assert "topic" in result, "Response should have 'topic'"
        assert result["sent"] == True, "Event should be sent successfully"
        assert result["topic"] == "security_events"
        print(f"✓ Produced event to {result['topic']}: sent={result['sent']}")
    
    def test_produce_multiple_events(self, auth_headers):
        """Test producing events to different topics"""
        topics = ["security_events", "alerts", "metrics"]
        for topic in topics:
            event_data = {
                "topic": topic,
                "event": {
                    "type": "test_event",
                    "message": f"Test event for {topic}",
                    "severity": "info"
                }
            }
            response = requests.post(f"{BASE_URL}/api/kafka/produce", json=event_data, headers=auth_headers)
            assert response.status_code == 200, f"Failed for topic {topic}: {response.text}"
        print(f"✓ Produced events to {len(topics)} topics")


class TestQueryAnalyzer(TestSetup):
    """Query Analyzer Module Tests - SQL Query Optimization"""
    
    def test_analyze_query_and_store(self, auth_headers):
        """POST /api/query-analyzer/analyze should analyze SQL query and store result"""
        query_data = {
            "query": "SELECT * FROM users WHERE status = 'active'",
            "db_id": "test_db",
            "duration_ms": 150
        }
        response = requests.post(f"{BASE_URL}/api/query-analyzer/analyze", json=query_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        
        # Verify analysis result structure
        assert "score" in result, "Result should have 'score'"
        assert "quality" in result, "Result should have 'quality'"
        assert "findings" in result, "Result should have 'findings'"
        assert isinstance(result["findings"], list)
        assert result["score"] >= 0 and result["score"] <= 100
        print(f"✓ Query analyzed: score={result['score']}, quality={result['quality']}, findings={len(result['findings'])}")
    
    def test_analyze_query_quick(self, auth_headers):
        """POST /api/query-analyzer/analyze/quick should analyze without storing"""
        query_data = {
            "query": "SELECT id, name FROM orders WHERE status = 'pending' ORDER BY created_at",
            "duration_ms": 0
        }
        response = requests.post(f"{BASE_URL}/api/query-analyzer/analyze/quick", json=query_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        
        assert "score" in result
        assert "quality" in result
        assert "findings" in result
        print(f"✓ Quick analysis: score={result['score']}, quality={result['quality']}")
    
    def test_analyze_problematic_query(self, auth_headers):
        """Test analyzing a query with issues (SELECT *)"""
        query_data = {
            "query": "SELECT * FROM large_table",
            "duration_ms": 5000
        }
        response = requests.post(f"{BASE_URL}/api/query-analyzer/analyze", json=query_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        result = response.json()
        
        # SELECT * should generate findings
        assert len(result.get("findings", [])) > 0, "SELECT * should generate findings"
        print(f"✓ Problematic query analyzed: {len(result['findings'])} findings detected")
    
    def test_get_slow_queries(self, auth_headers):
        """GET /api/query-analyzer/slow-queries should return analyzed queries"""
        response = requests.get(f"{BASE_URL}/api/query-analyzer/slow-queries?limit=30", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        queries = response.json()
        assert isinstance(queries, list), "Slow queries should be a list"
        
        # Verify query structure if queries exist
        if len(queries) > 0:
            q = queries[0]
            assert "query" in q
            assert "score" in q
            assert "quality" in q
        print(f"✓ Retrieved {len(queries)} analyzed queries")
    
    def test_get_query_stats(self, auth_headers):
        """GET /api/query-analyzer/stats should return statistics"""
        response = requests.get(f"{BASE_URL}/api/query-analyzer/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        stats = response.json()
        
        assert "total_analyzed" in stats, "Stats should have 'total_analyzed'"
        print(f"✓ Query stats: total_analyzed={stats['total_analyzed']}")


class TestAuthRequired(TestSetup):
    """Test that all endpoints require authentication"""
    
    def test_rbac_requires_auth(self):
        """RBAC endpoints should require authentication"""
        endpoints = [
            "/api/rbac/roles",
            "/api/rbac/permissions",
            "/api/rbac/audit",
            "/api/rbac/audit/stats"
        ]
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth, got {response.status_code}"
        print(f"✓ All {len(endpoints)} RBAC endpoints require authentication")
    
    def test_soc_requires_auth(self):
        """SOC endpoints should require authentication"""
        endpoints = ["/api/soc/feed", "/api/soc/stats"]
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth"
        print(f"✓ All SOC endpoints require authentication")
    
    def test_aws_requires_auth(self):
        """AWS endpoints should require authentication"""
        endpoints = [
            "/api/aws/connectors",
            "/api/aws/events/cloudtrail",
            "/api/aws/events/vpc"
        ]
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth"
        print(f"✓ All AWS endpoints require authentication")
    
    def test_kafka_requires_auth(self):
        """Kafka endpoints should require authentication"""
        response = requests.get(f"{BASE_URL}/api/kafka/stats")
        assert response.status_code in [401, 403], "Kafka stats should require auth"
        print(f"✓ Kafka endpoints require authentication")
    
    def test_query_analyzer_requires_auth(self):
        """Query Analyzer endpoints should require authentication"""
        endpoints = [
            "/api/query-analyzer/slow-queries",
            "/api/query-analyzer/stats"
        ]
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth"
        print(f"✓ All Query Analyzer endpoints require authentication")


class TestCleanup(TestSetup):
    """Cleanup test data"""
    
    def test_delete_custom_role(self, auth_headers):
        """Delete the test custom role created earlier"""
        response = requests.delete(f"{BASE_URL}/api/rbac/roles/test_custom_role", headers=auth_headers)
        # May return 200 or error if already deleted
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Cleanup: {result.get('message', 'Role deleted')}")
        else:
            print(f"✓ Cleanup: Role may have been already deleted or not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
