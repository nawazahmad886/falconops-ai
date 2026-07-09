"""
Iteration 41 - AI Agents Multi-Agent System Tests
Tests: RCA Agent, Alert Summarizer, Auto-Healing Agent
LLM Modes: Emergent Key (cloud), OpenAI Key (on-premise), Heuristic fallback
Endpoints: /api/ai/agents, /api/ai/agent/{id}, /api/ai/analyze, /api/ai/history, /api/ai/stats
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"

# Sample alert data for testing
SAMPLE_ALERT_DATA = {
    "alert": "High CPU on prod-web-01",
    "value": 95,
    "threshold": 85,
    "duration": "10min"
}


class TestAIAgentsAuth:
    """Authentication for AI Agents tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestAIAgentsEndpoints(TestAIAgentsAuth):
    """Test AI Agents API endpoints"""
    
    def test_get_agents_list(self, auth_headers):
        """GET /api/ai/agents - returns 3 agents and llm_mode"""
        response = requests.get(f"{BASE_URL}/api/ai/agents", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify agents list
        assert "agents" in data, "Missing 'agents' field"
        agents = data["agents"]
        assert len(agents) == 3, f"Expected 3 agents, got {len(agents)}"
        
        # Verify agent IDs
        agent_ids = [a["id"] for a in agents]
        assert "rca" in agent_ids, "Missing RCA agent"
        assert "summarizer" in agent_ids, "Missing Summarizer agent"
        assert "healer" in agent_ids, "Missing Healer agent"
        
        # Verify each agent has required fields
        for agent in agents:
            assert "id" in agent, "Agent missing 'id'"
            assert "name" in agent, "Agent missing 'name'"
            assert "role" in agent, "Agent missing 'role'"
        
        # Verify llm_mode
        assert "llm_mode" in data, "Missing 'llm_mode' field"
        llm_mode = data["llm_mode"]
        assert "mode" in llm_mode, "llm_mode missing 'mode'"
        assert llm_mode["mode"] in ["emergent", "openai", "fallback"], f"Invalid mode: {llm_mode['mode']}"
        
        print(f"✓ GET /api/ai/agents: 3 agents found, LLM mode: {llm_mode['mode']}")
    
    def test_llm_mode_is_emergent(self, auth_headers):
        """Verify LLM mode is 'emergent' (EMERGENT_LLM_KEY is set)"""
        response = requests.get(f"{BASE_URL}/api/ai/agents", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        llm_mode = data.get("llm_mode", {})
        
        # Should be emergent since EMERGENT_LLM_KEY is configured
        assert llm_mode.get("mode") == "emergent", f"Expected 'emergent' mode, got: {llm_mode.get('mode')}"
        print(f"✓ LLM mode is 'emergent' as expected")
    
    def test_run_single_rca_agent(self, auth_headers):
        """POST /api/ai/agent/rca - runs RCA agent with real LLM"""
        response = requests.post(
            f"{BASE_URL}/api/ai/agent/rca",
            headers=auth_headers,
            json={"data": SAMPLE_ALERT_DATA},
            timeout=30  # LLM calls can take 2-5 seconds
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert data.get("agent_id") == "rca", f"Wrong agent_id: {data.get('agent_id')}"
        assert "agent_name" in data, "Missing agent_name"
        assert "analysis" in data, "Missing analysis"
        assert "llm_mode" in data, "Missing llm_mode"
        assert "duration_ms" in data, "Missing duration_ms"
        assert "timestamp" in data, "Missing timestamp"
        
        # Verify analysis is real AI text (not heuristic)
        analysis = data.get("analysis", "")
        assert len(analysis) > 50, f"Analysis too short: {len(analysis)} chars"
        
        # Heuristic fallback starts with "Heuristic RCA:"
        is_heuristic = analysis.startswith("Heuristic")
        if data.get("llm_mode") == "emergent":
            assert not is_heuristic, "Got heuristic response when emergent mode expected"
        
        print(f"✓ RCA Agent: {len(analysis)} chars, {data.get('duration_ms')}ms, mode: {data.get('llm_mode')}")
    
    def test_run_single_summarizer_agent(self, auth_headers):
        """POST /api/ai/agent/summarizer - runs Alert Summarizer agent"""
        response = requests.post(
            f"{BASE_URL}/api/ai/agent/summarizer",
            headers=auth_headers,
            json={"data": SAMPLE_ALERT_DATA},
            timeout=30
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data.get("agent_id") == "summarizer"
        assert "analysis" in data
        assert len(data.get("analysis", "")) > 30
        
        print(f"✓ Summarizer Agent: {len(data.get('analysis', ''))} chars, {data.get('duration_ms')}ms")
    
    def test_run_single_healer_agent(self, auth_headers):
        """POST /api/ai/agent/healer - runs Auto-Healing agent"""
        response = requests.post(
            f"{BASE_URL}/api/ai/agent/healer",
            headers=auth_headers,
            json={"data": SAMPLE_ALERT_DATA},
            timeout=30
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data.get("agent_id") == "healer"
        assert "analysis" in data
        assert len(data.get("analysis", "")) > 30
        
        print(f"✓ Healer Agent: {len(data.get('analysis', ''))} chars, {data.get('duration_ms')}ms")
    
    def test_run_invalid_agent(self, auth_headers):
        """POST /api/ai/agent/invalid - should return error"""
        response = requests.post(
            f"{BASE_URL}/api/ai/agent/invalid_agent",
            headers=auth_headers,
            json={"data": SAMPLE_ALERT_DATA},
            timeout=10
        )
        # Should return 200 with error in response or 404
        data = response.json()
        if response.status_code == 200:
            assert "error" in data, "Expected error for invalid agent"
        print(f"✓ Invalid agent handled correctly")
    
    def test_run_crew_sequential(self, auth_headers):
        """POST /api/ai/analyze - runs all 3 agents sequentially"""
        response = requests.post(
            f"{BASE_URL}/api/ai/analyze",
            headers=auth_headers,
            json={
                "data": SAMPLE_ALERT_DATA,
                "agents": ["rca", "summarizer", "healer"],
                "parallel": False
            },
            timeout=60  # Sequential crew can take 10-15 seconds
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify crew response structure
        assert "crew_id" in data, "Missing crew_id"
        assert "agents_run" in data, "Missing agents_run"
        assert "results" in data, "Missing results"
        assert "total_duration_ms" in data, "Missing total_duration_ms"
        assert "llm_mode" in data, "Missing llm_mode"
        
        # Verify all 3 agents ran
        results = data.get("results", [])
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        
        result_agent_ids = [r.get("agent_id") for r in results]
        assert "rca" in result_agent_ids
        assert "summarizer" in result_agent_ids
        assert "healer" in result_agent_ids
        
        # Verify each result has analysis
        for result in results:
            assert "analysis" in result, f"Result missing analysis: {result}"
            assert len(result.get("analysis", "")) > 30
        
        print(f"✓ Crew (sequential): 3 agents, {data.get('total_duration_ms')}ms total")
    
    def test_run_crew_parallel(self, auth_headers):
        """POST /api/ai/analyze - runs agents in parallel mode"""
        response = requests.post(
            f"{BASE_URL}/api/ai/analyze",
            headers=auth_headers,
            json={
                "data": SAMPLE_ALERT_DATA,
                "agents": ["rca", "summarizer"],
                "parallel": True
            },
            timeout=30
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert len(data.get("results", [])) == 2
        
        print(f"✓ Crew (parallel): 2 agents, {data.get('total_duration_ms')}ms total")
    
    def test_get_analysis_history(self, auth_headers):
        """GET /api/ai/history - returns past analyses"""
        response = requests.get(
            f"{BASE_URL}/api/ai/history?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "History should be a list"
        
        # Should have at least some history from previous tests
        if len(data) > 0:
            item = data[0]
            assert "agent_id" in item, "History item missing agent_id"
            assert "analysis" in item, "History item missing analysis"
            assert "timestamp" in item, "History item missing timestamp"
        
        print(f"✓ GET /api/ai/history: {len(data)} items")
    
    def test_get_agent_stats(self, auth_headers):
        """GET /api/ai/stats - returns total analyses and per-agent counts"""
        response = requests.get(f"{BASE_URL}/api/ai/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify stats structure
        assert "total_analyses" in data, "Missing total_analyses"
        assert "by_agent" in data, "Missing by_agent"
        assert "llm_mode" in data, "Missing llm_mode"
        assert "available_agents" in data, "Missing available_agents"
        
        # Verify by_agent breakdown
        by_agent = data.get("by_agent", [])
        assert len(by_agent) == 3, f"Expected 3 agent stats, got {len(by_agent)}"
        
        for agent_stat in by_agent:
            assert "agent_id" in agent_stat
            assert "name" in agent_stat
            assert "count" in agent_stat
            assert isinstance(agent_stat["count"], int)
        
        # Verify available_agents
        available = data.get("available_agents", [])
        assert len(available) == 3
        
        print(f"✓ GET /api/ai/stats: total={data.get('total_analyses')}, by_agent={by_agent}")


class TestAIAgentsUnauthorized:
    """Test AI Agents endpoints without auth"""
    
    def test_agents_requires_auth(self):
        """GET /api/ai/agents without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/ai/agents")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/ai/agents requires authentication")
    
    def test_analyze_requires_auth(self):
        """POST /api/ai/analyze without auth should fail"""
        response = requests.post(
            f"{BASE_URL}/api/ai/analyze",
            json={"data": SAMPLE_ALERT_DATA}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /api/ai/analyze requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
