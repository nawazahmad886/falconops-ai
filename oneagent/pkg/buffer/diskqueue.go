// Package buffer implements a disk-backed FIFO queue used when the backend
// is unreachable or the in-memory pipeline is saturated. Segment-per-batch
// JSON files with size-capped eviction (oldest dropped first).
package buffer

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

type DiskQueue struct {
	dir      string
	maxBytes int64
	mu       sync.Mutex
	seq      int64
	closed   bool
}

func Open(dir string, maxBytes int64) (*DiskQueue, error) {
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, fmt.Errorf("buffer dir: %w", err)
	}
	return &DiskQueue{dir: dir, maxBytes: maxBytes, seq: time.Now().UnixNano()}, nil
}

// Push appends a batch as a new segment file. Evicts oldest segments when
// the queue exceeds maxBytes.
func (q *DiskQueue) Push(v any) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.closed {
		return fmt.Errorf("queue closed")
	}
	data, err := json.Marshal(v)
	if err != nil {
		return err
	}
	q.seq++
	tmp := filepath.Join(q.dir, fmt.Sprintf(".tmp-%d", q.seq))
	if err := os.WriteFile(tmp, data, 0o600); err != nil {
		return err
	}
	final := filepath.Join(q.dir, fmt.Sprintf("seg-%020d.json", q.seq))
	if err := os.Rename(tmp, final); err != nil {
		return err
	}
	q.evictLocked()
	return nil
}

// Pop reads + removes the oldest segment into v. Returns false when empty.
func (q *DiskQueue) Pop(v any) (bool, error) {
	q.mu.Lock()
	defer q.mu.Unlock()
	segs := q.segmentsLocked()
	if len(segs) == 0 {
		return false, nil
	}
	path := segs[0]
	data, err := os.ReadFile(path)
	if err != nil {
		_ = os.Remove(path)
		return false, err
	}
	if err := json.Unmarshal(data, v); err != nil {
		_ = os.Remove(path) // corrupt segment — discard
		return false, err
	}
	return true, os.Remove(path)
}

func (q *DiskQueue) Segments() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.segmentsLocked())
}

func (q *DiskQueue) Close() {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.closed = true
}

func (q *DiskQueue) segmentsLocked() []string {
	entries, err := os.ReadDir(q.dir)
	if err != nil {
		return nil
	}
	var segs []string
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), "seg-") && strings.HasSuffix(e.Name(), ".json") {
			segs = append(segs, filepath.Join(q.dir, e.Name()))
		}
	}
	sort.Strings(segs)
	return segs
}

func (q *DiskQueue) evictLocked() {
	segs := q.segmentsLocked()
	var total int64
	sizes := make([]int64, len(segs))
	for i, s := range segs {
		if fi, err := os.Stat(s); err == nil {
			sizes[i] = fi.Size()
			total += fi.Size()
		}
	}
	for i := 0; total > q.maxBytes && i < len(segs); i++ {
		_ = os.Remove(segs[i])
		total -= sizes[i]
	}
}
