# RASED (راصد)

Autonomous incident investigation: an alert comes in, RASED retrieves evidence
concurrently across seven synthetic telemetry sources, forms an initial
hypothesis from only what the alert itself contains, revises that hypothesis
once deeper evidence changes the picture, decides severity and escalation
against a cited SOP, and — within hard gates that always require human
approval for anything destructive — proposes or executes a remediation
action. Every step is traced live; every conclusion cites the evidence it
rests on; every action carries the mode it ran under.

**Data is synthetic only, always.** See "Data policy" below.

## Architecture

```
                                    ┌─────────────────────────────┐
                                    │   POST /incidents/trigger    │
                                    │   (KeepHQ-shaped webhook)     │
                                    └───────────────┬───────────────┘
                                                     │
                                                     ▼
                    ┌────────────────────────────────────────────────────────┐
                    │                   LangGraph state machine                │
                    │                                                          │
   suppressed ◄──────────── orchestrate ──► retrieve ──► analyze ──► decide    │
   (storm/dedup)              │                │            │          │      │
                               │                │      ┌─────┴─────┐    │      │
                               │                │       impact│rca      │      │
                               │                │      (concurrent)     │      │
                               │                │                       ▼      │
                               │                │                   execute    │
                               │                │                (ActionAgent) │
                               │                │                       │      │
                               │                │              interrupt()     │
                               │                │           (DESTRUCTIVE only, │
                               │                │            approve/reject    │
                               │                │             API resumes it)  │
                               │                │                       │      │
                               │                └──────────────────► case      │
                               └──────────────────────────────────────►│       │
                                                                        ▼      │
                                                                       done     │
                    └────────────────────────────────────────────────────────┘
                                                     │
                          ┌──────────────────────────┼──────────────────────────┐
                          ▼                           ▼                          ▼
                  db.rased_trace            db.rased_investigations      Jira / Teams
                  (+ Redis pub/sub,               (+ db.rased_cases)      (mock by default,
                   SSE stream)                                            live behind a
                                                                            config gate)
```

Seven adapters (`adapters/`) sit behind one `Adapter.query()` interface, each
bound to a Mongo collection a scenario generator seeds:
`elk · appdynamics · solarwinds · mq · db · cmdb · changes`.

State (`InvestigationState`), evidence, trace, and checkpoints all persist to
MongoDB (`db.rased_*` collections) — a finished or paused investigation is
fully inspectable via the API without re-running anything.

## Adapter swap: mock → live

Every external system RASED touches is behind an interface, so going live is
a config change, never a change to agent logic:

- **Telemetry adapters** (`adapters/*.py`): each is a `MongoSeededAdapter`
  reading synthetic data today. A live variant is a new `Adapter` subclass
  (same `source`, same `query(params) -> ToolResult` contract) registered in
  `adapters/__init__.py`'s `ADAPTERS` dict in place of the mock — nothing
  calling `ADAPTERS[...]` needs to know the difference.
- **Jira / Teams** (`integrations/jira.py`, `integrations/teams.py`): mock is
  the default and is what any demo runs on. `is_live()` requires
  `EXECUTION_MODE == "live"` **and** the adapter's own config (base URL/token
  or webhook URL) to be set — the live branch currently raises
  `NotImplementedError` rather than pretending to call an API that isn't
  wired into this build; replace that branch with a real client when one is
  ready.
- **Action executors** (`actions/executors.py`): every executor simulates its
  effect regardless of `EXECUTION_MODE` — none of the five action targets
  (k8s, MQ, gateway, deployment system, internal suppression) has a real
  backend in this codebase. `EXECUTION_MODE` here records which config gate
  was passed, not that a real system was reached; every `ActionResult`
  carries it either way, so the audit trail stays honest about what actually
  happened.
- **SOP retrieval** (`policy/`): `BM25Retriever` is the default and has no
  external dependency. `VectorRetriever` sits behind the same
  `SOPRetriever` interface, selected via `RASED_SOP_RETRIEVER_BACKEND=vector`.

## Execution safety

`config.EXECUTION_MODE` defaults to `"simulated"`. The only way to reach
`"live"` is setting `RASED_EXECUTION_MODE=live` explicitly — there is no
other code path to it. Every `ActionResult` records the mode it ran under.
`config.DEMO_MODE` (`RASED_DEMO_MODE=1`) is a separate switch: it replays
cached LLM responses instead of calling a real provider, so a slow or
rate-limited model never stalls a live run — it has no effect on
`EXECUTION_MODE` or on whether an action actually touches anything.

## Data policy

The scenario generator (`data/generator.py`, `data/scenarios.py`) never
produces real hostnames, IPs, endpoints, or identifiers — enforced by a test
(`test_rased_phase0.py::TestNoRealIdentifiers`) that scans every generated
string for IP/FQDN-shaped patterns. `redaction.py` is a second, independent
boundary: every string handed to an LLM passes through `sanitize_for_llm()`
first, which masks IPs, FQDNs, emails, AWS keys, JWTs, credential
assignments, and credit-card-shaped digit runs. On well-formed synthetic
data this is a no-op by design — the boundary exists so it's real and
demonstrable, not a claim resting on "nothing real is connected."

## Known risk surface

LangGraph's exact API (checkpointer internals, `interrupt()`/`Command`
resume semantics, `StateGraph.compile()`/`.ainvoke()` argument shapes) was
implemented against documented/typical shape, not against an actually-
imported `langgraph` package — no local Python interpreter was available
while building this. The specific files carrying that risk, in descending
order of how deep into LangGraph's internals they reach:

1. `graph/checkpointer.py` — `BaseCheckpointSaver` subclass
2. `agents/action.py` — the one `interrupt()` call site
3. `graph/runner.py` — `Command(resume=...)` and `.ainvoke()`
4. `graph/workflow.py` — `StateGraph`/`END` (most stable part of the API
   historically, so lowest risk of the four)

Every test file that exercises one of these paths (`test_rased_phase1.py`'s
`TestBuildGraph`, `test_rased_phase4.py`'s `TestInterruptImportPath`) is
guarded with `pytest.importorskip` so a real `langgraph` install is required
to run them — the rest of each test file's coverage (agent logic, hard
gates, tiering, redaction, retrieval) does not depend on LangGraph importing
at all. Run the full suite against a real `pip install langgraph==1.2.10` as
the first verification step before trusting the graph/approval-resume path.
