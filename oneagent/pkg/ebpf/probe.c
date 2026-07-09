// FalconOpsAI OneAgent — eBPF syscall-latency probe (CO-RE).
// Attached to raw tracepoints sys_enter/sys_exit; aggregates per-PID latency
// buckets in a BPF hash map read by the Go loader (loader_ebpf.go).
//
// Build (with the `ebpf` Go build tag):
//   clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -c probe.c -o probe.o
//
// Requires kernel >= 5.4 with BTF (CONFIG_DEBUG_INFO_BTF=y).

// +build ignore

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

char LICENSE[] SEC("license") = "GPL";

struct syscall_key {
    u32 pid;
    u32 syscall_nr;
};

struct latency_bucket {
    u64 count;
    u64 total_ns;
    u64 max_ns;
};

// pid+syscall → in-flight start timestamp
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, u64);
    __type(value, u64);
} start_ts SEC(".maps");

// pid+syscall → aggregated latency
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 10240);
    __type(key, struct syscall_key);
    __type(value, struct latency_bucket);
} latencies SEC(".maps");

SEC("raw_tracepoint/sys_enter")
int rtp_sys_enter(struct bpf_raw_tracepoint_args *ctx)
{
    u64 id = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    bpf_map_update_elem(&start_ts, &id, &ts, BPF_ANY);
    return 0;
}

SEC("raw_tracepoint/sys_exit")
int rtp_sys_exit(struct bpf_raw_tracepoint_args *ctx)
{
    u64 id = bpf_get_current_pid_tgid();
    u64 *start = bpf_map_lookup_elem(&start_ts, &id);
    if (!start)
        return 0;
    u64 delta = bpf_ktime_get_ns() - *start;
    bpf_map_delete_elem(&start_ts, &id);

    struct pt_regs *regs = (struct pt_regs *)ctx->args[0];
    long syscall_nr = ctx->args[1];

    struct syscall_key key = {
        .pid = id >> 32,
        .syscall_nr = (u32)syscall_nr,
    };
    struct latency_bucket *b = bpf_map_lookup_elem(&latencies, &key);
    if (b) {
        __sync_fetch_and_add(&b->count, 1);
        __sync_fetch_and_add(&b->total_ns, delta);
        if (delta > b->max_ns)
            b->max_ns = delta;
    } else {
        struct latency_bucket init = {.count = 1, .total_ns = delta, .max_ns = delta};
        bpf_map_update_elem(&latencies, &key, &init, BPF_NOEXIST);
    }
    return 0;
}
