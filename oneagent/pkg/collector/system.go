// Package collector reads system metrics from /proc and syscalls — zero deps.
package collector

import (
	"os"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

type SystemStats struct {
	CPUPercent     float64
	MemoryPercent  float64
	MemoryUsedMB   float64
	MemoryTotalMB  float64
	DiskPercent    float64
	DiskUsedGB     float64
	DiskTotalGB    float64
	NetworkInKBps  float64
	NetworkOutKBps float64
	LoadAvg1m      float64
	Timestamp      time.Time
}

type SystemCollector struct {
	mu           sync.Mutex
	prevIdle     uint64
	prevTotal    uint64
	prevNetIn    uint64
	prevNetOut   uint64
	prevNetAt    time.Time
	procRoot     string
	diskMount    string
}

func NewSystemCollector() *SystemCollector {
	root := os.Getenv("HOST_PROC")
	if root == "" {
		root = "/proc"
	}
	mount := os.Getenv("HOST_ROOT")
	if mount == "" {
		mount = "/"
	}
	return &SystemCollector{procRoot: root, diskMount: mount}
}

func (c *SystemCollector) Collect() SystemStats {
	c.mu.Lock()
	defer c.mu.Unlock()
	s := SystemStats{Timestamp: time.Now()}
	s.CPUPercent = c.cpuPercent()
	s.MemoryPercent, s.MemoryUsedMB, s.MemoryTotalMB = c.memory()
	s.DiskPercent, s.DiskUsedGB, s.DiskTotalGB = c.disk()
	s.NetworkInKBps, s.NetworkOutKBps = c.network()
	s.LoadAvg1m = c.loadavg()
	return s
}

func (c *SystemCollector) cpuPercent() float64 {
	line := firstLine(c.procRoot + "/stat")
	fields := strings.Fields(line)
	if len(fields) < 8 || fields[0] != "cpu" {
		return 0
	}
	var total, idle uint64
	for i, f := range fields[1:] {
		v, _ := strconv.ParseUint(f, 10, 64)
		total += v
		if i == 3 || i == 4 { // idle + iowait
			idle += v
		}
	}
	defer func() { c.prevIdle, c.prevTotal = idle, total }()
	if c.prevTotal == 0 || total <= c.prevTotal {
		return 0
	}
	dTotal := float64(total - c.prevTotal)
	dIdle := float64(idle - c.prevIdle)
	return round2(100 * (dTotal - dIdle) / dTotal)
}

func (c *SystemCollector) memory() (pct, usedMB, totalMB float64) {
	data, err := os.ReadFile(c.procRoot + "/meminfo")
	if err != nil {
		return
	}
	var totalKB, availKB float64
	for _, line := range strings.Split(string(data), "\n") {
		f := strings.Fields(line)
		if len(f) < 2 {
			continue
		}
		v, _ := strconv.ParseFloat(f[1], 64)
		switch f[0] {
		case "MemTotal:":
			totalKB = v
		case "MemAvailable:":
			availKB = v
		}
	}
	if totalKB == 0 {
		return
	}
	usedKB := totalKB - availKB
	return round2(100 * usedKB / totalKB), round2(usedKB / 1024), round2(totalKB / 1024)
}

func (c *SystemCollector) disk() (pct, usedGB, totalGB float64) {
	var st syscall.Statfs_t
	if err := syscall.Statfs(c.diskMount, &st); err != nil {
		return
	}
	total := float64(st.Blocks) * float64(st.Bsize)
	free := float64(st.Bavail) * float64(st.Bsize)
	used := total - free
	if total == 0 {
		return
	}
	const gb = 1024 * 1024 * 1024
	return round2(100 * used / total), round2(used / gb), round2(total / gb)
}

func (c *SystemCollector) network() (inKBps, outKBps float64) {
	data, err := os.ReadFile(c.procRoot + "/net/dev")
	if err != nil {
		return
	}
	var rx, tx uint64
	for _, line := range strings.Split(string(data), "\n") {
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		iface := strings.TrimSpace(parts[0])
		if iface == "lo" {
			continue
		}
		f := strings.Fields(parts[1])
		if len(f) < 9 {
			continue
		}
		r, _ := strconv.ParseUint(f[0], 10, 64)
		t, _ := strconv.ParseUint(f[8], 10, 64)
		rx += r
		tx += t
	}
	now := time.Now()
	defer func() { c.prevNetIn, c.prevNetOut, c.prevNetAt = rx, tx, now }()
	if c.prevNetAt.IsZero() {
		return 0, 0
	}
	secs := now.Sub(c.prevNetAt).Seconds()
	if secs <= 0 || rx < c.prevNetIn {
		return 0, 0
	}
	return round2(float64(rx-c.prevNetIn) / 1024 / secs), round2(float64(tx-c.prevNetOut) / 1024 / secs)
}

func (c *SystemCollector) loadavg() float64 {
	f := strings.Fields(firstLine(c.procRoot + "/loadavg"))
	if len(f) == 0 {
		return 0
	}
	v, _ := strconv.ParseFloat(f[0], 64)
	return v
}

// ProcessStats reads per-process CPU jiffies + RSS for a PID.
func (c *SystemCollector) ProcessStats(pid int) (cpuJiffies uint64, rssMB float64) {
	data, err := os.ReadFile(c.procRoot + "/" + strconv.Itoa(pid) + "/stat")
	if err != nil {
		return
	}
	// fields after the (comm) parens
	idx := strings.LastIndex(string(data), ")")
	if idx < 0 {
		return
	}
	f := strings.Fields(string(data)[idx+1:])
	if len(f) < 22 {
		return
	}
	utime, _ := strconv.ParseUint(f[11], 10, 64)
	stime, _ := strconv.ParseUint(f[12], 10, 64)
	rssPages, _ := strconv.ParseFloat(f[21], 64)
	return utime + stime, round2(rssPages * 4096 / 1024 / 1024)
}

func firstLine(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	if i := strings.IndexByte(string(data), '\n'); i > 0 {
		return string(data)[:i]
	}
	return string(data)
}

func round2(v float64) float64 {
	return float64(int64(v*100+0.5)) / 100
}
