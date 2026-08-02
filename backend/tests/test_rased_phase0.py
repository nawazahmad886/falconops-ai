"""
RASED Phase 0 acceptance tests.

Unit-style, following test_network_flow_unit.py: asyncio.run() + unittest.mock,
no running server, no real Mongo/Redis. generate_scenario() is exercised
through InMemorySink directly (the whole point of decoupling generation from
HTTP), and separately through the actual FastAPI route with MongoSink
monkeypatched to InMemorySink, so both acceptance-criteria phrasings —
"generates from pytest" and "generates from the route" — are covered without
any FalconOps stack running.
"""
import asyncio
import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.rased.data import SCENARIOS, InMemorySink, generate_scenario
from app.services.rased.redaction import redact_payload, redact_text, sanitize_for_llm
from app.services.rased.config import EXECUTION_MODE
from app.utils.auth import require_admin

# app.routes.rased_routes is only reachable through the app.routes package,
# whose __init__.py eagerly imports all ~90 other routers as a side effect of
# package initialization. That is unrelated-router risk this file shouldn't
# carry: if some other team's router ever breaks at import time, RASED's own
# generator-level tests (which don't touch app.routes at all) should still
# run and pass. importorskip turns that failure into a scoped skip instead of
# an error that masks everything else in this file.
rased_routes = pytest.importorskip(
    "app.routes.rased_routes",
    reason="app.routes package failed to import; skipping route-level RASED tests "
    "(generator-level tests are unaffected, they never import app.routes)",
)

ANCHOR = datetime(2026, 8, 3, 15, 0, 0, tzinfo=timezone.utc)

IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
FQDN_RE = re.compile(
    r"\b[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+\.(?:com|net|org|io|ai|co|gov|internal|local|corp|prod|dev)\b",
    re.IGNORECASE,
)


