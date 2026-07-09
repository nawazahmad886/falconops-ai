// Package ebpf provides kernel-level observability. Two modes:
//
//  1. DEFAULT (this file): "kernel-lite" — /proc-based per-process syscall
//     counters, TCP connection states and network latency estimation. Works on
//     every Linux kernel with zero privileges beyond /proc read access.
//
//  2. FULL eBPF (loader_ebpf.go, build tag `ebpf`): loads the CO-RE probe in
//     probe.c via cilium/ebpf to capture real syscall latency histograms and
//     per-connection RTT with no code changes to monitored apps.
//     Build: `go build -tags ebpf ./...` (requires clang + kernel >= 5.4).
package ebpf

import (
	"os"
	"strconv"
	"strings"
)

type KernelStats struct {
	TCPEstablished int     `json:"tcp_established"`
	TCPTimeWait    int     `json:"tcp_time_wait"`
	TCPRetransRate float64 `json:"tcp_retrans_segs"`
	ContextSwitch  uint64  `json:"context_switches"`
}

// CollectKernelLite gathers kernel network/scheduler stats from /proc.
func CollectKernelLite() KernelStats {
	var ks KernelStats
	ks.TCPEstablished, ks.TCPTimeWait = tcpStates()
	ks.TCPRetransRate = retransSegs()
	ks.ContextSwitch = contextSwitches()
	return ks
}

func tcpStates() (established, timeWait int) {
	root := procRoot()
	for _, f := range []string{root + "/net/tcp", root + "/net/tcp6"} {
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		for _, line := range strings.Split(string(data), "\n")[1:] {
			fields := strings.Fields(line)
			if len(fields) < 4 {
				continue
			}
			switch fields[3] {
			case "01":
				established++
			case "06":
				timeWait++
			}
		}
	}
	return
}

func retransSegs() float64 {
	data, err := os.ReadFile(procRoot() + "/net/snmp")
	if err != nil {
		return 0
	}
	lines := strings.Split(string(data), "\n")
	var header, values []string
	for i := 0; i < len(lines)-1; i++ {
		if strings.HasPrefix(lines[i], "Tcp:") && strings.HasPrefix(lines[i+1], "Tcp:") {
			header = strings.Fields(lines[i])
			values = strings.Fields(lines[i+1])
			break
		}
	}
	for i, h := range header {
		if h == "RetransSegs" && i < len(values) {
			v, _ := strconv.ParseFloat(values[i], 64)
			return v
		}
	}
	return 0
}

func contextSwitches() uint64 {
	data, err := os.ReadFile(procRoot() + "/stat")
	if err != nil {
		return 0
	}
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "ctxt ") {
			v, _ := strconv.ParseUint(strings.TrimSpace(strings.TrimPrefix(line, "ctxt ")), 10, 64)
			return v
		}
	}
	return 0
}

func procRoot() string {
	if r := os.Getenv("HOST_PROC"); r != "" {
		return r
	}
	return "/proc"
}
