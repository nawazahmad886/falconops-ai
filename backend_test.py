#!/usr/bin/env python3
"""
FalconApps NOC Platform - Backend API Testing Suite
Tests all backend endpoints including auth, alerts, incidents, runbooks, and analytics
"""

import requests
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

class FalconAppsAPITester:
    def __init__(self, base_url: str = "https://health-rules-engine.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details
        })
    
    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                    expected_status: int = 200, auth_required: bool = True) -> tuple[bool, Dict]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/api{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if auth_required and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=30)
            else:
                return False, {"error": f"Unsupported method: {method}"}
            
            success = response.status_code == expected_status
            try:
                response_data = response.json()
            except:
                response_data = {"status_code": response.status_code, "text": response.text[:200]}
            
            return success, response_data
            
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}
    
    def test_health_check(self):
        """Test basic health endpoints"""
        print("\n🔍 Testing Health Endpoints...")
        
        # Test root endpoint
        success, data = self.make_request('GET', '/', auth_required=False)
        self.log_test("Root endpoint", success, 
                     f"Expected API info, got: {data.get('message', 'No message')}")
        
        # Test health endpoint
        success, data = self.make_request('GET', '/health', auth_required=False)
        self.log_test("Health check", success,
                     f"Expected healthy status, got: {data.get('status', 'No status')}")
    
    def test_authentication(self):
        """Test user registration and login"""
        print("\n🔍 Testing Authentication...")
        
        # Test registration with test user
        test_email = "admin@falconapps.com"
        test_password = "admin123"
        
        register_data = {
            "email": test_email,
            "password": test_password,
            "full_name": "Test Admin",
            "organization": "FalconApps Test"
        }
        
        # Try registration (might fail if user exists, that's ok)
        success, data = self.make_request('POST', '/auth/register', register_data, 
                                        expected_status=200, auth_required=False)
        if not success and "already registered" in str(data):
            print("ℹ️  User already exists, proceeding with login")
        else:
            self.log_test("User registration", success, str(data))
        
        # Test login
        login_data = {
            "email": test_email,
            "password": test_password
        }
        
        success, data = self.make_request('POST', '/auth/login', login_data,
                                        expected_status=200, auth_required=False)
        self.log_test("User login", success, str(data))
        
        if success and 'access_token' in data:
            self.token = data['access_token']
            self.user_id = data.get('user', {}).get('id')
            print(f"🔑 Authentication successful, token acquired")
        
        # Test /auth/me endpoint
        if self.token:
            success, data = self.make_request('GET', '/auth/me')
            self.log_test("Get current user", success, str(data))
    
    def test_alert_webhook(self):
        """Test alert webhook endpoint"""
        print("\n🔍 Testing Alert Webhook...")
        
        # Test webhook with sample alert
        alert_data = {
            "source": "Prometheus",
            "severity": "critical",
            "title": "High CPU Usage",
            "description": "CPU usage above 90% for 5 minutes",
            "service": "web-server",
            "host": "web-01.prod",
            "metric_name": "cpu_usage_percent",
            "metric_value": 95.5,
            "threshold": 90.0,
            "tags": {"environment": "production", "team": "platform"},
            "raw_payload": {"alertname": "HighCPU", "instance": "web-01:9100"}
        }
        
        success, data = self.make_request('POST', '/alerts/webhook', alert_data,
                                        expected_status=200, auth_required=False)
        self.log_test("Alert webhook - critical alert", success, str(data))
        
        # Test another alert for same service (should correlate)
        alert_data2 = {
            "source": "Prometheus", 
            "severity": "warning",
            "title": "High Memory Usage",
            "description": "Memory usage above 80%",
            "service": "web-server",
            "host": "web-01.prod"
        }
        
        success, data = self.make_request('POST', '/alerts/webhook', alert_data2,
                                        expected_status=200, auth_required=False)
        self.log_test("Alert webhook - correlated alert", success, str(data))
        
        # Store alert ID for later tests
        if success and 'id' in data:
            self.alert_id = data['id']
    
    def test_alerts_api(self):
        """Test alerts management endpoints"""
        print("\n🔍 Testing Alerts API...")
        
        if not self.token:
            print("❌ Skipping alerts API tests - no authentication token")
            return
        
        # Get all alerts
        success, data = self.make_request('GET', '/alerts')
        self.log_test("Get all alerts", success, f"Found {len(data) if isinstance(data, list) else 0} alerts")
        
        # Get alerts with filters
        success, data = self.make_request('GET', '/alerts?status=open&severity=critical')
        self.log_test("Get filtered alerts", success, f"Found {len(data) if isinstance(data, list) else 0} critical alerts")
        
        # Test alert acknowledgment (if we have an alert)
        if hasattr(self, 'alert_id'):
            success, data = self.make_request('PATCH', f'/alerts/{self.alert_id}/acknowledge')
            self.log_test("Acknowledge alert", success, str(data))
            
            # Test alert resolution
            success, data = self.make_request('PATCH', f'/alerts/{self.alert_id}/resolve')
            self.log_test("Resolve alert", success, str(data))
    
    def test_incidents_api(self):
        """Test incidents management endpoints"""
        print("\n🔍 Testing Incidents API...")
        
        if not self.token:
            print("❌ Skipping incidents API tests - no authentication token")
            return
        
        # Get all incidents
        success, data = self.make_request('GET', '/incidents')
        self.log_test("Get all incidents", success, f"Found {len(data) if isinstance(data, list) else 0} incidents")
        
        # Store incident ID for further tests
        if success and isinstance(data, list) and len(data) > 0:
            self.incident_id = data[0]['id']
            
            # Get specific incident
            success, data = self.make_request('GET', f'/incidents/{self.incident_id}')
            self.log_test("Get specific incident", success, str(data))
            
            # Test AI analysis trigger
            success, data = self.make_request('POST', f'/incidents/{self.incident_id}/analyze')
            self.log_test("Trigger AI analysis", success, str(data))
            
            # Test incident status update
            success, data = self.make_request('PATCH', f'/incidents/{self.incident_id}/status?status=investigating')
            self.log_test("Update incident status", success, str(data))
    
    def test_runbooks_api(self):
        """Test runbooks management endpoints"""
        print("\n🔍 Testing Runbooks API...")
        
        if not self.token:
            print("❌ Skipping runbooks API tests - no authentication token")
            return
        
        # Create a test runbook
        runbook_data = {
            "name": "High CPU Mitigation",
            "description": "Steps to mitigate high CPU usage",
            "service": "web-server",
            "trigger_conditions": {"severity": "critical", "metric": "cpu_usage"},
            "steps": [
                {"step": 1, "action": "Check process list", "command": "ps aux --sort=-%cpu"},
                {"step": 2, "action": "Restart high CPU processes", "command": "systemctl restart nginx"},
                {"step": 3, "action": "Scale horizontally if needed", "command": "kubectl scale deployment web --replicas=3"}
            ],
            "auto_execute": False
        }
        
        success, data = self.make_request('POST', '/runbooks', runbook_data, expected_status=200)
        self.log_test("Create runbook", success, str(data))
        
        # Store runbook ID
        if success and 'id' in data:
            self.runbook_id = data['id']
        
        # Get all runbooks
        success, data = self.make_request('GET', '/runbooks')
        self.log_test("Get all runbooks", success, f"Found {len(data) if isinstance(data, list) else 0} runbooks")
        
        # Execute runbook
        if hasattr(self, 'runbook_id'):
            success, data = self.make_request('POST', f'/runbooks/{self.runbook_id}/execute')
            self.log_test("Execute runbook", success, str(data))
    
    def test_analytics_api(self):
        """Test analytics dashboard endpoint"""
        print("\n🔍 Testing Analytics API...")
        
        if not self.token:
            print("❌ Skipping analytics API tests - no authentication token")
            return
        
        # Get dashboard analytics
        success, data = self.make_request('GET', '/analytics/dashboard')
        self.log_test("Get dashboard analytics", success, str(data))
        
        # Verify analytics structure
        if success and isinstance(data, dict):
            required_fields = ['total_alerts', 'open_alerts', 'total_incidents', 'avg_mttr_seconds']
            missing_fields = [field for field in required_fields if field not in data]
            
            if not missing_fields:
                self.log_test("Analytics data structure", True, "All required fields present")
            else:
                self.log_test("Analytics data structure", False, f"Missing fields: {missing_fields}")
    
    def test_services_api(self):
        """Test services endpoint"""
        print("\n🔍 Testing Services API...")
        
        if not self.token:
            print("❌ Skipping services API tests - no authentication token")
            return
        
        # Get services
        success, data = self.make_request('GET', '/services')
        self.log_test("Get services", success, f"Found {len(data) if isinstance(data, list) else 0} services")
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 Starting FalconApps Backend API Tests")
        print(f"🎯 Target: {self.base_url}")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run all test categories
        self.test_health_check()
        self.test_authentication()
        self.test_alert_webhook()
        self.test_alerts_api()
        self.test_incidents_api()
        self.test_runbooks_api()
        self.test_analytics_api()
        self.test_services_api()
        
        # Print summary
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.tests_passed}/{self.tests_run}")
        print(f"❌ Failed: {self.tests_run - self.tests_passed}/{self.tests_run}")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"📈 Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        # Return success if >80% tests pass
        return self.tests_passed / self.tests_run >= 0.8

def main():
    """Main test execution"""
    tester = FalconAppsAPITester()
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()