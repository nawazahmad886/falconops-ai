// Package traces is the tracing plugin. It runs a local OTLP/HTTP receiver
// (default 127.0.0.1:4318) so any OpenTelemetry-instrumented app on the host
// exports spans with ZERO backend config changes — just point OTEL_EXPORTER_OTLP_ENDPOINT
// at the agent. Spans are normalized, forwarded to FalconOpsAI, and aggregated
// into per-service app metrics: request rate, error rate, latency p95/p99.
// W3C traceparent propagation is preserved end-to-end (agent is pass-through).
package traces

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sort"
	"strconv"
	"sync"
	"time"

	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/pipeline"
)

type Plugin struct {
	cfg    *config.Config
	pipe   *pipeline.Pipeline
	logger *log.Logger
	server *http.Server
	cancel context.CancelFunc

	mu  sync.Mutex
	agg map[string]*svcWindow // service → rolling window
}

type svcWindow struct {
	durations []float64
	errors    int
	total     int
}

func New(cfg *config.Config, pipe *pipeline.Pipeline, logger *log.Logger) *Plugin {
	return &Plugin{cfg: cfg, pipe: pipe, logger: logger, agg: map[string]*svcWindow{}}
}

func (p *Plugin) Name() string { return "traces" }

func (p *Plugin) Start(ctx context.Context) error {
	ctx, p.cancel = context.WithCancel(ctx)
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/traces", p.handleOTLP)
	p.server = &http.Server{Addr: p.cfg.OTLPListenAddr, Handler: mux, ReadTimeout: 15 * time.Second}
	go func() {
		if err := p.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			p.logger.Printf("traces: OTLP receiver failed: %v", err)
		}
	}()
	go p.flushAppMetrics(ctx)
	p.logger.Printf("traces: OTLP/HTTP receiver on %s (set OTEL_EXPORTER_OTLP_ENDPOINT=http://%s)",
		p.cfg.OTLPListenAddr, p.cfg.OTLPListenAddr)
	return nil
}

func (p *Plugin) Stop() {
	if p.cancel != nil {
		p.cancel()
	}
	if p.server != nil {
		shutCtx, done := context.WithTimeout(context.Background(), 3*time.Second)
		defer done()
		_ = p.server.Shutdown(shutCtx)
	}
}

// ── OTLP/HTTP JSON ingest ─────────────────────────────────

type otlpPayload struct {
	ResourceSpans []struct {
		Resource struct {
			Attributes []otlpAttr `json:"attributes"`
		} `json:"resource"`
		ScopeSpans []struct {
			Spans []otlpSpan `json:"spans"`
		} `json:"scopeSpans"`
	} `json:"resourceSpans"`
}

type otlpAttr struct {
	Key   string `json:"key"`
	Value struct {
		StringValue string `json:"stringValue"`
	} `json:"value"`
}

type otlpSpan struct {
	TraceID           string     `json:"traceId"`
	SpanID            string     `json:"spanId"`
	ParentSpanID      string     `json:"parentSpanId"`
	Name              string     `json:"name"`
	Kind              int        `json:"kind"`
	StartTimeUnixNano string     `json:"startTimeUnixNano"`
	EndTimeUnixNano   string     `json:"endTimeUnixNano"`
	Attributes        []otlpAttr `json:"attributes"`
	Status            struct {
		Code int `json:"code"`
	} `json:"status"`
}

func (p *Plugin) handleOTLP(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 8<<20))
	if err != nil {
		http.Error(w, "read error", http.StatusBadRequest)
		return
	}
	var payload otlpPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		http.Error(w, "expected OTLP/HTTP JSON", http.StatusBadRequest)
		return
	}
	now := time.Now().UTC().Format(time.RFC3339Nano)
	for _, rs := range payload.ResourceSpans {
		service := "unknown"
		for _, a := range rs.Resource.Attributes {
			if a.Key == "service.name" && a.Value.StringValue != "" {
				service = a.Value.StringValue
			}
		}
		for _, ss := range rs.ScopeSpans {
			for _, sp := range ss.Spans {
				durMs := nsDiffMs(sp.StartTimeUnixNano, sp.EndTimeUnixNano)
				isErr := sp.Status.Code == 2
				attrs := map[string]string{}
				for _, a := range sp.Attributes {
					if a.Value.StringValue != "" {
						attrs[a.Key] = a.Value.StringValue
					}
				}
				p.pipe.Emit(pipeline.Event{
					Kind: "trace", Service: service, Timestamp: now,
					Data: map[string]any{
						"trace_id": sp.TraceID, "span_id": sp.SpanID,
						"parent_span_id": sp.ParentSpanID, "name": sp.Name,
						"kind": sp.Kind, "duration_ms": durMs,
						"status": statusStr(isErr), "attributes": attrs,
						"start_time_unix_nano": sp.StartTimeUnixNano,
					},
					Tags: map[string]string{"host": p.cfg.Hostname},
				})
				p.record(service, durMs, isErr)
			}
		}
	}
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("{}"))
}

func (p *Plugin) record(service string, durMs float64, isErr bool) {
	p.mu.Lock()
	defer p.mu.Unlock()
	win := p.agg[service]
	if win == nil {
		win = &svcWindow{}
		p.agg[service] = win
	}
	win.total++
	if isErr {
		win.errors++
	}
	if len(win.durations) < 5000 { // bound memory
		win.durations = append(win.durations, durMs)
	}
}

// flushAppMetrics emits request_rate / error_rate / latency p95/p99 every 30s.
func (p *Plugin) flushAppMetrics(ctx context.Context) {
	const window = 30 * time.Second
	t := time.NewTicker(window)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
		}
		p.mu.Lock()
		snapshot := p.agg
		p.agg = map[string]*svcWindow{}
		p.mu.Unlock()
		now := time.Now().UTC().Format(time.RFC3339Nano)
		for service, win := range snapshot {
			if win.total == 0 {
				continue
			}
			emit := func(name string, value float64, unit string) {
				p.pipe.Emit(pipeline.Event{
					Kind: "metric", Service: service, Timestamp: now,
					Data: map[string]any{"name": name, "value": value, "unit": unit},
					Tags: map[string]string{"host": p.cfg.Hostname, "source": "traces"},
				})
			}
			emit("app.request_rate", round2(float64(win.total)/window.Seconds()), "req/s")
			emit("app.error_rate", round2(float64(win.errors)/float64(win.total)*100), "%")
			sort.Float64s(win.durations)
			emit("app.latency_p95_ms", percentile(win.durations, 0.95), "ms")
			emit("app.latency_p99_ms", percentile(win.durations, 0.99), "ms")
		}
	}
}

func percentile(sorted []float64, q float64) float64 {
	if len(sorted) == 0 {
		return 0
	}
	idx := int(q * float64(len(sorted)-1))
	return round2(sorted[idx])
}

func nsDiffMs(startNs, endNs string) float64 {
	s, err1 := strconv.ParseUint(startNs, 10, 64)
	e, err2 := strconv.ParseUint(endNs, 10, 64)
	if err1 != nil || err2 != nil || e < s {
		return 0
	}
	return round2(float64(e-s) / 1e6)
}

func statusStr(isErr bool) string {
	if isErr {
		return "ERROR"
	}
	return "OK"
}

func round2(v float64) float64 { return float64(int64(v*100+0.5)) / 100 }

var _ = fmt.Sprintf // keep fmt for debug builds
