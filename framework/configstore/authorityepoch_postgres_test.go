package configstore

import (
	"context"
	"errors"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/stretchr/testify/require"
	"gorm.io/gorm"
)

func waitForPrincipalAuthorizationEpochNotificationPayload(ctx context.Context, conn *pgx.Conn, want string) error {
	for {
		notification, err := conn.WaitForNotification(ctx)
		if err != nil {
			return err
		}
		if notification.Channel == principalAuthorizationEpochNotificationChannel && notification.Payload == want {
			return nil
		}
	}
}

func TestPostgresPrincipalAuthorizationEpochConcurrentAdvanceSerializes(t *testing.T) {
	store := setupPostgresDeadlockStore(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	principal := testAuthorityPrincipal()

	_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1)
	require.NoError(t, err)
	before, err := store.GetPrincipalAuthorizationEpochHighWatermark(ctx)
	require.NoError(t, err)

	const workers = 6
	start := make(chan struct{})
	errs := make(chan error, workers)
	var wg sync.WaitGroup
	for range workers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			_, err := store.AdvancePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonGroupRemoved)
			errs <- err
		}()
	}
	close(start)
	wg.Wait()
	close(errs)
	for err := range errs {
		require.NoError(t, err)
	}

	row, err := store.GetPrincipalAuthorizationEpoch(ctx, principal)
	require.NoError(t, err)
	require.Equal(t, uint64(1+workers), row.Epoch)
	require.True(t, row.Active)

	events, err := store.ListPrincipalAuthorizationEpochEventsAfter(ctx, before, workers)
	require.NoError(t, err)
	require.Len(t, events, workers)
	newEpochs := make([]uint64, 0, len(events))
	for _, event := range events {
		require.Equal(t, string(authorityepoch.ReasonGroupRemoved), event.Reason)
		require.True(t, event.Active)
		newEpochs = append(newEpochs, event.NewEpoch)
	}
	sort.Slice(newEpochs, func(i, j int) bool { return newEpochs[i] < newEpochs[j] })
	require.Equal(t, []uint64{2, 3, 4, 5, 6, 7}, newEpochs)
}

func TestPostgresPrincipalAuthorizationEpochConcurrentFirstActivationConvergesMonotonically(t *testing.T) {
	store := setupPostgresDeadlockStore(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	principal := testAuthorityPrincipal()

	epochs := []uint64{4, 1, 6, 2, 5, 3}
	start := make(chan struct{})
	type result struct {
		epoch uint64
		err   error
	}
	results := make(chan result, len(epochs))
	var wg sync.WaitGroup
	for _, epoch := range epochs {
		wg.Add(1)
		go func(epoch uint64) {
			defer wg.Done()
			<-start
			_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, principal, epoch)
			results <- result{epoch: epoch, err: err}
		}(epoch)
	}
	close(start)
	wg.Wait()
	close(results)

	var sawSuccess bool
	for res := range results {
		if res.err == nil {
			sawSuccess = true
			continue
		}
		require.ErrorIs(t, res.err, authorityepoch.ErrStaleEpoch)
		require.NotContains(t, strings.ToLower(res.err.Error()), "duplicate key")
		require.NotContains(t, strings.ToLower(res.err.Error()), "unique")
	}
	require.True(t, sawSuccess, "at least one activation should succeed")

	row, err := store.GetPrincipalAuthorizationEpoch(ctx, principal)
	require.NoError(t, err)
	require.Equal(t, uint64(6), row.Epoch)
	require.True(t, row.Active)

	events, err := store.ListPrincipalAuthorizationEpochEventsAfter(ctx, 0, len(epochs))
	require.NoError(t, err)
	require.NotEmpty(t, events)
	for i := 1; i < len(events); i++ {
		require.Greater(t, events[i].NewEpoch, events[i-1].NewEpoch)
	}
	require.Equal(t, uint64(6), events[len(events)-1].NewEpoch)
}

func TestPostgresPrincipalAuthorizationEpochNotifiesOnlyOnCommit(t *testing.T) {
	store := setupPostgresDeadlockStore(t)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	listener, err := pgx.Connect(ctx, postgresDSN)
	if err != nil {
		t.Skipf("postgres notification connection unavailable: %v", err)
	}
	require.NoError(t, (&pgxPrincipalAuthorizationEpochNotifyConn{conn: listener}).Listen(ctx))
	t.Cleanup(func() {
		closeCtx, closeCancel := context.WithTimeout(context.Background(), time.Second)
		defer closeCancel()
		_ = listener.Close(closeCtx)
	})

	principal := testAuthorityPrincipal()
	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1, tx)
		return err
	}))
	waitCtx, waitCancel := context.WithTimeout(context.Background(), 2*time.Second)
	require.NoError(t, waitForPrincipalAuthorizationEpochNotificationPayload(waitCtx, listener, ""))
	waitCancel()

	rollbackPrincipal := authorityepoch.Principal{
		Tenant:  "tenant-a",
		Issuer:  principal.Issuer,
		Subject: "rollback-subject",
	}
	sentinel := errors.New("force rollback")
	err = store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, rollbackPrincipal, 1, tx)
		if err != nil {
			return err
		}
		return sentinel
	})
	require.ErrorIs(t, err, sentinel)
	rollbackCtx, rollbackCancel := context.WithTimeout(context.Background(), 250*time.Millisecond)
	defer rollbackCancel()
	_, err = listener.WaitForNotification(rollbackCtx)
	require.ErrorIs(t, err, context.DeadlineExceeded)
}
