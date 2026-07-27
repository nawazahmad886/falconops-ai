"""Backend tests for the Live Call Flow WebSocket feed (iteration 63).

Covers: token gate on /api/traces/live, real cross-service span -> call_flow.event
broadcast (sourced from real OTLP trace ingestion, not simulated), the corrected
hook placement (broadcast happens per-span, before the edges_seen DB-upsert dedup,
so a batch with N real spans on one edge produces N events not 1), and the
existing GET /api/traces/services/dependencies regression.
"""
import os
import json
import time
import uuid
import requests
import pytest
from websockets.sync.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed


def _load_backend_url():
    val = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not val:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    return val.rstrip("/")


BASE_URL = _load_backend_url()
WS_BASE_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
ADMIN = {"email": "admin@falconapps.com", "password": "Admin@123"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _span(span_id, parent_id, name, status_code=1, start_offset_ns=0, dur_ns=40_000_000):
    now_ns = int(time.time() * 1_000_000_000) + start_offset_ns
    span = {
        "traceId": uuid.uuid4().hex,
        "spanId": span_id,
        "name": name,
        "kind": 2,
        "startTimeUnixNano": str(now_ns),
        "endTimeUnixNano": str(now_ns + dur_ns),
        "status": {"code": status_code},
    }
    if parent_id:
        span["parentSpanId"] = parent_id
    return span


def _resource_spans(service, spans, trace_id):
    for s in spans:
        s["traceId"] = trace_id
    return {
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
        "scopeSpans": [{"scope": {"name": "test"}, "spans": spans}],
    }


def _cross_service_payload(trace_id, parent_span_id, child_span_ids, parent_service, child_service, status_code=1):
    """One parent span in `parent_service`, N child spans in `child_service`,
    all sharing one trace — used to test both the single-call and
    multiple-calls-on-one-edge-in-one-batch cases."""
    parent = _span(parent_span_id, None, "call-child")
    children = [_span(cid, parent_span_id, "handle", status_code=status_code) for cid in child_span_ids]
    return {
        "resourceSpans": [
            _resource_spans(parent_service, [parent], trace_id),
            _resource_spans(child_service, children, trace_id),
        ]
    }


def _recv_call_flow_event(ws, expect_source, expect_target, timeout=10, max_messages=20):
    """Drain messages until a matching call_flow.event arrives or we time out."""
    deadline = time.time() + timeout
    for _ in range(max_messages):
        remaining = deadline - time.time()
        if remaining <= 0:
            return None
        try:
            raw = ws.recv(timeout=remaining)
        except (TimeoutError, ConnectionClosed):
            return None
        msg = json.loads(raw)
        if msg.get("type") == "call_flow.event" and msg.get("source") == expect_source and msg.get("target") == expect_target:
            return msg
    return None


# ─────────── WebSocket auth gate ───────────

def test_call_flow_ws_missing_token_rejected():
    with ws_connect(f"{WS_BASE_URL}/api/traces/live") as ws:
        raw = ws.recv(timeout=10)
        msg = json.loads(raw)
        assert msg.get("type") == "error"
        assert "token" in msg.get("error", "")
        with pytest.raises(ConnectionClosed):
            ws.recv(timeout=5)


def test_call_flow_ws_invalid_token_rejected():
    with ws_connect(f"{WS_BASE_URL}/api/traces/live?token=not-a-real-jwt") as ws:
        raw = ws.recv(timeout=10)
        msg = json.loads(raw)
        assert msg.get("type") == "error"
        assert "invalid" in msg.get("error", "")


# ─────────── Real span -> live event ───────────

def test_call_flow_event_broadcast_on_cross_service_span(admin_token):
    parent_service = f"svc-a-{uuid.uuid4().hex[:8]}"
    child_service = f"svc-b-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    parent_span_id = uuid.uuid4().hex[:16]
    child_span_id = uuid.uuid4().hex[:16]

    with ws_connect(f"{WS_BASE_URL}/api/traces/live?token={admin_token}") as ws:
        payload = _cross_service_payload(trace_id, parent_span_id, [child_span_id], parent_service, child_service)
        r = requests.post(f"{BASE_URL}/api/otel/v1/traces", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("accepted") == 2

        event = _recv_call_flow_event(ws, parent_service, child_service)
        assert event is not None, "expected a call_flow.event for the cross-service span"
        assert event["status"] == "OK"
        assert event["trace_id"] == trace_id
        assert event["span_id"] == child_span_id


def test_dependencies_endpoint_still_shows_edge(admin_token):
    """Regression: the existing service_dependencies persistence/read path is
    untouched by the live-broadcast hook."""
    parent_service = f"svc-a-{uuid.uuid4().hex[:8]}"
    child_service = f"svc-b-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    parent_span_id = uuid.uuid4().hex[:16]
    child_span_id = uuid.uuid4().hex[:16]

    payload = _cross_service_payload(trace_id, parent_span_id, [child_span_id], parent_service, child_service)
    r = requests.post(f"{BASE_URL}/api/otel/v1/traces", json=payload, timeout=15)
    assert r.status_code == 200, r.text

    r = requests.get(
        f"{BASE_URL}/api/traces/services/dependencies?hours=1",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    edges = r.json().get("edges", [])
    assert any(e.get("service") == parent_service and e.get("depends_on") == child_service for e in edges)


def test_multiple_spans_same_edge_broadcast_individually(admin_token):
    """A batch with N real spans on the same edge must produce N events, not 1 —
    verifies the broadcast sits before the edges_seen dedup, not after it."""
    parent_service = f"svc-a-{uuid.uuid4().hex[:8]}"
    child_service = f"svc-b-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    parent_span_id = uuid.uuid4().hex[:16]
    child_span_ids = [uuid.uuid4().hex[:16] for _ in range(3)]

    with ws_connect(f"{WS_BASE_URL}/api/traces/live?token={admin_token}") as ws:
        payload = _cross_service_payload(trace_id, parent_span_id, child_span_ids, parent_service, child_service)
        r = requests.post(f"{BASE_URL}/api/otel/v1/traces", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("accepted") == 4  # 1 parent + 3 children

        seen_span_ids = set()
        deadline = time.time() + 15
        while len(seen_span_ids) < 3 and time.time() < deadline:
            try:
                raw = ws.recv(timeout=max(0.1, deadline - time.time()))
            except (TimeoutError, ConnectionClosed):
                break
            msg = json.loads(raw)
            if (msg.get("type") == "call_flow.event" and msg.get("source") == parent_service
                    and msg.get("target") == child_service and msg.get("span_id") in child_span_ids):
                seen_span_ids.add(msg["span_id"])

        assert seen_span_ids == set(child_span_ids), (
            f"expected one event per span on the same edge, got {seen_span_ids}"
        )


def test_call_flow_event_error_status_propagates(admin_token):
    parent_service = f"svc-a-{uuid.uuid4().hex[:8]}"
    child_service = f"svc-b-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    parent_span_id = uuid.uuid4().hex[:16]
    child_span_id = uuid.uuid4().hex[:16]

    with ws_connect(f"{WS_BASE_URL}/api/traces/live?token={admin_token}") as ws:
        payload = _cross_service_payload(
            trace_id, parent_span_id, [child_span_id], parent_service, child_service, status_code=2,
        )
        r = requests.post(f"{BASE_URL}/api/otel/v1/traces", json=payload, timeout=15)
        assert r.status_code == 200, r.text

        event = _recv_call_flow_event(ws, parent_service, child_service)
        assert event is not None
        assert event["status"] == "ERROR"
