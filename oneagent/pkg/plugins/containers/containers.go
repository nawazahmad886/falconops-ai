// Package containers is the container-resource-metrics plugin: for every
// discovered service with a container_id (discovery.go's cgroup-derived
// tag), reads real cgroup CPU/memory stats (collector.ContainerCollector)
// and emits container.cpu.percent / container.memory.used_mb /
// container.memory.limit_mb. Opt-in (same pattern as gpu/netflow — add
// "containers" to enabled_plugins in agent.yaml).
package containers

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
	cfg     *config.Config
	pipe    *pipeline.Pipeline
	disc    *discovery.Discovery
	logger  *log.Logger
	coll    *collector.ContainerCollector
	cancel  context.CancelFunc
	prevCPU map[string]cpuSample // by container_id
}

type cpuSample struct {
	usec int64
	at   time.Time
}

func New(cfg *config.Config, pipe *pipeline.Pipeline, disc *discovery.Discovery, logger *log.Logger) *Plugin {
	return &Plugin{
		cfg: cfg, pipe: pipe, disc: disc, logger: logger,
		coll: collector.NewContainerCollector(), prevCPU: map[string]cpuSample{},
	}
}

func (p *Plugin) Name() string { return "containers" }

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
	now := time.Now()
	host := p.cfg.Hostname
	seenContainers := map[string]bool{}

	for _, svc := range p.disc.Services() {
		if svc.ContainerID == "" || seenContainers[svc.ContainerID] {
			continue // one reading per container, not per process within it
		}
		seenContainers[svc.ContainerID] = true

		stats := p.coll.Collect(svc.PID)
		if !stats.Available {
			p.logger.Printf("containers: %s (pid=%d): %s", svc.ContainerID, svc.PID, stats.Reason)
			continue // fails independently — one unreadable container never blocks the others
		}

		tags := map[string]string{"host": host, "container_id": svc.ContainerID, "service": svc.Name}
		nowISO := now.UTC().Format(time.RFC3339Nano)
		emit := func(name string, value float64, unit string) {
			p.pipe.Emit(pipeline.Event{
				Kind: "metric", Service: svc.Name, Timestamp: nowISO,
				Data: map[string]any{"name": name, "value": value, "unit": unit}, Tags: tags,
			})
		}

		if prev, ok := p.prevCPU[svc.ContainerID]; ok {
			elapsedSec := now.Sub(prev.at).Seconds()
			if elapsedSec > 0 && stats.CPUUsageUsec >= prev.usec {
				pct := 100 * float64(stats.CPUUsageUsec-prev.usec) / 1_000_000 / elapsedSec
				emit("container.cpu.percent", round2(pct), "%")
			}
		}
		p.prevCPU[svc.ContainerID] = cpuSample{usec: stats.CPUUsageUsec, at: now}

		emit("container.memory.used_mb", stats.MemoryUsedMB, "MB")
		if stats.MemoryLimitMB >= 0 {
			emit("container.memory.limit_mb", stats.MemoryLimitMB, "MB")
		}
	}

	// prune containers no longer seen so a long-lived agent doesn't leak
	// per-container CPU baselines for containers that exited.
	for id := range p.prevCPU {
		if !seenContainers[id] {
			delete(p.prevCPU, id)
		}
	}
}

func round2(v float64) float64 {
	return float64(int64(v*100+0.5)) / 100
}
