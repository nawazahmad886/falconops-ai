package pipeline

import (
	"fmt"
	"testing"
)

func TestSamplerDedupsNoise(t *testing.T) {
	s := newSampler(1.0)
	kept := 0
	for i := 0; i < 100; i++ {
		e := Event{Service: "svc", Kind: "log",
			Data: map[string]any{"level": "ERROR", "message": fmt.Sprintf("timeout after %dms", 5000+i)}}
		if s.keep(e) {
			kept++
		}
	}
	if kept != maxPerWindow {
		t.Errorf("kept %d identical-fingerprint events, want %d", kept, maxPerWindow)
	}
}

func TestSamplerKeepsDistinctMessages(t *testing.T) {
	s := newSampler(1.0)
	kept := 0
	for i := 0; i < 30; i++ {
		e := Event{Service: "svc", Kind: "log",
			Data: map[string]any{"level": "ERROR", "message": fmt.Sprintf("distinct failure kind %c", 'a'+i)}}
		if s.keep(e) {
			kept++
		}
	}
	if kept != 30 {
		t.Errorf("kept %d distinct events, want 30", kept)
	}
}

func TestSamplerNeverDropsErrorsProbabilistically(t *testing.T) {
	s := newSampler(0.01) // aggressive sampling
	e := Event{Service: "svc", Kind: "log",
		Data: map[string]any{"level": "ERROR", "message": "unique critical failure"}}
	if !s.keep(e) {
		t.Error("first ERROR event must always be kept regardless of sampling_rate")
	}
}

func TestNormalizeMsg(t *testing.T) {
	a := normalizeMsg("timeout after 5001ms")
	b := normalizeMsg("timeout after 5999ms")
	if a != b {
		t.Errorf("normalized messages differ: %q vs %q", a, b)
	}
}
