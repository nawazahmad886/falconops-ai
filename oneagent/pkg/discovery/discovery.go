// Package discovery auto-discovers running services by scanning /proc.
// Detects Node.js, Python, Java, Go, .NET and generic processes, derives
// service names automatically and tags them (runtime, container id, k8s pod).
package discovery

import (
	"context"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/falconops/oneagent/pkg/config"
)

type Service struct {
	PID         int               `json:"pid"`
	Name        string            `json:"name"`
	Runtime     string            `json:"runtime"` // nodejs|python|java|go|dotnet|native
	Cmdline     string            `json:"cmdline"`
	ContainerID string            `json:"container_id,omitempty"`
	Ports       []int             `json:"ports,omitempty"`
	Tags        map[string]string `json:"tags"`
	FirstSeen   time.Time         `json:"first_seen"`
	LastSeen    time.Time         `json:"last_seen"`
}

type Discovery struct {
	cfg      *config.Config
	logger   *log.Logger
	mu       sync.RWMutex
	services map[int]*Service // by PID
	procRoot string
}

func New(cfg *config.Config, logger *log.Logger) *Discovery {
	root := os.Getenv("HOST_PROC")
	if root == "" {
		root = "/proc"
	}
	return &Discovery{cfg: cfg, logger: logger, services: map[int]*Service{}, procRoot: root}
}

func (d *Discovery) Start(ctx context.Context) {
	d.scan()
	go func() {
		t := time.NewTicker(30 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				d.scan()
			}
		}
	}()
}

// Services returns a snapshot of currently discovered services.
func (d *Discovery) Services() []Service {
	d.mu.RLock()
	defer d.mu.RUnlock()
	out := make([]Service, 0, len(d.services))
	for _, s := range d.services {
		out = append(out, *s)
	}
	return out
}

func (d *Discovery) scan() {
	entries, err := os.ReadDir(d.procRoot)
	if err != nil {
		return
	}
	now := time.Now()
	seen := map[int]bool{}
	for _, e := range entries {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		cmdline := readProcFile(filepath.Join(d.procRoot, e.Name(), "cmdline"))
		if cmdline == "" {
			continue
		}
		cmdline = strings.ReplaceAll(cmdline, "\x00", " ")
		cmdline = strings.TrimSpace(cmdline)
		runtime := ClassifyRuntime(cmdline)
		if runtime == "" {
			continue // not an interesting service process
		}
		seen[pid] = true
		d.mu.Lock()
		if existing, ok := d.services[pid]; ok {
			existing.LastSeen = now
			d.mu.Unlock()
			continue
		}
		cgroup := readProcFile(filepath.Join(d.procRoot, e.Name(), "cgroup"))
		containerID := extractContainerID(cgroup)
		name := DeriveServiceName(cmdline, runtime, d.readCwd(pid))
		tags := map[string]string{"runtime": runtime, "host": d.cfg.Hostname}
		for k, v := range d.cfg.Tags {
			tags[k] = v
		}
		if containerID != "" {
			tags["container_id"] = containerID
		}
		ports := d.listeningPorts(e.Name())
		d.services[pid] = &Service{
			PID: pid, Name: name, Runtime: runtime, Cmdline: truncate(cmdline, 300),
			ContainerID: containerID, Ports: ports, Tags: tags, FirstSeen: now, LastSeen: now,
		}
		d.logger.Printf("discovered service %q (runtime=%s pid=%d)", name, runtime, pid)
		d.mu.Unlock()
	}
	// prune dead processes
	d.mu.Lock()
	for pid := range d.services {
		if !seen[pid] {
			delete(d.services, pid)
		}
	}
	d.mu.Unlock()
}

func (d *Discovery) readCwd(pid int) string {
	link, _ := os.Readlink(filepath.Join(d.procRoot, strconv.Itoa(pid), "cwd"))
	return link
}

