// Package netflow is the network-connection-tracking plugin: periodically
// parses /proc/net/tcp{,6} + /proc/<pid>/fd/* (the same technique ss/lsof use
// internally) to report established TCP connections, attributed to a
// discovered service where possible.
//
// This is NOT eBPF-grade packet capture. Known limitations:
//   - No L7 protocol/query decoding and no TLS decryption — only IP/port/state.
//   - No per-connection byte/packet counters (procfs doesn't expose these
//     per-flow, only per-interface aggregates, which collector.SystemCollector
//     already reports separately).
//   - Connections that open and close entirely between two polling ticks are
//     invisible — this is a periodic snapshot, not continuous capture, so a
//     fast port scan can be under-reported. Good for sustained/internal
//     topology and malicious-IP detection; not a replacement for real packet
//     capture.
//   - Reading another user's /proc/<pid>/fd/* generally requires the same
//     privilege level as the rest of this agent's process discovery (root, or
//     running as the same user as monitored services) — unreadable PIDs are
//     silently skipped, same as discovery.go's existing behavior.
package netflow

import (
	"context"
	"encoding/hex"
	"log"
	"net"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/falconops/oneagent/pkg/config"
	"github.com/falconops/oneagent/pkg/discovery"
	"github.com/falconops/oneagent/pkg/pipeline"
)

// MaxConnectionsPerCycle bounds event volume on busy hosts.
const MaxConnectionsPerCycle = 2000

var tcpStateNames = map[string]string{
	"01": "ESTABLISHED",
	"02": "SYN_SENT",
	"03": "SYN_RECV",
	"04": "FIN_WAIT1",
	"05": "FIN_WAIT2",
	"06": "TIME_WAIT",
	"07": "CLOSE",
	"08": "CLOSE_WAIT",
	"09": "LAST_ACK",
	"0A": "LISTEN",
	"0B": "CLOSING",
}

const establishedState = "01"

var socketInodeRe = regexp.MustCompile(`^socket:\[(\d+)\]$`)

type Plugin struct {
	cfg      *config.Config
	pipe     *pipeline.Pipeline
	disc     *discovery.Discovery
	logger   *log.Logger
	procRoot string
	cancel   context.CancelFunc
}

func New(cfg *config.Config, pipe *pipeline.Pipeline, disc *discovery.Discovery, logger *log.Logger) *Plugin {
	root := os.Getenv("HOST_PROC")
	if root == "" {
		root = "/proc"
	}
	return &Plugin{cfg: cfg, pipe: pipe, disc: disc, logger: logger, procRoot: root}
}

func (p *Plugin) Name() string { return "netflow" }

func (p *Plugin) Start(ctx context.Context) error {
	ctx, p.cancel = context.WithCancel(ctx)
	go p.loop(ctx)
	return nil
}

func (p *Plugin) Stop() {
	if p.cancel != nil {
		p.cancel()
	}
}

func (p *Plugin) loop(ctx context.Context) {
	t := time.NewTicker(p.cfg.NetflowInterval())
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			p.collectOnce()
		}
	}
}

func (p *Plugin) collectOnce() {
	inodeToPID := p.buildInodeToPIDMap()
	pidToService := map[int]discovery.Service{}
	for _, svc := range p.disc.Services() {
		pidToService[svc.PID] = svc
	}

	conns := p.parseConnections()
	now := time.Now().UTC().Format(time.RFC3339Nano)
	host := p.cfg.Hostname
	emitted := 0

	for _, c := range conns {
		if c.State != establishedState {
			continue
		}
		if emitted >= MaxConnectionsPerCycle {
			p.logger.Printf("netflow: truncated at %d connections this cycle", MaxConnectionsPerCycle)
			break
		}

		pid, hasPID := inodeToPID[c.Inode]
		serviceName := "unknown"
		var processName string
		if hasPID {
			if svc, ok := pidToService[pid]; ok {
				serviceName = svc.Name
				processName = svc.Name
			} else if comm := p.readComm(pid); comm != "" {
				serviceName = comm
				processName = comm
			}
		}

		p.pipe.Emit(pipeline.Event{
			Kind:      "netflow",
			Service:   serviceName,
			Timestamp: now,
			Data: map[string]any{
				"local_ip":     c.LocalIP,
				"local_port":   c.LocalPort,
				"remote_ip":    c.RemoteIP,
				"remote_port":  c.RemotePort,
				"state":        tcpStateNames[c.State],
				"pid":          pid,
				"process_name": processName,
			},
			Tags: map[string]string{"host": host},
		})
		emitted++
	}
}