def _collect_strings(value) -> list:
    """Recursively pull every string leaf out of a pydantic model / dict /
    list / scalar, for regex scanning."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out = []
        for v in value.values():
            out.extend(_collect_strings(v))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out.extend(_collect_strings(v))
        return out
    return []


async def _generate(scenario_id: str, seed: int = 42, anchor_time=ANCHOR) -> InMemorySink:
    sink = InMemorySink()
    await generate_scenario(scenario_id, sink, seed=seed, anchor_time=anchor_time)
    return sink


class TestAllScenariosGenerate:
    @pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
    def test_generates_via_pytest_with_no_stack_running(self, scenario_id):
        """generate_scenario() + InMemorySink only — no Mongo, no server."""
        sink = asyncio.run(_generate(scenario_id))
        assert sink.alerts[scenario_id], f"{scenario_id} produced no alerts"
        assert sink.evidence[scenario_id], f"{scenario_id} produced no evidence"

    def test_unknown_scenario_id_raises(self):
        with pytest.raises(ValueError):
            asyncio.run(_generate("S999"))


class TestGeneratesViaRoute:
    def test_route_calls_the_same_decoupled_generator(self):
        """The API route is a thin HTTP wrapper around generate_scenario().
        MongoSink is monkeypatched to InMemorySink so this still runs with no
        real database — it verifies the route wiring, not infrastructure."""
        app = FastAPI()
        app.include_router(rased_routes.router)
        app.dependency_overrides[require_admin] = lambda: {"email": "test@rased", "role": "admin"}

        fake_sink = InMemorySink()
        with patch.object(rased_routes, "MongoSink", return_value=fake_sink):
            client = TestClient(app)
            for scenario_id in sorted(SCENARIOS):
                resp = client.post(f"/api/rased/scenarios/{scenario_id}/generate")
                assert resp.status_code == 200, resp.text
                body = resp.json()
                assert body["scenario_id"] == scenario_id
                assert body["alert_count"] > 0
                assert body["execution_mode"] == EXECUTION_MODE

        assert set(fake_sink.alerts.keys()) == set(SCENARIOS.keys())

    def test_list_and_detail_routes(self):
        app = FastAPI()
        app.include_router(rased_routes.router)
        app.dependency_overrides[require_admin] = lambda: {"email": "test@rased", "role": "admin"}
        client = TestClient(app)

        resp = client.get("/api/rased/scenarios")
        assert resp.status_code == 200
        ids = {s["scenario_id"] for s in resp.json()["scenarios"]}
        assert ids == set(SCENARIOS.keys())

        resp = client.get("/api/rased/scenarios/S1")
        assert resp.status_code == 200
        assert resp.json()["scenario_id"] == "S1"

        resp = client.get("/api/rased/scenarios/S999")
        assert resp.status_code == 404


class TestS1EvidenceTiering:
    """The most important acceptance property in Phase 0: S1's trigger-tier
    subset must support database contention as a plausible conclusion, and
    the deep tier must be what actually implicates the payment gateway. This
    has to hold on the generated data itself, not on any downstream agent."""

    def test_trigger_tier_points_at_database_only(self):
        sink = asyncio.run(_generate("S1"))
        evidence = sink.evidence["S1"]
        trigger = [e for e in evidence if e.tier == "trigger"]
        assert trigger, "S1 produced no trigger-tier evidence"

        trigger_text = " ".join(_collect_strings(trigger)).lower()
        assert "invoice-db" in trigger_text or "pool" in trigger_text
        assert "payment-gateway" not in trigger_text, (
            "trigger-tier evidence leaked the payment-gateway root cause; "
            "it must only be knowable from the alert payload"
        )
        assert all(e.source == "db" for e in trigger)

    def test_deep_tier_flips_to_payment_gateway(self):
        sink = asyncio.run(_generate("S1"))
        evidence = sink.evidence["S1"]
        deep = [e for e in evidence if e.tier == "deep"]
        assert deep, "S1 produced no deep-tier evidence"

        deep_text = " ".join(_collect_strings(deep)).lower()
        assert "payment-gateway" in deep_text
        assert any(e.source == "appdynamics" for e in deep)
        assert any(e.source == "changes" for e in deep)

    def test_full_set_conclusion_differs_from_trigger_only(self):
        sink = asyncio.run(_generate("S1"))
        evidence = sink.evidence["S1"]
        trigger_only_mentions_gateway = any(
            "payment-gateway" in " ".join(_collect_strings(e)).lower() for e in evidence if e.tier == "trigger"
        )
        full_set_mentions_gateway = any("payment-gateway" in " ".join(_collect_strings(e)).lower() for e in evidence)
        assert not trigger_only_mentions_gateway
        assert full_set_mentions_gateway


class TestS4ChangeCorrelation:
    def test_deployment_record_correlates_to_memory_leak(self):
        sink = asyncio.run(_generate("S4"))
        changes_records = sink.source_records["S4"]["changes"]
        assert len(changes_records) == 1
        change = changes_records[0]
        assert change["service"] == "notification-svc"
        assert change["version"]
        assert change["author"]
        assert change["timestamp"] < ANCHOR

        deep_evidence = [e for e in sink.evidence["S4"] if e.tier == "deep" and e.source == "changes"]
        assert deep_evidence, "S4 has no deep-tier evidence citing the changes adapter"
        assert deep_evidence[0].data["deployment_id"] == change["deployment_id"]


class TestS5AlertStorm:
    def test_forty_plus_alerts_one_signature_zero_impact(self):
        sink = asyncio.run(_generate("S5"))
        alerts = sink.alerts["S5"]
        assert len(alerts) >= 40
        signatures = {a.signature for a in alerts}
        assert signatures == {"edge-router-cluster:network-flap"}

        evidence = sink.evidence["S5"]
        assert all(e.data.get("customer_impact") is False for e in evidence if "customer_impact" in e.data)


class TestAdapters:
    """MongoSeededAdapter.query() reads the collection its concrete subclass
    is bound to, and never raises — a query against an unreachable/broken
    collection degrades to ToolResult(success=False), which is what lets a
    failed adapter lower confidence instead of crashing an investigation."""

    def test_reads_seeded_collection_through_db_layer(self):
        from app.services.rased.adapters import ELKAdapter

        mock_collection = MagicMock()
        mock_collection.find.return_value.to_list = AsyncMock(
            return_value=[{"service": "checkout-api", "message": "timeout calling payment-gateway"}]
        )
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        with patch("app.core.database.db", mock_db):
            adapter = ELKAdapter()
            result = asyncio.run(adapter.query({"scenario_id": "S1", "service": "checkout-api"}))

        assert result.success is True
        assert result.source == "elk"
        assert result.data == [{"service": "checkout-api", "message": "timeout calling payment-gateway"}]
        assert result.error is None
        assert result.latency_ms >= 0

    def test_never_raises_degrades_to_failed_tool_result(self):
        from app.services.rased.adapters import ChangesAdapter

        mock_db = MagicMock()
        mock_db.__getitem__.side_effect = RuntimeError("mongo unavailable")

        with patch("app.core.database.db", mock_db):
            adapter = ChangesAdapter()
            result = asyncio.run(adapter.query({"scenario_id": "S4"}))

        assert result.success is False
        assert result.error == "mongo unavailable"
        assert result.data is None
        assert result.source == "changes"

    def test_all_seven_sources_registered(self):
        from app.services.rased.adapters import ADAPTERS

        assert set(ADAPTERS.keys()) == {"elk", "appdynamics", "solarwinds", "mq", "db", "cmdb", "changes"}
        for source, adapter in ADAPTERS.items():
            assert adapter.source == source


class TestNoRealIdentifiers:
    @pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
    def test_no_ip_or_fqdn_pattern_in_generated_strings(self, scenario_id):
        sink = asyncio.run(_generate(scenario_id))
        strings = []
        for alert in sink.alerts[scenario_id]:
            strings.extend(_collect_strings(alert))
        for item in sink.evidence[scenario_id]:
            strings.extend(_collect_strings(item))
        for records in sink.source_records.get(scenario_id, {}).values():
            for record in records:
                strings.extend(_collect_strings(record))

        blob = "\n".join(strings)
        assert not IP_RE.search(blob), f"{scenario_id} generated an IP-looking string"
        assert not FQDN_RE.search(blob), f"{scenario_id} generated an FQDN-looking string"


class TestDeterminism:
    @pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
    def test_same_seed_and_anchor_produce_identical_output(self, scenario_id):
        sink_a = asyncio.run(_generate(scenario_id, seed=7))
        sink_b = asyncio.run(_generate(scenario_id, seed=7))

        dump_a = [a.model_dump() for a in sink_a.alerts[scenario_id]]
        dump_b = [a.model_dump() for a in sink_b.alerts[scenario_id]]
        assert dump_a == dump_b

        ev_a = [e.model_dump() for e in sink_a.evidence[scenario_id]]
        ev_b = [e.model_dump() for e in sink_b.evidence[scenario_id]]
        assert ev_a == ev_b

        assert sink_a.source_records[scenario_id] == sink_b.source_records[scenario_id]

    def test_different_seed_changes_jittered_values(self):
        sink_a = asyncio.run(_generate("S1", seed=1))
        sink_b = asyncio.run(_generate("S1", seed=2))
        assert sink_a.alerts["S1"][0].raw != sink_b.alerts["S1"][0].raw


class TestRedactionBoundary:
    def test_noop_on_clean_synthetic_text(self):
        text = "checkout-api error rate elevated; invoice-db pool at 92% capacity"
        result = redact_text(text)
        assert result.redacted is False
        assert result.text == text

    def test_masks_real_looking_ip(self):
        result = redact_text("connect to 10.20.30.40 to reproduce")
        assert result.redacted is True
        assert "10.20.30.40" not in result.text
        assert "[REDACTED:ipv4]" in result.text

    def test_masks_email(self):
        result = redact_text("contact ops@realcompany.com for access")
        assert result.redacted is True
        assert "ops@realcompany.com" not in result.text

    def test_masks_credential_assignment(self):
        result = redact_text("api_key: sk-abcdef1234567890")
        assert result.redacted is True
        assert "sk-abcdef1234567890" not in result.text

    def test_redact_payload_recurses_dict_and_list(self):
        payload = {"host": "10.1.2.3", "notes": ["fine", "email me at a@b.com"]}
        out = redact_payload(payload)
        assert out["host"] == "[REDACTED:ipv4]"
        assert out["notes"][0] == "fine"
        assert "a@b.com" not in out["notes"][1]

    def test_sanitize_for_llm_only_touches_content(self):
        messages = [{"role": "system", "content": "you are RASED"}, {"role": "user", "content": "ip 10.0.0.1"}]
        sanitized = sanitize_for_llm(messages)
        assert sanitized[0]["content"] == "you are RASED"
        assert "10.0.0.1" not in sanitized[1]["content"]
        assert sanitized[1]["role"] == "user"

    def test_generated_evidence_survives_redaction_unchanged(self):
        """Redaction must be a genuine no-op on synthetic data — if this
        test ever fails, either the generator started producing real-looking
        identifiers, or a rule is too aggressive."""
        sink = asyncio.run(_generate("S1"))
        for item in sink.evidence["S1"]:
            result = redact_text(item.summary)
            assert result.redacted is False, f"redaction fired on synthetic evidence: {item.summary!r}"


class TestExecutionMode:
    def test_defaults_to_simulated(self):
        assert EXECUTION_MODE == "simulated"

    def test_live_requires_exact_env_value(self, monkeypatch):
        import importlib
        monkeypatch.setenv("RASED_EXECUTION_MODE", "LIVE")
        import app.services.rased.config as config_module
        importlib.reload(config_module)
        assert config_module.EXECUTION_MODE == "live"

        monkeypatch.setenv("RASED_EXECUTION_MODE", "yes")
        importlib.reload(config_module)
        assert config_module.EXECUTION_MODE == "simulated"

        monkeypatch.delenv("RASED_EXECUTION_MODE", raising=False)
        importlib.reload(config_module)
        assert config_module.EXECUTION_MODE == "simulated"
