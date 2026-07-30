"""
FalconOps AI - LLM Latency Percentiles + GPU Monitoring tests (iteration 67)

Covers: real p50/p90/p95/p99 latency computed from ai_monitoring_events
(no dual-write, no new collection), and GPU metrics flowing through OneAgent's
existing schema-less /api/ingest/metrics path into db.metrics_timeseries,
queried via metrics_timeseries_service.get_top_metrics()'s new multi-tag
group_by extension.
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

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


class TestLatencyPercentiles:
    def test_percentiles_are_correctly_ordered(self, authenticated_client):
        test_model = f"test-model-{uuid.uuid4().hex[:8]}"
        latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        for lat in latencies:
            r = authenticated_client.post(f"{BASE_URL}/api/ai-monitoring/evaluate", json={
                "user_input": "test latency sample",
                "ai_output": "ok",
                "latency_ms": lat,
                "model": test_model,
                "provider": "test",
                "source": "manual",
                "skip_llm_agents": True,
            })
            assert r.status_code == 200, r.text

        stats = authenticated_client.get(f"{BASE_URL}/api/ai-monitoring/latency-stats?model={test_model}")
        assert stats.status_code == 200, stats.text
        overall = stats.json()["overall"]
        assert overall["sample_size"] == len(latencies)
        assert overall["p50"] <= overall["p90"] <= overall["p95"] <= overall["p99"]
        # p50 of a 100..1000 evenly-spaced series should land near the middle
        assert 400 <= overall["p50"] <= 600
        assert overall["p99"] >= 900
        print(f"✓ latency-stats computed real percentiles: {overall}")


class TestGPUIngestAndSummary:
    def _seed_gpu_metrics(self, authenticated_client, host, gpu_index, gpu_name, gpu_vendor):
        key_resp = authenticated_client.post(f"{BASE_URL}/api/oneagent/keys", json={"name": f"gpu-test-key-{uuid.uuid4().hex[:8]}"})
        assert key_resp.status_code == 200, key_resp.text
        api_key = key_resp.json()["key"]

        tags = {"host": host, "gpu_index": gpu_index, "gpu_name": gpu_name, "gpu_vendor": gpu_vendor}
        batch = [
            {"name": "gpu.utilization.percent", "value": 72.5, "unit": "%", "tags": dict(tags)},
            {"name": "gpu.memory.percent", "value": 60.0, "unit": "%", "tags": dict(tags)},
            {"name": "gpu.memory.used_mb", "value": 12000.0, "unit": "MB", "tags": dict(tags)},
            {"name": "gpu.memory.total_mb", "value": 20000.0, "unit": "MB", "tags": dict(tags)},
            {"name": "gpu.temperature.c", "value": 68.0, "unit": "C", "tags": dict(tags)},
            {"name": "gpu.power.watts", "value": 250.0, "unit": "W", "tags": dict(tags)},
            {"name": "gpu.fan.percent", "value": 55.0, "unit": "%", "tags": dict(tags)},
        ]
        ingest = requests.post(
            f"{BASE_URL}/api/ingest/metrics",
            json={"host": host, "environment": "production", "agent_version": "1.0.0", "batch": batch},
            headers={"X-API-Key": api_key},
        )
        assert ingest.status_code == 200, ingest.text
        assert ingest.json()["ingested"] == len(batch)

    def test_seeded_gpu_appears_in_summary(self, authenticated_client):
        host = f"gpu-host-{uuid.uuid4().hex[:8]}"
        gpu_index, gpu_name, gpu_vendor = "0", "NVIDIA A100", "nvidia"
        self._seed_gpu_metrics(authenticated_client, host, gpu_index, gpu_name, gpu_vendor)

        summary = authenticated_client.get(f"{BASE_URL}/api/ai-monitoring/gpu?hours=1")
        assert summary.status_code == 200, summary.text
        data = summary.json()
        assert data["detected"] is True

        match = next((g for g in data["gpus"] if g["host"] == host and g["gpu_index"] == gpu_index), None)
        assert match is not None, f"expected seeded GPU host={host} idx={gpu_index} in {data['gpus']}"
        assert match["gpu_name"] == gpu_name
        assert match["gpu_vendor"] == gpu_vendor
        assert match["utilization_pct"] == pytest.approx(72.5, abs=0.01)
        assert match["memory_used_mb"] == pytest.approx(12000.0, abs=0.01)
        assert match["memory_total_mb"] == pytest.approx(20000.0, abs=0.01)
        assert match["temperature_c"] == pytest.approx(68.0, abs=0.01)
        assert match["power_watts"] == pytest.approx(250.0, abs=0.01)
        assert match["fan_pct"] == pytest.approx(55.0, abs=0.01)
        print(f"✓ seeded GPU correctly merged across all 7 metric names: {match}")


class TestGPUHonestEmptyState:
    def test_no_data_reports_honest_reason(self, authenticated_client):
        # An hours=1 window right after a fresh tenant/test run with no GPU data
        # seeded yet may or may not have zero rows depending on test execution
        # order, so this only asserts the CONTRACT: whenever detected is False,
        # a real reason must accompany it (never silently empty).
        summary = authenticated_client.get(f"{BASE_URL}/api/ai-monitoring/gpu?hours=1")
        assert summary.status_code == 200, summary.text
        data = summary.json()
        if not data["detected"]:
            assert data["not_available_reason"], "expected an honest reason when no GPU is detected"
            assert data["gpus"] == []
        print(f"✓ GPU summary honesty contract holds (detected={data['detected']})")


class TestAuthRequired:
    def test_latency_stats_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/ai-monitoring/latency-stats").status_code in (401, 403)

    def test_gpu_summary_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/ai-monitoring/gpu").status_code in (401, 403)

    def test_gpu_timeseries_requires_auth(self):
        assert requests.get(f"{BASE_URL}/api/ai-monitoring/gpu/timeseries?host=x&gpu_index=0").status_code in (401, 403)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
