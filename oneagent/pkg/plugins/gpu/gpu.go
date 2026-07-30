// Package gpu is the GPU-metrics plugin: NVIDIA (nvidia-smi) or AMD (rocm-smi)
// utilization/memory/temperature/power/fan, per physical GPU. Host-level only
// (unlike the metrics plugin, has no per-service discovery dependency).
package gpu

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/falconops/oneagent/pkg/collector"
	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/pipeline"
)

type Plugin struct {
	cfg    *config.Config
	pipe   *pipeline.Pipeline
	logger *log.Logger
	gpu    *collector.GPUCollector
	cancel context.CancelFunc
}

func New(cfg *config.Config, pipe *pipeline.Pipeline, logger *log.Logger) *Plugin {
	return &Plugin{cfg: cfg, pipe: pipe, logger: logger, gpu: collector.NewGPUCollector()}
}

func (p *Plugin) Name() string { return "gpu" }

func (p *Plugin) Start(ctx context.Context) error {
	if !p.gpu.Detected() {
		return fmt.Errorf("no GPU management tool found (nvidia-smi/rocm-smi) — gpu plugin will not run")
	}
	ctx, p.cancel = context.WithCancel(ctx)
	p.logger.Printf("gpu plugin: detected vendor=%s", p.gpu.Vendor())
	go p.loop(ctx)
	return nil
}

func (p *Plugin) Stop() {
	if p.cancel != nil {
		p.cancel()
	}
}

func (p *Plugin) loop(ctx context.Context) {
	t := time.NewTicker(p.cfg.GPUInterval())
	defer t.Stop()
	p.collectOnce(ctx) // prime immediately rather than waiting a full interval
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			p.collectOnce(ctx)
		}
	}
}

func (p *Plugin) collectOnce(ctx context.Context) {
	stats, err := p.gpu.Collect(ctx)
	if err != nil {
		p.logger.Printf("gpu plugin: collect failed: %v", err)
		return
	}
	now := time.Now().UTC().Format(time.RFC3339Nano)
	host := p.cfg.Hostname
	emit := func(gpuIndex, gpuName, gpuVendor, name string, value float64, unit string) {
		p.pipe.Emit(pipeline.Event{
			Kind: "metric", Service: "host", Timestamp: now,
			Data: map[string]any{"name": name, "value": value, "unit": unit},
			Tags: map[string]string{
				"host": host, "gpu_index": gpuIndex, "gpu_name": gpuName, "gpu_vendor": gpuVendor,
			},
		})
	}
	for _, s := range stats {
		emit(s.Index, s.Name, s.Vendor, "gpu.utilization.percent", s.UtilizationPct, "%")
		emit(s.Index, s.Name, s.Vendor, "gpu.memory.percent", s.MemoryPercent, "%")
		emit(s.Index, s.Name, s.Vendor, "gpu.memory.used_mb", s.MemoryUsedMB, "MB")
		emit(s.Index, s.Name, s.Vendor, "gpu.memory.total_mb", s.MemoryTotalMB, "MB")
		emit(s.Index, s.Name, s.Vendor, "gpu.temperature.c", s.TemperatureC, "C")
		emit(s.Index, s.Name, s.Vendor, "gpu.power.watts", s.PowerWatts, "W")
		emit(s.Index, s.Name, s.Vendor, "gpu.fan.percent", s.FanPercent, "%")
	}
}
