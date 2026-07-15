package configstore

import (
	"context"
	"errors"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
	"gorm.io/gorm"
)

func setupVKInvalidationTestStore(t *testing.T) *RDBConfigStore {
	t.Helper()
	store := setupRDBTestStore(t)
	require.NoError(t, store.DB().AutoMigrate(&tables.TableVirtualKeyInvalidationEvent{}))
	return store
}

func TestAppendVirtualKeyInvalidationRollsBackWithCallerTransaction(t *testing.T) {
	store := setupVKInvalidationTestStore(t)
	ctx := context.Background()
	wantRollback := errors.New("rollback authority change")

	err := store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		require.NoError(t, store.AppendVirtualKeyInvalidation(ctx, tx, &tables.TableVirtualKeyInvalidationEvent{
			EntityType: tables.VirtualKeyInvalidationEntityType,
			Action:     tables.VirtualKeyInvalidationActionDelete,
			EntityID:   "vk-rolled-back",
		}))
		return wantRollback
	})
	require.ErrorIs(t, err, wantRollback)

	events, err := store.ListVirtualKeyInvalidationsAfter(ctx, 0, 10)
	require.NoError(t, err)
	require.Empty(t, events)
}

func TestVirtualKeyInvalidationCursorIsStrictOrderedAndBounded(t *testing.T) {
	store := setupVKInvalidationTestStore(t)
	ctx := context.Background()
	var ids []uint64
	for _, entityID := range []string{"vk-1", "vk-2", "vk-3"} {
		event := &tables.TableVirtualKeyInvalidationEvent{
			EntityType: tables.VirtualKeyInvalidationEntityType,
			Action:     tables.VirtualKeyInvalidationActionReload,
			EntityID:   entityID,
		}
		require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
			return store.AppendVirtualKeyInvalidation(ctx, tx, event)
		}))
		ids = append(ids, event.ID)
	}

	firstBatch, err := store.ListVirtualKeyInvalidationsAfter(ctx, 0, 2)
	require.NoError(t, err)
	require.Equal(t, []uint64{ids[0], ids[1]}, []uint64{firstBatch[0].ID, firstBatch[1].ID})

	// Re-reading the same cursor is deliberately safe and returns stable event IDs.
	replayed, err := store.ListVirtualKeyInvalidationsAfter(ctx, 0, 2)
	require.NoError(t, err)
	require.Equal(t, firstBatch, replayed)

	secondBatch, err := store.ListVirtualKeyInvalidationsAfter(ctx, firstBatch[1].ID, 2)
	require.NoError(t, err)
	require.Len(t, secondBatch, 1)
	require.Equal(t, ids[2], secondBatch[0].ID)

	_, err = store.ListVirtualKeyInvalidationsAfter(ctx, 0, 0)
	require.Error(t, err)
	_, err = store.ListVirtualKeyInvalidationsAfter(ctx, 0, MaxVirtualKeyInvalidationBatchSize+1)
	require.Error(t, err)
}

