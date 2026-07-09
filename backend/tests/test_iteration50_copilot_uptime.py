"""
Iteration 50 — Advanced URL monitors (assertions, timeseries, SSL)
+ AI Copilot chat & approval workflow.
"""
import os
import time
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://health-rules-engine.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}
VIEWER = {"email": "test@falconapps.com", "password": "testpass123"}


# ───────────────────────── Helpers & Fixtures ─────────────────────────

def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def viewer_token():
    return _login(VIEWER)


@pytest.fixture(scope="module")
def admin_hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def viewer_hdr(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}", "Content-Type": "application/json"}


# State across module
created_monitor_ids = []
created_session_ids = []


# ───────────────────────── Uptime: Advanced Monitor ─────────────────────────

class TestUptimeAdvanced:
    def test_create_monitor_with_safe_defaults(self, admin_hdr):
        payload = {
            "name": "TEST_safe_defaults",
            "url": "https://httpbin.org/status/200",
            "interval": 300,
            "apply_safe_defaults": True,
        }
        r = requests.post(f"{API}/uptime/monitors", json=payload, headers=admin_hdr, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        mid = data.get("id") or data.get("_id") or data.get("monitor", {}).get("id")
        assert mid, f"no id in {data}"
        created_monitor_ids.append(mid)
        # safe defaults should create a list of assertions (>= 1)
        assertions = data.get("assertions") or data.get("monitor", {}).get("assertions") or []
        assert isinstance(assertions, list)
        assert len(assertions) >= 5, f"expected safe-default assertions merged in, got {len(assertions)}"
        # should include a not_contains for traceback or 5xx
        joined = json.dumps(assertions).lower()
        assert "traceback" in joined or "internal server error" in joined, joined[:300]

    def test_healthy_url_check(self, admin_hdr):
        mid = created_monitor_ids[0]
        r = requests.post(f"{API}/uptime/monitors/{mid}/check", headers=admin_hdr, timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("success") is True, f"expected success=true got {data}"
        # ssl_days_remaining positive
        ssl_days = data.get("ssl_days_remaining")
        assert ssl_days is None or (isinstance(ssl_days, int) and ssl_days > 0), f"ssl_days_remaining weird: {ssl_days}"

    def test_false_positive_detected_via_assertions(self, admin_hdr):
        # URL returns 200 but body contains 'Traceback (most recent call last):' & 'internal server error'
        url = "https://httpbin.org/response-headers?content=Traceback+%28most+recent+call+last%29%3A+internal+server+error"
        payload = {
            "name": "TEST_false_positive_traceback",
            "url": url,
            "interval": 300,
            "apply_safe_defaults": True,
        }
        r = requests.post(f"{API}/uptime/monitors", json=payload, headers=admin_hdr, timeout=30)
        assert r.status_code == 200, r.text[:300]
        mid = r.json().get("id") or r.json().get("monitor", {}).get("id")
        created_monitor_ids.append(mid)

        chk = requests.post(f"{API}/uptime/monitors/{mid}/check", headers=admin_hdr, timeout=60)
        assert chk.status_code == 200, chk.text[:300]
        data = chk.json()
        # Must detect false-positive → success=false
        assert data.get("success") is False, f"expected false positive failure, got: {data}"
        reason = (data.get("failure_reason") or data.get("failure_message") or "").lower()
        assert reason, f"no failure_reason, data={data}"
        assert "assert" in reason or "traceback" in reason or "internal server" in reason or "not_contains" in reason, reason

    def test_json_path_assertion_success(self, admin_hdr):
        payload = {
            "name": "TEST_jsonpath_ok",
            "url": "https://jsonplaceholder.typicode.com/todos/1",
            "interval": 300,
            "apply_safe_defaults": False,
            "assertions": [{"type": "json_path_eq", "path": "$.userId", "value": 1}],
        }
        r = requests.post(f"{API}/uptime/monitors", json=payload, headers=admin_hdr, timeout=30)
        assert r.status_code == 200, r.text[:300]
        mid = r.json().get("id") or r.json().get("monitor", {}).get("id")
        created_monitor_ids.append(mid)

        chk = requests.post(f"{API}/uptime/monitors/{mid}/check", headers=admin_hdr, timeout=60).json()
        assert chk.get("success") is True, f"jsonpath eq should succeed: {chk}"

    def test_json_path_assertion_failure(self, admin_hdr):
        payload = {
            "name": "TEST_jsonpath_fail",
            "url": "https://jsonplaceholder.typicode.com/todos/1",
            "interval": 300,
            "apply_safe_defaults": False,
            "assertions": [{"type": "json_path_eq", "path": "$.userId", "value": 999}],
        }
        r = requests.post(f"{API}/uptime/monitors", json=payload, headers=admin_hdr, timeout=30)
        mid = r.json().get("id") or r.json().get("monitor", {}).get("id")
        created_monitor_ids.append(mid)

        chk = requests.post(f"{API}/uptime/monitors/{mid}/check", headers=admin_hdr, timeout=60).json()
        assert chk.get("success") is False, f"jsonpath 999 should fail: {chk}"

    def test_contains_and_not_contains(self, admin_hdr):
        payload = {
            "name": "TEST_contains",
            "url": "https://jsonplaceholder.typicode.com/todos/1",
            "interval": 300,
            "apply_safe_defaults": False,
            "assertions": [
                {"type": "contains", "value": "userId", "case_sensitive": True},
                {"type": "not_contains", "value": "IMPOSSIBLE_XYZ", "case_sensitive": False},
                {"type": "status_in", "value": [200, 201]},
            ],
        }
        r = requests.post(f"{API}/uptime/monitors", json=payload, headers=admin_hdr, timeout=30)
        mid = r.json().get("id") or r.json().get("monitor", {}).get("id")
        created_monitor_ids.append(mid)
        chk = requests.post(f"{API}/uptime/monitors/{mid}/check", headers=admin_hdr, timeout=60).json()
        assert chk.get("success") is True, f"contains flow should succeed: {chk}"

    def test_timeseries_endpoint_multi_hours(self, admin_hdr):
        mid = created_monitor_ids[0]
        for h in [1, 6, 24, 72, 168]:
            r = requests.get(f"{API}/uptime/monitors/{mid}/timeseries?hours={h}", headers=admin_hdr, timeout=30)
            assert r.status_code == 200, f"{h}h: {r.text[:200]}"
            data = r.json()
            assert "series" in data and isinstance(data["series"], list), data
            assert "summary" in data and isinstance(data["summary"], dict), data
            for k in ("total_checks", "successful", "failed", "uptime_pct"):
                assert k in data["summary"], f"missing {k} in summary for {h}h"
            assert "bucket_minutes" in data

    def test_backfill_safe_defaults_admin(self, admin_hdr):
        r = requests.post(f"{API}/uptime/monitors/backfill-safe-defaults", headers=admin_hdr, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "updated" in data and "skipped" in data, data

    def test_backfill_safe_defaults_viewer_forbidden(self, viewer_hdr):
        r = requests.post(f"{API}/uptime/monitors/backfill-safe-defaults", headers=viewer_hdr, timeout=30)
        assert r.status_code == 403, f"expected 403 for viewer, got {r.status_code} {r.text[:200]}"


# ───────────────────────── AI Copilot ─────────────────────────

class TestAICopilot:
    def test_sessions_requires_auth(self):
        r = requests.get(f"{API}/ai-copilot/sessions", timeout=15)
        assert r.status_code in (401, 403), r.status_code

    def test_list_sessions_ok(self, admin_hdr):
        r = requests.get(f"{API}/ai-copilot/sessions", headers=admin_hdr, timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "sessions" in data and isinstance(data["sessions"], list)

    def test_chat_creates_monitor_proposal(self, admin_hdr):
        msg = ("Please create a URL monitor for https://jsonplaceholder.typicode.com/todos/1 "
               "that checks every 60 seconds.")
        r = requests.post(f"{API}/ai-copilot/chat",
                          json={"message": msg}, headers=admin_hdr, timeout=120)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert data.get("session_id"), data
        assert data.get("assistant_message"), data
        created_session_ids.append(data["session_id"])
        pa = data.get("proposed_action") or {}
        assert pa, f"expected proposed_action, got {data}"
        assert pa.get("action") in ("create_url_monitor", "create_monitor"), pa
        assert pa.get("status") == "pending", pa
        pytest.action_id = pa.get("id") or pa.get("_id")
        assert pytest.action_id, pa

    def test_chat_multi_turn_context(self, admin_hdr):
        sid = created_session_ids[0]
        r = requests.post(f"{API}/ai-copilot/chat",
                          json={"message": "What URL were we discussing just now?",
                                "session_id": sid}, headers=admin_hdr, timeout=120)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert data.get("session_id") == sid
        assistant = (data.get("assistant_message") or {}).get("content") or data.get("assistant_message") or ""
        if isinstance(assistant, dict):
            assistant = assistant.get("content", "")
        # context retention: should mention jsonplaceholder or typicode
        assert "jsonplaceholder" in assistant.lower() or "typicode" in assistant.lower() or "todos" in assistant.lower(), \
            f"no context continuity in: {assistant[:300]}"

    def test_session_messages(self, admin_hdr):
        sid = created_session_ids[0]
        r = requests.get(f"{API}/ai-copilot/sessions/{sid}/messages", headers=admin_hdr, timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert "messages" in data and len(data["messages"]) >= 2

    def test_viewer_cannot_approve(self, viewer_hdr):
        aid = getattr(pytest, "action_id", None)
        if not aid:
            pytest.skip("no action id")
        r = requests.post(f"{API}/ai-copilot/actions/{aid}/approve", headers=viewer_hdr, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_admin_approve_executes(self, admin_hdr):
        aid = getattr(pytest, "action_id", None)
        if not aid:
            pytest.skip("no action id")
        r = requests.post(f"{API}/ai-copilot/actions/{aid}/approve", headers=admin_hdr, timeout=60)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert data.get("status") == "executed", data
        er = data.get("execution_result") or {}
        created = er.get("created_monitor") or {}
        mid = created.get("id") or er.get("monitor_id")
        assert mid, f"no created monitor id in {data}"
        created_monitor_ids.append(mid)

        # Verify it's in list
        mlist = requests.get(f"{API}/uptime/monitors", headers=admin_hdr, timeout=15).json()
        items = mlist if isinstance(mlist, list) else mlist.get("monitors", [])
        ids = [m.get("id") for m in items]
        assert mid in ids, f"monitor {mid} not listed"

    def test_second_action_reject_flow(self, admin_hdr, viewer_hdr):
        # create another proposal
        r = requests.post(f"{API}/ai-copilot/chat",
                          json={"message": "Monitor https://httpbin.org/status/200 every 120s"},
                          headers=admin_hdr, timeout=120)
        assert r.status_code == 200, r.text[:300]
        pa = r.json().get("proposed_action") or {}
        aid = pa.get("id")
        if not aid:
            pytest.skip("no proposed action for reject test")
        created_session_ids.append(r.json().get("session_id"))

        # viewer rejection → 403
        rv = requests.post(f"{API}/ai-copilot/actions/{aid}/reject",
                           json={"reason": "no"}, headers=viewer_hdr, timeout=15)
        assert rv.status_code == 403, f"viewer reject got {rv.status_code}"

        # admin reject → rejected
        ra = requests.post(f"{API}/ai-copilot/actions/{aid}/reject",
                           json={"reason": "not needed"}, headers=admin_hdr, timeout=30)
        assert ra.status_code == 200, ra.text[:300]
        assert ra.json().get("status") == "rejected", ra.json()

    def test_empty_message_rejected(self, admin_hdr):
        r = requests.post(f"{API}/ai-copilot/chat", json={"message": ""}, headers=admin_hdr, timeout=15)
        assert r.status_code in (400, 422), r.status_code

    def test_unknown_session_messages(self, admin_hdr):
        r = requests.get(f"{API}/ai-copilot/sessions/does-not-exist-xyz/messages", headers=admin_hdr, timeout=15)
        # Either empty list or 404 — both acceptable
        assert r.status_code in (200, 404), r.status_code
        if r.status_code == 200:
            assert r.json().get("messages") == []

    def test_delete_session_cascades(self, admin_hdr):
        sid = created_session_ids[0] if created_session_ids else None
        if not sid:
            pytest.skip("no session id")
        r = requests.delete(f"{API}/ai-copilot/sessions/{sid}", headers=admin_hdr, timeout=15)
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("deleted") is True
        # messages should now be empty or 404
        m = requests.get(f"{API}/ai-copilot/sessions/{sid}/messages", headers=admin_hdr, timeout=15)
        if m.status_code == 200:
            assert m.json().get("messages") == []


# ───────────────────────── Cleanup ─────────────────────────

def test_zz_cleanup(admin_hdr=None):
    """Best-effort cleanup: delete TEST_ monitors and remaining sessions."""
    try:
        tok = _login(ADMIN)
        hdr = {"Authorization": f"Bearer {tok}"}
        for mid in set(created_monitor_ids):
            try:
                requests.delete(f"{API}/uptime/monitors/{mid}", headers=hdr, timeout=15)
            except Exception:
                pass
        for sid in set(created_session_ids):
            try:
                requests.delete(f"{API}/ai-copilot/sessions/{sid}", headers=hdr, timeout=15)
            except Exception:
                pass
    except Exception:
        pass
