package configstore

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

func setupVirtualKeyNotifyPostgresTest(t *testing.T) (*RDBConfigStore, *pgx.Conn) {
	t.Helper()
	db, err := gorm.Open(postgres.Open(postgresDSN), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Skipf("postgres unavailable: %v", err)
	}
	sqlDB, err := db.DB()
	if err != nil {
		t.Skipf("postgres sql DB unavailable: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	if err := sqlDB.PingContext(ctx); err != nil {
		t.Skipf("postgres unavailable: %v", err)
	}
	require.NoError(t, db.AutoMigrate(&tables.TableVirtualKeyInvalidationEvent{}))

	listener, err := pgx.Connect(ctx, postgresDSN)
	if err != nil {
		t.Skipf("postgres notification connection unavailable: %v", err)
	}
	require.NoError(t, (&pgxVirtualKeyInvalidationNotifyConn{conn: listener}).Listen(ctx))
	t.Cleanup(func() {
		closeCtx, closeCancel := context.WithTimeout(context.Background(), time.Second)
		defer closeCancel()
		_ = listener.Close(closeCtx)
		_ = sqlDB.Close()
	})
	store := &RDBConfigStore{}
	store.db.Store(db)
	return store, listener
}

func waitForVirtualKeyNotificationPayload(ctx context.Context, conn *pgx.Conn, want string) error {
	for {
		notification, err := conn.WaitForNotification(ctx)
		if err != nil {
			return err
		}
		if notification.Channel == virtualKeyInvalidationNotificationChannel && notification.Payload == want {
			return nil
		}
	}
}

func TestAppendVirtualKeyInvalidationPostgresNotifiesOnlyOnCommit(t *testing.T) {
	store, listener := setupVirtualKeyNotifyPostgresTest(t)
	ctx := context.Background()
	event := &tables.TableVirtualKeyInvalidationEvent{
		EntityType: tables.VirtualKeyInvalidationEntityType,
		Action:     tables.VirtualKeyInvalidationActionReload,
		EntityID:   "notify-commit",
	}
	secondEvent := &tables.TableVirtualKeyInvalidationEvent{
		EntityType: tables.VirtualKeyInvalidationEntityType,
		Action:     tables.VirtualKeyInvalidationActionReload,
		EntityID:   "notify-commit-second",
	}
	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		if err := store.AppendVirtualKeyInvalidation(ctx, tx, event); err != nil {
			return err
		}
		return store.AppendVirtualKeyInvalidation(ctx, tx, secondEvent)
	}))
	waitCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	require.NoError(t, waitForVirtualKeyNotificationPayload(waitCtx, listener, ""))
	coalesceCtx, coalesceCancel := context.WithTimeout(ctx, 100*time.Millisecond)
	_, err := listener.WaitForNotification(coalesceCtx)
	coalesceCancel()
	require.ErrorIs(t, err, context.DeadlineExceeded, "identical wake hints in one transaction must coalesce")

	rollbackEvent := &tables.TableVirtualKeyInvalidationEvent{
		EntityType: tables.VirtualKeyInvalidationEntityType,
		Action:     tables.VirtualKeyInvalidationActionReload,
		EntityID:   "notify-rollback",
	}
	sentinel := errors.New("force rollback")
	err = store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		if err := store.AppendVirtualKeyInvalidation(ctx, tx, rollbackEvent); err != nil {
			return err
		}
		return sentinel
	})
	require.ErrorIs(t, err, sentinel)
	rollbackWaitCtx, rollbackCancel := context.WithTimeout(ctx, 250*time.Millisecond)
	defer rollbackCancel()
	_, err = listener.WaitForNotification(rollbackWaitCtx)
	require.ErrorIs(t, err, context.DeadlineExceeded, "rolled-back pg_notify must not be delivered")
}

func TestVirtualKeyInvalidationListenerDoesNotConsumeGORMPool(t *testing.T) {
	store, manualListener := setupVirtualKeyNotifyPostgresTest(t)
	// This connection only establishes that the fixture is ready; the listener
	// under test must use its own physical connection.
	require.NoError(t, manualListener.Close(context.Background()))

	sqlDB, err := store.DB().DB()
	require.NoError(t, err)
	sqlDB.SetMaxOpenConns(1)
	sqlDB.SetMaxIdleConns(1)
	store.virtualKeyInvalidationNotifyDial = func(ctx context.Context) (virtualKeyInvalidationNotifyConn, error) {
		conn, err := pgx.Connect(ctx, postgresDSN)
		if err != nil {
			return nil, err
		}
		return &pgxVirtualKeyInvalidationNotifyConn{conn: conn}, nil
	}

	ctx, cancel := context.WithCancel(context.Background())
	wake := store.VirtualKeyInvalidationWakeups(ctx)
	select {
	case <-wake: // synthetic wake proves LISTEN is active
	case <-time.After(2 * time.Second):
		cancel()
		t.Fatal("dedicated listener did not become ready")
	}

	queryCtx, queryCancel := context.WithTimeout(context.Background(), time.Second)
	_, err = store.GetVirtualKeyInvalidationHighWatermark(queryCtx)
	queryCancel()
	cancel()
	require.NoError(t, err, "LISTEN must not consume the only database/sql connection")
}