func TestVirtualKeyInvalidationValidatesContractAndReportsHighWatermark(t *testing.T) {
	store := setupVKInvalidationTestStore(t)
	ctx := context.Background()

	highWatermark, err := store.GetVirtualKeyInvalidationHighWatermark(ctx)
	require.NoError(t, err)
	require.Zero(t, highWatermark)

	tests := []struct {
		name  string
		event *tables.TableVirtualKeyInvalidationEvent
	}{
		{name: "nil event", event: nil},
		{name: "wrong entity", event: &tables.TableVirtualKeyInvalidationEvent{EntityType: "team", Action: tables.VirtualKeyInvalidationActionReload, EntityID: "vk-1"}},
		{name: "wrong action", event: &tables.TableVirtualKeyInvalidationEvent{EntityType: tables.VirtualKeyInvalidationEntityType, Action: "upsert", EntityID: "vk-1"}},
		{name: "blank id", event: &tables.TableVirtualKeyInvalidationEvent{EntityType: tables.VirtualKeyInvalidationEntityType, Action: tables.VirtualKeyInvalidationActionReload, EntityID: "  "}},
		{name: "future schema", event: &tables.TableVirtualKeyInvalidationEvent{EntityType: tables.VirtualKeyInvalidationEntityType, Action: tables.VirtualKeyInvalidationActionReload, EntityID: "vk-1", SchemaVersion: 2}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
				return store.AppendVirtualKeyInvalidation(ctx, tx, tt.event)
			})
			require.Error(t, err)
		})
	}
	require.Error(t, store.AppendVirtualKeyInvalidation(ctx, nil, &tables.TableVirtualKeyInvalidationEvent{}))

	tenant, scope := "tenant-a", "internal"
	event := &tables.TableVirtualKeyInvalidationEvent{
		EntityType: tables.VirtualKeyInvalidationEntityType,
		Action:     tables.VirtualKeyInvalidationActionDelete,
		EntityID:   "vk-valid",
		TenantID:   &tenant,
		Scope:      &scope,
	}
	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		return store.AppendVirtualKeyInvalidation(ctx, tx, event)
	}))
	require.Equal(t, tables.VirtualKeyInvalidationSchemaVersion, event.SchemaVersion)

	highWatermark, err = store.GetVirtualKeyInvalidationHighWatermark(ctx)
	require.NoError(t, err)
	require.Equal(t, event.ID, highWatermark)
	events, err := store.ListVirtualKeyInvalidationsAfter(ctx, 0, 1)
	require.NoError(t, err)
	require.Equal(t, &tenant, events[0].TenantID)
	require.Equal(t, &scope, events[0].Scope)
}

func TestAppendVirtualKeyInvalidationCommitsWithCallerTransaction(t *testing.T) {
	store := setupVKInvalidationTestStore(t)
	ctx := context.Background()

	event := &tables.TableVirtualKeyInvalidationEvent{
		EntityType: tables.VirtualKeyInvalidationEntityType,
		Action:     tables.VirtualKeyInvalidationActionReload,
		EntityID:   "vk-123",
	}
	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		return store.AppendVirtualKeyInvalidation(ctx, tx, event)
	}))
	require.NotZero(t, event.ID)

	events, err := store.ListVirtualKeyInvalidationsAfter(ctx, 0, 10)
	require.NoError(t, err)
	require.Len(t, events, 1)
	require.Equal(t, event.ID, events[0].ID)
	require.Equal(t, event.EntityType, events[0].EntityType)
	require.Equal(t, event.Action, events[0].Action)
	require.Equal(t, event.EntityID, events[0].EntityID)
	require.Equal(t, event.SchemaVersion, events[0].SchemaVersion)
	require.True(t, event.CreatedAt.Equal(events[0].CreatedAt))
}

func TestUpdateMCPClientConfigInvalidatesEveryReferencingVirtualKey(t *testing.T) {
	store := setupVKInvalidationTestStore(t)
	ctx := context.Background()
	client := &tables.TableMCPClient{ClientID: "mcp-1", Name: "tools", ConnectionType: "http"}
	require.NoError(t, store.DB().WithContext(ctx).Create(client).Error)
	for _, id := range []string{"vk-b", "vk-a"} {
		require.NoError(t, store.CreateVirtualKey(ctx, &tables.TableVirtualKey{ID: id, Name: id, Value: *schemas.NewSecretVar("sk-bf-" + id)}))
		require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableVirtualKeyMCPConfig{
			VirtualKeyID: id,
			MCPClientID:  client.ID,
		}).Error)
	}

	client.Name = "renamed-tools"
	require.NoError(t, store.UpdateMCPClientConfig(ctx, client.ClientID, client))
	events, err := store.ListVirtualKeyInvalidationsAfter(ctx, 0, 10)
	require.NoError(t, err)
	require.Len(t, events, 2)
	require.Equal(t, []string{"vk-a", "vk-b"}, []string{events[0].EntityID, events[1].EntityID})
	for _, event := range events {
		require.Equal(t, tables.VirtualKeyInvalidationActionReload, event.Action)
	}
}
