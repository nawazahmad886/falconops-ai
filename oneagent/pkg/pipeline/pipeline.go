// Package pipeline is the async data pipeline: bounded channels → batching →
// smart sampling → transport, with disk-queue spill on failure (backpressure).
package pipeline

import (
	"context"
	"hash/fnv"
	"log"
	"math/rand"
	"sync"
	"sync/atomic"
	"time"

	"github.com/falconops/oneagent/pkg/buffer"
	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/transport"
)

// Event is the universal payload unit flowing through the pipeline.
type Event struct {
	Kind      string            `json:"kind"` // log|metric|trace
	Service   string            `json:"service"`
	Timestamp string            `json:"timestamp"`
	Data      map[string]any    `json:"data"`
	Tags      map[string]string `json:"tags,omitempty"`
}

type Stats struct {
	Enqueued  uint64 `json:"enqueued"`
	Sent      uint64 `json:"sent"`
	Sampled   uint64 `json:"sampled_out"`
	Spilled   uint64 `json:"spilled_to_disk"`
	Replayed  uint64 `json:"replayed"`
	Dropped   uint64 `json:"dropped"`
	QueueLen  int    `json:"queue_len"`
	BufferLen int    `json:"disk_buffer_segments"`
}

type Pipeline struct {
	cfg     *config.Config
	sender  transport.Sender
	logger  *log.Logger
	ch      chan Event
	dq      *buffer.DiskQueue
	sampler *sampler
	wg      sync.WaitGroup

	enqueued, sent, sampledOut, spilled, replayed, dropped uint64
}

func New(cfg *config.Config, sender transport.Sender, logger *log.Logger) (*Pipeline, error) {
	dq, err := buffer.Open(cfg.BufferDir, int64(cfg.BufferMaxMB)*1024*1024)
	if err != nil {
		return nil, err
	}
	return &Pipeline{
		cfg: cfg, sender: sender, logger: logger,
		ch:      make(chan Event, 8192),
		dq:      dq,
		sampler: newSampler(cfg.SamplingRate),
	}, nil
}

// Emit enqueues an event. Non-blocking: if the channel is full the event is
// spilled straight to the disk queue (backpressure without blocking callers).
func (p *Pipeline) Emit(e Event) {
	atomic.AddUint64(&p.enqueued, 1)
	if e.Kind == "log" && !p.sampler.keep(e) {
		atomic.AddUint64(&p.sampledOut, 1)
		return
	}
	select {
	case p.ch <- e:
	default:
		if err := p.dq.Push([]Event{e}); err != nil {
			atomic.AddUint64(&p.dropped, 1)
		} else {
			atomic.AddUint64(&p.spilled, 1)
		}
	}
}

// Run starts the batcher + disk replay loops.
func (p *Pipeline) Run(ctx context.Context) {
	p.wg.Add(2)
	go p.batchLoop(ctx)
	go p.replayLoop(ctx)
}

func (p *Pipeline) batchLoop(ctx context.Context) {
	defer p.wg.Done()
	batches := map[string][]Event{}
	timer := time.NewTicker(p.cfg.BatchMaxWait())
	defer timer.Stop()
	flush := func(kind string) {
		b := batches[kind]
		if len(b) == 0 {
			return
		}
		batches[kind] = nil
		if err := p.sender.Send(ctx, kind, toPayload(b)); err != nil {
			if derr := p.dq.Push(b); derr != nil {
				atomic.AddUint64(&p.dropped, uint64(len(b)))
			} else {
				atomic.AddUint64(&p.spilled, uint64(len(b)))
			}
			return
		}
		atomic.AddUint64(&p.sent, uint64(len(b)))
	}
	flushAll := func() {
		for kind := range batches {
			flush(kind)
		}
	}
	for {
		select {
		case <-ctx.Done():
			flushAll()
			return
		case <-timer.C:
			flushAll()
		case e := <-p.ch:
			batches[e.Kind] = append(batches[e.Kind], e)
			if len(batches[e.Kind]) >= p.cfg.BatchMaxEvents {
				flush(e.Kind)
			}
		}
	}
}

