package mcpownership

import (
	"context"
	"errors"
	"testing"
)

func TestMemoryBackendCompareAndSwapFencesStaleWriters(t *testing.T) {
	b := NewMemoryBackend()
	key := ConnectionKey{ClientID: "client", Principal: "user", SessionKey: "session"}
	first := DurableRecord{Key: key, Version: 1, Fence: 1, OwnerPod: "pod-a"}
	if err := b.Write(context.Background(), 0, first); err != nil {
		t.Fatalf("initial write: %v", err)
	}
	if err := b.Write(context.Background(), 0, first); err != nil {
		t.Fatalf("identical retried write should be idempotent: %v", err)
	}
	if err := b.Write(context.Background(), 1, DurableRecord{Key: key, Version: 2, Fence: 0, OwnerPod: "pod-b"}); !errors.Is(err, ErrFenceRegression) {
		t.Fatalf("fence regression error = %v, want ErrFenceRegression", err)
	}
	if err := b.Write(context.Background(), 0, DurableRecord{Key: key, Version: 2, Fence: 2, OwnerPod: "pod-b"}); !errors.Is(err, ErrVersionConflict) {
		t.Fatalf("stale version error = %v, want ErrVersionConflict", err)
	}
	if err := b.Write(context.Background(), 1, DurableRecord{Key: key, Version: 2, Fence: 2, OwnerPod: "pod-b"}); err != nil {
		t.Fatalf("current writer update: %v", err)
	}
	got, err := b.Read(context.Background(), key)
	if err != nil || got.OwnerPod != "pod-b" || got.Fence != 2 || got.Version != 2 {
		t.Fatalf("read = %#v, %v", got, err)
	}
}

func TestMemoryBackendHonorsCancellationAndCopiesState(t *testing.T) {
	b := NewMemoryBackend()
	key := ConnectionKey{ClientID: "client", Principal: "user", SessionKey: "session"}
	rec := DurableRecord{Key: key, Version: 1, Fence: 1, Operations: []DurableOperation{{ID: "op", Status: OperationPending}}}
	if err := b.Write(context.Background(), 0, rec); err != nil {
		t.Fatal(err)
	}
	got, err := b.Read(context.Background(), key)
	if err != nil {
		t.Fatal(err)
	}
	got.Operations[0].ID = "mutated"
	again, err := b.Read(context.Background(), key)
	if err != nil || again.Operations[0].ID != "op" {
		t.Fatalf("backend state was not isolated: %#v %v", again, err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := b.Read(ctx, key); !errors.Is(err, context.Canceled) {
		t.Fatalf("read cancellation = %v", err)
	}
}
