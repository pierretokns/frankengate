package mcpownership

import (
	"context"
	"errors"
	"testing"
	"time"
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

func TestDurableStoreRestartPreservesFenceAndRetriesAmbiguousCall(t *testing.T) {
	backend := NewMemoryBackend()
	// Two stores model two gateway processes sharing the same durable row. No
	// process-local state is allowed to make the second process forget the
	// in-flight operation.
	first := NewDurableStore(backend)
	second := NewDurableStore(backend)
	key := ConnectionKey{ClientID: "client", Principal: "tenant:user", SessionKey: "session"}
	started := time.Unix(100, 0)
	claimA, err := first.Claim(started, key, "pod-a", time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := first.StartCall(started, key, "pod-a", claimA.Fence, "op-1"); err != nil {
		t.Fatal(err)
	}

	// After the lease expires, a restarted pod fences the old owner and sees
	// the pending operation as ambiguous, requiring an explicit retry.
	claimB, err := second.Claim(started.Add(2*time.Second), key, "pod-b", time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if claimB.Fence <= claimA.Fence || len(claimB.Reconnect.AmbiguousOperations) != 1 || claimB.Reconnect.AmbiguousOperations[0] != "op-1" {
		t.Fatalf("restart claim = %#v, want incremented fence and op-1 ambiguity", claimB)
	}
	retry, err := second.StartCall(started.Add(2*time.Second), key, "pod-b", claimB.Fence, "op-1")
	if err != nil {
		t.Fatal(err)
	}
	if !retry.AmbiguousPrevious || retry.Attempt != 2 {
		t.Fatalf("retry receipt = %#v, want ambiguous previous and attempt 2", retry)
	}
	if _, err := second.StartCall(started.Add(2*time.Second), key, "pod-b", claimB.Fence, "op-1"); err != nil {
		t.Fatalf("same-process retry should be idempotent: %v", err)
	}
	if _, err := first.CompleteCall(started.Add(2*time.Second), key, "pod-a", claimA.Fence, "op-1", true); !errors.Is(err, ErrStaleFence) {
		t.Fatalf("old owner completion = %v, want ErrStaleFence", err)
	}
	if _, err := second.CompleteCall(started.Add(2*time.Second), key, "pod-b", claimB.Fence, "op-1", true); err != nil {
		t.Fatal(err)
	}
	ops := first.Operations(key)
	if len(ops) != 1 || ops[0].Status != OperationSucceeded || ops[0].Attempt != 2 {
		t.Fatalf("persisted operation = %#v", ops)
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
