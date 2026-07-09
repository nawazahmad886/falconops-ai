"""
Iteration 42 - AI Agent Memory & Auto-Trigger Pipeline Tests
Tests: Memory search/stats/clear, Pipeline config/toggle/simulate/events/stats
Endpoints:
  Memory: POST /api/ai/memory/search, GET /api/ai/memory/stats, DELETE /api/ai/memory/clear
  Pipeline: GET /api/ai/pipeline/config, POST /api/ai/pipeline/toggle, POST /api/ai/pipeline/simulate,
            GET /api/ai/pipeline/events, GET /api/ai/pipeline/stats
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"
VIEWER_EMAIL = "test@falconapps.com"
VIEWER_PASSWORD = "testpass123"

# Sample data for testing
SAMPLE_ALERT_DATA = {
    "alert": "High CPU on prod-web-01",
    "value": 95,
    "threshold": 85,
    "duration": "10min"
}

SAMPLE_MEMORY_SEARCH_DATA = {
    "alert": "High CPU",
    "server": "prod-web"
}


class TestMemoryPipelineAuth:
    """Authentication fixtures for Memory & Pipeline tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Get admin auth headers"""
        return {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def viewer_token(self):
        """Get viewer authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": VIEWER_EMAIL, "password": VIEWER_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip("Viewer account not available")
        data = response.json()
        return data.get("access_token")
    
    @pytest.fixture(scope="class")
    def viewer_headers(self, viewer_token):
        """Get viewer auth headers"""
        if not viewer_token:
            pytest.skip("Viewer token not available")
        return {
            "Authorization": f"Bearer {viewer_token}",
            "Content-Type": "application/json"
        }


# ======================== MEMORY TESTS ========================

