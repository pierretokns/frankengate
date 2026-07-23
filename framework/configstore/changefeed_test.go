package configstore

import (
	"context"
	"testing"

	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

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

func TestConfigChangefeedRetentionFailsClosedForStaleCursor(t *testing.T) {
	db := testChangefeedDB(t)
	ctx := context.Background()
	var events []ConfigChangefeedEvent
	for _, payload := range []string{"one", "two", "three"} {
		require.NoError(t, db.Transaction(func(tx *gorm.DB) error {
			event, err := AppendConfigChangefeed(ctx, tx, "tenant-a", "provider", payload, []byte(payload))
			if err == nil {
				events = append(events, event)
			}
			return err
		}))
	}
	require.NoError(t, db.Transaction(func(tx *gorm.DB) error {
		return RetainConfigChangefeedFrom(ctx, tx, "tenant-a", events[0].Generation, events[1].Cursor)
	}))

	_, err := ListConfigChangefeedAfter(ctx, db, "tenant-a", events[0].Generation, 0, 10)
	var stale *ConfigChangefeedCursorTooOldError
	require.ErrorAs(t, err, &stale)
	require.Equal(t, events[1].Cursor, stale.RetainedFloor)

	got, err := ListConfigChangefeedAfter(ctx, db, "tenant-a", events[0].Generation, events[1].Cursor-1, 10)
	require.NoError(t, err)
	require.Len(t, got, 2)
	require.Equal(t, events[1].Cursor, got[0].Cursor)
}

func TestConfigChangefeedRejectsInvalidAppend(t *testing.T) {
	db := testChangefeedDB(t)
	_, err := AppendConfigChangefeed(context.Background(), db, "", "provider", "id", []byte("{}"))
	require.Error(t, err)
	_, err = AppendConfigChangefeed(context.Background(), db, "global", "provider", "id", nil)
	require.Error(t, err)
}
