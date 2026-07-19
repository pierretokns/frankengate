package otel

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

type replayContextStore struct {
	ctx    context.Context
	putErr error
}

func (s *replayContextStore) Put(ctx context.Context, _ *schemas.Trace) error {
	s.ctx = ctx
	s.putErr = ctx.Err()
	return s.putErr
}
func (*replayContextStore) Get(context.Context, string, string) (*ReplayRecord, error) {
	return nil, errors.New("unused")
}
func (*replayContextStore) List(context.Context, string, int) ([]ReplayRecord, error) {
	return nil, errors.New("unused")
}
func (*replayContextStore) Close() error { return nil }

func TestInjectReplayPersistenceDoesNotInheritCanceledRequest(t *testing.T) {
	store := &replayContextStore{}
	p := &OtelPlugin{replayStore: store}
	requestCtx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := p.Inject(requestCtx, &schemas.Trace{TraceID: "trace", Attributes: map[string]any{"tenant": "acme"}}); err != nil {
		t.Fatalf("Inject returned error: %v", err)
	}
	if store.ctx == nil {
		t.Fatal("replay store was not called")
	}
	if err := store.putErr; err != nil {
		t.Fatalf("replay context was canceled before Put completed: %v", err)
	}
	if _, ok := store.ctx.Deadline(); !ok {
		t.Fatal("replay persistence must have a bounded deadline")
	}
	// Ensure the deadline is materially independent from the canceled request
	// and does not leave a long-lived context behind.
	if remaining := time.Until(mustDeadline(t, store.ctx)); remaining <= 0 || remaining > 5*time.Second {
		t.Fatalf("unexpected replay deadline remaining: %s", remaining)
	}
}

func mustDeadline(t *testing.T, ctx context.Context) time.Time {
	t.Helper()
	deadline, ok := ctx.Deadline()
	if !ok {
		t.Fatal("missing deadline")
	}
	return deadline
}
