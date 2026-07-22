# FalconOps AI — Component Guide

FalconOps AI is organized as one FastAPI backend (`backend/app/`) with ~90 service
modules and ~90 route files, and one React frontend (`frontend/src/`) with ~90 pages.
Documenting every individual file would be noise, not signal — this guide groups
components by functional subsystem, briefs what each one actually does, and points at
the specific files to open if you need to go deeper.

Every subsystem below is described as it actually behaves in the code today — not as a
roadmap or aspiration. Where a capability is a stub or dry-run only, that's stated
explicitly.

---

## 1. Core Platform

**Auth & tenancy** — `backend/app/routes/auth.py`, `tenants.py`, `rbac_routes.py` /
`services/rbac_service.py`, `tenant_routing_service.py`. JWT-based login/signup with
per-IP rate limiting (`rate_limiter_service.py`) and real-time security-event logging on
every login/signup attempt (feeds the threat-detection pipeline below). Multi-tenant
routing resolves a tenant from the request's Host header or a `/t/{slug}` path prefix.
RBAC enforces role-based route access; role escalation on tenant-user creation requires
an existing global admin.

**Billing & licensing** — `billing_routes.py` (Stripe integration), `licensing_service.py`
/ `licenses.py` (license key issuance/validation), `monetization_routes.py`.

**Admin console** — `AdminConsolePage.js` / `admin_control_routes.py`: tenant
management, feature flags (`feature_flags_service.py`), email templates, plans.

---

## 2. Monitoring & Observability

**Server & synthetic monitoring** — `monitoring_service.py`, `synthetic_monitoring_service.py`,
`uptime_monitor_service.py`, `check_node_service.py`: real scheduled checks (HTTP/ping/
port) against registered servers and URLs, uptime % and SLA computation
(`sla_service.py`), multi-region check nodes.

**Metrics** — `metrics_timeseries_service.py` is the real TSDB-backed store (VictoriaMetrics
if reachable, MongoDB fallback otherwise) that every anomaly/capacity/health-score
feature below reads from. `metrics_service.py`/`metrics_observability.py` are the
query/dashboard layer over it.

**Database monitoring** — `db_monitoring.py`, `query_analyzer_service.py`
(SQL-text analysis for missing indexes/slow patterns — static analysis, not a live DB
connection).

**Health rules & detection rules** — `health_rule_engine.py` / `health_rule_evaluator.py`,
`detection_rules_service.py`: user-defined threshold rules evaluated against real
metric/log data to raise alerts.

---

## 3. AIOps, Correlation & Incident Management

**Alert engine** — `alert_engine.py`: alert lifecycle (trigger → acknowledge → resolve),
fires real-time hooks into workflow "Problem triggers" (§7) and autonomous investigation
for critical/high alerts.

**Correlation engines** — `ai_correlation.py` (legacy, writes to `db.incidents`) and
`smart_correlation_engine.py` (newer, writes to `db.incidents_engine`) both group
related alerts by topology dependency, metric pattern, severity cascade, host, or
service, sharing one grouping implementation (`correlation_shared.py`). Alerts grouped
by a shared topology dependency get a structured `root_cause_entity` (a real topology
node, with a confidence score based on whether that node itself is alerting) — not just
a prose guess.

**Incident engine** — `incident_engine.py`: incident CRUD, severity/priority scoring,
SLA-breach deadlines per severity, `get_most_critical_incident()` for one-click "what's
on fire right now."

**Autonomous ops orchestrator** — `autonomous_ops_orchestrator.py`: on a new
correlated/critical incident, runs a real investigate → recommend → (human-approved)
remediate → validate → escalate-on-SLA-breach loop, recording real outcomes
(`db.incident_outcomes`) so future recommendations can learn from what actually worked.

**Multi-agent RCA chain** — `rca_chain_service.py`: a 4-step chain (Root Cause Agent →
Root Cause Details Agent → Data Analysis Agent → Synthesis) for one incident, each step's
evidence recorded separately for the UI to show progressively, with automatic
retry-on-weak-evidence in the log-analysis step.

**Topology & impact analysis** — `topology_service.py` (service dependency graph,
auto-discovered from real trace parent/child spans), `impact_analysis_engine.py` /
`impact_analysis_service.py` (blast-radius BFS, system risk scoring).

