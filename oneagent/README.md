# FalconOpsAI OneAgent

Universal, lightweight observability agent for the FalconOpsAI platform.
Auto-discovers services, collects **logs / metrics / traces**, and ships them to
your FalconOpsAI backend (SaaS or on-prem) — with a footprint budget of
**< 2% CPU and < 100 MB RAM**.

```
┌────────────────────────── host / node ──────────────────────────┐
│  auto-discovery (/proc) ──┐                                     │
│  logs plugin  (tail)  ────┤   async pipeline    ┌─ disk queue ─┐│
│  metrics plugin (/proc) ──┼─▶ batch ▶ sample ▶──┤  (fallback)  ││
│  traces plugin (OTLP) ────┘                     └──────┬───────┘│
│  ebpf (kernel-lite / CO-RE)                            │        │
└────────────────────────────────────────────────────────┼────────┘
                             gzip JSON + TLS + X-API-Key ▼
                    FalconOpsAI  /api/ingest/{logs,metrics,traces}
```

## Features

| Feature | How |
|---|---|
| **Service auto-discovery** | `/proc` scan; detects Node.js, Python, Java, Go, .NET; auto service naming (jar/script/cwd heuristics), container-id tagging |
| **Log collection** | Tails `/var/log`, Docker json-file logs, Kubernetes pod logs; level + service filters; batch + gzip |
| **Metrics** | Host CPU/mem/disk/network/load + per-service process CPU/RSS; app request-rate, error-rate, p95/p99 latency derived from traces |
| **Distributed tracing** | Built-in OTLP/HTTP receiver on `127.0.0.1:4318` — point any OpenTelemetry SDK at it, zero app code changes; W3C traceparent propagation preserved |
| **eBPF** | Default: kernel-lite (/proc TCP states, retransmits, ctx switches). Full CO-RE probe (`pkg/ebpf/probe.c`) for syscall latency via `go build -tags ebpf` |
| **Plugin architecture** | `logs`, `metrics`, `traces` are independent plugins; enable/disable in `agent.yaml` |
| **Data pipeline** | Async bounded channels, batching, disk-queue spill on failure, exponential-backoff replay, oldest-first eviction (backpressure) |
| **Smart sampling** | Probabilistic sampling of DEBUG/INFO (`sampling_rate`), automatic dedup of identical messages (25/min per fingerprint), errors never sampled out |
| **Security** | API-key auth (`X-API-Key`), TLS (custom CA support), `0600` config, systemd hardening |
| **Ops** | `/health` + `/debug` on `127.0.0.1:8126`, `--debug` mode, heartbeat with discovered-services inventory |

## Quick start

### 1. Linux (systemd)

```bash
curl -sL https://<falconops-host>/api/oneagent/install.sh | \
  FALCONOPS_API_KEY=<your-key> \
  FALCONOPS_BACKEND_URL=https://<falconops-host> bash
```

Generate an API key in **FalconOps → Downloads → OneAgent → Generate API Key**.

### 2. Docker

```bash
docker run -d --name falconops-oneagent \
  -e FALCONOPS_API_KEY=<your-key> \
  -e FALCONOPS_BACKEND_URL=https://<falconops-host> \
  -v /proc:/host/proc:ro -e HOST_PROC=/host/proc \
  -v /var/log:/var/log:ro \
  -v /var/lib/docker/containers:/var/lib/docker/containers:ro \
  --pid=host --network=host \
  falconops/oneagent:latest
```

### 3. Kubernetes (DaemonSet)

```bash
kubectl create ns falconops
kubectl -n falconops create secret generic falconops-oneagent \
  --from-literal=api-key=<your-key> \
  --from-literal=backend-url=https://<falconops-host>
kubectl apply -f deploy/kubernetes/daemonset.yaml
```

## Sending traces (zero code changes)

Any OpenTelemetry-instrumented app just needs:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
export OTEL_SERVICE_NAME=my-service
```

The agent receives spans locally, forwards them to FalconOpsAI, and computes
`app.request_rate`, `app.error_rate`, `app.latency_p95_ms`, `app.latency_p99_ms`
per service automatically.

## Configuration

See [`agent.yaml`](agent.yaml). Required: `api_key`, `backend_url`.
Env overrides: `FALCONOPS_API_KEY`, `FALCONOPS_BACKEND_URL`, `FALCONOPS_HOSTNAME`.

## Building from source

```bash
go build -o falconops-oneagent ./cmd/agent          # standard build
go build -tags ebpf ./cmd/agent                     # with full eBPF loader
go test ./...                                       # unit tests
```

Full eBPF probe (optional, kernel >= 5.4 + BTF):

```bash
clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -c pkg/ebpf/probe.c -o probe.o
```

## Payload format

```
POST /api/ingest/logs      {host, environment, agent_version, batch: [{service, timestamp, level, message, tags}]}
POST /api/ingest/metrics   {host, ..., batch: [{service, timestamp, name, value, unit, tags}]}
POST /api/ingest/traces    {host, ..., batch: [{service, timestamp, trace_id, span_id, parent_span_id, name, duration_ms, status, attributes}]}
POST /api/ingest/heartbeat {host, agent_version, services: [{name, runtime}]}
```

Auth: `X-API-Key: <key>` header on every request. Bodies are gzip-compressed JSON.

## Transport

HTTP(S) is the active transport (gzip JSON, 3 retries + disk-queue fallback).
The `transport.Sender` interface is transport-agnostic — a gRPC sender can be
dropped in when the backend exposes a gRPC ingest service.

## Local ops

```bash
curl -s http://127.0.0.1:8126/health | jq   # status, plugins, pipeline stats
curl -s http://127.0.0.1:8126/debug | jq    # redacted config + discovered services
journalctl -u falconops-oneagent -f          # logs (systemd install)
```

## Performance envelope

- systemd unit enforces `CPUQuota=20%` (of one core) and `MemoryMax=128M`
- K8s DaemonSet limits: `cpu: 200m`, `memory: 128Mi`
- All I/O is non-blocking; senders use bounded retries; buffers are size-capped
