"""
FalconOps AI - Enterprise Resource Explorer tests (iteration 66)

Covers: db.servers + db.oneagent_agents merge-dedup into one host resource,
enrichment honesty (no fabricated predicted-failure), monitoring toggle
flipping a linked db.monitors.enabled, retire/restore, the Alerts tab's
reuse of problems_service, WS broadcast, and auth requirements.
"""
import os
import time
import uuid
import requests
import pytest
from websockets.sync.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
WS_BASE_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

ADMIN_EMAIL = "admin@falconapps.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


def _sync(authenticated_client):
    r = authenticated_client.post(f"{BASE_URL}/api/resources/sync")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    return r.json()


def _find_resource_by_name(authenticated_client, name):
    r = authenticated_client.get(f"{BASE_URL}/api/resources?search={name}&limit=10")
    assert r.status_code == 200, r.text
    matches = [res for res in r.json()["resources"] if res["name"] == name]
    return matches[0] if matches else None


class TestBridgeDedup:
    def test_server_and_oneagent_merge_into_one_resource(self, authenticated_client):
        # Seed db.servers (creates prod-web-01 among others)
        seed = authenticated_client.post(f"{BASE_URL}/api/servers/simulate")
        assert seed.status_code == 200, seed.text

        # Seed a matching db.oneagent_agents heartbeat for the same hostname
        key_resp = authenticated_client.post(f"{BASE_URL}/api/oneagent/keys", json={"name": f"test-key-{uuid.uuid4().hex[:8]}"})
        assert key_resp.status_code == 200, key_resp.text
        api_key = key_resp.json()["key"]

        hb = requests.post(f"{BASE_URL}/api/ingest/heartbeat", json={
            "host": "prod-web-01", "environment": "production", "agent_version": "1.0.0", "services": [],
        }, headers={"X-API-Key": api_key})
        assert hb.status_code == 200, hb.text

        _sync(authenticated_client)
        resource = _find_resource_by_name(authenticated_client, "prod-web-01")
        assert resource is not None, "expected a merged resource named prod-web-01"
        collections = {sr["collection"] for sr in (resource.get("source_refs") or [])}
        assert collections == {"servers", "oneagent_agents"}, f"expected both sources merged, got {collections}"
        assert resource["resource_category"] == "infrastructure"

        # Re-sync must not create a duplicate
        _sync(authenticated_client)
        r = authenticated_client.get(f"{BASE_URL}/api/resources?search=prod-web-01&limit=10")
        matches = [res for res in r.json()["resources"] if res["name"] == "prod-web-01"]
        assert len(matches) == 1, f"expected exactly 1 resource after re-sync, got {len(matches)}"
        print("✓ db.servers + db.oneagent_agents merged into exactly one resource, re-sync stayed deduplicated")


class TestEnrichmentHonesty:
    def test_database_resource_predicted_failure_has_honest_reason(self, authenticated_client):
        name = f"test-db-{uuid.uuid4().hex[:8]}"
        create = authenticated_client.post(f"{BASE_URL}/api/db-monitoring/instances", json={
            "name": name, "db_type": "postgres", "host": "10.0.5.5", "port": 5432,
            "database": "appdb", "environment": "production", "tags": {},
        })
        assert create.status_code == 200, create.text

        _sync(authenticated_client)
        resource = _find_resource_by_name(authenticated_client, name)
        assert resource is not None, "expected the seeded db instance to appear as a resource"

        detail = authenticated_client.get(f"{BASE_URL}/api/resources/{resource['id']}")
        assert detail.status_code == 200, detail.text
        enrichment = detail.json()["enrichment"]
        assert enrichment.get("predicted_failure") is None
        assert "predicted_failure_not_available_reason" in enrichment, "expected an honest reason, not a fabricated value"
        print(f"✓ database resource predicted_failure honestly reports: {enrichment['predicted_failure_not_available_reason'][:60]}...")


class TestMonitoringToggle:
    def test_disable_enable_flips_linked_monitor(self, authenticated_client):
        seed = authenticated_client.post(f"{BASE_URL}/api/servers/simulate")
        assert seed.status_code == 200
        _sync(authenticated_client)
        resource = _find_resource_by_name(authenticated_client, "prod-db-01")
        assert resource is not None

        monitor = authenticated_client.post(f"{BASE_URL}/api/monitors", json={
            "name": f"test-monitor-{uuid.uuid4().hex[:8]}", "target": "prod-db-01",
            "monitor_type": "ping", "enabled": True,
        })
        assert monitor.status_code == 200, monitor.text

        disable = authenticated_client.post(f"{BASE_URL}/api/resources/{resource['id']}/disable-monitoring")
        assert disable.status_code == 200, disable.text
        monitors_after_disable = authenticated_client.get(f"{BASE_URL}/api/monitors?environment=production").json()
        linked = next(m for m in monitors_after_disable if m["target"] == "prod-db-01")
        assert linked["enabled"] is False, "expected linked monitor to be disabled"

        enable = authenticated_client.post(f"{BASE_URL}/api/resources/{resource['id']}/enable-monitoring")
        assert enable.status_code == 200, enable.text
        monitors_after_enable = authenticated_client.get(f"{BASE_URL}/api/monitors?environment=production").json()
        linked_again = next(m for m in monitors_after_enable if m["target"] == "prod-db-01")
        assert linked_again["enabled"] is True, "expected linked monitor to be re-enabled"
        print("✓ enable/disable-monitoring correctly flips the linked db.monitors.enabled")


