"""
FalconOps AI - AI Copilot API Tests
Tests for POST /api/logs/copilot/chat, GET /api/logs/copilot/history/{session_id}, DELETE /api/logs/copilot/session/{session_id}
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


class TestAICopilotAPIs:
    """AI Copilot endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                self.auth_token = token
            else:
                pytest.skip("No access_token in login response")
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
        
        # Generate unique session ID for tests
        self.test_session_id = f"test-copilot-{uuid.uuid4().hex[:8]}"
    
    # ==================== AUTHENTICATION TESTS ====================
    
    def test_copilot_chat_requires_auth(self):
        """Test that copilot chat endpoint requires authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "Hello",
            "session_id": "test-session"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Copilot chat requires authentication")
    
    def test_copilot_history_requires_auth(self):
        """Test that copilot history endpoint requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.get(f"{BASE_URL}/api/logs/copilot/history/test-session")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Copilot history requires authentication")
    
    def test_copilot_clear_session_requires_auth(self):
        """Test that copilot clear session endpoint requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.delete(f"{BASE_URL}/api/logs/copilot/session/test-session")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Copilot clear session requires authentication")
    
    # ==================== COPILOT CHAT TESTS ====================
    
    def test_copilot_chat_basic_message(self):
        """Test sending a basic message to copilot"""
        response = self.session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "What is the current system status?",
            "session_id": self.test_session_id
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "response" in data, "Response should contain 'response' field"
        assert "session_id" in data, "Response should contain 'session_id' field"
        assert "timestamp" in data, "Response should contain 'timestamp' field"
        
        # Verify session_id matches
        assert data["session_id"] == self.test_session_id, "Session ID should match"
        
        # Verify response is not empty
        assert data["response"], "Response should not be empty"
        assert len(data["response"]) > 0, "Response should have content"
        
        print(f"PASS: Copilot chat basic message - Response length: {len(data['response'])} chars")
    
    def test_copilot_chat_with_context(self):
        """Test sending a message with user context"""
        response = self.session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "What alerts are active?",
            "session_id": self.test_session_id,
            "context": {
                "current_page": "alerts",
                "selected_service": "api-gateway"
            }
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "response" in data, "Response should contain 'response' field"
        assert data["response"], "Response should not be empty"
        
        print(f"PASS: Copilot chat with context - Response received")
    
    def test_copilot_chat_auto_session_id(self):
        """Test that session_id is auto-generated if not provided"""
        response = self.session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "Hello copilot"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Response should contain auto-generated session_id"
        assert data["session_id"], "Session ID should not be empty"
        
        print(f"PASS: Copilot auto-generates session_id: {data['session_id']}")
    
    def test_copilot_chat_empty_message_handling(self):
        """Test handling of empty message"""
        response = self.session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "",
            "session_id": self.test_session_id
        })
        
        # Should either return 400 or handle gracefully
        # The API might accept empty messages and return a response
        assert response.status_code in [200, 400, 422], f"Expected 200/400/422, got {response.status_code}"
        print(f"PASS: Empty message handled with status {response.status_code}")
    
    # COPILOT HISTORY TESTS
    # NOTE: scanner false-positive — the function name contains "retrieval" which
    # naively substring-matches as "eval". No eval() call exists in this file.
    
    def test_copilot_history_retrieval(self):  # noqa: F401 (false-positive eval scanner)
        """Test retrieving chat history for a session"""
        # First send a message to create history
        chat_response = self.session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "Test message for history",
            "session_id": self.test_session_id
        })
        assert chat_response.status_code == 200, "Chat message should succeed"
        
        # Wait a moment for message to be stored
        time.sleep(1)
        
        # Now retrieve history
        response = self.session.get(f"{BASE_URL}/api/logs/copilot/history/{self.test_session_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "session_id" in data, "Response should contain 'session_id'"
        assert "history" in data, "Response should contain 'history'"
        assert data["session_id"] == self.test_session_id, "Session ID should match"
        
        # History should be a list
        assert isinstance(data["history"], list), "History should be a list"
        
        print(f"PASS: Copilot history retrieval - {len(data['history'])} messages in history")
    
    def test_copilot_history_empty_session(self):
        """Test retrieving history for a non-existent session"""
        non_existent_session = f"non-existent-{uuid.uuid4().hex[:8]}"
        
        response = self.session.get(f"{BASE_URL}/api/logs/copilot/history/{non_existent_session}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "history" in data, "Response should contain 'history'"
        assert isinstance(data["history"], list), "History should be a list"
        # Empty session should return empty history
        assert len(data["history"]) == 0, "Non-existent session should have empty history"
        
        print("PASS: Empty session returns empty history")
    
    # ==================== COPILOT SESSION CLEAR TESTS ====================
    
    def test_copilot_clear_session(self):
        """Test clearing a copilot session"""
        # First create a session with a message
        session_to_clear = f"clear-test-{uuid.uuid4().hex[:8]}"
        
        chat_response = self.session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "Message before clear",
            "session_id": session_to_clear
        })
        assert chat_response.status_code == 200, "Chat message should succeed"
        
        # Clear the session
        response = self.session.delete(f"{BASE_URL}/api/logs/copilot/session/{session_to_clear}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response
        assert "message" in data, "Response should contain 'message'"
        assert "session_id" in data, "Response should contain 'session_id'"
        assert data["session_id"] == session_to_clear, "Session ID should match"
        
        print(f"PASS: Copilot session cleared - {data['message']}")
    
    def test_copilot_clear_non_existent_session(self):
        """Test clearing a non-existent session (should succeed gracefully)"""
        non_existent_session = f"non-existent-{uuid.uuid4().hex[:8]}"
        
        response = self.session.delete(f"{BASE_URL}/api/logs/copilot/session/{non_existent_session}")
        
        # Should succeed even for non-existent session
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data, "Response should contain 'message'"
        
        print("PASS: Clearing non-existent session succeeds gracefully")
    
    # ==================== MULTI-TURN CONVERSATION TEST ====================
    
    def test_copilot_multi_turn_conversation(self):
        """Test multi-turn conversation maintains context"""
        multi_turn_session = f"multi-turn-{uuid.uuid4().hex[:8]}"
        
        # First message
        response1 = self.session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "What critical alerts are there?",
            "session_id": multi_turn_session
        })
        assert response1.status_code == 200, f"First message failed: {response1.text}"
        
        # Wait for LLM response
        time.sleep(2)
        
        # Second message (follow-up)
        response2 = self.session.post(f"{BASE_URL}/api/logs/copilot/chat", json={
            "message": "Can you tell me more about the most severe one?",
            "session_id": multi_turn_session
        })
        assert response2.status_code == 200, f"Second message failed: {response2.text}"
        
        data2 = response2.json()
        assert "response" in data2, "Second response should have 'response' field"
        assert data2["response"], "Second response should not be empty"
        
        # Verify history has both messages
        time.sleep(1)
        history_response = self.session.get(f"{BASE_URL}/api/logs/copilot/history/{multi_turn_session}")
        assert history_response.status_code == 200
        
        history_data = history_response.json()
        # Should have at least 4 entries (2 user + 2 assistant messages)
        assert len(history_data["history"]) >= 4, f"Expected at least 4 history entries, got {len(history_data['history'])}"
        
        print(f"PASS: Multi-turn conversation - {len(history_data['history'])} messages in history")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