**Anomaly detection** — `anomaly_detection_engine.py`: a real IsolationForest + ensemble
model over `metrics_timeseries_service` data, reused by API-abuse detection, capacity
alerts, and elsewhere rather than re-implemented per feature.

**Capacity forecasting** — `capacity_prediction_engine.py`: real linear-regression trend
analysis (scipy) over historical CPU/memory/disk metrics, producing time-to-threshold
predictions — not a point-in-time snapshot.

---

## 4. APM & Distributed Tracing

**OTLP ingestion** — `backend/app/routes/otlp_routes.py`: accepts real OpenTelemetry
OTLP/HTTP+JSON traces/metrics/logs at `POST /api/otel/v1/{traces,metrics,logs}`. Spans
are normalized into `db.otel_spans`/`db.otel_traces`, including real exception
type/message captured from OTel span events when the instrumented app recorded one.
Every span batch also auto-updates the real service-dependency graph
(`db.service_dependencies`, `db.topology_nodes/edges`).

**Service Map** (`APMTracesPage.js`, "Service Map" tab) — a D3 force-directed dependency
graph with real per-node latency/error % badges. Clicking a node opens a correlation
panel (upstream/downstream dependencies, recent traces) with a "View full page" link.

**Service Detail Page** (`ServiceDetailPage.js`, route `/apm/services/:name`) — the
per-service drill-down: AI-computed health score (latency/error-rate/dependency-health/
capacity-risk composite — any signal that isn't available for a service is dropped from
the average, never faked), per-endpoint transaction stats, dependencies, a real error
breakdown (grouped by exception type when captured), and on-demand AI root cause +
recommendations scoped to that one service.

**Trace RCA** — `trace_rca_service.py`: per-trace root-cause chain walking (error
cascade detection, slow-span/hotspot detection) plus a bulk cross-trace anomaly report.

**Legacy APM pipeline** (`apm.py`, `APMPage.js`) — a separate ingestion path
(`POST /api/apm/ingest/*`) for a hypothetical external APM agent. **Nothing in this
codebase currently posts to it** — the dashboard it powers will show real registered
services but empty transaction/error data until an external agent is actually wired up
to it. Prefer the OTLP path above for anything real.

---

## 5. AI Agents & Copilot

Three distinct "agent" mechanisms exist, each real, none faked:

- **Core crew agents** (`ai_agents_service.py`) — `rca`, `summarizer`, `healer`: simple
  prompt-only agents (no tool-calling), with real vector-similarity memory of past
  incidents and outcomes (`recall_similar`/`recall_similar_outcomes`). Run from
  `AIAgentsPage.js`'s "Analyze" tab.
- **Tool-calling specialist agents** — `security_agents_service.py` (Threat Hunting,
  Compliance, Cloud Security, Network, Identity) and `ops_agents_service.py` (API
  Performance, Capacity, SLA Risk, Executive Ops): each gathers real evidence in
  parallel via the shared tool registry (`ai_tools_service.py`) before one LLM call,
  with evidence-capped confidence. A Kubernetes agent was deliberately not built — the
  k8s healing service behind it (§7) is dry-run only with no real cluster client, so
  there's no real state for an agent to reason over. Both families are runnable from
  `AIAgentsPage.js`'s "Specialized" tab.
