package configstore

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

type fakeVirtualKeyNotifyConn struct {
	listenErr error
	waits     chan error
	closed    atomic.Bool
	waiting   chan struct{}
	closeDone chan struct{}
}

func (c *fakeVirtualKeyNotifyConn) Listen(context.Context) error { return c.listenErr }
func (c *fakeVirtualKeyNotifyConn) WaitForNotification(ctx context.Context) error {
	if c.waiting != nil {
		select {
		case c.waiting <- struct{}{}:
		default:
		}
	}
	select {
	case <-ctx.Done():
		return ctx.Err()
	case err := <-c.waits:
		return err
	}
}
func (c *fakeVirtualKeyNotifyConn) Close(context.Context) error {
	c.closed.Store(true)
	if c.closeDone != nil {
		select {
		case <-c.closeDone:
		default:
			close(c.closeDone)
		}
	}
	return nil
}

func TestVirtualKeyInvalidationWakeupsUnsupportedForSQLite(t *testing.T) {
	store := setupVKInvalidationTestStore(t)
	require.Nil(t, store.VirtualKeyInvalidationWakeups(context.Background()))
}

func TestVirtualKeyInvalidationWakeupsCoalesceAndReconnect(t *testing.T) {
	first := &fakeVirtualKeyNotifyConn{waits: make(chan error, 2)}
	second := &fakeVirtualKeyNotifyConn{waits: make(chan error, 2)}
	connections := []virtualKeyInvalidationNotifyConn{first, second}
	var mu sync.Mutex
	store := &RDBConfigStore{}
	var metricMu sync.Mutex
	metrics := map[string]float64{}
	store.SetVirtualKeyInvalidationMetricSink(func(name string, value float64) {
		metricMu.Lock()
		metrics[name] += value
		metricMu.Unlock()
	})
	store.virtualKeyInvalidationNotifyDial = func(context.Context) (virtualKeyInvalidationNotifyConn, error) {
		mu.Lock()
		defer mu.Unlock()
		if len(connections) == 0 {
			return nil, errors.New("no more fake connections")
		}
		conn := connections[0]
		connections = connections[1:]
		return conn, nil
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	wake := store.VirtualKeyInvalidationWakeups(ctx)

	// Successful LISTEN emits a synthetic wake to cover notifications missed
	// while disconnected.
	select {
	case <-wake:
	case <-time.After(time.Second):
		t.Fatal("initial listener did not wake")
	}

	// Multiple notifications coalesce into the channel's single buffered hint.
	first.waits <- nil
	first.waits <- nil
	require.Eventually(t, func() bool { return len(wake) == 1 }, time.Second, 10*time.Millisecond)
	time.Sleep(20 * time.Millisecond)
	require.Len(t, wake, 1)
	<-wake

	// A failed wait closes the old connection, reconnects, and emits another
	// synthetic wake. Durable polling, not the notification, fills the gap.
	first.waits <- errors.New("connection lost")
	select {
	case <-wake:
	case <-time.After(2 * time.Second):
		t.Fatal("listener did not reconnect")
	}
	require.Eventually(t, first.closed.Load, time.Second, 10*time.Millisecond)
	metricMu.Lock()
	defer metricMu.Unlock()
	require.GreaterOrEqual(t, metrics["listener_reconnects"], float64(2), "initial listen and reconnect should be observable")
	require.GreaterOrEqual(t, metrics["wakeups"], float64(2), "initial and reconnect wake hints should be observable")
}

func TestVirtualKeyInvalidationWakeupsHundredConsumersCoalesceStorm(t *testing.T) {
	const consumers = 100
	type listener struct {
		store *RDBConfigStore
		conn  *fakeVirtualKeyNotifyConn
		wake  <-chan struct{}
	}
	listeners := make([]listener, 0, consumers)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	for i := 0; i < consumers; i++ {
		conn := &fakeVirtualKeyNotifyConn{waits: make(chan error, 256)}
		store := &RDBConfigStore{}
		store.virtualKeyInvalidationNotifyDial = func(context.Context) (virtualKeyInvalidationNotifyConn, error) {
			return conn, nil
		}
		wake := store.VirtualKeyInvalidationWakeups(ctx)
		select {
		case <-wake: // synthetic wake after LISTEN establishes the durable poll edge
		case <-time.After(time.Second):
			t.Fatalf("consumer %d did not establish its listener", i)
		}
		listeners = append(listeners, listener{store: store, conn: conn, wake: wake})
	}

	// A notification storm must remain a bounded wake hint per consumer. The
	// durable outbox is still authoritative, so no consumer needs one channel
	// signal per database notification.
	for i := range listeners {
		for n := 0; n < 100; n++ {
			listeners[i].conn.waits <- nil
		}
	}
	for i := range listeners {
		require.Eventually(t, func() bool { return len(listeners[i].wake) == 1 }, time.Second, 5*time.Millisecond,
			"consumer %d should coalesce a notification storm", i)
		require.Len(t, listeners[i].wake, 1)
	}
}

func TestVirtualKeyInvalidationListenerCancellationInterruptsBackoff(t *testing.T) {
	store := &RDBConfigStore{}
	var dialCalls atomic.Int32
	store.virtualKeyInvalidationNotifyDial = func(context.Context) (virtualKeyInvalidationNotifyConn, error) {
		dialCalls.Add(1)
		return nil, errors.New("database unavailable")
	}
	ctx, cancel := context.WithCancel(context.Background())
	wake := store.VirtualKeyInvalidationWakeups(ctx)
	require.NotNil(t, wake)
	require.Eventually(t, func() bool { return dialCalls.Load() == 1 }, time.Second, time.Millisecond)
	cancel()
	// The channel deliberately remains open: consumers select on their shared
	// context and cannot spin on a closed optional wake channel.
	select {
	case _, ok := <-wake:
		require.True(t, ok)
	case <-time.After(50 * time.Millisecond):
	}
	// Cancellation must interrupt the reconnect timer. Waiting beyond the
	// minimum backoff proves the listener did not redial after shutdown.
	time.Sleep(2 * virtualKeyInvalidationReconnectMinBackoff)
	require.Equal(t, int32(1), dialCalls.Load())
}

func TestVirtualKeyInvalidationListenerCancellationClosesActiveConnection(t *testing.T) {
	conn := &fakeVirtualKeyNotifyConn{
		waits:     make(chan error),
		waiting:   make(chan struct{}, 1),
		closeDone: make(chan struct{}),
	}
	store := &RDBConfigStore{}
	store.virtualKeyInvalidationNotifyDial = func(context.Context) (virtualKeyInvalidationNotifyConn, error) {
		return conn, nil
	}
	ctx, cancel := context.WithCancel(context.Background())
	wake := store.VirtualKeyInvalidationWakeups(ctx)
	require.NotNil(t, wake)
	select {
	case <-conn.waiting:
	case <-time.After(time.Second):
		t.Fatal("listener never entered WaitForNotification")
	}
	cancel()
	select {
	case <-conn.closeDone:
	case <-time.After(time.Second):
		t.Fatal("active listener connection was not closed after cancellation")
	}
	require.True(t, conn.closed.Load())
}

func TestVirtualKeyInvalidationListenerBacksOffAcrossAcceptThenDrop(t *testing.T) {
	dials := make(chan time.Time, 4)
	store := &RDBConfigStore{}
	store.virtualKeyInvalidationNotifyDial = func(context.Context) (virtualKeyInvalidationNotifyConn, error) {
		dials <- time.Now()
		waits := make(chan error, 1)
		waits <- errors.New("session dropped immediately")
		return &fakeVirtualKeyNotifyConn{waits: waits}, nil
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	_ = store.VirtualKeyInvalidationWakeups(ctx)

	nextDial := func() time.Time {
		t.Helper()
		select {
		case at := <-dials:
			return at
		case <-time.After(2 * time.Second):
			t.Fatal("listener did not attempt the expected reconnect")
			return time.Time{}
		}
	}
	first := nextDial()
	second := nextDial()
	third := nextDial()
	cancel()
	firstDelay := second.Sub(first)
	secondDelay := third.Sub(second)
	require.GreaterOrEqual(t, firstDelay, 75*time.Millisecond)
	require.Greater(t, secondDelay, firstDelay+firstDelay/4,
		"short-lived LISTEN sessions must retain exponential reconnect backoff")
}

func TestJitterVirtualKeyInvalidationBackoffIsBounded(t *testing.T) {
	base := time.Second
	for _, salt := range []int64{-99, 0, 1, 99, time.Now().UnixNano()} {
		got := jitterVirtualKeyInvalidationBackoff(base, salt)
		require.GreaterOrEqual(t, got, 800*time.Millisecond)
		require.LessOrEqual(t, got, 1200*time.Millisecond)
	}
}
