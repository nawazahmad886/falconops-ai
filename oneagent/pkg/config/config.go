// Package config loads and validates agent.yaml.
package config

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

type LogFilters struct {
	MinLevel        string   `yaml:"min_level"`        // debug|info|warn|error
	IncludeServices []string `yaml:"include_services"` // empty = all
	ExcludeServices []string `yaml:"exclude_services"`
	ExtraPaths      []string `yaml:"extra_paths"` // additional log files/globs to tail
}

type TLSConfig struct {
	InsecureSkipVerify bool   `yaml:"insecure_skip_verify"`
	CAFile             string `yaml:"ca_file"`
}

type Config struct {
	APIKey         string     `yaml:"api_key"`
	BackendURL     string     `yaml:"backend_url"`
	Hostname       string     `yaml:"hostname"`
	Environment    string     `yaml:"environment"` // production|staging|dev
	EnabledPlugins []string   `yaml:"enabled_plugins"`
	SamplingRate   float64    `yaml:"sampling_rate"` // 0.0-1.0 for debug/info logs
	LogFilters     LogFilters `yaml:"log_filters"`
	TLS            TLSConfig  `yaml:"tls"`

	MetricsIntervalSec int    `yaml:"metrics_interval_sec"`
	NetflowIntervalSec int    `yaml:"netflow_interval_sec"`
	GPUIntervalSec     int    `yaml:"gpu_interval_sec"`
	BatchMaxEvents     int    `yaml:"batch_max_events"`
	BatchMaxWaitSec    int    `yaml:"batch_max_wait_sec"`
	BufferDir          string `yaml:"buffer_dir"`
	BufferMaxMB        int    `yaml:"buffer_max_mb"`
	OTLPListenAddr     string `yaml:"otlp_listen_addr"`
	HealthListenAddr   string `yaml:"health_listen_addr"`
	Debug              bool   `yaml:"debug"`

	Tags map[string]string `yaml:"tags"`
}

func defaults() *Config {
	host, _ := os.Hostname()
	return &Config{
		Hostname:           host,
		Environment:        "production",
		EnabledPlugins:     []string{"logs", "metrics", "traces"},
		SamplingRate:       1.0,
		LogFilters:         LogFilters{MinLevel: "info"},
		MetricsIntervalSec: 30,
		NetflowIntervalSec: 20,
		GPUIntervalSec:     30,
		BatchMaxEvents:     500,
		BatchMaxWaitSec:    5,
		BufferDir:          "/var/lib/falconops/buffer",
		BufferMaxMB:        256,
		OTLPListenAddr:     "127.0.0.1:4318",
		HealthListenAddr:   "127.0.0.1:8126",
		Tags:               map[string]string{},
	}
}

// Load reads agent.yaml, applies env overrides and validates.
func Load(path string) (*Config, error) {
	cfg := defaults()
	raw, err := os.ReadFile(path)
	if err == nil {
		if err := yaml.Unmarshal(raw, cfg); err != nil {
			return nil, fmt.Errorf("parse %s: %w", path, err)
		}
	} else if !os.IsNotExist(err) {
		return nil, err
	}
	// Env overrides (12-factor friendly, also used by Docker/K8s deploys)
	if v := os.Getenv("FALCONOPS_API_KEY"); v != "" {
		cfg.APIKey = v
	}
	if v := os.Getenv("FALCONOPS_BACKEND_URL"); v != "" {
		cfg.BackendURL = v
	}
	if v := os.Getenv("FALCONOPS_HOSTNAME"); v != "" {
		cfg.Hostname = v
	}
	if cfg.BackendURL == "" {
		return nil, fmt.Errorf("backend_url is required (agent.yaml or FALCONOPS_BACKEND_URL)")
	}
	if cfg.APIKey == "" {
		return nil, fmt.Errorf("api_key is required (agent.yaml or FALCONOPS_API_KEY)")
	}
	if cfg.SamplingRate <= 0 || cfg.SamplingRate > 1 {
		cfg.SamplingRate = 1.0
	}
	if cfg.BatchMaxEvents < 1 {
		cfg.BatchMaxEvents = 500
	}
	return cfg, nil
}

func (c *Config) BatchMaxWait() time.Duration {
	if c.BatchMaxWaitSec < 1 {
		return 5 * time.Second
	}
	return time.Duration(c.BatchMaxWaitSec) * time.Second
}

func (c *Config) MetricsInterval() time.Duration {
	if c.MetricsIntervalSec < 5 {
		return 30 * time.Second
	}
	return time.Duration(c.MetricsIntervalSec) * time.Second
}

func (c *Config) NetflowInterval() time.Duration {
	if c.NetflowIntervalSec < 5 {
		return 20 * time.Second
	}
	return time.Duration(c.NetflowIntervalSec) * time.Second
}

func (c *Config) GPUInterval() time.Duration {
	if c.GPUIntervalSec < 5 {
		return 30 * time.Second
	}
	return time.Duration(c.GPUIntervalSec) * time.Second
}

func (c *Config) PluginEnabled(name string) bool {
	for _, p := range c.EnabledPlugins {
		if p == name {
			return true
		}
	}
	return false
}

// Redacted returns a copy safe for debug output.
func (c *Config) Redacted() Config {
	cp := *c
	if len(cp.APIKey) > 8 {
		cp.APIKey = cp.APIKey[:4] + "…" + cp.APIKey[len(cp.APIKey)-4:]
	} else if cp.APIKey != "" {
		cp.APIKey = "…"
	}
	return cp
}
