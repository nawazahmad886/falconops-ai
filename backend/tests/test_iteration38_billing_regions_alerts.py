"""
FalconOps AI - Iteration 38 Tests
Testing 3 NEW features:
1. Uptime Failure Alerts (webhook/email/slack channels, consecutive failure threshold, recovery notifications)
2. Multi-Region Uptime Checks (5 regions: us-east, us-west, eu-west, me-south, ap-southeast)
3. SaaS Billing via Stripe (Free/$49 Pro/$199 Enterprise tiers, checkout, transactions)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@falconapps.com",
        "password": "Admin@123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for API requests"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ======================== MULTI-REGION TESTS ========================

class TestMultiRegion:
    """Multi-region uptime check tests"""
    
    def test_get_regions_returns_5_regions(self, auth_headers):
        """GET /api/uptime/regions should return 5 regions"""
        response = requests.get(f"{BASE_URL}/api/uptime/regions", headers=auth_headers)
        assert response.status_code == 200
        regions = response.json()
        assert isinstance(regions, list)
        assert len(regions) == 5
        
        # Verify all expected regions
        region_ids = [r["id"] for r in regions]
        expected = ["us-east", "us-west", "eu-west", "me-south", "ap-southeast"]
        for exp in expected:
            assert exp in region_ids, f"Missing region: {exp}"
        
        # Verify region structure
        for r in regions:
            assert "id" in r
            assert "name" in r
            assert "latency_offset" in r
            print(f"Region: {r['id']} - {r['name']} (offset: {r['latency_offset']}ms)")
    
    def test_create_monitor_with_multiple_regions(self, auth_headers):
        """POST /api/uptime/monitors with regions array"""
        payload = {
            "name": "TEST_MultiRegion_Monitor",
            "url": "https://httpbin.org/status/200",
            "interval": 60,
            "method": "GET",
            "expected_status": 200,
            "timeout": 10,
            "regions": ["us-east", "eu-west", "ap-southeast"],
            "consecutive_failures": 3,
            "alert_channels": []
        }
        response = requests.post(f"{BASE_URL}/api/uptime/monitors", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "TEST_MultiRegion_Monitor"
        assert data["regions"] == ["us-east", "eu-west", "ap-southeast"]
        assert data["consecutive_failures"] == 3
        print(f"Created monitor with regions: {data['regions']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/uptime/monitors/{data['id']}", headers=auth_headers)
    
    def test_get_monitor_region_stats(self, auth_headers):
        """GET /api/uptime/monitors/{id}/regions returns per-region latency stats"""
        # First get existing monitors
        response = requests.get(f"{BASE_URL}/api/uptime/monitors", headers=auth_headers)
        monitors = response.json()
        
        if not monitors:
            pytest.skip("No monitors available for region stats test")
        
        monitor_id = monitors[0]["id"]
        response = requests.get(f"{BASE_URL}/api/uptime/monitors/{monitor_id}/regions?hours=24", headers=auth_headers)
        assert response.status_code == 200
        stats = response.json()
        
        assert isinstance(stats, list)
        print(f"Region stats for monitor {monitor_id}: {len(stats)} regions with data")
        
        for s in stats:
            assert "region" in s
            assert "avg_response_ms" in s
            assert "total_checks" in s
            assert "uptime_pct" in s
            print(f"  {s['region']}: avg={s['avg_response_ms']}ms, checks={s['total_checks']}, uptime={s['uptime_pct']}%")


# ======================== UPTIME ALERTS TESTS ========================

class TestUptimeAlerts:
    """Uptime failure alerts tests"""
    
    def test_create_monitor_with_alert_channels(self, auth_headers):
        """POST /api/uptime/monitors with alert_channels"""
        payload = {
            "name": "TEST_Alert_Monitor",
            "url": "https://httpbin.org/status/200",
            "interval": 60,
            "method": "GET",
            "expected_status": 200,
            "timeout": 10,
            "regions": ["us-east"],
            "consecutive_failures": 2,
            "alert_channels": [
                {"type": "webhook", "url": "https://example.com/webhook"},
                {"type": "email", "address": "alert@example.com"},
                {"type": "slack", "webhook_url": "https://hooks.slack.com/test"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/uptime/monitors", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "TEST_Alert_Monitor"
        assert data["consecutive_failures"] == 2
        assert len(data["alert_channels"]) == 3
        
        # Verify channel types
        channel_types = [ch["type"] for ch in data["alert_channels"]]
        assert "webhook" in channel_types
        assert "email" in channel_types
        assert "slack" in channel_types
        print(f"Created monitor with {len(data['alert_channels'])} alert channels")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/uptime/monitors/{data['id']}", headers=auth_headers)
    
    def test_update_monitor_config(self, auth_headers):
        """PUT /api/uptime/monitors/{id} updates monitor config"""
        # Create a monitor first
        create_payload = {
            "name": "TEST_Update_Monitor",
            "url": "https://httpbin.org/status/200",
            "interval": 60,
            "regions": ["us-east"],
            "consecutive_failures": 3,
            "alert_channels": []
        }
        create_resp = requests.post(f"{BASE_URL}/api/uptime/monitors", json=create_payload, headers=auth_headers)
        assert create_resp.status_code == 200
        monitor_id = create_resp.json()["id"]
        
        # Update the monitor
        update_payload = {
            "name": "TEST_Updated_Monitor",
            "regions": ["us-east", "us-west"],
            "consecutive_failures": 5,
            "alert_channels": [{"type": "email", "address": "updated@example.com"}]
        }
        update_resp = requests.put(f"{BASE_URL}/api/uptime/monitors/{monitor_id}", json=update_payload, headers=auth_headers)
        assert update_resp.status_code == 200
        updated = update_resp.json()
        
        assert updated["name"] == "TEST_Updated_Monitor"
        assert updated["regions"] == ["us-east", "us-west"]
        assert updated["consecutive_failures"] == 5
        assert len(updated["alert_channels"]) == 1
        print(f"Updated monitor: {updated['name']} with regions {updated['regions']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/uptime/monitors/{monitor_id}", headers=auth_headers)
    
    def test_get_alert_history(self, auth_headers):
        """GET /api/uptime/alerts returns alert history"""
        response = requests.get(f"{BASE_URL}/api/uptime/alerts?limit=30", headers=auth_headers)
        assert response.status_code == 200
        alerts = response.json()
        
        assert isinstance(alerts, list)
        print(f"Alert history: {len(alerts)} alerts")
        
        for a in alerts[:5]:  # Check first 5
            assert "id" in a
            assert "monitor_id" in a
            assert "alert_type" in a
            assert "timestamp" in a
            print(f"  Alert: {a.get('monitor_name', 'N/A')} - {a['alert_type']} at {a['timestamp']}")
    
    def test_get_alert_history_by_monitor(self, auth_headers):
        """GET /api/uptime/alerts?monitor_id=X filters by monitor"""
        # Get a monitor first
        monitors_resp = requests.get(f"{BASE_URL}/api/uptime/monitors", headers=auth_headers)
        monitors = monitors_resp.json()
        
        if not monitors:
            pytest.skip("No monitors for alert filter test")
        
        monitor_id = monitors[0]["id"]
        response = requests.get(f"{BASE_URL}/api/uptime/alerts?monitor_id={monitor_id}&limit=10", headers=auth_headers)
        assert response.status_code == 200
        alerts = response.json()
        
        assert isinstance(alerts, list)
        # All alerts should be for this monitor
        for a in alerts:
            assert a["monitor_id"] == monitor_id
        print(f"Filtered alerts for monitor {monitor_id}: {len(alerts)}")


# ======================== BILLING TESTS ========================

class TestBilling:
    """SaaS Billing via Stripe tests"""
    
    def test_get_billing_plans(self, auth_headers):
        """GET /api/billing/plans returns 3 plans"""
        response = requests.get(f"{BASE_URL}/api/billing/plans", headers=auth_headers)
        assert response.status_code == 200
        plans = response.json()
        
        assert isinstance(plans, list)
        assert len(plans) == 3
        
        plan_ids = [p["id"] for p in plans]
        assert "free" in plan_ids
        assert "pro" in plan_ids
        assert "enterprise" in plan_ids
        
        # Verify plan structure and prices
        for p in plans:
            assert "id" in p
            assert "name" in p
            assert "price" in p
            assert "max_monitors" in p
            assert "max_users" in p
            assert "features" in p
            print(f"Plan: {p['name']} - ${p['price']}/mo, {p['max_monitors']} monitors, {p['max_users']} users")
        
        # Verify specific prices
        free_plan = next(p for p in plans if p["id"] == "free")
        pro_plan = next(p for p in plans if p["id"] == "pro")
        enterprise_plan = next(p for p in plans if p["id"] == "enterprise")
        
        assert free_plan["price"] == 0
        assert pro_plan["price"] == 49.0
        assert enterprise_plan["price"] == 199.0
    
    def test_get_current_plan(self, auth_headers):
        """GET /api/billing/current returns user's current plan"""
        response = requests.get(f"{BASE_URL}/api/billing/current", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "plan_id" in data
        assert "plan" in data
        assert "status" in data
        
        print(f"Current plan: {data['plan_id']} - {data['plan']['name']}")
        print(f"Status: {data['status']}")
    
    def test_checkout_creates_stripe_session(self, auth_headers):
        """POST /api/billing/checkout creates Stripe checkout session"""
        payload = {
            "plan_id": "pro",
            "origin_url": "https://health-rules-engine.preview.emergentagent.com"
        }
        response = requests.post(f"{BASE_URL}/api/billing/checkout", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "url" in data
        assert "session_id" in data
        assert data["url"].startswith("https://checkout.stripe.com")
        print(f"Checkout session created: {data['session_id'][:20]}...")
        print(f"Checkout URL: {data['url'][:60]}...")
    
    def test_checkout_free_plan_rejected(self, auth_headers):
        """POST /api/billing/checkout rejects free plan"""
        payload = {
            "plan_id": "free",
            "origin_url": "https://health-rules-engine.preview.emergentagent.com"
        }
        response = requests.post(f"{BASE_URL}/api/billing/checkout", json=payload, headers=auth_headers)
        assert response.status_code == 400
        print("Free plan checkout correctly rejected")
    
    def test_checkout_invalid_plan_rejected(self, auth_headers):
        """POST /api/billing/checkout rejects invalid plan"""
        payload = {
            "plan_id": "invalid_plan",
            "origin_url": "https://health-rules-engine.preview.emergentagent.com"
        }
        response = requests.post(f"{BASE_URL}/api/billing/checkout", json=payload, headers=auth_headers)
        assert response.status_code == 400
        print("Invalid plan checkout correctly rejected")
    
    def test_get_transactions(self, auth_headers):
        """GET /api/billing/transactions returns payment history"""
        response = requests.get(f"{BASE_URL}/api/billing/transactions?limit=20", headers=auth_headers)
        assert response.status_code == 200
        txns = response.json()
        
        assert isinstance(txns, list)
        print(f"Transaction history: {len(txns)} transactions")
        
        for tx in txns[:5]:
            assert "session_id" in tx or "id" in tx
            assert "plan_id" in tx
            assert "amount" in tx
            assert "payment_status" in tx
            print(f"  TX: {tx['plan_id']} - ${tx['amount']} - {tx['payment_status']}")
    
    def test_downgrade_to_free(self, auth_headers):
        """POST /api/billing/downgrade downgrades to free plan"""
        response = requests.post(f"{BASE_URL}/api/billing/downgrade", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert data["plan_id"] == "free"
        print(f"Downgrade response: {data['message']}")
    
    def test_checkout_status_endpoint(self, auth_headers):
        """GET /api/billing/checkout/status/{id} checks payment status"""
        # First create a checkout session
        payload = {
            "plan_id": "enterprise",
            "origin_url": "https://health-rules-engine.preview.emergentagent.com"
        }
        checkout_resp = requests.post(f"{BASE_URL}/api/billing/checkout", json=payload, headers=auth_headers)
        assert checkout_resp.status_code == 200
        session_id = checkout_resp.json()["session_id"]
        
        # Check status
        status_resp = requests.get(f"{BASE_URL}/api/billing/checkout/status/{session_id}", headers=auth_headers)
        assert status_resp.status_code == 200
        status = status_resp.json()
        
        assert "status" in status
        assert "payment_status" in status
        print(f"Checkout status: {status['status']} - payment: {status['payment_status']}")


# ======================== EXISTING MONITOR VERIFICATION ========================

class TestExistingMonitors:
    """Verify existing monitors still work"""
    
    def test_existing_google_monitor(self, auth_headers):
        """Verify existing Google monitor is still working"""
        response = requests.get(f"{BASE_URL}/api/uptime/monitors", headers=auth_headers)
        assert response.status_code == 200
        monitors = response.json()
        
        # Find Google monitor
        google_monitor = None
        for m in monitors:
            if "google" in m["name"].lower() or "google" in m["url"].lower():
                google_monitor = m
                break
        
        if not google_monitor:
            print("No Google monitor found - may have been deleted")
            return
        
        assert google_monitor["status"] in ["up", "down", "pending"]
        assert google_monitor["total_checks"] > 0
        print(f"Google monitor: {google_monitor['name']}")
        print(f"  Status: {google_monitor['status']}")
        print(f"  Uptime: {google_monitor['uptime_pct']}%")
        print(f"  Total checks: {google_monitor['total_checks']}")
        print(f"  Regions: {google_monitor.get('regions', ['us-east'])}")
    
    def test_uptime_stats(self, auth_headers):
        """GET /api/uptime/stats returns aggregate stats"""
        response = requests.get(f"{BASE_URL}/api/uptime/stats?hours=24", headers=auth_headers)
        assert response.status_code == 200
        stats = response.json()
        
        assert "total_monitors" in stats
        assert "up" in stats
        assert "down" in stats
        assert "avg_uptime_pct" in stats
        assert "total_checks_period" in stats
        
        print(f"Uptime Stats (24h):")
        print(f"  Total monitors: {stats['total_monitors']}")
        print(f"  Up: {stats['up']}, Down: {stats['down']}")
        print(f"  Avg uptime: {stats['avg_uptime_pct']}%")
        print(f"  Total checks: {stats['total_checks_period']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
