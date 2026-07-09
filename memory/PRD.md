# FalconOps AI — Product Requirements Document

## Original Problem Statement
FalconOps AI: unified enterprise-grade platform combining AIOps, SIEM, Threat Detection, and Enterprise Reporting. Evolved through 38 phases into an AI-driven observability platform with APM/OTLP tracing, AI RCA, multi-agent AI monitoring, N8n automation, AWS deployment wizards, monetization/billing portal, and on-prem installation bundle.

## Users / Personas
- NOC/SRE engineers (dashboards, monitors, incident triage, natural-language debugging)
- Security analysts (SIEM, UEBA, SOC feed, attack simulator)
- Platform admins (Admin Control Console, billing, licensing, tenants)
- Clients (client portal, executive reports)

## Credentials
- Admin: admin@falconapps.com / Admin@123
- Viewer: test@falconapps.com / testpass123

## Architecture
- Backend: FastAPI (`/app/backend/app/{routes,services,models,core,utils}`), MongoDB, WebSockets
- Frontend: React + Tailwind + Shadcn, EnterpriseLayout module-based nav
- LLM: pluggable provider (`llm_provider_service.py`) — Ollama (on-prem) / OpenAI / Anthropic / Gemini / Emergent key / rule_based fallback; pre-flight injection guard built in; auto-instruments every call into AI Monitoring
- RAG: ChromaDB embedded (`/app/backend/data/chroma`) + sentence-transformers all-MiniLM-L6-v2 (shared with vector_memory_service)

## Completed (latest first)
### Phase 39 — FalconOpsAI OneAgent (July 2026) ✅ tested (iteration_64, 19/19 backend + frontend 100%)
- Production-grade Go observability agent at `/app/oneagent` (Dynatrace-style OneAgent):
  - Service auto-discovery via /proc (Node.js/Python/Java/Go/.NET, auto-naming, container tagging)
  - Plugins (enable/disable via agent.yaml): logs (tail /var/log + Docker + K8s, level/service filters), metrics (host + per-process), traces (built-in OTLP/HTTP receiver :4318 → zero-code-change tracing; app req-rate/error-rate/p95/p99 derived from spans)
  - Async pipeline: batching, smart sampling (prob. sampling + dedup 25/min/fingerprint, errors never dropped), disk queue spill + backoff replay, oldest-first eviction
  - eBPF: kernel-lite /proc fallback + CO-RE probe.c + cilium/ebpf loader behind `ebpf` build tag
  - Transport: HTTPS gzip JSON, X-API-Key, TLS custom CA, 3 retries; Sender interface for future gRPC
  - Ops: /health + /debug (:8126), --debug, heartbeat with service inventory; unit tests pass (config/buffer/discovery/sampling)
  - Deploy: install.sh (systemd, CPUQuota=20%/MemoryMax=128M), Dockerfile, K8s DaemonSet; static binaries amd64+arm64 (~7MB) + src tarball in /app/backend/static/agents/oneagent/
- Backend: `oneagent_routes.py` — POST /api/ingest/{logs,metrics,traces,heartbeat} (X-API-Key auth, gzip support, maps into db.logs/metrics_timeseries/otel_spans+otel_traces/oneagent_agents); /api/oneagent/keys CRUD (admin), /agents, public downloads (install.sh, binary?arch=, source)
- Frontend: featured OneAgent card on /download — API key generation (shown once), install command, binary/source downloads
- E2E verified: real compiled binary ran against live backend; discovery+logs+metrics+OTLP traces+heartbeat all landed in Mongo

### Phase 38 — AI Intelligence Layer (July 2026) ✅ tested (iteration_63, 100%)
- Tooling interface (`ai_tools_service.py`): get_logs, get_metrics, get_traces, get_deployments, get_incidents + execute_tool dispatcher with param whitelisting. Agents access data ONLY via tools.
- Incident Analysis Agent (`intelligence_agents_service.py`): "Why is service X slow?" → parallel tool gathering + RAG similar incidents → structured {summary, evidence, confidence, recommended_actions}; analyses persisted in `ai_intelligence_analyses` and fed back into RAG memory.
- Monitoring Copilot Agent: NL → planner (LLM→JSON tool call, regex fallback) → tool execution → structured answer.
- Lightweight RAG (`rag_service.py`): ChromaDB embedded, collections falcon_incident_history + falcon_recent_logs; reindex endpoint.
- Routes: POST /api/ai-intelligence/ask (auto|incident|copilot), GET /tools, POST /tools/{name}/execute, GET /services, GET /history, GET /analysis/{id}, GET /rag/stats, POST /rag/reindex.
- UI: `/ask-falconops` page (chat + AI Insights panel: confidence gauge, evidence, recommended actions, similar past incidents, tool-call transparency) — first item in AI Observability sidebar.
- AI self-observability: free via chat_completion auto-instrumentation (prompts, outputs, latency, failures → ai_monitoring_events).
- NOTE: Pre-flight regex injection block (previously listed P0) was found ALREADY IMPLEMENTED in chat_completion() — verified present.

### Phases 34–37 (earlier this cycle)
- Phase 37: AI Log Analyzer MVP (chunking, caching, LLM verdicts, UI tab)
- Phase 36: Code quality audit fixes (complexity, secrets → conftest)
- Phase 35: AI Observability v2 (10 agents: hallucination, injection, cost, performance, quality, PII, toxicity, policy, drift, security + WS live feed)
- Phase 34: Landing/Pricing/Auth funnel fixes
- Phases 1–33: core AIOps, SIEM, APM/OTLP, RCA engine, N8n automation, AWS wizard, monetization, on-prem bundle, reports, multi-tenancy (see git history)

## Backlog
### P1
- N8n auto-quarantine + "Remediate via N8n" button in AI Log Analyzer (backend wiring was lost between sessions — needs implementation in log_analyzer_service/routes + LogAnalyzerTab.js)
- Safe Automation Phase 2: Auto-Remediation Agent for AI Intelligence Layer (approval-gated in SaaS, direct exec on-prem) — user's Step 9
### P2
- Refactor AdminControlConsole.js (1300+ LOC) and EventAnalyzerPage.js (1894+ LOC)
- Arabic Translation & RTL support
- RAG: periodic background reindex of recent logs (currently manual via button)
- OneAgent hardening (from code review): hash API keys at rest, rate-limit /api/ingest/*; agents inventory UI page; gRPC transport; publish Docker image

## 3rd Party Integrations
- Emergent LLM Key (AI Copilot, 10-agent observability, Log Analyzer, Intelligence Layer)
- Stripe (user key), Resend (sandbox/mocked), N8n webhooks (UI-configured), Ollama (on-prem option)

## Key DB Collections
logs, metrics_timeseries, otel_traces/otel_spans, incidents, ai_monitoring_events, ai_monitoring_policies, ai_intelligence_analyses (new), n8n_configs, vector_memory
