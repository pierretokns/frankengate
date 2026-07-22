package configstore

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

type fakeConfigChangefeedNotifyConn struct {
	waits  chan error
	closed atomic.Bool
}

func (f *fakeConfigChangefeedNotifyConn) Listen(context.Context) error { return nil }
func (f *fakeConfigChangefeedNotifyConn) WaitForNotification(ctx context.Context) error {
	select {
	case err := <-f.waits:
		return err
	case <-ctx.Done():
		return ctx.Err()
	}
}
func (f *fakeConfigChangefeedNotifyConn) Close(context.Context) error {
	f.closed.Store(true)
	return nil
}

func TestConfigChangefeedWakeupsCoalesceAndReconnect(t *testing.T) {
	first := &fakeConfigChangefeedNotifyConn{waits: make(chan error, 2)}
	second := &fakeConfigChangefeedNotifyConn{waits: make(chan error, 1)}
	connections := []configChangefeedNotifyConn{first, second}
	store := &RDBConfigStore{}
	store.configChangefeedNotifyDial = func(context.Context) (configChangefeedNotifyConn, error) {
		if len(connections) == 0 {
			return nil, errors.New("no more connections")
		}
		c := connections[0]
		connections = connections[1:]
		return c, nil
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	wake := store.ConfigChangefeedWakeups(ctx)
	select {
	case <-wake:
	case <-time.After(time.Second):
		t.Fatal("listener did not become ready")
	}
	first.waits <- nil
	first.waits <- nil
	time.Sleep(20 * time.Millisecond)
	if len(wake) != 1 {
		t.Fatalf("wake storm was not coalesced: %d", len(wake))
	}
	<-wake
	first.waits <- errors.New("connection lost")
	select {
	case <-wake:
	case <-time.After(2 * time.Second):
		t.Fatal("listener did not reconnect")
	}
	if !first.closed.Load() {
		t.Fatal("lost listener was not closed")
	}
}

func TestConfigChangefeedWakeupsWithPollingSurvivesMissingListener(t *testing.T) {
	store := &RDBConfigStore{}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	wake := store.ConfigChangefeedWakeupsWithPolling(ctx, 10*time.Millisecond)
	select {
	case <-wake:
	case <-time.After(250 * time.Millisecond):
		t.Fatal("polling fallback did not emit a wakeup")
	}
}

func testChangefeedDB(t *testing.T) *gorm.DB {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	require.NoError(t, err)
	require.NoError(t, EnsureConfigChangefeedSchema(context.Background(), db))
	return db
}

func TestConfigChangefeedPreservesScopedGenerationCursor(t *testing.T) {
	db := testChangefeedDB(t)
	ctx := context.Background()
	var first, second ConfigChangefeedEvent
	require.NoError(t, db.Transaction(func(tx *gorm.DB) error {
		var err error
		first, err = AppendConfigChangefeed(ctx, tx, "global", "provider", "mantle", []byte(`{"v":1}`))
		return err
	}))
	require.NoError(t, db.Transaction(func(tx *gorm.DB) error {
		var err error
		second, err = AppendConfigChangefeed(ctx, tx, "global", "provider", "openai", []byte(`{"v":2}`))
		return err
	}))
	require.Equal(t, uint64(1), first.Generation)
	require.Equal(t, uint64(1), first.Cursor)
	require.Equal(t, uint64(2), second.Cursor)
	events, err := ListConfigChangefeedAfter(ctx, db, "global", 1, 0, 10)
	require.NoError(t, err)
	require.Len(t, events, 2)
	require.Equal(t, second.PayloadSHA, events[1].PayloadSHA)
	other, err := ListConfigChangefeedAfter(ctx, db, "tenant-a", 1, 0, 10)
	require.NoError(t, err)
	require.Empty(t, other)
}

func TestConfigChangefeedRollbackLeavesNoEventOrCursor(t *testing.T) {
	db := testChangefeedDB(t)
	ctx := context.Background()
	err := db.Transaction(func(tx *gorm.DB) error {
		_, err := AppendConfigChangefeed(ctx, tx, "global", "provider", "rollback", []byte(`{"v":1}`))
		if err != nil {
			return err
		}
		return gorm.ErrInvalidTransaction
	})
	require.ErrorIs(t, err, gorm.ErrInvalidTransaction)
	events, err := ListConfigChangefeedAfter(ctx, db, "global", 1, 0, 10)
	require.NoError(t, err)
	require.Empty(t, events)
	var generation ConfigChangefeedGeneration
	require.ErrorIs(t, db.First(&generation, "scope = ?", "global").Error, gorm.ErrRecordNotFound)
}

func TestConfigChangefeedRejectsInvalidAppend(t *testing.T) {
	db := testChangefeedDB(t)
	_, err := AppendConfigChangefeed(context.Background(), db, "", "provider", "id", []byte("{}"))
	require.Error(t, err)
	_, err = AppendConfigChangefeed(context.Background(), db, "global", "provider", "id", nil)
	require.Error(t, err)
}
