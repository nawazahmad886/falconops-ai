// Package health exposes the local ops endpoints: /health and /debug
// (default 127.0.0.1:8126). Used by systemd watchdog, K8s probes and humans.
package health

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/discovery"
	"github.com/falconops/oneagent/pkg/pipeline"
	"github.com/falconops/oneagent/pkg/plugins"
)

type Server struct {
	cfg      *config.Config
	version  string
	registry *plugins.Registry
	pipe     *pipeline.Pipeline
	disc     *discovery.Discovery
	logger   *log.Logger
	started  time.Time
}

func New(cfg *config.Config, version string, registry *plugins.Registry,
	pipe *pipeline.Pipeline, disc *discovery.Discovery, logger *log.Logger) *Server {
	return &Server{cfg: cfg, version: version, registry: registry, pipe: pipe,
		disc: disc, logger: logger, started: time.Now()}
}

func (s *Server) Start(ctx context.Context) {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/debug", s.handleDebug)
	srv := &http.Server{Addr: s.cfg.HealthListenAddr, Handler: mux, ReadTimeout: 5 * time.Second}
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			s.logger.Printf("health server failed: %v", err)
		}
	}()
	go func() {
		<-ctx.Done()
		shutCtx, done := context.WithTimeout(context.Background(), 2*time.Second)
		defer done()
		_ = srv.Shutdown(shutCtx)
	}()
	s.logger.Printf("health endpoint on http://%s/health", s.cfg.HealthListenAddr)
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, map[string]any{
		"status":         "ok",
		"version":        s.version,
		"uptime_seconds": int(time.Since(s.started).Seconds()),
		"plugins":        s.registry.Statuses(),
		"pipeline":       s.pipe.Stats(),
	})
}

func (s *Server) handleDebug(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, map[string]any{
		"config":              s.cfg.Redacted(),
		"discovered_services": s.disc.Services(),
		"pipeline":            s.pipe.Stats(),
	})
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