class TestRetireRestore:
    def test_retire_hides_by_default_restore_reappears(self, authenticated_client):
        seed = authenticated_client.post(f"{BASE_URL}/api/servers/simulate")
        assert seed.status_code == 200
        _sync(authenticated_client)
        resource = _find_resource_by_name(authenticated_client, "prod-cache-01")
        assert resource is not None

        retire = authenticated_client.post(f"{BASE_URL}/api/resources/{resource['id']}/retire", json={"reason": "test"})
        assert retire.status_code == 200, retire.text
        assert retire.json()["lifecycle_status"] == "retired"

        default_view = authenticated_client.get(f"{BASE_URL}/api/resources?search=prod-cache-01")
        assert not any(r["id"] == resource["id"] for r in default_view.json()["resources"]), "retired resource visible by default"

        with_retired = authenticated_client.get(f"{BASE_URL}/api/resources?search=prod-cache-01&include_retired=true")
        assert any(r["id"] == resource["id"] for r in with_retired.json()["resources"]), "retired resource missing even with include_retired=true"

        restore = authenticated_client.post(f"{BASE_URL}/api/resources/{resource['id']}/restore")
        assert restore.status_code == 200, restore.text
        assert restore.json()["lifecycle_status"] in ("monitored", "discovered")

        default_view_after = authenticated_client.get(f"{BASE_URL}/api/resources?search=prod-cache-01")
        assert any(r["id"] == resource["id"] for r in default_view_after.json()["resources"]), "restored resource should reappear by default"
        print("✓ retire hides by default, restore brings it back")


class TestRelatedAlertsReuse:
    def test_soc_event_matching_resource_name_appears_in_alerts_tab(self, authenticated_client):
        seed = authenticated_client.post(f"{BASE_URL}/api/servers/simulate")
        assert seed.status_code == 200
        _sync(authenticated_client)
        resource = _find_resource_by_name(authenticated_client, "prod-api-01")
        assert resource is not None

        ingest = requests.post(f"{BASE_URL}/api/soc-engine/ingest", json={
            "source": "test", "service": "prod-api-01", "severity": "high",
            "message": f"resource explorer alert reuse test {uuid.uuid4().hex[:8]}",
        })
        assert ingest.status_code == 200, ingest.text

        alerts = authenticated_client.get(f"{BASE_URL}/api/resources/{resource['id']}/alerts")
        assert alerts.status_code == 200, alerts.text
        assert any(a["source_collection"] == "soc_event" for a in alerts.json()["alerts"]), "expected the soc_event to appear via problems_service reuse"
        print("✓ /alerts tab correctly reuses problems_service.list_problems(service=name)")


class TestWSBroadcast:
    def test_sync_pushes_resource_synced_event(self, auth_token, authenticated_client):
        # Ensure at least one host will need updating so the sync produces a change
        requests.post(f"{BASE_URL}/api/servers/simulate")
        with ws_connect(f"{WS_BASE_URL}/api/resources/live?token={auth_token}") as ws:
            authenticated_client.post(f"{BASE_URL}/api/resources/sync")
            deadline = time.time() + 10
            found = False
            while time.time() < deadline:
                try:
                    raw = ws.recv(timeout=max(0.1, deadline - time.time()))
                except (TimeoutError, ConnectionClosed):
                    break
                import json
                msg = json.loads(raw)
                if msg.get("type") == "resource.synced":
                    found = True
                    break
            assert found, "expected a resource.synced broadcast after a sync with changes"
            print("✓ /api/resources/live pushed a resource.synced event")


class TestAuthRequired:
    def test_list_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/resources").status_code in (401, 403)

    def test_facets_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/resources/facets").status_code in (401, 403)

    def test_detail_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/resources/nonexistent").status_code in (401, 403)

    def test_sync_requires_auth(self):
        assert requests.post(f"{BASE_URL}/api/resources/sync").status_code in (401, 403)

    def test_retire_requires_auth(self):
        assert requests.post(f"{BASE_URL}/api/resources/nonexistent/retire", json={}).status_code in (401, 403)

    def test_live_requires_token(self):
        with ws_connect(f"{WS_BASE_URL}/api/resources/live") as ws:
            import json
            msg = json.loads(ws.recv(timeout=10))
            assert msg.get("type") == "error"
            assert "token" in msg.get("error", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