// replayLoop retries disk-buffered batches with exponential backoff.
func (p *Pipeline) replayLoop(ctx context.Context) {
	defer p.wg.Done()
	backoff := 5 * time.Second
	for {
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
		var events []Event
		ok, err := p.dq.Pop(&events)
		if err != nil || !ok {
			backoff = 10 * time.Second
			continue
		}
		byKind := map[string][]Event{}
		for _, e := range events {
			byKind[e.Kind] = append(byKind[e.Kind], e)
		}
		failed := false
		for kind, b := range byKind {
			if err := p.sender.Send(ctx, kind, toPayload(b)); err != nil {
				failed = true
				_ = p.dq.Push(b) // requeue
			} else {
				atomic.AddUint64(&p.replayed, uint64(len(b)))
			}
		}
		if failed {
			backoff = min(backoff*2, 5*time.Minute)
		} else {
			backoff = 2 * time.Second
		}
	}
}

// Drain flushes remaining in-memory events to disk on shutdown.
func (p *Pipeline) Drain() {
	close(p.ch)
	var rest []Event
	for e := range p.ch {
		rest = append(rest, e)
	}
	if len(rest) > 0 {
		_ = p.dq.Push(rest)
	}
	p.dq.Close()
}

func (p *Pipeline) Stats() Stats {
	return Stats{
		Enqueued: atomic.LoadUint64(&p.enqueued), Sent: atomic.LoadUint64(&p.sent),
		Sampled: atomic.LoadUint64(&p.sampledOut), Spilled: atomic.LoadUint64(&p.spilled),
		Replayed: atomic.LoadUint64(&p.replayed), Dropped: atomic.LoadUint64(&p.dropped),
		QueueLen: len(p.ch), BufferLen: p.dq.Segments(),
	}
}

func toPayload(b []Event) []map[string]any {
	out := make([]map[string]any, 0, len(b))
	for _, e := range b {
		item := map[string]any{"service": e.Service, "timestamp": e.Timestamp, "tags": e.Tags}
		for k, v := range e.Data {
			item[k] = v
		}
		out = append(out, item)
	}
	return out
}

// ── Smart sampling ───────────────────────────────────────
// 1. Probabilistic sampling of low-severity logs (sampling_rate).
// 2. Noise dedup: identical (service, level, message) fingerprints are
//    rate-limited to maxPerWindow occurrences per minute.

type sampler struct {
	rate   float64
	mu     sync.Mutex
	window time.Time
	counts map[uint64]int
}

const maxPerWindow = 25

func newSampler(rate float64) *sampler {
	return &sampler{rate: rate, window: time.Now(), counts: map[uint64]int{}}
}

func (s *sampler) keep(e Event) bool {
	level, _ := e.Data["level"].(string)
	msg, _ := e.Data["message"].(string)
	// never sample out warnings/errors probabilistically
	lowSeverity := level == "DEBUG" || level == "INFO" || level == ""
	if lowSeverity && s.rate < 1.0 && rand.Float64() > s.rate {
		return false
	}
	h := fnv.New64a()
	h.Write([]byte(e.Service))
	h.Write([]byte(level))
	h.Write([]byte(normalizeMsg(msg)))
	fp := h.Sum64()
	s.mu.Lock()
	defer s.mu.Unlock()
	if time.Since(s.window) > time.Minute {
		s.window = time.Now()
		s.counts = map[uint64]int{}
	}
	s.counts[fp]++
	return s.counts[fp] <= maxPerWindow
}

// normalizeMsg strips digits so "timeout after 5001ms" == "timeout after 5002ms".
func normalizeMsg(s string) string {
	if len(s) > 200 {
		s = s[:200]
	}
	out := make([]byte, 0, len(s))
	for i := 0; i < len(s); i++ {
		if s[i] >= '0' && s[i] <= '9' {
			continue
		}
		out = append(out, s[i])
	}
	return string(out)
}

func min(a, b time.Duration) time.Duration {
	if a < b {
		return a
	}
	return b
}
