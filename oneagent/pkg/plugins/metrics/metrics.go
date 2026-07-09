// Package metrics is the metrics-collection plugin: host metrics (CPU, memory,
// disk, network) plus per-discovered-service process metrics (cpu%, rss).
package metrics

import (
	"context"
	"log"
	"time"

	"github.com/falconops/oneagent/pkg/collector"
	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/discovery"
	"github.com/falconops/oneagent/pkg/pipeline"
)

type Plugin struct {
	cfg    *config.Config
	pipe   *pipeline.Pipeline
	disc   *discovery.Discovery
	logger *log.Logger
	sys    *collector.SystemCollector
	cancel context.CancelFunc

	prevProcJiffies map[int]uint64
	prevProcAt      time.Time
}

func New(cfg *config.Config, pipe *pipeline.Pipeline, disc *discovery.Discovery, logger *log.Logger) *Plugin {
	return &Plugin{cfg: cfg, pipe: pipe, disc: disc, logger: logger,
		sys: collector.NewSystemCollector(), prevProcJiffies: map[int]uint64{}}
}

func (p *Plugin) Name() string { return "metrics" }

func (p *Plugin) Start(ctx context.Context) error {
	ctx, p.cancel = context.WithCancel(ctx)
	go p.loop(ctx)
	return nil
}

func (p *Plugin) Stop() {
	if p.cancel != nil {
		p.cancel()
	}
}

func (p *Plugin) loop(ctx context.Context) {
	p.sys.Collect() // prime deltas
	t := time.NewTicker(p.cfg.MetricsInterval())
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			p.collectOnce()
		}
	}
}

func (p *Plugin) collectOnce() {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	s := p.sys.Collect()
	host := p.cfg.Hostname
	emit := func(name string, value float64, unit, service string) {
		p.pipe.Emit(pipeline.Event{
			Kind: "metric", Service: service, Timestamp: now,
			Data: map[string]any{"name": name, "value": value, "unit": unit},
			Tags: map[string]string{"host": host},
		})
	}
	emit("system.cpu.percent", s.CPUPercent, "%", "host")
	emit("system.memory.percent", s.MemoryPercent, "%", "host")
	emit("system.memory.used_mb", s.MemoryUsedMB, "MB", "host")
	emit("system.disk.percent", s.DiskPercent, "%", "host")
	emit("system.network.in_kbps", s.NetworkInKBps, "KB/s", "host")
	emit("system.network.out_kbps", s.NetworkOutKBps, "KB/s", "host")
	emit("system.load.1m", s.LoadAvg1m, "", "host")

	// Per-service process metrics
	elapsed := time.Since(p.prevProcAt).Seconds()
	next := map[int]uint64{}
	for _, svc := range p.disc.Services() {
		jiffies, rssMB := p.sys.ProcessStats(svc.PID)
		next[svc.PID] = jiffies
		if prev, ok := p.prevProcJiffies[svc.PID]; ok && elapsed > 0 && jiffies >= prev {
			// jiffies → % of one core (USER_HZ=100)
			cpuPct := float64(jiffies-prev) / 100.0 / elapsed * 100.0
			emit("process.cpu.percent", round2(cpuPct), "%", svc.Name)
		}
		if rssMB > 0 {
			emit("process.memory.rss_mb", rssMB, "MB", svc.Name)
		}
	}
	p.prevProcJiffies = next
	p.prevProcAt = time.Now()
}

func round2(v float64) float64 { return float64(int64(v*100+0.5)) / 100 }
