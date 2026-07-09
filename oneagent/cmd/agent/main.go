// FalconOpsAI OneAgent — universal observability agent.
// Auto-discovers services, collects logs/metrics/traces, ships them to the
// FalconOpsAI backend with minimal footprint (<2% CPU, <100MB RSS).
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/discovery"
	"github.com/falconops/oneagent/pkg/health"
	"github.com/falconops/oneagent/pkg/pipeline"
	"github.com/falconops/oneagent/pkg/plugins"
	"github.com/falconops/oneagent/pkg/plugins/logs"
	"github.com/falconops/oneagent/pkg/plugins/metrics"
	"github.com/falconops/oneagent/pkg/plugins/traces"
	"github.com/falconops/oneagent/pkg/transport"
)

var Version = "1.0.0"

func main() {
	cfgPath := flag.String("config", "/etc/falconops/agent.yaml", "path to agent.yaml")
	debug := flag.Bool("debug", false, "enable debug logging")
	showVersion := flag.Bool("version", false, "print version and exit")
	flag.Parse()

	if *showVersion {
		fmt.Println("FalconOpsAI OneAgent v" + Version)
		return
	}

	cfg, err := config.Load(*cfgPath)
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	if *debug {
		cfg.Debug = true
	}
	logger := newLogger(cfg.Debug)
	logger.Printf("FalconOpsAI OneAgent v%s starting (host=%s backend=%s)", Version, cfg.Hostname, cfg.BackendURL)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	sender, err := transport.NewHTTPSender(cfg, Version, logger)
	if err != nil {
		log.Fatalf("transport: %v", err)
	}

	pipe, err := pipeline.New(cfg, sender, logger)
	if err != nil {
		log.Fatalf("pipeline: %v", err)
	}

	disc := discovery.New(cfg, logger)
	disc.Start(ctx)

	registry := plugins.NewRegistry(logger)
	registry.Register(logs.New(cfg, pipe, logger))
	registry.Register(metrics.New(cfg, pipe, disc, logger))
	registry.Register(traces.New(cfg, pipe, logger))
	registry.StartEnabled(ctx, cfg.EnabledPlugins)

	hs := health.New(cfg, Version, registry, pipe, disc, logger)
	hs.Start(ctx)

	go sender.HeartbeatLoop(ctx, disc)
	pipe.Run(ctx)

	<-ctx.Done()
	logger.Printf("shutdown: flushing buffers…")
	registry.StopAll()
	pipe.Drain()
	logger.Printf("bye")
}

func newLogger(debug bool) *log.Logger {
	flags := log.LstdFlags
	if debug {
		flags |= log.Lshortfile
	}
	return log.New(os.Stdout, "[oneagent] ", flags)
}
