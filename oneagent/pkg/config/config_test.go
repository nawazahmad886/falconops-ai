package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadDefaultsAndOverrides(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "agent.yaml")
	yaml := `
api_key: fops_test_key_123
backend_url: https://falcon.example.com
enabled_plugins: [logs, metrics]
sampling_rate: 0.5
log_filters:
  min_level: warn
  exclude_services: [noisy-svc]
tags:
  team: platform
`
	if err := os.WriteFile(path, []byte(yaml), 0o600); err != nil {
		t.Fatal(err)
	}
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if cfg.APIKey != "fops_test_key_123" || cfg.BackendURL != "https://falcon.example.com" {
		t.Errorf("basic fields wrong: %+v", cfg)
	}
	if cfg.SamplingRate != 0.5 {
		t.Errorf("sampling_rate = %v", cfg.SamplingRate)
	}
	if !cfg.PluginEnabled("logs") || cfg.PluginEnabled("traces") {
		t.Errorf("plugin enablement wrong: %v", cfg.EnabledPlugins)
	}
	if cfg.LogFilters.MinLevel != "warn" || cfg.LogFilters.ExcludeServices[0] != "noisy-svc" {
		t.Errorf("log filters wrong: %+v", cfg.LogFilters)
	}
	if cfg.Tags["team"] != "platform" {
		t.Errorf("tags wrong: %v", cfg.Tags)
	}
	// defaults preserved
	if cfg.BatchMaxEvents != 500 || cfg.OTLPListenAddr != "127.0.0.1:4318" {
		t.Errorf("defaults lost: %+v", cfg)
	}
}

func TestLoadEnvOverride(t *testing.T) {
	t.Setenv("FALCONOPS_API_KEY", "env_key")
	t.Setenv("FALCONOPS_BACKEND_URL", "https://env.example.com")
	cfg, err := Load(filepath.Join(t.TempDir(), "missing.yaml"))
	if err != nil {
		t.Fatalf("load with env: %v", err)
	}
	if cfg.APIKey != "env_key" || cfg.BackendURL != "https://env.example.com" {
		t.Errorf("env overrides not applied: %+v", cfg)
	}
}

func TestLoadMissingRequired(t *testing.T) {
	if _, err := Load(filepath.Join(t.TempDir(), "missing.yaml")); err == nil {
		t.Error("expected error for missing api_key/backend_url")
	}
}

func TestRedacted(t *testing.T) {
	c := &Config{APIKey: "fops_secret_key_abcd"}
	r := c.Redacted()
	if r.APIKey == c.APIKey || r.APIKey == "" {
		t.Errorf("api key not redacted: %q", r.APIKey)
	}
}
