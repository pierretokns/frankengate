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

type exportContextClient struct {
	ctx context.Context
	err error
}

func (c *exportContextClient) Emit(ctx context.Context, _ []*ResourceSpan) error {
	c.ctx = ctx
	c.err = ctx.Err()
	return c.err
}
func (*exportContextClient) Close() error { return nil }

type flakyExportClient struct {
	calls int
}

func (c *flakyExportClient) Emit(context.Context, []*ResourceSpan) error {
	c.calls++
	if c.calls < 3 {
		return errors.New("temporary collector outage")
	}
	return nil
}
func (*flakyExportClient) Close() error { return nil }

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

func TestInjectTraceExportDoesNotInheritCanceledRequest(t *testing.T) {
	client := &exportContextClient{}
	p := &OtelPlugin{targets: []*otelTarget{{client: client, serviceName: "test"}}}
	requestCtx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := p.Inject(requestCtx, &schemas.Trace{TraceID: "trace", Attributes: map[string]any{"tenant": "acme"}}); err != nil {
		t.Fatalf("Inject returned error: %v", err)
	}
	if client.ctx == nil {
		t.Fatal("trace exporter was not called")
	}
	if client.err != nil {
		t.Fatalf("trace export inherited canceled request context: %v", client.err)
	}
	if remaining, ok := client.ctx.Deadline(); !ok || time.Until(remaining) <= 0 || time.Until(remaining) > 30*time.Second {
		t.Fatalf("trace export must have a bounded independent deadline, deadline=%v", remaining)
	}
}

func TestInjectRetriesTransientTraceExport(t *testing.T) {
	client := &flakyExportClient{}
	p := &OtelPlugin{targets: []*otelTarget{{client: client, serviceName: "test"}}}
	if err := p.Inject(context.Background(), &schemas.Trace{TraceID: "trace"}); err != nil {
		t.Fatalf("Inject returned error: %v", err)
	}
	if client.calls != 3 {
		t.Fatalf("export attempts = %d, want 3 (initial plus two bounded retries)", client.calls)
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
