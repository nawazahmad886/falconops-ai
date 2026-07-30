// GPU metrics collector: shells out to nvidia-smi (NVIDIA) or rocm-smi (AMD) —
// the only external-binary dependency in this agent, since GPU telemetry has
// no /proc equivalent the way CPU/memory/disk/network do. Vendor is detected
// once at construction; Collect() returns (nil, nil) when neither tool is on
// PATH, and the gpu plugin (pkg/plugins/gpu) refuses to start in that case —
// never fabricates a reading for hardware that isn't there.
package collector

import (
	"bytes"
	"context"
	"encoding/json"
	"os/exec"
	"strconv"
	"strings"
)

type GPUStats struct {
	Index          string
	Name           string
	Vendor         string // "nvidia" | "amd"
	UtilizationPct float64
	MemoryUsedMB   float64
	MemoryTotalMB  float64
	MemoryPercent  float64
	TemperatureC   float64
	PowerWatts     float64
	FanPercent     float64
}

type GPUCollector struct {
	vendor string // "nvidia", "amd", or "" (none detected)
}

func NewGPUCollector() *GPUCollector {
	c := &GPUCollector{}
	if _, err := exec.LookPath("nvidia-smi"); err == nil {
		c.vendor = "nvidia"
	} else if _, err := exec.LookPath("rocm-smi"); err == nil {
		c.vendor = "amd"
	}
	return c
}

func (c *GPUCollector) Detected() bool { return c.vendor != "" }
func (c *GPUCollector) Vendor() string { return c.vendor }

func (c *GPUCollector) Collect(ctx context.Context) ([]GPUStats, error) {
	switch c.vendor {
	case "nvidia":
		return c.collectNvidia(ctx)
	case "amd":
		return c.collectAMD(ctx)
	default:
		return nil, nil
	}
}

func (c *GPUCollector) collectNvidia(ctx context.Context) ([]GPUStats, error) {
	cmd := exec.CommandContext(ctx, "nvidia-smi",
		"--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,fan.speed",
		"--format=csv,noheader,nounits")
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		return nil, err
	}
	var stats []GPUStats
	for _, line := range strings.Split(strings.TrimSpace(out.String()), "\n") {
		if line == "" {
			continue
		}
		f := strings.Split(line, ",")
		for i := range f {
			f[i] = strings.TrimSpace(f[i])
		}
		if len(f) < 9 {
			continue
		}
		memUsed := parseFloatSafe(f[4])
		memTotal := parseFloatSafe(f[5])
		memPct := 0.0
		if memTotal > 0 {
			memPct = round2(100 * memUsed / memTotal)
		}
		stats = append(stats, GPUStats{
			Index:          f[0],
			Name:           f[1],
			Vendor:         "nvidia",
			UtilizationPct: parseFloatSafe(f[2]),
			MemoryUsedMB:   memUsed,
			MemoryTotalMB:  memTotal,
			MemoryPercent:  memPct,
			TemperatureC:   parseFloatSafe(f[6]),
			PowerWatts:     parseFloatSafe(f[7]),
			FanPercent:     parseFloatSafe(f[8]),
		})
	}
	return stats, nil
}

// rocm-smi's JSON schema has varied across ROCm releases (card keys like
// "card0", field names like "GPU use (%)" vs "GFX Activity"). Parsed
// tolerantly via a key-alias list per field — an unrecognized/missing key
// degrades to 0, never crashes. Verify these exact key names against your
// installed ROCm version's `rocm-smi --showuse --showmeminfo vram --showtemp
// --showpower --showfan --json` output; adjust the alias lists below if they
// differ (this was implemented from ROCm's published CLI docs, not a live
// AMD GPU — no AMD hardware is available in the environment this was written in).
func (c *GPUCollector) collectAMD(ctx context.Context) ([]GPUStats, error) {
	cmd := exec.CommandContext(ctx, "rocm-smi",
		"--showuse", "--showmeminfo", "vram", "--showtemp", "--showpower", "--showfan", "--showproductname", "--json")
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		return nil, err
	}
	var raw map[string]map[string]any
	if err := json.Unmarshal(out.Bytes(), &raw); err != nil {
		return nil, err
	}
	var stats []GPUStats
	for card, fields := range raw {
		index := strings.TrimPrefix(card, "card")
		memUsed := parseAnyBytesToMB(fields, "VRAM Total Used Memory (B)")
		memTotal := parseAnyBytesToMB(fields, "VRAM Total Memory (B)")
		memPct := 0.0
		if memTotal > 0 {
			memPct = round2(100 * memUsed / memTotal)
		}
		stats = append(stats, GPUStats{
			Index:          index,
			Name:           strField(fields, "Card series", "Card Series", "Device Name"),
			Vendor:         "amd",
			UtilizationPct: parseAnyFloat(fields, "GPU use (%)", "GFX Activity"),
			MemoryUsedMB:   memUsed,
			MemoryTotalMB:  memTotal,
			MemoryPercent:  memPct,
			TemperatureC:   parseAnyFloat(fields, "Temperature (Sensor edge) (C)", "Temperature (Sensor junction) (C)"),
			PowerWatts:     parseAnyFloat(fields, "Average Graphics Package Power (W)", "Current Socket Graphics Package Power (W)"),
			FanPercent:     parseAnyFloat(fields, "Fan speed (%)"),
		})
	}
	return stats, nil
}

func strField(m map[string]any, keys ...string) string {
	for _, k := range keys {
		if v, ok := m[k]; ok {
			if s, ok := v.(string); ok && s != "" {
				return s
			}
		}
	}
	return "unknown"
}

func parseAnyFloat(m map[string]any, keys ...string) float64 {
	for _, k := range keys {
		v, ok := m[k]
		if !ok {
			continue
		}
		if s, ok := v.(string); ok {
			return parseFloatSafe(s)
		}
		if f, ok := v.(float64); ok {
			return f
		}
	}
	return 0
}

func parseAnyBytesToMB(m map[string]any, keys ...string) float64 {
	b := parseAnyFloat(m, keys...)
	if b == 0 {
		return 0
	}
	return round2(b / 1024 / 1024)
}

func parseFloatSafe(s string) float64 {
	s = strings.TrimSpace(s)
	s = strings.TrimSuffix(s, "%")
	if s == "" || strings.Contains(s, "N/A") {
		return 0
	}
	v, _ := strconv.ParseFloat(s, 64)
	return v
}
