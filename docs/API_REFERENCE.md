# FalconOps AI — API Reference for External Integrators

This is the previously-missing "integrate WITH FalconOps" documentation — everything
below reflects the real, currently-deployed API, verified against the route source,
not aspirational. For the full, always-current endpoint catalog (every route, every
request/response schema), use the auto-generated interactive docs:

- Swagger UI: `{your-falconops-url}/docs`
- ReDoc: `{your-falconops-url}/redoc`
- Raw OpenAPI schema: `{your-falconops-url}/openapi.json`

This document is the curated "getting started" guide that sits in front of those —
read this first to understand authentication and the handful of endpoints most
third-party integrations actually need, then use `/docs` for exhaustive detail on
any specific endpoint.

## Versioning and stability

There is no formal API version prefix (`/v1/...`) or deprecation policy today —
endpoints are `/api/{resource}/...`. Treat this API as pre-1.0: breaking changes are
possible between releases. If you're building a production integration, pin to a
specific FalconOps release and re-test on upgrade rather than assuming stability.

## Authentication

FalconOps has two distinct auth mechanisms depending on what you're doing — there is
no single unified "API key" system for all endpoints today.

### 1. JWT bearer token (the general REST API)

Most endpoints (`require_auth`/`require_admin` in the route source) expect a JWT
obtained by logging in:

```bash
curl -X POST https://your-falconops-url/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "..."}'
# -> {"access_token": "...", "token_type": "bearer", ...}
```

Use the returned token on every subsequent request:

```
Authorization: Bearer <access_token>
```

There is currently no long-lived, non-expiring "service account" API key for the
general REST API — a real gap if you're building an unattended integration that
can't handle interactive login. Today, the workaround is a dedicated service-account
user whose credentials your integration stores securely and re-authenticates with as
needed (tokens expire; check `/docs` → `/api/auth/login`'s response for the actual
expiry).

### 2. Per-agent API keys (data-ingestion agents only)

A few specific ingestion agents use their own long-lived `X-API-Key` header instead
of a JWT — e.g. the DB Monitoring agent (`app/routes/db_monitoring.py`):

```
X-API-Key: <key issued when the agent/instance was registered>
```

These keys are scoped to one integration/instance, not general API access. Do not
assume an X-API-Key issued for one agent works against unrelated endpoints — it
doesn't; each ingestion route validates its own key independently.

### 3. Unauthenticated ingestion (OTLP only)

The OpenTelemetry trace/metric/log ingestion endpoints (see below) are
deliberately public — no auth header required — matching how most self-hosted OTLP
collectors are deployed. If you're exposing FalconOps beyond a trusted network,
put these behind your own network-level access control (an API gateway, mTLS,
IP allowlist) rather than assuming FalconOps restricts who can POST telemetry to them.

## Sending data in

### Metrics

```
POST /api/metrics            — single metric point
POST /api/metrics/batch      — multiple points in one call (prefer this for volume)
```

Body shape (batch):

```json
{
  "metrics": [
    {"name": "cpu_usage", "value": 42.1, "timestamp": "2026-01-01T00:00:00Z",
     "tags": {"host": "web-01"}, "unit": "%", "service": "web", "host": "web-01"}
  ]
}
```

(Field names verified against `MetricIngest`/`metrics_service.ingest_batch()` — this
is a separate ingestion path from the Connector SDK's own `metrics_timeseries`
collection used by built-in connectors like Prometheus/Azure Monitor/GCP Cloud
Monitoring; both exist in this codebase today, not unified into one.)

Requires `Authorization: Bearer <token>` (JWT).

### Logs

```
POST /api/logs/ingest         — single log line
POST /api/logs/ingest/batch   — multiple lines in one call
```

Requires `Authorization: Bearer <token>` (JWT).

### Distributed traces / metrics / logs via OpenTelemetry

Standard OTLP/HTTP+JSON (not gRPC/protobuf — see the platform enhancement notes for
that known gap) against:

```
POST /api/otel/v1/traces
POST /api/otel/v1/metrics
POST /api/otel/v1/logs
```

Point any standard OpenTelemetry SDK/Collector's OTLP/HTTP exporter at
`https://your-falconops-url/api/otel/v1` with protocol `http/json`. No auth header
— see the "unauthenticated ingestion" note above.

### Database monitoring agent

If you're not using the bundled `falcon_db_agent.py` (see `backend/static/agents/`)
and want to push your own database metrics:

```
POST /api/db-monitoring/metrics/ingest
Headers: X-API-Key: <per-instance key>
Body: {"instance_id": "...", "metrics": {...}, "slow_queries": [...], "locks": [...]}
```

See `GET /api/db-monitoring/agent/config-template` for the exact field shapes the
bundled agent produces — matching that shape is the safest way to stay compatible.

## Getting data out (webhooks)

FalconOps can push events to your own HTTP endpoint via the Custom Webhook
integration (Admin → Integrations → Custom Webhook). Configure a URL, optional
`Authorization` header value, and HTTP method; FalconOps then POSTs a JSON body
per triggered event (alert fired, incident created, etc.) to that URL. There is no
HMAC request-signing today — if you need to verify a request genuinely came from
your FalconOps instance, use a shared-secret `Authorization` header value and
check it strictly rather than trusting source IP alone.

## Rate limits

Rate limiting is real but selective, not a blanket global limit — currently applied
to auth, topology, agent-ingestion, and a few other specific routes
(`rate_limiter_service.py`), not every endpoint. Don't assume every route is
protected from abuse; if you're building a high-volume integration, be a good
citizen (batch requests, respect backoff on errors) regardless of whether a given
endpoint currently enforces a limit.

## Multi-tenancy

If your FalconOps deployment is multi-tenant, most endpoints scope results to the
tenant resolved from your auth token — you generally don't need to pass a
`tenant_id` yourself; it's derived server-side from who you authenticated as.

## Getting help

- Full endpoint catalog with live request/response schemas: `/docs` (Swagger UI)
- Internal admin-facing docs (not this file's audience): `docs/ADMIN_GUIDE.md`,
  `docs/COMPONENTS.md`
