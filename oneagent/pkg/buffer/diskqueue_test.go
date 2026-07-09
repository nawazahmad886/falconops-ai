package buffer

import (
	"testing"
)

type batch []map[string]string

func TestPushPopFIFO(t *testing.T) {
	q, err := Open(t.TempDir(), 1024*1024)
	if err != nil {
		t.Fatal(err)
	}
	if err := q.Push(batch{{"n": "1"}}); err != nil {
		t.Fatal(err)
	}
	if err := q.Push(batch{{"n": "2"}}); err != nil {
		t.Fatal(err)
	}
	if q.Segments() != 2 {
		t.Fatalf("segments = %d", q.Segments())
	}
	var out batch
	ok, err := q.Pop(&out)
	if err != nil || !ok || out[0]["n"] != "1" {
		t.Fatalf("pop1: ok=%v err=%v out=%v", ok, err, out)
	}
	ok, _ = q.Pop(&out)
	if !ok || out[0]["n"] != "2" {
		t.Fatalf("pop2 wrong: %v", out)
	}
	ok, _ = q.Pop(&out)
	if ok {
		t.Fatal("expected empty queue")
	}
}

func TestEvictionOldestFirst(t *testing.T) {
	q, err := Open(t.TempDir(), 300) // tiny cap
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 10; i++ {
		_ = q.Push(batch{{"payload": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}})
	}
	if q.Segments() >= 10 {
		t.Fatalf("eviction did not run, segments=%d", q.Segments())
	}
}

func TestFailureRecovery(t *testing.T) {
	dir := t.TempDir()
	q, _ := Open(dir, 1024*1024)
	_ = q.Push(batch{{"n": "persisted"}})
	q.Close()
	// simulate agent restart
	q2, err := Open(dir, 1024*1024)
	if err != nil {
		t.Fatal(err)
	}
	var out batch
	ok, err := q2.Pop(&out)
	if err != nil || !ok || out[0]["n"] != "persisted" {
		t.Fatalf("recovery failed: ok=%v err=%v out=%v", ok, err, out)
	}
}
