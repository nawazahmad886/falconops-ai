"""
FalconOps AI - Custom Database Query Monitoring Tests (Iteration 23)
Tests for custom SQL query creation, execution simulation, timeseries data, and dashboard widgets.
MOCKED: Query execution is simulated (not real SQL execution against a DB).
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@falconapps.com"
TEST_PASSWORD = "Admin@123"

# Known instance IDs
PRODUCTION_POSTGRES_ID = "b9b9b607-e8ce-4a42-a8de-bd6c4a91fd48"
ORACLE_RAC_ID = "d25796d5-0109-4274-bd72-c842899440ee"


class TestCustomQueryAuth:
    """Test authentication requirements for custom query endpoints"""
    
    def test_list_custom_queries_requires_auth(self):
        """GET /api/db-monitoring/custom-queries/{instance_id} requires auth"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{PRODUCTION_POSTGRES_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: GET /api/db-monitoring/custom-queries/{instance_id} requires auth")
    
    def test_custom_dashboard_requires_auth(self):
        """GET /api/db-monitoring/custom-queries/{instance_id}/dashboard requires auth"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{PRODUCTION_POSTGRES_ID}/dashboard")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: GET /api/db-monitoring/custom-queries/{instance_id}/dashboard requires auth")
    
    def test_custom_results_requires_auth(self):
        """GET /api/db-monitoring/custom-results/{instance_id} requires auth"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-results/{PRODUCTION_POSTGRES_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: GET /api/db-monitoring/custom-results/{instance_id} requires auth")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for authenticated tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        token = data.get("token") or data.get("access_token")
        print(f"AUTH: Got token successfully")
        return token
    pytest.skip(f"Authentication failed: {response.status_code}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestListCustomQueries:
    """Test listing custom queries for an instance"""
    
    def test_list_custom_queries_for_postgres(self, auth_headers):
        """GET /api/db-monitoring/custom-queries/{instance_id} - list queries for Production PostgreSQL"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{PRODUCTION_POSTGRES_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "queries" in data, "Response should contain 'queries' key"
        queries = data["queries"]
        assert isinstance(queries, list), "queries should be a list"
        
        # Should have seeded queries
        print(f"PASS: GET custom-queries returned {len(queries)} queries for Production PostgreSQL")
        
        if queries:
            q = queries[0]
            # Verify query structure
            assert "id" in q, "Query should have 'id'"
            assert "name" in q, "Query should have 'name'"
            assert "query" in q, "Query should have 'query' (SQL)"
            assert "instance_id" in q, "Query should have 'instance_id'"
            assert "chart_type" in q, "Query should have 'chart_type'"
            assert "interval" in q, "Query should have 'interval'"
            assert "enabled" in q, "Query should have 'enabled'"
            # New fields for visualization
            assert "color" in q, "Query should have 'color'"
            print(f"  First query: {q['name']} - chart_type: {q['chart_type']}, color: {q['color']}, interval: {q['interval']}s")
        return queries
    
    def test_list_custom_queries_empty_instance(self, auth_headers):
        """GET /api/db-monitoring/custom-queries for instance with no queries"""
        # Oracle RAC might have no queries
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{ORACLE_RAC_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "queries" in data, "Response should contain 'queries' key"
        print(f"PASS: Oracle RAC has {len(data['queries'])} custom queries")


class TestCustomQueryCRUD:
    """Test Create, Read, Update, Delete operations for custom queries"""
    
    def test_create_custom_query(self, auth_headers):
        """POST /api/db-monitoring/custom-queries - create a new custom query"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "instance_id": PRODUCTION_POSTGRES_ID,
            "name": f"TEST_Query_{test_id}",
            "query": "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';",
            "interval": 30,
            "enabled": True,
            "chart_type": "line",
            "description": "Test query for counting active connections",
            "unit": "connections",
            "color": "#FF5733"
        }
        response = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries", headers=auth_headers, json=payload)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data, "Response should contain 'id'"
        assert data["name"] == payload["name"], f"Name mismatch: {data['name']} != {payload['name']}"
        assert data["query"] == payload["query"], "Query SQL should match"
        assert data["instance_id"] == PRODUCTION_POSTGRES_ID, "Instance ID should match"
        assert data["chart_type"] == "line", "Chart type should be 'line'"
        assert data["color"] == "#FF5733", "Color should match"
        assert data["unit"] == "connections", "Unit should match"
        assert data["description"] == payload["description"], "Description should match"
        assert data["interval"] == 30, "Interval should be 30"
        assert data["enabled"] == True, "Should be enabled"
        
        print(f"PASS: POST custom-queries created query: {data['id'][:8]}")
        return data["id"]
    
    def test_update_custom_query(self, auth_headers):
        """PUT /api/db-monitoring/custom-queries/{query_id} - update a custom query"""
        # First create a query to update
        test_id = str(uuid.uuid4())[:8]
        create_payload = {
            "instance_id": PRODUCTION_POSTGRES_ID,
            "name": f"TEST_Update_{test_id}",
            "query": "SELECT 1;",
            "interval": 60,
            "chart_type": "line",
            "color": "#00FF00"
        }
        create_res = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries", headers=auth_headers, json=create_payload)
        assert create_res.status_code in [200, 201]
        query_id = create_res.json()["id"]
        
        # Update the query
        update_payload = {
            "name": f"TEST_Updated_{test_id}",
            "query": "SELECT count(*) FROM users;",
            "interval": 120,
            "chart_type": "bar",
            "color": "#0000FF",
            "description": "Updated description",
            "unit": "users"
        }
        response = requests.put(f"{BASE_URL}/api/db-monitoring/custom-queries/{query_id}", headers=auth_headers, json=update_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify updates
        assert data["name"] == update_payload["name"], "Name should be updated"
        assert data["query"] == update_payload["query"], "Query should be updated"
        assert data["interval"] == 120, "Interval should be updated"
        assert data["chart_type"] == "bar", "Chart type should be updated"
        assert data["color"] == "#0000FF", "Color should be updated"
        assert data["description"] == "Updated description", "Description should be updated"
        assert data["unit"] == "users", "Unit should be updated"
        
        print(f"PASS: PUT custom-queries/{query_id[:8]} updated successfully")
        return query_id
    
    def test_update_nonexistent_query(self, auth_headers):
        """PUT /api/db-monitoring/custom-queries/{non-existent} - should return 404"""
        fake_id = str(uuid.uuid4())
        update_payload = {"name": "Should not work"}
        response = requests.put(f"{BASE_URL}/api/db-monitoring/custom-queries/{fake_id}", headers=auth_headers, json=update_payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: PUT non-existent query returns 404")
    
    def test_toggle_custom_query(self, auth_headers):
        """POST /api/db-monitoring/custom-queries/{query_id}/toggle - toggle enable/disable"""
        # First create a query
        test_id = str(uuid.uuid4())[:8]
        create_payload = {
            "instance_id": PRODUCTION_POSTGRES_ID,
            "name": f"TEST_Toggle_{test_id}",
            "query": "SELECT 1;",
            "enabled": True,
            "chart_type": "gauge",
            "color": "#FFFF00"
        }
        create_res = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries", headers=auth_headers, json=create_payload)
        assert create_res.status_code in [200, 201]
        query_id = create_res.json()["id"]
        initial_enabled = create_res.json().get("enabled", True)
        
        # Toggle the query
        response = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries/{query_id}/toggle", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "id" in data, "Response should contain 'id'"
        assert "enabled" in data, "Response should contain 'enabled'"
        assert data["enabled"] != initial_enabled, "Enabled state should be toggled"
        
        print(f"PASS: POST toggle changed enabled from {initial_enabled} to {data['enabled']}")
        
        # Toggle again to verify it toggles back
        response2 = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries/{query_id}/toggle", headers=auth_headers)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["enabled"] == initial_enabled, "Second toggle should restore original state"
        print(f"PASS: Second toggle restored enabled to {data2['enabled']}")
        return query_id
    
    def test_toggle_nonexistent_query(self, auth_headers):
        """POST /api/db-monitoring/custom-queries/{non-existent}/toggle - should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries/{fake_id}/toggle", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Toggle non-existent query returns 404")
    
    def test_delete_custom_query(self, auth_headers):
        """DELETE /api/db-monitoring/custom-queries/{query_id} - delete a query"""
        # First create a query to delete
        test_id = str(uuid.uuid4())[:8]
        create_payload = {
            "instance_id": PRODUCTION_POSTGRES_ID,
            "name": f"TEST_Delete_{test_id}",
            "query": "SELECT 1;",
            "chart_type": "area",
            "color": "#FF00FF"
        }
        create_res = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries", headers=auth_headers, json=create_payload)
        assert create_res.status_code in [200, 201]
        query_id = create_res.json()["id"]
        
        # Delete the query
        response = requests.delete(f"{BASE_URL}/api/db-monitoring/custom-queries/{query_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("deleted") == True, "Response should confirm deletion"
        
        # Verify it's gone by trying to toggle it (should 404)
        verify_res = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries/{query_id}/toggle", headers=auth_headers)
        assert verify_res.status_code == 404, "Deleted query should not exist"
        
        print(f"PASS: DELETE custom-queries/{query_id[:8]} successful")
    
    def test_delete_nonexistent_query(self, auth_headers):
        """DELETE /api/db-monitoring/custom-queries/{non-existent} - should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(f"{BASE_URL}/api/db-monitoring/custom-queries/{fake_id}", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: DELETE non-existent query returns 404")


class TestCustomQueryExecution:
    """Test query execution simulation - NOTE: This is MOCKED (no real SQL execution)"""
    
    def test_execute_custom_query(self, auth_headers):
        """POST /api/db-monitoring/custom-queries/{query_id}/execute - execute a query (SIMULATED)"""
        # First create a query to execute
        test_id = str(uuid.uuid4())[:8]
        create_payload = {
            "instance_id": PRODUCTION_POSTGRES_ID,
            "name": f"TEST_Exec_{test_id}",
            "query": "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';",
            "chart_type": "line",
            "color": "#00E0FF",
            "unit": "connections"
        }
        create_res = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries", headers=auth_headers, json=create_payload)
        assert create_res.status_code in [200, 201]
        query_id = create_res.json()["id"]
        
        # Execute the query
        response = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries/{query_id}/execute", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify execution result structure
        assert "id" in data, "Result should have 'id'"
        assert "query_id" in data, "Result should have 'query_id'"
        assert data["query_id"] == query_id, "Query ID should match"
        assert "instance_id" in data, "Result should have 'instance_id'"
        assert "status" in data, "Result should have 'status'"
        assert data["status"] == "success", "Execution status should be 'success'"
        assert "value" in data, "Result should have 'value'"
        assert "duration_ms" in data, "Result should have 'duration_ms'"
        assert "executed_at" in data, "Result should have 'executed_at'"
        assert "query_name" in data, "Result should have 'query_name'"
        
        print(f"PASS: Execute query returned value={data['value']}, duration={data['duration_ms']}ms (SIMULATED)")
        return query_id
    
    def test_execute_nonexistent_query(self, auth_headers):
        """POST /api/db-monitoring/custom-queries/{non-existent}/execute - should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries/{fake_id}/execute", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Execute non-existent query returns 404")


class TestCustomQueryDashboard:
    """Test dashboard widgets endpoint"""
    
    def test_get_custom_query_dashboard(self, auth_headers):
        """GET /api/db-monitoring/custom-queries/{instance_id}/dashboard - get dashboard widgets"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{PRODUCTION_POSTGRES_ID}/dashboard?hours=24", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "widgets" in data, "Response should contain 'widgets'"
        assert "instance_id" in data, "Response should contain 'instance_id'"
        assert "period_hours" in data, "Response should contain 'period_hours'"
        assert data["instance_id"] == PRODUCTION_POSTGRES_ID
        assert data["period_hours"] == 24
        
        widgets = data["widgets"]
        assert isinstance(widgets, list), "widgets should be a list"
        
        print(f"PASS: Dashboard returned {len(widgets)} widgets")
        
        if widgets:
            w = widgets[0]
            assert "query" in w, "Widget should have 'query'"
            assert "timeseries" in w, "Widget should have 'timeseries'"
            assert "latest_result" in w, "Widget should have 'latest_result'"
            assert "total_executions" in w, "Widget should have 'total_executions'"
            
            q = w["query"]
            assert "id" in q, "Query should have 'id'"
            assert "name" in q, "Query should have 'name'"
            assert "chart_type" in q, "Query should have 'chart_type'"
            assert "color" in q, "Query should have 'color'"
            
            ts = w["timeseries"]
            print(f"  Widget: {q['name']} - {len(ts)} timeseries points, {w['total_executions']} total executions")
            
            if ts:
                ts_point = ts[0]
                assert "value" in ts_point, "Timeseries point should have 'value'"
                assert "executed_at" in ts_point, "Timeseries point should have 'executed_at'"
        return widgets


class TestCustomQueryResults:
    """Test custom query results endpoints"""
    
    def test_get_custom_results(self, auth_headers):
        """GET /api/db-monitoring/custom-results/{instance_id} - get execution results"""
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-results/{PRODUCTION_POSTGRES_ID}?limit=50", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "results" in data, "Response should contain 'results'"
        results = data["results"]
        assert isinstance(results, list), "results should be a list"
        
        print(f"PASS: custom-results returned {len(results)} results")
        
        if results:
            r = results[0]
            assert "query_id" in r, "Result should have 'query_id'"
            assert "instance_id" in r, "Result should have 'instance_id'"
            assert "value" in r, "Result should have 'value'"
            assert "executed_at" in r, "Result should have 'executed_at'"
            assert "status" in r, "Result should have 'status'"
        return results
    
    def test_get_custom_results_with_query_filter(self, auth_headers):
        """GET /api/db-monitoring/custom-results/{instance_id}?query_id= - filter by query_id"""
        # First get a query ID from the dashboard
        dash_res = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{PRODUCTION_POSTGRES_ID}/dashboard", headers=auth_headers)
        widgets = dash_res.json().get("widgets", [])
        if not widgets:
            pytest.skip("No widgets available for filter test")
        
        query_id = widgets[0]["query"]["id"]
        
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-results/{PRODUCTION_POSTGRES_ID}?query_id={query_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        results = data.get("results", [])
        
        # All results should be for this query
        for r in results:
            assert r.get("query_id") == query_id, f"Result query_id should match filter: {r.get('query_id')} != {query_id}"
        
        print(f"PASS: custom-results filtered by query_id returned {len(results)} results")
    
    def test_get_timeseries_for_query(self, auth_headers):
        """GET /api/db-monitoring/custom-results/{instance_id}/timeseries/{query_id} - get timeseries"""
        # First get a query ID
        dash_res = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{PRODUCTION_POSTGRES_ID}/dashboard", headers=auth_headers)
        widgets = dash_res.json().get("widgets", [])
        if not widgets:
            pytest.skip("No widgets available for timeseries test")
        
        query_id = widgets[0]["query"]["id"]
        
        response = requests.get(f"{BASE_URL}/api/db-monitoring/custom-results/{PRODUCTION_POSTGRES_ID}/timeseries/{query_id}?hours=24", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "query_id" in data, "Response should contain 'query_id'"
        assert "timeseries" in data, "Response should contain 'timeseries'"
        assert "period_hours" in data, "Response should contain 'period_hours'"
        assert data["query_id"] == query_id
        assert data["period_hours"] == 24
        
        timeseries = data["timeseries"]
        assert isinstance(timeseries, list), "timeseries should be a list"
        
        print(f"PASS: timeseries for query {query_id[:8]} returned {len(timeseries)} points")
        return timeseries


class TestSeedDemoQueries:
    """Test seed demo queries endpoint"""
    
    def test_seed_demo_queries(self, auth_headers):
        """POST /api/db-monitoring/custom-queries/seed/{instance_id} - seed demo queries"""
        # Use Oracle RAC which might not have queries yet
        response = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries/seed/{ORACLE_RAC_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "queries_created" in data, "Response should contain 'queries_created'"
        assert "results_seeded" in data, "Response should contain 'results_seeded'"
        assert "queries" in data, "Response should contain 'queries' list"
        
        queries_created = data["queries_created"]
        results_seeded = data["results_seeded"]
        queries = data["queries"]
        
        assert queries_created >= 1, "Should create at least 1 query"
        assert results_seeded >= 1, "Should seed at least 1 result"
        assert len(queries) == queries_created, "Queries list length should match queries_created"
        
        print(f"PASS: Seeded {queries_created} queries with {results_seeded} historical data points")
        
        # Verify queries were created
        verify_res = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{ORACLE_RAC_ID}", headers=auth_headers)
        verify_data = verify_res.json()
        assert len(verify_data.get("queries", [])) >= queries_created, "Queries should be persisted"
        
        return data
    
    def test_seed_nonexistent_instance(self, auth_headers):
        """POST /api/db-monitoring/custom-queries/seed/{non-existent} - should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.post(f"{BASE_URL}/api/db-monitoring/custom-queries/seed/{fake_id}", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Seed for non-existent instance returns 404")


class TestCleanup:
    """Cleanup test data after tests"""
    
    def test_cleanup_test_queries(self, auth_headers):
        """Cleanup: Remove TEST_ prefixed custom queries from Production PostgreSQL"""
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{PRODUCTION_POSTGRES_ID}", headers=auth_headers)
        queries = list_res.json().get("queries", [])
        deleted = 0
        for q in queries:
            if q.get("name", "").startswith("TEST_"):
                del_res = requests.delete(f"{BASE_URL}/api/db-monitoring/custom-queries/{q['id']}", headers=auth_headers)
                if del_res.status_code == 200:
                    deleted += 1
        print(f"CLEANUP: Removed {deleted} TEST_ queries from Production PostgreSQL")
    
    def test_cleanup_oracle_queries(self, auth_headers):
        """Cleanup: Remove TEST_ prefixed custom queries from Oracle RAC"""
        list_res = requests.get(f"{BASE_URL}/api/db-monitoring/custom-queries/{ORACLE_RAC_ID}", headers=auth_headers)
        queries = list_res.json().get("queries", [])
        deleted = 0
        for q in queries:
            if q.get("name", "").startswith("TEST_"):
                del_res = requests.delete(f"{BASE_URL}/api/db-monitoring/custom-queries/{q['id']}", headers=auth_headers)
                if del_res.status_code == 200:
                    deleted += 1
        print(f"CLEANUP: Removed {deleted} TEST_ queries from Oracle RAC")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
