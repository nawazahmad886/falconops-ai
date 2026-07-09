//go:build ebpf

// Full eBPF loader — compiled only with `go build -tags ebpf`.
// Loads probe.c (compiled to probe.o) via cilium/ebpf, attaches the
// sys_enter/sys_exit raw tracepoints and periodically drains the latency map
// into agent metrics. Requires: CAP_BPF (or root), kernel >= 5.4 with BTF.
//
// Add the dependency when building with this tag:
//   go get github.com/cilium/ebpf@latest
package ebpf

import (
	"encoding/binary"
	"fmt"
	"time"

	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/rlimit"
)

type SyscallLatency struct {
	PID       uint32
	SyscallNr uint32
	Count     uint64
	AvgNs     uint64
	MaxNs     uint64
}

type Probe struct {
	coll    *ebpf.Collection
	enterLn link.Link
	exitLn  link.Link
}

// LoadProbe loads probe.o and attaches raw tracepoints.
func LoadProbe(objPath string) (*Probe, error) {
	if err := rlimit.RemoveMemlock(); err != nil {
		return nil, fmt.Errorf("memlock: %w", err)
	}
	spec, err := ebpf.LoadCollectionSpec(objPath)
	if err != nil {
		return nil, fmt.Errorf("load spec: %w", err)
	}
	coll, err := ebpf.NewCollection(spec)
	if err != nil {
		return nil, fmt.Errorf("new collection: %w", err)
	}
	enter, err := link.AttachRawTracepoint(link.RawTracepointOptions{
		Name: "sys_enter", Program: coll.Programs["rtp_sys_enter"]})
	if err != nil {
		coll.Close()
		return nil, fmt.Errorf("attach sys_enter: %w", err)
	}
	exit, err := link.AttachRawTracepoint(link.RawTracepointOptions{
		Name: "sys_exit", Program: coll.Programs["rtp_sys_exit"]})
	if err != nil {
		enter.Close()
		coll.Close()
		return nil, fmt.Errorf("attach sys_exit: %w", err)
	}
	return &Probe{coll: coll, enterLn: enter, exitLn: exit}, nil
}

// Drain reads + clears the latency map, returning per-PID syscall latencies.
func (p *Probe) Drain() ([]SyscallLatency, error) {
	m := p.coll.Maps["latencies"]
	var out []SyscallLatency
	var key [8]byte
	var val struct{ Count, TotalNs, MaxNs uint64 }
	iter := m.Iterate()
	var keys [][8]byte
	for iter.Next(&key, &val) {
		pid := binary.LittleEndian.Uint32(key[0:4])
		nr := binary.LittleEndian.Uint32(key[4:8])
		avg := uint64(0)
		if val.Count > 0 {
			avg = val.TotalNs / val.Count
		}
		out = append(out, SyscallLatency{PID: pid, SyscallNr: nr,
			Count: val.Count, AvgNs: avg, MaxNs: val.MaxNs})
		keys = append(keys, key)
	}
	for _, k := range keys {
		_ = m.Delete(&k)
	}
	return out, iter.Err()
}

func (p *Probe) Close() {
	if p.enterLn != nil {
		p.enterLn.Close()
	}
	if p.exitLn != nil {
		p.exitLn.Close()
	}
	if p.coll != nil {
		p.coll.Close()
	}
}

var _ = time.Second
