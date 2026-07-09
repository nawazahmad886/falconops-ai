// Package logs is the log-collection plugin: tails /var/log, Docker container
// logs and Kubernetes pod logs; applies level/service filters; feeds the
// pipeline (which batches + compresses on send).
package logs

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/pipeline"
)

var levelOrder = map[string]int{"DEBUG": 0, "INFO": 1, "WARN": 2, "WARNING": 2, "ERROR": 3, "CRITICAL": 4, "FATAL": 4}

var levelRe = regexp.MustCompile(`(?i)\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b`)

type Plugin struct {
	cfg    *config.Config
	pipe   *pipeline.Pipeline
	logger *log.Logger
	cancel context.CancelFunc
	wg     sync.WaitGroup
	mu     sync.Mutex
	tails  map[string]bool
}

func New(cfg *config.Config, pipe *pipeline.Pipeline, logger *log.Logger) *Plugin {
	return &Plugin{cfg: cfg, pipe: pipe, logger: logger, tails: map[string]bool{}}
}

func (p *Plugin) Name() string { return "logs" }

func (p *Plugin) Start(ctx context.Context) error {
	ctx, p.cancel = context.WithCancel(ctx)
	go p.discoverLoop(ctx)
	return nil
}

func (p *Plugin) Stop() {
	if p.cancel != nil {
		p.cancel()
	}
	p.wg.Wait()
}

// discoverLoop rescans log sources every 30s and starts tailers for new files.
func (p *Plugin) discoverLoop(ctx context.Context) {
	scan := func() {
		for _, path := range p.candidateFiles() {
			p.mu.Lock()
			already := p.tails[path]
			if !already {
				p.tails[path] = true
			}
			p.mu.Unlock()
			if !already {
				p.wg.Add(1)
				go p.tail(ctx, path)
			}
		}
	}
	scan()
	t := time.NewTicker(30 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			scan()
		}
	}
}

func (p *Plugin) candidateFiles() []string {
	var files []string
	add := func(matches []string) {
		for _, m := range matches {
			if fi, err := os.Stat(m); err == nil && fi.Mode().IsRegular() {
				files = append(files, m)
			}
		}
	}
	// 1. /var/log classics
	m, _ := filepath.Glob("/var/log/*.log")
	add(m)
	m, _ = filepath.Glob("/var/log/syslog")
	add(m)
	// 2. Docker json-file logs
	m, _ = filepath.Glob("/var/lib/docker/containers/*/*-json.log")
	add(m)
	// 3. Kubernetes pod logs
	m, _ = filepath.Glob("/var/log/pods/*/*/*.log")
	add(m)
	m, _ = filepath.Glob("/var/log/containers/*.log")
	add(m)
	// 4. Operator-defined extra paths
	for _, g := range p.cfg.LogFilters.ExtraPaths {
		m, _ = filepath.Glob(g)
		add(m)
	}
	return files
}

// tail follows a file from its end (like `tail -F`), handling rotation.
func (p *Plugin) tail(ctx context.Context, path string) {
	defer p.wg.Done()
	service, sourceType := classifySource(path)
	if !p.serviceAllowed(service) {
		return
	}
	f, err := os.Open(path)
	if err != nil {
		return
	}
	_, _ = f.Seek(0, io.SeekEnd)
	reader := bufio.NewReaderSize(f, 64*1024)
	defer func() { _ = f.Close() }()
	var offset int64
	if fi, err := f.Stat(); err == nil {
		offset = fi.Size()
	}
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}
		line, err := reader.ReadString('\n')
		if err != nil {
			// rotation check: file shrank or was replaced
			if fi, serr := os.Stat(path); serr == nil {
				if cur, cerr := f.Stat(); cerr == nil && (fi.Size() < offset || !os.SameFile(fi, cur)) {
					_ = f.Close()
					if nf, oerr := os.Open(path); oerr == nil {
						f = nf
						reader = bufio.NewReaderSize(f, 64*1024)
						offset = 0
						continue
					}
					p.mu.Lock()
					delete(p.tails, path)
					p.mu.Unlock()
					return
				}
			} else {
				p.mu.Lock()
				delete(p.tails, path)
				p.mu.Unlock()
				return
			}
			select {
			case <-ctx.Done():
				return
			case <-time.After(time.Second):
			}
			continue
		}
		offset += int64(len(line))
		p.emitLine(service, sourceType, strings.TrimRight(line, "\n"))
	}
}

func (p *Plugin) emitLine(service, sourceType, line string) {
	if line == "" {
		return
	}
	message := line
	if sourceType == "docker" || sourceType == "kubernetes" {
		// docker json-file: {"log":"...","stream":"stdout","time":"..."}
		var wrapper struct {
			Log  string `json:"log"`
			Time string `json:"time"`
		}
		if err := json.Unmarshal([]byte(line), &wrapper); err == nil && wrapper.Log != "" {
			message = strings.TrimRight(wrapper.Log, "\n")
		}
	}
	level := detectLevel(message)
	if !p.levelAllowed(level) {
		return
	}
	p.pipe.Emit(pipeline.Event{
		Kind: "log", Service: service,
		Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
		Data:      map[string]any{"level": level, "message": truncate(message, 4000), "source": sourceType},
		Tags:      map[string]string{"host": p.cfg.Hostname},
	})
}

func (p *Plugin) levelAllowed(level string) bool {
	min, ok := levelOrder[strings.ToUpper(p.cfg.LogFilters.MinLevel)]
	if !ok {
		return true
	}
	return levelOrder[level] >= min
}

func (p *Plugin) serviceAllowed(service string) bool {
	f := p.cfg.LogFilters
	for _, ex := range f.ExcludeServices {
		if ex == service {
			return false
		}
	}
	if len(f.IncludeServices) == 0 {
		return true
	}
	for _, in := range f.IncludeServices {
		if in == service {
			return true
		}
	}
	return false
}

func detectLevel(line string) string {
	if m := levelRe.FindString(line); m != "" {
		up := strings.ToUpper(m)
		if up == "WARNING" {
			return "WARN"
		}
		return up
	}
	return "INFO"
}

// classifySource derives (service, source_type) from the log path.
func classifySource(path string) (string, string) {
	switch {
	case strings.HasPrefix(path, "/var/lib/docker/containers/"):
		parts := strings.Split(path, "/")
		if len(parts) > 5 {
			return "docker-" + parts[5][:min(12, len(parts[5]))], "docker"
		}
		return "docker", "docker"
	case strings.HasPrefix(path, "/var/log/pods/"):
		// /var/log/pods/<ns>_<pod>_<uid>/<container>/N.log
		parts := strings.Split(path, "/")
		if len(parts) > 5 {
			meta := strings.SplitN(parts[4], "_", 3)
			if len(meta) >= 2 {
				return meta[1], "kubernetes"
			}
		}
		return "kubernetes", "kubernetes"
	case strings.HasPrefix(path, "/var/log/containers/"):
		base := strings.TrimSuffix(filepath.Base(path), ".log")
		if i := strings.Index(base, "_"); i > 0 {
			return base[:i], "kubernetes"
		}
		return base, "kubernetes"
	default:
		return strings.TrimSuffix(filepath.Base(path), ".log"), "file"
	}
}

func truncate(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
