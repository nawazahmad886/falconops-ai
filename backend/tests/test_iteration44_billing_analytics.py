"""
Iteration 44 - Billing Analytics Dashboard Tests
Tests for enhanced billing dashboard with:
- GET /api/billing/analytics (daily usage, agent breakdown, projections)
- GET /api/billing/usage (ai_runs_used, ai_runs_limit, overage)
- GET /api/billing/plans (3 plans with max_ai_runs field)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBillingAnalytics:
    """Billing Analytics endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for all tests"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@falconapps.com",
            "password": "Admin@123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    # ======================== BILLING PLANS ========================
    
    def test_billing_plans_returns_3_plans(self):
        """GET /api/billing/plans returns 3 plans"""
        resp = requests.get(f"{BASE_URL}/api/billing/plans", headers=self.headers)
        assert resp.status_code == 200
        plans = resp.json()
        assert isinstance(plans, list)
        assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"
        
        plan_ids = [p['id'] for p in plans]
        assert 'free' in plan_ids
        assert 'pro' in plan_ids
        assert 'enterprise' in plan_ids
    
    def test_billing_plans_have_max_ai_runs(self):
        """Each plan has max_ai_runs field with correct values"""
        resp = requests.get(f"{BASE_URL}/api/billing/plans", headers=self.headers)
        assert resp.status_code == 200
        plans = resp.json()
        
        expected_limits = {'free': 50, 'pro': 2000, 'enterprise': 10000}
        for plan in plans:
            assert 'max_ai_runs' in plan, f"Plan {plan['id']} missing max_ai_runs"
            assert plan['max_ai_runs'] == expected_limits[plan['id']], \
                f"Plan {plan['id']} has wrong max_ai_runs: {plan['max_ai_runs']}"
    
    def test_billing_plans_structure(self):
        """Plans have required fields: name, price, features, max_monitors, max_users, max_servers"""
        resp = requests.get(f"{BASE_URL}/api/billing/plans", headers=self.headers)
        assert resp.status_code == 200
        plans = resp.json()
        
        required_fields = ['id', 'name', 'price', 'features', 'max_monitors', 'max_users', 'max_servers', 'max_ai_runs']
        for plan in plans:
            for field in required_fields:
                assert field in plan, f"Plan {plan.get('id', 'unknown')} missing field: {field}"
    
    # ======================== BILLING USAGE ========================
    
    def test_billing_usage_returns_ai_runs(self):
        """GET /api/billing/usage returns ai_runs_used and ai_runs_limit"""
        resp = requests.get(f"{BASE_URL}/api/billing/usage", headers=self.headers)
        assert resp.status_code == 200
        usage = resp.json()
        
        assert 'ai_runs_used' in usage
        assert 'ai_runs_limit' in usage
        assert isinstance(usage['ai_runs_used'], int)
        assert isinstance(usage['ai_runs_limit'], int)
    
    def test_billing_usage_has_usage_pct(self):
        """Usage includes usage_pct calculation"""
        resp = requests.get(f"{BASE_URL}/api/billing/usage", headers=self.headers)
        assert resp.status_code == 200
        usage = resp.json()
        
        assert 'usage_pct' in usage
        # Verify calculation is correct
        expected_pct = round((usage['ai_runs_used'] / max(usage['ai_runs_limit'], 1)) * 100, 1)
        assert usage['usage_pct'] == expected_pct, f"usage_pct mismatch: {usage['usage_pct']} vs {expected_pct}"
    
    def test_billing_usage_has_overage_fields(self):
        """Usage includes overage_runs and overage_cost"""
        resp = requests.get(f"{BASE_URL}/api/billing/usage", headers=self.headers)
        assert resp.status_code == 200
        usage = resp.json()
        
        assert 'overage_runs' in usage
        assert 'overage_cost' in usage
        assert isinstance(usage['overage_runs'], int)
        assert isinstance(usage['overage_cost'], (int, float))
    
    def test_billing_usage_cost_per_run(self):
        """Usage includes cost_per_run = $0.002"""
        resp = requests.get(f"{BASE_URL}/api/billing/usage", headers=self.headers)
        assert resp.status_code == 200
        usage = resp.json()
        
        assert 'cost_per_run' in usage
        assert usage['cost_per_run'] == 0.002, f"Expected cost_per_run=0.002, got {usage['cost_per_run']}"
    
    def test_billing_usage_has_plan_info(self):
        """Usage includes plan_id and plan_name"""
        resp = requests.get(f"{BASE_URL}/api/billing/usage", headers=self.headers)
        assert resp.status_code == 200
        usage = resp.json()
        
        assert 'plan_id' in usage
        assert 'plan_name' in usage
        assert usage['plan_id'] in ['free', 'pro', 'enterprise']
    
    # ======================== BILLING ANALYTICS ========================
    
    def test_billing_analytics_returns_daily_usage(self):
        """GET /api/billing/analytics returns daily_usage array"""
        resp = requests.get(f"{BASE_URL}/api/billing/analytics", headers=self.headers)
        assert resp.status_code == 200
        analytics = resp.json()
        
        assert 'daily_usage' in analytics
        assert isinstance(analytics['daily_usage'], list)
        
        # Each day should have date, day, ai_runs, cost
        if len(analytics['daily_usage']) > 0:
            day = analytics['daily_usage'][0]
            assert 'date' in day
            assert 'day' in day
            assert 'ai_runs' in day
            assert 'cost' in day
    
    def test_billing_analytics_returns_agent_breakdown(self):
        """Analytics returns agent_breakdown with rca, summarizer, healer"""
        resp = requests.get(f"{BASE_URL}/api/billing/analytics", headers=self.headers)
        assert resp.status_code == 200
        analytics = resp.json()
        
        assert 'agent_breakdown' in analytics
        assert isinstance(analytics['agent_breakdown'], list)
        
        agent_ids = [a['agent'] for a in analytics['agent_breakdown']]
        assert 'rca' in agent_ids, "Missing rca agent in breakdown"
        assert 'summarizer' in agent_ids, "Missing summarizer agent in breakdown"
        assert 'healer' in agent_ids, "Missing healer agent in breakdown"
        
        # Each agent should have runs and cost
        for agent in analytics['agent_breakdown']:
            assert 'runs' in agent
            assert 'cost' in agent
    
    def test_billing_analytics_has_projections(self):
        """Analytics includes projected_monthly_runs and estimated_total_bill"""
        resp = requests.get(f"{BASE_URL}/api/billing/analytics", headers=self.headers)
        assert resp.status_code == 200
        analytics = resp.json()
        
        assert 'projected_monthly_runs' in analytics
        assert 'estimated_total_bill' in analytics
        assert isinstance(analytics['projected_monthly_runs'], (int, float))
        assert isinstance(analytics['estimated_total_bill'], (int, float))
    
    def test_billing_analytics_has_avg_daily_runs(self):
        """Analytics includes avg_daily_runs"""
        resp = requests.get(f"{BASE_URL}/api/billing/analytics", headers=self.headers)
        assert resp.status_code == 200
        analytics = resp.json()
        
        assert 'avg_daily_runs' in analytics
        assert isinstance(analytics['avg_daily_runs'], (int, float))
    
    def test_billing_analytics_has_cost_per_run(self):
        """Analytics includes cost_per_run = $0.002"""
        resp = requests.get(f"{BASE_URL}/api/billing/analytics", headers=self.headers)
        assert resp.status_code == 200
        analytics = resp.json()
        
        assert 'cost_per_run' in analytics
        assert analytics['cost_per_run'] == 0.002
    
    def test_billing_analytics_has_total_runs(self):
        """Analytics includes total_runs_this_month"""
        resp = requests.get(f"{BASE_URL}/api/billing/analytics", headers=self.headers)
        assert resp.status_code == 200
        analytics = resp.json()
        
        assert 'total_runs_this_month' in analytics
        assert isinstance(analytics['total_runs_this_month'], int)
    
    def test_billing_analytics_has_plan_cost(self):
        """Analytics includes plan_cost"""
        resp = requests.get(f"{BASE_URL}/api/billing/analytics", headers=self.headers)
        assert resp.status_code == 200
        analytics = resp.json()
        
        assert 'plan_cost' in analytics
        assert isinstance(analytics['plan_cost'], (int, float))
    
    # ======================== BILLING CURRENT ========================
    
    def test_billing_current_returns_plan_info(self):
        """GET /api/billing/current returns current plan info"""
        resp = requests.get(f"{BASE_URL}/api/billing/current", headers=self.headers)
        assert resp.status_code == 200
        current = resp.json()
        
        assert 'plan_id' in current
        assert 'plan' in current
        assert 'status' in current
        assert current['plan_id'] in ['free', 'pro', 'enterprise']
    
    # ======================== BILLING TRANSACTIONS ========================
    
    def test_billing_transactions_returns_list(self):
        """GET /api/billing/transactions returns transaction list"""
        resp = requests.get(f"{BASE_URL}/api/billing/transactions", headers=self.headers)
        assert resp.status_code == 200
        transactions = resp.json()
        
        assert isinstance(transactions, list)
        # Transactions may be empty if no payments made
        if len(transactions) > 0:
            tx = transactions[0]
            assert 'plan_id' in tx or 'amount' in tx
    
    # ======================== AUTH REQUIRED ========================
    
    def test_billing_endpoints_require_auth(self):
        """All billing endpoints require authentication"""
        endpoints = [
            '/api/billing/plans',
            '/api/billing/usage',
            '/api/billing/analytics',
            '/api/billing/current',
            '/api/billing/transactions'
        ]
        
        for endpoint in endpoints:
            resp = requests.get(f"{BASE_URL}{endpoint}")
            assert resp.status_code in [401, 403], f"{endpoint} should require auth, got {resp.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
