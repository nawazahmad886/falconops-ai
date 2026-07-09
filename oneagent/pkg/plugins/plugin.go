// Package plugins defines the plugin architecture: every collector feature
// (logs, metrics, traces) is a plugin that can be enabled/disabled via config.
package plugins

import (
	"context"
	"log"
	"sync"
)

type Plugin interface {
	Name() string
	Start(ctx context.Context) error
	Stop()
}

type Status struct {
	Name    string `json:"name"`
	Enabled bool   `json:"enabled"`
	Running bool   `json:"running"`
	Error   string `json:"error,omitempty"`
}

type Registry struct {
	logger  *log.Logger
	mu      sync.Mutex
	plugins []Plugin
	status  map[string]*Status
}

func NewRegistry(logger *log.Logger) *Registry {
	return &Registry{logger: logger, status: map[string]*Status{}}
}

func (r *Registry) Register(p Plugin) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.plugins = append(r.plugins, p)
	r.status[p.Name()] = &Status{Name: p.Name()}
}

func (r *Registry) StartEnabled(ctx context.Context, enabled []string) {
	on := map[string]bool{}
	for _, n := range enabled {
		on[n] = true
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, p := range r.plugins {
		st := r.status[p.Name()]
		st.Enabled = on[p.Name()]
		if !st.Enabled {
			r.logger.Printf("plugin %q disabled by config", p.Name())
			continue
		}
		if err := p.Start(ctx); err != nil {
			st.Error = err.Error()
			r.logger.Printf("plugin %q failed to start: %v", p.Name(), err)
			continue
		}
		st.Running = true
		r.logger.Printf("plugin %q started", p.Name())
	}
}

func (r *Registry) StopAll() {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, p := range r.plugins {
		if st := r.status[p.Name()]; st != nil && st.Running {
			p.Stop()
			st.Running = false
		}
	}
}

func (r *Registry) Statuses() []Status {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]Status, 0, len(r.status))
	for _, p := range r.plugins {
		out = append(out, *r.status[p.Name()])
	}
	return out
}
