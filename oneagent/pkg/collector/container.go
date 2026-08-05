// Container resource collection — cgroup-based, host-agent-observed (not a
// Docker/Kubernetes-API collector, consistent with the rest of this agent's
// "observe via /proc and cgroups" design, no cluster credential dependency).
//
// Path resolution deliberately does NOT guess Docker/containerd/Kubernetes
// naming conventions (docker-<id>.scope vs kubepods.slice/... vary by cgroup
// driver and container runtime, and getting this wrong on an unverified host
// would silently under-report). Instead it reads /proc/<pid>/cgroup, which
// the kernel always populates correctly regardless of runtime or driver, and
// uses the path it reports directly.
package collector

import (
	"os"
	"strconv"
	"strings"
)

type ContainerStats struct {
	CPUUsageUsec  int64   // cumulative CPU time in microseconds (cgroup v2) — caller computes a rate
	MemoryUsedMB  float64
	MemoryLimitMB float64 // -1 when the cgroup reports no limit ("max" / unbounded)
	Available     bool
	Reason        string // set when Available is false — never fabricate a stat instead
}

type ContainerCollector struct {
	procRoot   string
	cgroupRoot string
}

func NewContainerCollector() *ContainerCollector {
	procRoot := os.Getenv("HOST_PROC")
	if procRoot == "" {
		procRoot = "/proc"
	}
	cgroupRoot := os.Getenv("HOST_CGROUP")
	if cgroupRoot == "" {
		cgroupRoot = "/sys/fs/cgroup"
	}
	return &ContainerCollector{procRoot: procRoot, cgroupRoot: cgroupRoot}
}

// Collect reads real cgroup stats for the process's own cgroup — a
// containerized service's main process's cgroup boundary is the container's
// boundary, so this is an accurate per-container measurement without any
// container-ID-based path guessing.
func (c *ContainerCollector) Collect(pid int) ContainerStats {
	v2Path, v1Paths, err := c.resolveCgroupPaths(pid)
	if err != nil {
		return ContainerStats{Available: false, Reason: "cgroup path not resolvable: " + err.Error()}
	}

	if v2Path != "" {
		return c.collectV2(v2Path)
	}
	if len(v1Paths) > 0 {
		return c.collectV1(v1Paths)
	}
	return ContainerStats{Available: false, Reason: "no cgroup controllers found for this process"}
}

// resolveCgroupPaths parses /proc/<pid>/cgroup. cgroup v2 (unified hierarchy)
// is a single "0::<path>" line. cgroup v1 has one line per controller,
// "<hierarchy-id>:<controller-list>:<path>" — we only need the memory and
// cpu/cpuacct controller lines.
func (c *ContainerCollector) resolveCgroupPaths(pid int) (v2Path string, v1Paths map[string]string, err error) {
	data, readErr := os.ReadFile(c.procRoot + "/" + strconv.Itoa(pid) + "/cgroup")
	if readErr != nil {
		return "", nil, readErr
	}
	v1Paths = map[string]string{}
	for _, line := range strings.Split(string(data), "\n") {
		parts := strings.SplitN(line, ":", 3)
		if len(parts) != 3 {
			continue
		}
		hierarchyID, controllers, path := parts[0], parts[1], parts[2]
		if hierarchyID == "0" && controllers == "" {
			v2Path = path
			continue
		}
		for _, ctrl := range strings.Split(controllers, ",") {
			if ctrl == "memory" || ctrl == "cpu" || ctrl == "cpuacct" {
				v1Paths[ctrl] = path
			}
		}
	}
	return v2Path, v1Paths, nil
}

func (c *ContainerCollector) collectV2(path string) ContainerStats {
	base := c.cgroupRoot + path
	cpuUsec, ok := readCgroupKeyedInt(base+"/cpu.stat", "usage_usec")
	memUsedBytes, memOK := readCgroupPlainInt(base + "/memory.current")
	memLimitBytes, limitOK := readCgroupPlainIntOrMax(base + "/memory.max")

	if !ok && !memOK {
		return ContainerStats{Available: false, Reason: "cgroup v2 stat files not readable at " + base}
	}

	stats := ContainerStats{Available: true}
	if ok {
		stats.CPUUsageUsec = cpuUsec
	}
	if memOK {
		stats.MemoryUsedMB = round2(float64(memUsedBytes) / 1024 / 1024)
	}
	if limitOK && memLimitBytes >= 0 {
		stats.MemoryLimitMB = round2(float64(memLimitBytes) / 1024 / 1024)
	} else {
		stats.MemoryLimitMB = -1
	}
	return stats
}

func (c *ContainerCollector) collectV1(paths map[string]string) ContainerStats {
	stats := ContainerStats{Available: false, MemoryLimitMB: -1}
	if memPath, ok := paths["memory"]; ok {
		base := c.cgroupRoot + "/memory" + memPath
		if used, ok := readCgroupPlainInt(base + "/memory.usage_in_bytes"); ok {
			stats.MemoryUsedMB = round2(float64(used) / 1024 / 1024)
			stats.Available = true
		}
		if limit, ok := readCgroupPlainInt(base + "/memory.limit_in_bytes"); ok {
			// cgroup v1 reports an enormous sentinel (close to 2^63) for "no limit".
			if limit > 0 && limit < 1<<62 {
				stats.MemoryLimitMB = round2(float64(limit) / 1024 / 1024)
			}
		}
	}
	cpuCtrl := paths["cpuacct"]
	if cpuCtrl == "" {
		cpuCtrl = paths["cpu"]
	}
	if cpuCtrl != "" {
		// Mount naming for the combined cpu/cpuacct controller varies by
		// distro — try each plausible mount point rather than assuming one.
		for _, mountName := range []string{"cpuacct", "cpu,cpuacct", "cpu"} {
			base := c.cgroupRoot + "/" + mountName + cpuCtrl
			if usageNs, ok := readCgroupPlainInt(base + "/cpuacct.usage"); ok {
				stats.CPUUsageUsec = usageNs / 1000
				stats.Available = true
				break
			}
		}
	}
	if !stats.Available {
		stats.Reason = "cgroup v1 stat files not readable for this process's controllers"
	}
	return stats
}

func readCgroupPlainInt(path string) (int64, bool) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, false
	}
	v, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

// readCgroupPlainIntOrMax handles memory.max, which contains the literal
// string "max" (not a number) when the cgroup has no memory limit set.
func readCgroupPlainIntOrMax(path string) (int64, bool) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, false
	}
	trimmed := strings.TrimSpace(string(data))
	if trimmed == "max" {
		return -1, true
	}
	v, err := strconv.ParseInt(trimmed, 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

func readCgroupKeyedInt(path, key string) (int64, bool) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, false
	}
	for _, line := range strings.Split(string(data), "\n") {
		fields := strings.Fields(line)
		if len(fields) == 2 && fields[0] == key {
			v, err := strconv.ParseInt(fields[1], 10, 64)
			if err != nil {
				return 0, false
			}
			return v, true
		}
	}
	return 0, false
}
