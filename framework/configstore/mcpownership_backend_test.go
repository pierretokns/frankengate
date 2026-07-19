package configstore

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/mcpownership"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestGORMMCPOwnershipBackendCASAndRoundTrip(t *testing.T) {
	db, err := gorm.Open(sqlite.Open("file:mcp_ownership_test?mode=memory&cache=shared"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	if err := EnsureMCPOwnershipSchema(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	b := NewGORMMCPOwnershipBackend(db)
	key := mcpownership.ConnectionKey{ClientID: "client", Principal: "tenant:user", SessionKey: "session"}
	rec := mcpownership.DurableRecord{Key: key, Version: 1, Fence: 1, OwnerPod: "pod-a", LeaseUntil: time.Unix(100, 0), Operations: []mcpownership.DurableOperation{{ID: "op", Status: mcpownership.OperationPending}}}
	if err := b.Write(context.Background(), 0, rec); err != nil {
		t.Fatal(err)
	}
	if err := b.Write(context.Background(), 0, rec); err != nil {
		t.Fatalf("idempotent retry: %v", err)
	}
	if err := b.Write(context.Background(), 0, mcpownership.DurableRecord{Key: key, Version: 2, Fence: 2, OwnerPod: "pod-b"}); !errors.Is(err, mcpownership.ErrVersionConflict) {
		t.Fatalf("stale writer error=%v", err)
	}
	updated := rec
	updated.Version = 2
	updated.Fence = 2
	updated.OwnerPod = "pod-b"
	updated.LeaseUntil = time.Unix(200, 0)
	if err := b.Write(context.Background(), 1, updated); err != nil {
		t.Fatal(err)
	}
	got, err := b.Read(context.Background(), key)
	if err != nil || got.OwnerPod != "pod-b" || got.Fence != 2 || got.Operations[0].ID != "op" {
		t.Fatalf("read=%#v err=%v", got, err)
	}
}

func TestGORMMCPOwnershipBackendNotFoundAndCancellation(t *testing.T) {
	db, _ := gorm.Open(sqlite.Open("file:mcp_ownership_test2?mode=memory&cache=shared"), &gorm.Config{})
	_ = EnsureMCPOwnershipSchema(context.Background(), db)
	b := NewGORMMCPOwnershipBackend(db)
	_, err := b.Read(context.Background(), mcpownership.ConnectionKey{ClientID: "missing", Principal: "p", SessionKey: "s"})
	if !errors.Is(err, mcpownership.ErrNotFound) {
		t.Fatalf("not found=%v", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := b.Write(ctx, 0, mcpownership.DurableRecord{Key: mcpownership.ConnectionKey{ClientID: "c", Principal: "p", SessionKey: "s"}, Version: 1}); err == nil {
		t.Fatal("expected cancellation error")
	}
}

func TestGORMMCPOwnershipDurableStoreRestartAndOperationRetry(t *testing.T) {
	db, err := gorm.Open(sqlite.Open("file:mcp_ownership_restart?mode=memory&cache=shared"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	if err := EnsureMCPOwnershipSchema(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	backend := NewGORMMCPOwnershipBackend(db)
	first := mcpownership.NewDurableStore(backend)
	second := mcpownership.NewDurableStore(backend)
	key := mcpownership.ConnectionKey{ClientID: "client", Principal: "tenant:user", SessionKey: "session"}
	now := time.Unix(100, 0)
	a, err := first.Claim(now, key, "pod-a", time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := first.StartCall(now, key, "pod-a", a.Fence, "op-1"); err != nil {
		t.Fatal(err)
	}
	b, err := second.Claim(now.Add(2*time.Second), key, "pod-b", time.Second)
	if err != nil || len(b.Reconnect.AmbiguousOperations) != 1 {
		t.Fatalf("restart claim=%#v err=%v", b, err)
	}
	retry, err := second.StartCall(now.Add(2*time.Second), key, "pod-b", b.Fence, "op-1")
	if err != nil || !retry.AmbiguousPrevious || retry.Attempt != 2 {
		t.Fatalf("retry=%#v err=%v", retry, err)
	}
	if _, err := first.CompleteCall(now.Add(2*time.Second), key, "pod-a", a.Fence, "op-1", true); !errors.Is(err, mcpownership.ErrStaleFence) {
		t.Fatalf("old owner completion=%v", err)
	}
	if _, err := second.CompleteCall(now.Add(2*time.Second), key, "pod-b", b.Fence, "op-1", true); err != nil {
		t.Fatal(err)
	}
}
