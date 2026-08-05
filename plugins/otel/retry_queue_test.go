package otel

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

type queuedRetryClient struct {
	mu       sync.Mutex
	calls    int
	failures int
	called   chan struct{}
}

func (c *queuedRetryClient) Emit(context.Context, []*ResourceSpan) error {
	c.mu.Lock()
	c.calls++
	calls := c.calls
	c.mu.Unlock()
	select {
	case c.called <- struct{}{}:
	default:
	}
	if calls <= c.failures {
		return errors.New("collector unavailable")
	}
	return nil
}

func (*queuedRetryClient) Close() error { return nil }

func (c *queuedRetryClient) count() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.calls
}

func TestTraceRetryWorkerRecoversAfterCollectorOutage(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	client := &queuedRetryClient{failures: 1, called: make(chan struct{}, 4)}
	p := &OtelPlugin{ctx: ctx, retryQueue: make(chan traceDeliveryRetry, 2), retryBackoff: time.Millisecond}
	p.retryWG.Add(1)
	go p.runTraceRetryWorker()

	p.enqueueTraceRetry(&otelTarget{client: client, serviceName: "test"}, &schemas.Trace{TraceID: "trace"})
	deadline := time.After(time.Second)
	for client.count() < 2 {
		select {
		case <-client.called:
		case <-deadline:
			t.Fatalf("retry calls = %d, want at least 2", client.count())
		}
	}
	cancel()
	p.retryWG.Wait()
}

func TestTraceRetryQueueDropsWhenFull(t *testing.T) {
	p := &OtelPlugin{retryQueue: make(chan traceDeliveryRetry, 1)}
	target := &otelTarget{serviceName: "test"}
	trace := &schemas.Trace{TraceID: "trace"}
	p.enqueueTraceRetry(target, trace)
	p.enqueueTraceRetry(target, trace)
	if got := len(p.retryQueue); got != 1 {
		t.Fatalf("retry queue length = %d, want 1 after bounded drop", got)
	}
}