// ─────────────────────────────────────────────
//  /proc/net/tcp{,6} parsing
// ─────────────────────────────────────────────

type connection struct {
	LocalIP    string
	LocalPort  int
	RemoteIP   string
	RemotePort int
	State      string
	Inode      string
}

func (p *Plugin) parseConnections() []connection {
	var out []connection
	for _, f := range []string{p.procRoot + "/net/tcp", p.procRoot + "/net/tcp6"} {
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		lines := strings.Split(string(data), "\n")
		if len(lines) < 2 {
			continue
		}
		for _, line := range lines[1:] {
			fields := strings.Fields(line)
			if len(fields) < 10 {
				continue
			}
			localIP, localPort, err := splitProcAddrPort(fields[1])
			if err != nil {
				continue
			}
			remoteIP, remotePort, err := splitProcAddrPort(fields[2])
			if err != nil {
				continue
			}
			out = append(out, connection{
				LocalIP:    localIP.String(),
				LocalPort:  localPort,
				RemoteIP:   remoteIP.String(),
				RemotePort: remotePort,
				State:      strings.ToUpper(fields[3]),
				Inode:      fields[9],
			})
		}
	}
	return out
}

// splitProcAddrPort decodes a "HEXADDR:HEXPORT" field from /proc/net/tcp{,6}.
func splitProcAddrPort(field string) (net.IP, int, error) {
	parts := strings.SplitN(field, ":", 2)
	if len(parts) != 2 {
		return nil, 0, errBadField
	}
	ip, err := decodeProcAddr(parts[0])
	if err != nil {
		return nil, 0, err
	}
	port, err := strconv.ParseUint(parts[1], 16, 32)
	if err != nil {
		return nil, 0, err
	}
	return ip, int(port), nil
}

var errBadField = &procParseError{"malformed addr:port field"}

type procParseError struct{ msg string }

func (e *procParseError) Error() string { return e.msg }

// decodeProcAddr decodes the kernel's /proc/net/tcp{,6} address encoding: the
// address is stored as a sequence of 32-bit big-endian words, but printed via
// a host-endian hex dump — on little-endian hosts (the overwhelming majority)
// this means each 4-byte group appears byte-reversed relative to normal
// network byte order. Reversing every 4-byte group recovers the real address,
// for both IPv4 (one group) and IPv6 (four groups). This is the same
// algorithm used by prometheus/procfs and the kernel's own documentation.
func decodeProcAddr(hexAddr string) (net.IP, error) {
	raw, err := hex.DecodeString(hexAddr)
	if err != nil {
		return nil, err
	}
	if len(raw) != 4 && len(raw) != 16 {
		return nil, &procParseError{"unexpected proc address length"}
	}
	out := make([]byte, len(raw))
	for i := 0; i+4 <= len(raw); i += 4 {
		out[i], out[i+1], out[i+2], out[i+3] = raw[i+3], raw[i+2], raw[i+1], raw[i]
	}
	return net.IP(out), nil
}

// ─────────────────────────────────────────────
//  inode → PID attribution (fd table walk)
// ─────────────────────────────────────────────

func (p *Plugin) buildInodeToPIDMap() map[string]int {
	out := map[string]int{}
	entries, err := os.ReadDir(p.procRoot)
	if err != nil {
		return out
	}
	for _, e := range entries {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		fdDir := filepath.Join(p.procRoot, e.Name(), "fd")
		fds, err := os.ReadDir(fdDir)
		if err != nil {
			continue // permission denied or process exited — skip, matches discovery.go's error handling
		}
		for _, fd := range fds {
			link, err := os.Readlink(filepath.Join(fdDir, fd.Name()))
			if err != nil {
				continue
			}
			if m := socketInodeRe.FindStringSubmatch(link); m != nil {
				out[m[1]] = pid
			}
		}
	}
	return out
}

func (p *Plugin) readComm(pid int) string {
	b, err := os.ReadFile(filepath.Join(p.procRoot, strconv.Itoa(pid), "comm"))
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(b))
}