// listeningPorts reads the process's own /proc/<pid>/net/tcp{,6} — its own
// network-namespace view (correct for both host processes and containerized
// ones with a private netns, unlike scanning the host's /proc/net/tcp and
// cross-referencing by inode) — and returns local ports in LISTEN state
// (kernel state code "0A", same vocabulary netflow.go's tcpStateNames uses).
// Computed once at first discovery, same lifecycle as Name/Runtime/ContainerID
// above — not re-read on every 30s tick for already-known PIDs.
func (d *Discovery) listeningPorts(pidDir string) []int {
	const listenState = "0A"
	seen := map[int]bool{}
	var ports []int
	for _, f := range []string{"net/tcp", "net/tcp6"} {
		data, err := os.ReadFile(filepath.Join(d.procRoot, pidDir, f))
		if err != nil {
			continue // permission denied or process exited — skip, matches netflow.go's handling
		}
		lines := strings.Split(string(data), "\n")
		if len(lines) < 2 {
			continue
		}
		for _, line := range lines[1:] {
			fields := strings.Fields(line)
			if len(fields) < 4 || strings.ToUpper(fields[3]) != listenState {
				continue
			}
			parts := strings.SplitN(fields[1], ":", 2)
			if len(parts) != 2 {
				continue
			}
			port, err := strconv.ParseUint(parts[1], 16, 32)
			if err != nil {
				continue
			}
			if !seen[int(port)] {
				seen[int(port)] = true
				ports = append(ports, int(port))
			}
		}
	}
	return ports
}

// ClassifyRuntime identifies the service runtime from its command line.
func ClassifyRuntime(cmdline string) string {
	first := strings.Fields(cmdline)
	if len(first) == 0 {
		return ""
	}
	exe := filepath.Base(first[0])
	switch {
	case strings.HasPrefix(exe, "node") || exe == "nodejs":
		return "nodejs"
	case strings.HasPrefix(exe, "python"):
		return "python"
	case exe == "java":
		return "java"
	case exe == "dotnet":
		return "dotnet"
	case strings.Contains(cmdline, "go run ") || strings.HasSuffix(exe, ".go"):
		return "go"
	}
	// Go binaries: standalone executables under common service dirs
	if strings.HasPrefix(first[0], "/usr/local/bin/") || strings.HasPrefix(first[0], "/app/") ||
		strings.HasPrefix(first[0], "/opt/") || strings.HasPrefix(first[0], "/srv/") {
		return "native"
	}
	return ""
}

var jarRe = regexp.MustCompile(`([\w.-]+)\.jar`)

// DeriveServiceName produces a human service name from the process cmdline.
// Priority: SERVICE_NAME-style flags > script/jar name > cwd dir > executable.
func DeriveServiceName(cmdline, runtime, cwd string) string {
	fields := strings.Fields(cmdline)
	// explicit flag e.g. --service-name=payments
	for _, f := range fields {
		for _, p := range []string{"--service-name=", "--service=", "-Dservice.name="} {
			if strings.HasPrefix(f, p) {
				return sanitizeName(strings.TrimPrefix(f, p))
			}
		}
	}
	switch runtime {
	case "java":
		if m := jarRe.FindStringSubmatch(cmdline); len(m) > 1 {
			return sanitizeName(m[1])
		}
	case "nodejs", "python":
		for _, f := range fields[1:] {
			if strings.HasPrefix(f, "-") {
				continue
			}
			base := filepath.Base(f)
			base = strings.TrimSuffix(strings.TrimSuffix(base, ".js"), ".py")
			if base != "" && base != "." {
				if (base == "main" || base == "app" || base == "index" || base == "server" || base == "manage") && cwd != "" {
					return sanitizeName(filepath.Base(cwd))
				}
				return sanitizeName(base)
			}
		}
	case "dotnet":
		for _, f := range fields[1:] {
			if strings.HasSuffix(f, ".dll") {
				return sanitizeName(strings.TrimSuffix(filepath.Base(f), ".dll"))
			}
		}
	}
	if cwd != "" && cwd != "/" {
		return sanitizeName(filepath.Base(cwd))
	}
	return sanitizeName(filepath.Base(fields[0]))
}

func sanitizeName(s string) string {
	s = strings.ToLower(strings.TrimSpace(s))
	s = strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' || r == '_' || r == '.' {
			return r
		}
		return '-'
	}, s)
	return strings.Trim(s, "-")
}

var containerRe = regexp.MustCompile(`[0-9a-f]{64}`)

func extractContainerID(cgroup string) string {
	if m := containerRe.FindString(cgroup); m != "" {
		return m[:12]
	}
	return ""
}

func readProcFile(path string) string {
	b, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return string(b)
}

func truncate(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}
