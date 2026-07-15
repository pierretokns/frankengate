package server

import (
	"context"
	"testing"

	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/plugins/governance"
	"github.com/stretchr/testify/require"
)

func TestEvictVirtualKeyRuntimeRecoversDeletedAuthoritySecretFromMemory(t *testing.T) {
	ctx := context.Background()
	store, err := governance.NewLocalGovernanceStore(
		ctx,
		bifrost.NewDefaultLogger(schemas.LogLevelError),
		nil,
		&configstore.GovernanceConfig{},
		nil,
	)
	require.NoError(t, err)

	vk := &tables.TableVirtualKey{
		ID:    "vk-deleted-on-peer",
		Name:  "deleted-on-peer",
		Value: *schemas.NewSecretVar("sk-bf-deleted-on-peer"),
	}
	store.CreateVirtualKeyInMemory(ctx, vk)

	var evictedMCPValue string
	evictVirtualKeyRuntime(ctx, store, vk.ID, "", func(value string) {
		// The MCP capability must be evicted before the governance entry, because
		// after deletion the old secret is no longer recoverable from authority.
		_, stillPresent := store.GetVirtualKey(ctx, value)
		require.True(t, stillPresent)
		evictedMCPValue = value
	})

	require.Equal(t, vk.Value.GetValue(), evictedMCPValue)
	_, presentByValue := store.GetVirtualKey(ctx, vk.Value.GetValue())
	require.False(t, presentByValue)
	_, presentByID := store.GetVirtualKeyByID(ctx, vk.ID)
	require.False(t, presentByID)
}

func TestEvictVirtualKeyRuntimeUsesKnownAuthorityValue(t *testing.T) {
	ctx := context.Background()
	store, err := governance.NewLocalGovernanceStore(
		ctx,
		bifrost.NewDefaultLogger(schemas.LogLevelError),
		nil,
		&configstore.GovernanceConfig{},
		nil,
	)
	require.NoError(t, err)

	var evicted string
	evictVirtualKeyRuntime(ctx, store, "vk-not-in-memory", "sk-bf-known", func(value string) {
		evicted = value
	})
	require.Equal(t, "sk-bf-known", evicted)
}