class TestMemoryEndpoints(TestMemoryPipelineAuth):
    """Test Agent Memory API endpoints"""
    
    def test_get_memory_stats(self, admin_headers):
        """GET /api/ai/memory/stats - returns memory statistics"""
        response = requests.get(f"{BASE_URL}/api/ai/memory/stats", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "total_memories" in data, "Missing 'total_memories' field"
        assert "unique_patterns" in data, "Missing 'unique_patterns' field"
        assert "by_agent" in data, "Missing 'by_agent' field"
        
        # Verify data types
        assert isinstance(data["total_memories"], int), "total_memories should be int"
        assert isinstance(data["unique_patterns"], int), "unique_patterns should be int"
        assert isinstance(data["by_agent"], dict), "by_agent should be dict"
        
        # Verify by_agent has expected agent keys
        by_agent = data["by_agent"]
        expected_agents = ["rca", "summarizer", "healer"]
        for agent in expected_agents:
            assert agent in by_agent, f"Missing agent '{agent}' in by_agent"
            assert isinstance(by_agent[agent], int), f"by_agent[{agent}] should be int"
        
        print(f"✓ GET /api/ai/memory/stats: total={data['total_memories']}, unique={data['unique_patterns']}, by_agent={by_agent}")
    
    def test_memory_search_with_data(self, admin_headers):
        """POST /api/ai/memory/search - searches past incidents by similarity"""
        response = requests.post(
            f"{BASE_URL}/api/ai/memory/search",
            headers=admin_headers,
            json={
                "data": SAMPLE_MEMORY_SEARCH_DATA,
                "limit": 5
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list), "Memory search should return a list"
        
        # If there are results, verify structure
        if len(data) > 0:
            result = data[0]
            assert "similarity" in result, "Result missing 'similarity'"
            assert "agent_id" in result, "Result missing 'agent_id'"
            assert "agent_name" in result, "Result missing 'agent_name'"
            assert "input_summary" in result, "Result missing 'input_summary'"
            assert "analysis_summary" in result, "Result missing 'analysis_summary'"
            assert "timestamp" in result, "Result missing 'timestamp'"
            
            # Verify similarity is a percentage (0-100)
            assert 0 <= result["similarity"] <= 100, f"Invalid similarity: {result['similarity']}"
            
            print(f"✓ POST /api/ai/memory/search: {len(data)} results, top similarity: {result['similarity']}%")
        else:
            print(f"✓ POST /api/ai/memory/search: 0 results (no similar incidents found)")
    
    def test_memory_search_with_agent_filter(self, admin_headers):
        """POST /api/ai/memory/search - filter by agent_id"""
        response = requests.post(
            f"{BASE_URL}/api/ai/memory/search",
            headers=admin_headers,
            json={
                "data": SAMPLE_MEMORY_SEARCH_DATA,
                "agent_id": "rca",
                "limit": 3
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        # All results should be from RCA agent
        for result in data:
            assert result.get("agent_id") == "rca", f"Expected rca agent, got: {result.get('agent_id')}"
        
        print(f"✓ POST /api/ai/memory/search (agent_id=rca): {len(data)} results")
    
    def test_memory_search_empty_query(self, admin_headers):
        """POST /api/ai/memory/search - with minimal data"""
        response = requests.post(
            f"{BASE_URL}/api/ai/memory/search",
            headers=admin_headers,
            json={
                "data": {"description": "test"},
                "limit": 3
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ POST /api/ai/memory/search (minimal data): {len(data)} results")
    
    def test_memory_stats_requires_auth(self):
        """GET /api/ai/memory/stats without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/ai/memory/stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/ai/memory/stats requires authentication")
    
    def test_memory_search_requires_auth(self):
        """POST /api/ai/memory/search without auth should fail"""
        response = requests.post(
            f"{BASE_URL}/api/ai/memory/search",
            json={"data": SAMPLE_MEMORY_SEARCH_DATA}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/ai/memory/search requires authentication")


class TestMemoryClear(TestMemoryPipelineAuth):
    """Test memory clear endpoint (admin only)"""
    
    def test_memory_clear_requires_admin(self, viewer_headers):
        """DELETE /api/ai/memory/clear - requires admin role"""
        response = requests.delete(
            f"{BASE_URL}/api/ai/memory/clear",
            headers=viewer_headers
        )
        # Should fail for non-admin
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        print("✓ DELETE /api/ai/memory/clear requires admin role")
    
    def test_memory_clear_requires_auth(self):
        """DELETE /api/ai/memory/clear without auth should fail"""
        response = requests.delete(f"{BASE_URL}/api/ai/memory/clear")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ DELETE /api/ai/memory/clear requires authentication")


# ======================== PIPELINE TESTS ========================

class TestPipelineEndpoints(TestMemoryPipelineAuth):
    """Test Auto-Trigger Pipeline API endpoints"""
    
    def test_get_pipeline_config(self, admin_headers):
        """GET /api/ai/pipeline/config - returns pipeline configuration"""
        response = requests.get(f"{BASE_URL}/api/ai/pipeline/config", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "enabled" in data, "Missing 'enabled' field"
        assert "description" in data, "Missing 'description' field"
        assert "cooldown_seconds" in data, "Missing 'cooldown_seconds' field"
        assert "agents" in data, "Missing 'agents' field"
        
        # Verify data types
        assert isinstance(data["enabled"], bool), "enabled should be bool"
        assert isinstance(data["description"], str), "description should be str"
        assert isinstance(data["cooldown_seconds"], int), "cooldown_seconds should be int"
        assert isinstance(data["agents"], list), "agents should be list"
        
        print(f"✓ GET /api/ai/pipeline/config: enabled={data['enabled']}, agents={data['agents']}")
    
    def test_get_pipeline_stats(self, admin_headers):
        """GET /api/ai/pipeline/stats - returns pipeline statistics"""
        response = requests.get(f"{BASE_URL}/api/ai/pipeline/stats", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "total_triggers" in data, "Missing 'total_triggers' field"
        assert "triggers_24h" in data, "Missing 'triggers_24h' field"
        assert "by_rule" in data, "Missing 'by_rule' field"
        
        # Verify data types
        assert isinstance(data["total_triggers"], int), "total_triggers should be int"
        assert isinstance(data["triggers_24h"], int), "triggers_24h should be int"
        assert isinstance(data["by_rule"], list), "by_rule should be list"
        
        # Verify by_rule structure if not empty
        for rule in data["by_rule"]:
            assert "rule_id" in rule, "by_rule item missing 'rule_id'"
            assert "count" in rule, "by_rule item missing 'count'"
        
        print(f"✓ GET /api/ai/pipeline/stats: total={data['total_triggers']}, 24h={data['triggers_24h']}, rules={len(data['by_rule'])}")
    
    def test_get_pipeline_events(self, admin_headers):
        """GET /api/ai/pipeline/events - returns trigger event history"""
        response = requests.get(
            f"{BASE_URL}/api/ai/pipeline/events?limit=20",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list), "Pipeline events should return a list"
        
        # If there are events, verify structure
        if len(data) > 0:
            event = data[0]
            assert "rule_id" in event, "Event missing 'rule_id'"
            assert "rule_name" in event, "Event missing 'rule_name'"
            assert "severity" in event, "Event missing 'severity'"
            assert "timestamp" in event, "Event missing 'timestamp'"
            assert "crew_result" in event, "Event missing 'crew_result'"
            
            # Verify crew_result structure
            crew_result = event.get("crew_result", {})
            assert "crew_id" in crew_result, "crew_result missing 'crew_id'"
            assert "agents_run" in crew_result, "crew_result missing 'agents_run'"
            
            print(f"✓ GET /api/ai/pipeline/events: {len(data)} events, latest rule: {event['rule_name']}")
        else:
            print(f"✓ GET /api/ai/pipeline/events: 0 events")
    
    def test_pipeline_config_requires_auth(self):
        """GET /api/ai/pipeline/config without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/ai/pipeline/config")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/ai/pipeline/config requires authentication")
    
    def test_pipeline_stats_requires_auth(self):
        """GET /api/ai/pipeline/stats without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/ai/pipeline/stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/ai/pipeline/stats requires authentication")
    
    def test_pipeline_events_requires_auth(self):
        """GET /api/ai/pipeline/events without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/ai/pipeline/events")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/ai/pipeline/events requires authentication")


class TestPipelineToggle(TestMemoryPipelineAuth):
    """Test pipeline toggle endpoint (admin only)"""
    
    def test_pipeline_toggle_requires_admin(self, viewer_headers):
        """POST /api/ai/pipeline/toggle - requires admin role"""
        response = requests.post(
            f"{BASE_URL}/api/ai/pipeline/toggle",
            headers=viewer_headers,
            json={"enabled": True}
        )
        # Should fail for non-admin
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        print("✓ POST /api/ai/pipeline/toggle requires admin role")
    
    def test_pipeline_toggle_requires_auth(self):
        """POST /api/ai/pipeline/toggle without auth should fail"""
        response = requests.post(
            f"{BASE_URL}/api/ai/pipeline/toggle",
            json={"enabled": True}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/ai/pipeline/toggle requires authentication")
    
    def test_pipeline_toggle_enable_disable(self, admin_headers):
        """POST /api/ai/pipeline/toggle - admin can toggle pipeline"""
        # Get current state
        config_response = requests.get(f"{BASE_URL}/api/ai/pipeline/config", headers=admin_headers)
        assert config_response.status_code == 200
        current_state = config_response.json().get("enabled", True)
        
        # Toggle to opposite state
        new_state = not current_state
        toggle_response = requests.post(
            f"{BASE_URL}/api/ai/pipeline/toggle",
            headers=admin_headers,
            json={"enabled": new_state}
        )
        assert toggle_response.status_code == 200, f"Toggle failed: {toggle_response.text}"
        
        data = toggle_response.json()
        assert data.get("enabled") == new_state, f"Expected enabled={new_state}, got {data.get('enabled')}"
        
        # Verify state changed
        verify_response = requests.get(f"{BASE_URL}/api/ai/pipeline/config", headers=admin_headers)
        assert verify_response.status_code == 200
        assert verify_response.json().get("enabled") == new_state
        
        # Toggle back to original state
        restore_response = requests.post(
            f"{BASE_URL}/api/ai/pipeline/toggle",
            headers=admin_headers,
            json={"enabled": current_state}
        )
        assert restore_response.status_code == 200
        
        print(f"✓ POST /api/ai/pipeline/toggle: toggled {current_state} -> {new_state} -> {current_state}")


class TestPipelineSimulate(TestMemoryPipelineAuth):
    """Test pipeline simulate endpoint (admin only, takes 5-10s due to LLM calls)"""
    
    def test_pipeline_simulate_requires_admin(self, viewer_headers):
        """POST /api/ai/pipeline/simulate - requires admin role"""
        response = requests.post(
            f"{BASE_URL}/api/ai/pipeline/simulate",
            headers=viewer_headers,
            json={
                "rule_id": "test_rule",
                "rule_name": "Test Rule",
                "severity": "warning"
            }
        )
        # Should fail for non-admin
        assert response.status_code in [401, 403], f"Expected 401/403 for viewer, got {response.status_code}"
        print("✓ POST /api/ai/pipeline/simulate requires admin role")
    
    def test_pipeline_simulate_requires_auth(self):
        """POST /api/ai/pipeline/simulate without auth should fail"""
        response = requests.post(
            f"{BASE_URL}/api/ai/pipeline/simulate",
            json={
                "rule_id": "test_rule",
                "rule_name": "Test Rule",
                "severity": "warning"
            }
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/ai/pipeline/simulate requires authentication")
    
    def test_pipeline_simulate_trigger(self, admin_headers):
        """POST /api/ai/pipeline/simulate - triggers AI agents (5-10s)"""
        # Ensure pipeline is enabled first
        requests.post(
            f"{BASE_URL}/api/ai/pipeline/toggle",
            headers=admin_headers,
            json={"enabled": True}
        )
        
        # Get initial event count
        initial_events = requests.get(
            f"{BASE_URL}/api/ai/pipeline/events?limit=50",
            headers=admin_headers
        ).json()
        initial_count = len(initial_events)
        
        # Simulate trigger (takes 5-10s due to real LLM calls)
        response = requests.post(
            f"{BASE_URL}/api/ai/pipeline/simulate",
            headers=admin_headers,
            json={
                "rule_id": "sim_test_iter42",
                "rule_name": "Iteration 42 Test Rule",
                "severity": "warning",
                "metric": "cpu_usage",
                "threshold": 90,
                "event_data": {
                    "server": "test-server-iter42",
                    "value": 95,
                    "description": "Simulated high CPU for iteration 42 pipeline test"
                }
            },
            timeout=60  # Long timeout for LLM calls
        )
        assert response.status_code == 200, f"Simulate failed: {response.text}"
        
        data = response.json()
        
        # Check if pipeline was skipped (disabled or cooldown)
        if data.get("status") == "skipped":
            print(f"✓ POST /api/ai/pipeline/simulate: skipped - {data.get('reason')}")
            return
        
        # Verify crew result structure
        assert "crew_id" in data, "Missing 'crew_id' in simulate response"
        assert "agents_run" in data, "Missing 'agents_run' in simulate response"
        assert "results" in data, "Missing 'results' in simulate response"
        assert "total_duration_ms" in data, "Missing 'total_duration_ms' in simulate response"
        
        # Verify agents ran (should be rca and summarizer)
        agents_run = data.get("agents_run", [])
        assert "rca" in agents_run, "RCA agent should have run"
        assert "summarizer" in agents_run, "Summarizer agent should have run"
        
        # Verify results
        results = data.get("results", [])
        assert len(results) >= 2, f"Expected at least 2 results, got {len(results)}"
        
        for result in results:
            assert "agent_id" in result, "Result missing 'agent_id'"
            assert "analysis" in result, "Result missing 'analysis'"
            assert len(result.get("analysis", "")) > 30, "Analysis too short"
        
        # Verify event was stored
        time.sleep(1)  # Brief wait for DB write
        final_events = requests.get(
            f"{BASE_URL}/api/ai/pipeline/events?limit=50",
            headers=admin_headers
        ).json()
        
        # Should have at least one more event
        assert len(final_events) > initial_count, "No new pipeline event created"
        
        # Verify latest event matches our simulation
        latest_event = final_events[0]
        assert latest_event.get("rule_id") == "sim_test_iter42", f"Wrong rule_id: {latest_event.get('rule_id')}"
        assert latest_event.get("rule_name") == "Iteration 42 Test Rule"
        
        print(f"✓ POST /api/ai/pipeline/simulate: {len(results)} agents ran, {data.get('total_duration_ms')}ms, event stored")


# ======================== INTEGRATION TESTS ========================

class TestMemoryIntegration(TestMemoryPipelineAuth):
    """Test memory integration with agent execution"""
    
    def test_agent_response_includes_memory_used(self, admin_headers):
        """Verify agent responses include memory_used field"""
        response = requests.post(
            f"{BASE_URL}/api/ai/agent/rca",
            headers=admin_headers,
            json={"data": SAMPLE_ALERT_DATA},
            timeout=30
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify memory_used field exists
        assert "memory_used" in data, "Agent response missing 'memory_used' field"
        assert isinstance(data["memory_used"], int), "memory_used should be int"
        assert data["memory_used"] >= 0, "memory_used should be non-negative"
        
        print(f"✓ Agent response includes memory_used: {data['memory_used']}")
    
    def test_memory_accumulates_after_analysis(self, admin_headers):
        """Verify memory stats increase after running analysis"""
        # Get initial memory stats
        initial_stats = requests.get(
            f"{BASE_URL}/api/ai/memory/stats",
            headers=admin_headers
        ).json()
        initial_total = initial_stats.get("total_memories", 0)
        
        # Run a single agent analysis
        requests.post(
            f"{BASE_URL}/api/ai/agent/summarizer",
            headers=admin_headers,
            json={"data": {"alert": "Memory test alert", "server": "test-server"}},
            timeout=30
        )
        
        # Get updated memory stats
        time.sleep(1)  # Brief wait for DB write
        updated_stats = requests.get(
            f"{BASE_URL}/api/ai/memory/stats",
            headers=admin_headers
        ).json()
        updated_total = updated_stats.get("total_memories", 0)
        
        # Memory should have increased
        assert updated_total > initial_total, f"Memory did not increase: {initial_total} -> {updated_total}"
        
        print(f"✓ Memory accumulates after analysis: {initial_total} -> {updated_total}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