- **Intelligence / Copilot engine** (`intelligence_agents_service.py`) — the deepest
  one: `incident_analysis()` (single-shot RCA), `copilot_query()` (iterative tool-calling
  loop, up to 3 steps, that re-plans based on what it's already found), unified behind
  `ask()`. This is the real natural-language-to-tool-call engine — **the dedicated
  frontend for it is `AskFalconOpsPage.js`** (chat-style, evidence-handle citations,
  history). `IntelligencePage.js` and `ServiceDetailPage.js` each also have a smaller,
  independent "ask a question" box wired to the same `/api/ai-intelligence/ask`
  endpoint, scoped/embedded for those specific pages.
- **Agent evaluation framework** (`agent_eval_service.py`) — YAML test sets
  (`backend/eval/agent_test_sets/*.yaml`, question + expectations) run against any of
  the agents above, capturing a trajectory (tool calls + answer) and scoring it via
  deterministic checks plus an LLM-as-judge call, with run-over-run regression
  comparison. Run from `AIAgentsPage.js`'s "Eval" tab.

---

## 6. Security & SOC

**Threat detection** — `security_service.py`: real rule-based detectors (brute force,
credential stuffing, impossible travel, lateral movement, bot traffic, malicious IP via
a real synced threat-intel feed, API abuse via the real anomaly engine).

**UEBA** — `ueba_service.py`: per-user behavioral risk profiles and insider-threat
candidate identification from real security-event history.

**SOC ingestion & live feed** — `soc_ingestion_service.py` (generic event ingestion +
correlation + secret-exposure scanning on every event), `soc_live_feed.py` (WebSocket
push to `SOCLiveFeedPage.js`).

**MITRE / threat intel / vulnerabilities / compliance** — `mitre_mapping_service.py`
(keyword-based ATT&CK technique classification), `threat_intel_service.py` (real
abuse.ch/Spamhaus IOC feed sync), `vulnerability_service.py` (real NVD CVE sync +
topology-aware priority scoring), `compliance_service.py` (SOC2/ISO27001 control
status — controls without a real backing signal report `"unknown"`, never a fabricated
pass).

**Attack simulation** — `attack_simulator_service.py`: safe, synthetic attack-pattern
generation for testing detection coverage.

**Executive Security Dashboard** — `executive_routes.py` /
`ExecutiveSecurityDashboardPage.js`: composite security score aggregating the above.

---

## 7. Workflow Automation & Runbooks

**Runbook engine** — `runbook_engine.py`: sequential step executor (17+ action types —
HTTP, shell [allowlisted commands only], Kubernetes [simulated, see below],
notification, condition, loop, and `call_agent` which invokes any security/ops/core
agent from §5 and captures its output for later steps).

**Workflow triggers** — `workflow_trigger_service.py`: generalizes runbooks beyond
manual execution — Problem triggers (fire on matching alerts), Event triggers (fire on
matching ingested SOC events), AI-Anomaly triggers (fire on detected threats), and
Schedule triggers (cron/interval/fixed-time, actually polled by a background scheduler
— a previously-dead gap this closed).

**Visual builder** — `WorkflowCanvas.js` (React Flow node-graph editor: one trigger node
+ chained step nodes), `WorkflowTemplateGallery.js`, `RunbooksPage.js`.

**Kubernetes healing** — `k8s_healing_service.py` is **dry-run/plan-preview only** —
it generates `kubectl` command text and logs a simulated result; there is no real
cluster client or execution anywhere in this codebase.

---

## 8. Reporting & Dashboards

`reports_service.py`, `report_generator_service.py`, `report_scheduler_service.py` /
`weekly_report_scheduler_service.py`: uptime/incident/SLA reports, scheduled email
delivery (Resend), custom report builder. `custom_dashboard_routes.py` /
`CustomDashboardPage.js`: user-defined dashboard widgets over real metrics/alerts data.

---

## 9. Enterprise & Integrations

**Client portal** — `client_portal_service.py`: a public-facing status/report view for
external clients, separate from the internal admin app.

**Integrations** — `integration_management_service.py` / `connector_dispatcher.py`:
Slack, PagerDuty, SendGrid, generic webhook, all outbound calls SSRF-guarded
(`ssrf_guard.py`) before dispatch.

**Event bus** — `kafka_pipeline.py` / `kafka_consumers.py`: real Kafka producer/consumer
if `KAFKA_BOOTSTRAP_SERVERS` is reachable, degrading to a MongoDB-backed fallback queue
automatically otherwise — every publisher in the codebase is safe to call regardless of
whether Kafka is actually deployed.

---

## Non-obvious cross-cutting facts worth knowing

- **Two parallel incident/alert data models coexist**: the legacy `db.alerts`/
  `db.incidents` (via `ai_correlation.py`) and the newer `db.alerts_engine`/
  `db.incidents_engine` (via `smart_correlation_engine.py` and `incident_engine.py`).
  They are not merged into one collection — check which route/page you're looking at to
  know which one you're reading.
- **Every background job degrades honestly on missing infrastructure** (no Kafka
  broker, no VictoriaMetrics, network failure fetching a threat-intel feed) — none of
  them crash the app or fabricate data; they log a warning and keep serving whatever
  real data they already have.
- **Nothing auto-executes destructive remediation.** Every agent/runbook/orchestrator
  path in this codebase produces a recommendation or a simulated/dry-run action;
  anything that would actually change infrastructure state requires an explicit human
  trigger.
