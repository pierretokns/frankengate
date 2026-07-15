package configstore

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/require"
)

func TestPrincipalAuthorizationEpochWakeupsUnsupportedForSQLite(t *testing.T) {
	store := setupAuthorityEpochTestStore(t)
	require.Nil(t, store.PrincipalAuthorizationEpochWakeups(context.Background()))
}

func TestPrincipalAuthorizationEpochWakeupsCoalesceAndReconnect(t *testing.T) {
	first := &fakeVirtualKeyNotifyConn{waits: make(chan error, 2)}
	second := &fakeVirtualKeyNotifyConn{waits: make(chan error, 2)}
	connections := []principalAuthorizationEpochNotifyConn{first, second}
	var mu sync.Mutex
	store := &RDBConfigStore{}
	store.principalAuthorizationEpochNotifyDial = func(context.Context) (principalAuthorizationEpochNotifyConn, error) {
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
	wake := store.PrincipalAuthorizationEpochWakeups(ctx)

	select {
	case <-wake:
	case <-time.After(time.Second):
		t.Fatal("initial authority-epoch listener did not wake")
	}

	first.waits <- nil
	first.waits <- nil
	require.Eventually(t, func() bool { return len(wake) == 1 }, time.Second, 10*time.Millisecond)
	time.Sleep(20 * time.Millisecond)
	require.Len(t, wake, 1)
	<-wake

	first.waits <- errors.New("connection lost")
	select {
	case <-wake:
	case <-time.After(2 * time.Second):
		t.Fatal("authority-epoch listener did not reconnect")
	}
	require.Eventually(t, first.closed.Load, time.Second, 10*time.Millisecond)
}
