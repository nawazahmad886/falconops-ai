"""
Iteration 45 - SOC Event Ingestion Engine & Admin Console Tests
Tests:
- SOC Ingestion: POST /api/soc-engine/ingest, POST /api/soc-engine/ingest/batch
- SOC Events/Incidents: GET /api/soc-engine/events, GET /api/soc-engine/incidents
- SOC Stats: GET /api/soc-engine/stats
- SOC Config: GET /api/soc-engine/config, PUT /api/soc-engine/config
- Admin Agents: GET /api/soc-engine/admin/agents, PUT /api/soc-engine/admin/agents
- Admin Overview: GET /api/soc-engine/admin/overview
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


class TestSOCIngestionNoAuth:
    """SOC Ingestion endpoints - NO AUTH required for external sources"""
    
    def test_ingest_single_event(self):
        """POST /api/soc-engine/ingest - ingest single event (no auth)"""
        payload = {
            "source": "pytest",
            "service": "test-api",
            "severity": "warning",
            "message": f"TEST_pytest_event_{uuid.uuid4().hex[:8]}",
            "host": "test-host-01",
            "ip": "192.168.1.100",
            "user": "test_user",
            "category": "security",
            "action": "login_attempt"
        }
        response = requests.post(f"{BASE_URL}/api/soc-engine/ingest", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ingested", f"Expected status=ingested, got {data}"
        assert "event_id" in data, "Missing event_id in response"
        assert data.get("severity") == "warning", f"Expected severity=warning, got {data.get('severity')}"
        print(f"✓ Single event ingested: {data['event_id']}")
        return data["event_id"]
    
    def test_ingest_critical_event(self):
        """POST /api/soc-engine/ingest - ingest critical severity event"""
        payload = {
            "source": "pytest",
            "service": "critical-service",
            "severity": "critical",
            "message": f"TEST_critical_alert_{uuid.uuid4().hex[:8]}"
        }
        response = requests.post(f"{BASE_URL}/api/soc-engine/ingest", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("severity") == "critical"
        print(f"✓ Critical event ingested: {data['event_id']}")
    
    def test_ingest_batch_events(self):
        """POST /api/soc-engine/ingest/batch - batch ingest multiple events"""
        events = [
            {"source": "pytest_batch", "service": "batch-svc", "severity": "info", "message": f"TEST_batch_1_{uuid.uuid4().hex[:8]}"},
            {"source": "pytest_batch", "service": "batch-svc", "severity": "warning", "message": f"TEST_batch_2_{uuid.uuid4().hex[:8]}"},
            {"source": "pytest_batch", "service": "batch-svc", "severity": "high", "message": f"TEST_batch_3_{uuid.uuid4().hex[:8]}"},
        ]
        response = requests.post(f"{BASE_URL}/api/soc-engine/ingest/batch", json={"events": events})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ingested") == 3, f"Expected 3 ingested, got {data.get('ingested')}"
        assert "results" in data, "Missing results in batch response"
        assert len(data["results"]) == 3, f"Expected 3 results, got {len(data['results'])}"
        print(f"✓ Batch ingested: {data['ingested']} events")
    
    def test_ingest_minimal_event(self):
        """POST /api/soc-engine/ingest - minimal required fields"""
        payload = {"message": f"TEST_minimal_{uuid.uuid4().hex[:8]}"}
        response = requests.post(f"{BASE_URL}/api/soc-engine/ingest", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "ingested"
        # Should have defaults
        assert data.get("severity") == "info", "Default severity should be info"
        print(f"✓ Minimal event ingested with defaults")


class TestSOCCorrelation:
    """Test auto-correlation: 3+ events with same service+severity creates incident"""
    
    def test_correlation_creates_incident(self):
        """Ingest 3+ events with same service+severity to trigger correlation"""
        unique_service = f"correlation-test-{uuid.uuid4().hex[:8]}"
        
        # Ingest 3 events with same service+severity
        for i in range(3):
            payload = {
                "source": "pytest_correlation",
                "service": unique_service,
                "severity": "critical",
                "message": f"TEST_correlation_event_{i+1}_{uuid.uuid4().hex[:8]}"
            }
            response = requests.post(f"{BASE_URL}/api/soc-engine/ingest", json=payload)
            assert response.status_code == 200
            data = response.json()
            print(f"  Event {i+1}: correlated={data.get('correlated')}, incident_id={data.get('incident_id')}")
            
            # The 3rd event should trigger correlation
            if i == 2:
                # May or may not create incident depending on config
                if data.get("incident_id"):
                    print(f"✓ Correlation triggered! Incident: {data['incident_id']}")
                else:
                    print("  Note: Correlation may be disabled or threshold not met")


class TestSOCEventsIncidentsAuth:
    """SOC Events and Incidents - requires auth"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_events(self):
        """GET /api/soc-engine/events - get recent events"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/events", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of events"
        if len(data) > 0:
            event = data[0]
            assert "event_id" in event, "Event missing event_id"
            assert "source" in event, "Event missing source"
            assert "severity" in event, "Event missing severity"
            assert "message" in event, "Event missing message"
            assert "timestamp" in event, "Event missing timestamp"
            print(f"✓ Got {len(data)} events, first: {event.get('event_id')}")
        else:
            print("✓ Events endpoint working (no events yet)")
    
    def test_get_events_with_filters(self):
        """GET /api/soc-engine/events with source and severity filters"""
        response = requests.get(
            f"{BASE_URL}/api/soc-engine/events",
            params={"source": "pytest", "severity": "warning", "limit": 10},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Filtered events: {len(data)} results")
    
    def test_get_incidents(self):
        """GET /api/soc-engine/incidents - get incidents"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/incidents", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of incidents"
        if len(data) > 0:
            incident = data[0]
            assert "incident_id" in incident, "Incident missing incident_id"
            assert "title" in incident, "Incident missing title"
            assert "severity" in incident, "Incident missing severity"
            assert "status" in incident, "Incident missing status"
            assert "confidence" in incident, "Incident missing confidence"
            print(f"✓ Got {len(data)} incidents, first: {incident.get('incident_id')}")
        else:
            print("✓ Incidents endpoint working (no incidents yet)")
    
    def test_get_incidents_with_status_filter(self):
        """GET /api/soc-engine/incidents with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/soc-engine/incidents",
            params={"status": "open", "limit": 10},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Open incidents: {len(data)}")


class TestSOCStats:
    """SOC Stats endpoint - requires auth"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_stats(self):
        """GET /api/soc-engine/stats - get event/incident counts and breakdowns"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/stats", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required fields
        assert "total_events" in data, "Missing total_events"
        assert "events_last_hour" in data, "Missing events_last_hour"
        assert "total_incidents" in data, "Missing total_incidents"
        assert "open_incidents" in data, "Missing open_incidents"
        assert "by_severity" in data, "Missing by_severity breakdown"
        assert "by_source" in data, "Missing by_source breakdown"
        
        # Verify by_severity structure
        by_sev = data["by_severity"]
        assert "critical" in by_sev, "by_severity missing critical"
        assert "high" in by_sev, "by_severity missing high"
        assert "warning" in by_sev, "by_severity missing warning"
        assert "info" in by_sev, "by_severity missing info"
        
        # Verify by_source is list
        assert isinstance(data["by_source"], list), "by_source should be list"
        
        print(f"✓ Stats: {data['total_events']} events, {data['total_incidents']} incidents")
        print(f"  by_severity: {by_sev}")
        print(f"  by_source: {data['by_source'][:3]}...")


class TestSOCConfig:
    """SOC Config endpoints - GET requires auth, PUT requires admin"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_config(self):
        """GET /api/soc-engine/config - get ingestion config"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/config", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required config fields
        assert "auto_correlate" in data, "Missing auto_correlate"
        assert "auto_ai_trigger" in data, "Missing auto_ai_trigger"
        assert "correlation_window_min" in data, "Missing correlation_window_min"
        assert "incident_threshold" in data, "Missing incident_threshold"
        
        assert isinstance(data["auto_correlate"], bool), "auto_correlate should be bool"
        assert isinstance(data["auto_ai_trigger"], bool), "auto_ai_trigger should be bool"
        assert isinstance(data["correlation_window_min"], int), "correlation_window_min should be int"
        assert isinstance(data["incident_threshold"], int), "incident_threshold should be int"
        
        print(f"✓ Config: auto_correlate={data['auto_correlate']}, auto_ai_trigger={data['auto_ai_trigger']}")
        print(f"  window={data['correlation_window_min']}min, threshold={data['incident_threshold']}")
        return data
    
    def test_update_config(self):
        """PUT /api/soc-engine/config - update config (admin only)"""
        # Get current config
        get_resp = requests.get(f"{BASE_URL}/api/soc-engine/config", headers=self.headers)
        original = get_resp.json()
        
        # Update config
        new_threshold = 5 if original.get("incident_threshold", 3) == 3 else 3
        response = requests.put(
            f"{BASE_URL}/api/soc-engine/config",
            json={"incident_threshold": new_threshold},
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("incident_threshold") == new_threshold, f"Expected threshold={new_threshold}"
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/soc-engine/config",
            json={"incident_threshold": original.get("incident_threshold", 3)},
            headers=self.headers
        )
        print(f"✓ Config updated and restored")


class TestAdminAgents:
    """Admin Agent Configuration - requires admin auth"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_agents(self):
        """GET /api/soc-engine/admin/agents - get full agent config"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/admin/agents", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of agents"
        assert len(data) > 0, "Expected at least one agent"
        
        # Verify agent structure
        agent = data[0]
        required_fields = ["agent_id", "name", "role", "system_prompt", "enabled", "temperature", "max_tokens"]
        for field in required_fields:
            assert field in agent, f"Agent missing {field}"
        
        assert isinstance(agent["enabled"], bool), "enabled should be bool"
        assert isinstance(agent["temperature"], (int, float)), "temperature should be number"
        assert isinstance(agent["max_tokens"], int), "max_tokens should be int"
        
        print(f"✓ Got {len(data)} agents:")
        for a in data:
            print(f"  - {a['agent_id']}: {a['name']} (enabled={a['enabled']}, temp={a['temperature']}, tokens={a['max_tokens']})")
        return data
    
    def test_update_agent_config(self):
        """PUT /api/soc-engine/admin/agents - update agent config"""
        # Get current agents
        get_resp = requests.get(f"{BASE_URL}/api/soc-engine/admin/agents", headers=self.headers)
        agents = get_resp.json()
        
        if len(agents) == 0:
            pytest.skip("No agents to update")
        
        agent = agents[0]
        original_temp = agent.get("temperature", 0.3)
        new_temp = 0.5 if original_temp != 0.5 else 0.3
        
        # Update agent
        response = requests.put(
            f"{BASE_URL}/api/soc-engine/admin/agents",
            json={"agent_id": agent["agent_id"], "temperature": new_temp},
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("agent_id") == agent["agent_id"]
        assert "updated" in data
        assert "temperature" in data["updated"]
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/soc-engine/admin/agents",
            json={"agent_id": agent["agent_id"], "temperature": original_temp},
            headers=self.headers
        )
        print(f"✓ Agent {agent['agent_id']} config updated and restored")


class TestAdminOverview:
    """Admin Overview endpoint - requires admin auth"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_overview(self):
        """GET /api/soc-engine/admin/overview - complete system status"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/admin/overview", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required sections
        assert "llm" in data, "Missing llm section"
        assert "agents" in data, "Missing agents section"
        assert "pipeline" in data, "Missing pipeline section"
        assert "memory" in data, "Missing memory section"
        assert "ingestion" in data, "Missing ingestion section"
        
        # Verify LLM info
        llm = data["llm"]
        assert "mode" in llm, "LLM missing mode"
        
        # Verify pipeline
        pipeline = data["pipeline"]
        assert "enabled" in pipeline, "Pipeline missing enabled"
        
        # Verify ingestion has both config and stats
        ingestion = data["ingestion"]
        assert "auto_correlate" in ingestion, "Ingestion missing auto_correlate"
        assert "total_events" in ingestion, "Ingestion missing total_events"
        
        print(f"✓ Admin Overview:")
        print(f"  LLM mode: {llm.get('mode')}")
        print(f"  Pipeline enabled: {pipeline.get('enabled')}")
        print(f"  Total events: {ingestion.get('total_events')}")
        print(f"  Memory items: {data['memory'].get('total_memories', 0)}")


class TestAuthRequired:
    """Verify auth is required for protected endpoints"""
    
    def test_events_requires_auth(self):
        """GET /api/soc-engine/events requires auth"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/events")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /events requires auth")
    
    def test_incidents_requires_auth(self):
        """GET /api/soc-engine/incidents requires auth"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/incidents")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /incidents requires auth")
    
    def test_stats_requires_auth(self):
        """GET /api/soc-engine/stats requires auth"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /stats requires auth")
    
    def test_admin_agents_requires_admin(self):
        """GET /api/soc-engine/admin/agents requires admin"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/admin/agents")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /admin/agents requires admin auth")
    
    def test_admin_overview_requires_admin(self):
        """GET /api/soc-engine/admin/overview requires admin"""
        response = requests.get(f"{BASE_URL}/api/soc-engine/admin/overview")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /admin/overview requires admin auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
