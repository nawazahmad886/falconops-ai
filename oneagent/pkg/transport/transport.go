// Package transport ships batches to the FalconOpsAI backend.
// Primary implementation: HTTP(S) — gzip JSON, X-API-Key auth, bounded retries.
// The Sender interface allows a gRPC transport to be plugged in when the
// backend exposes a gRPC ingest service (HTTP is the active default since
// the FalconOpsAI SaaS/on-prem backend ingests over HTTPS).
package transport

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/discovery"
)

// Sender is the transport abstraction used by the pipeline.
type Sender interface {
	Send(ctx context.Context, kind string, batch []map[string]any) error
}

type HTTPSender struct {
	cfg     *config.Config
	client  *http.Client
	logger  *log.Logger
	version string
}

func NewHTTPSender(cfg *config.Config, version string, logger *log.Logger) (*HTTPSender, error) {
	tlsCfg := &tls.Config{InsecureSkipVerify: cfg.TLS.InsecureSkipVerify} //nolint:gosec // operator opt-in
	if cfg.TLS.CAFile != "" {
		pem, err := os.ReadFile(cfg.TLS.CAFile)
		if err != nil {
			return nil, fmt.Errorf("read ca_file: %w", err)
		}
		pool := x509.NewCertPool()
		if !pool.AppendCertsFromPEM(pem) {
			return nil, fmt.Errorf("invalid CA pem in %s", cfg.TLS.CAFile)
		}
		tlsCfg.RootCAs = pool
	}
	return &HTTPSender{
		cfg: cfg, version: version, logger: logger,
		client: &http.Client{
			Timeout: 30 * time.Second,
			Transport: &http.Transport{
				TLSClientConfig:     tlsCfg,
				MaxIdleConnsPerHost: 4,
				IdleConnTimeout:     90 * time.Second,
			},
		},
	}, nil
}

// Send posts a batch to /api/ingest/{logs|metrics|traces} with 3 retries.
func (s *HTTPSender) Send(ctx context.Context, kind string, batch []map[string]any) error {
	if len(batch) == 0 {
		return nil
	}
	payload := map[string]any{
		"host":          s.cfg.Hostname,
		"environment":   s.cfg.Environment,
		"agent_version": s.version,
		"batch":         batch,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	url := strings.TrimRight(s.cfg.BackendURL, "/") + "/api/ingest/" + kind + "s"
	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(time.Duration(attempt) * 2 * time.Second):
			}
		}
		lastErr = s.post(ctx, url, body)
		if lastErr == nil {
			return nil
		}
	}
	return lastErr
}

func (s *HTTPSender) post(ctx context.Context, url string, body []byte) error {
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	if _, err := gz.Write(body); err != nil {
		return err
	}
	if err := gz.Close(); err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, &buf)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Content-Encoding", "gzip")
	req.Header.Set("X-API-Key", s.cfg.APIKey)
	req.Header.Set("User-Agent", "falconops-oneagent/"+s.version)
	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		return fmt.Errorf("auth rejected (%d): check api_key", resp.StatusCode)
	}
	if resp.StatusCode >= 300 {
		return fmt.Errorf("backend returned %d", resp.StatusCode)
	}
	return nil
}

// HeartbeatLoop registers the agent and reports discovered services every 60s.
func (s *HTTPSender) HeartbeatLoop(ctx context.Context, disc *discovery.Discovery) {
	url := strings.TrimRight(s.cfg.BackendURL, "/") + "/api/ingest/heartbeat"
	send := func() {
		services := disc.Services()
		names := make([]map[string]string, 0, len(services))
		for _, svc := range services {
			names = append(names, map[string]string{"name": svc.Name, "runtime": svc.Runtime})
		}
		body, _ := json.Marshal(map[string]any{
			"host": s.cfg.Hostname, "environment": s.cfg.Environment,
			"agent_version": s.version, "services": names,
		})
		if err := s.post(ctx, url, body); err != nil && s.cfg.Debug {
			s.logger.Printf("heartbeat failed: %v", err)
		}
	}
	send()
	t := time.NewTicker(60 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			send()
		}
	}
}
