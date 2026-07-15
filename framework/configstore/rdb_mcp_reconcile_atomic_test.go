package configstore

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
	"gorm.io/gorm"
)

func seedMCPReconcileAtomicFixture(t *testing.T, store *RDBConfigStore, granted bool) {
	t.Helper()
	ctx := context.Background()
	mcpClient := &tables.TableMCPClient{ClientID: "mcp-atomic", Name: "Atomic MCP", ConnectionType: "stdio"}
	require.NoError(t, store.DB().WithContext(ctx).Create(mcpClient).Error)
	vk := &tables.TableVirtualKey{ID: "vk-atomic", Name: "Atomic VK", Value: *schemas.NewSecretVar("sk-bf-atomic")}
	require.NoError(t, store.DB().WithContext(ctx).Create(vk).Error)
	if granted {
		require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableVirtualKeyMCPConfig{
			VirtualKeyID: vk.ID,
			MCPClientID:  mcpClient.ID,
		}).Error)
	}
	vkID := vk.ID
	require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableOauthUserToken{
		ID: "oauth-atomic", MCPClientID: mcpClient.ClientID, VirtualKeyID: &vkID,
		AuthMode: string(schemas.MCPAuthModeVK), Status: "active", AccessToken: "token",
		TokenType: "Bearer", OauthConfigID: "oauth-config",
	}).Error)
	require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableMCPPerUserHeaderCredential{
		ID: "header-atomic", MCPClientID: mcpClient.ClientID, VirtualKeyID: &vkID,
		AuthMode: string(schemas.MCPAuthModeVK), Status: "active", HeadersJSON: "{}",
	}).Error)
}

func credentialStatuses(t *testing.T, store *RDBConfigStore) (string, string) {
	t.Helper()
	var oauth tables.TableOauthUserToken
	var header tables.TableMCPPerUserHeaderCredential
	require.NoError(t, store.DB().Unscoped().First(&oauth, "id = ?", "oauth-atomic").Error)
	require.NoError(t, store.DB().Unscoped().First(&header, "id = ?", "header-atomic").Error)
	return oauth.Status, header.Status
}

func TestReconcileCredentialsAfterMCPChangeTxRequiresTransaction(t *testing.T) {
	store := setupRDBTestStore(t)
	err := store.ReconcileCredentialsAfterMCPChangeTx(context.Background(), nil, "mcp-atomic", false)
	require.ErrorContains(t, err, "transaction is required")
}

func TestReconcileCredentialsAfterMCPChangeTxRollsBackBothSurfaces(t *testing.T) {
	store := setupRDBTestStore(t)
	seedMCPReconcileAtomicFixture(t, store, true)
	before, err := store.GetMCPClientByID(context.Background(), "mcp-atomic")
	require.NoError(t, err)

	// OAuth is reconciled first. Force the subsequent header update to fail;
	// the caller transaction must roll the OAuth change back as well.
	require.NoError(t, store.DB().Exec(`
		CREATE TRIGGER fail_header_reconcile
		BEFORE UPDATE OF status ON mcp_per_user_header_credentials
		BEGIN
			SELECT RAISE(ABORT, 'injected header reconciliation failure');
		END
	`).Error)
	err = store.ExecuteTransaction(context.Background(), func(tx *gorm.DB) error {
		if err := store.UpdateMCPClientConfig(context.Background(), "mcp-atomic", &tables.TableMCPClient{
			Name: "must-roll-back", ConnectionType: "stdio", UpdatedAt: before.UpdatedAt,
		}, tx); err != nil {
			return err
		}
		if err := tx.Where("virtual_key_id = ?", "vk-atomic").Delete(&tables.TableVirtualKeyMCPConfig{}).Error; err != nil {
			return err
		}
		if err := store.ReconcileCredentialsAfterMCPChangeTx(context.Background(), tx, "mcp-atomic", false); err != nil {
			return err
		}
		return store.AppendVirtualKeyInvalidation(context.Background(), tx, &tables.TableVirtualKeyInvalidationEvent{
			EntityType: tables.VirtualKeyInvalidationEntityType,
			Action:     tables.VirtualKeyInvalidationActionReload,
			EntityID:   "vk-atomic",
		})
	})
	require.ErrorContains(t, err, "injected header reconciliation failure")
	oauthStatus, headerStatus := credentialStatuses(t, store)
	require.Equal(t, "active", oauthStatus)
	require.Equal(t, "active", headerStatus)
	var grants, events int64
	require.NoError(t, store.DB().Model(&tables.TableVirtualKeyMCPConfig{}).Where("virtual_key_id = ?", "vk-atomic").Count(&grants).Error)
	require.NoError(t, store.DB().Model(&tables.TableVirtualKeyInvalidationEvent{}).Count(&events).Error)
	require.Equal(t, int64(1), grants, "authority mutation must roll back with credential reconciliation")
	require.Zero(t, events, "outbox must not commit for a rolled-back authority mutation")
	after, getErr := store.GetMCPClientByID(context.Background(), "mcp-atomic")
	require.NoError(t, getErr)
	require.Equal(t, "Atomic MCP", after.Name, "MCP config must roll back with credentials and grants")
}

func TestReconcileCredentialsAfterMCPChangeTxReactivatesThenMarksSchemaChange(t *testing.T) {
	store := setupRDBTestStore(t)
	seedMCPReconcileAtomicFixture(t, store, true)
	require.NoError(t, store.DB().Model(&tables.TableOauthUserToken{}).
		Where("id = ?", "oauth-atomic").Update("status", "orphaned").Error)
	require.NoError(t, store.DB().Model(&tables.TableMCPPerUserHeaderCredential{}).
		Where("id = ?", "header-atomic").Update("status", "orphaned").Error)

	require.NoError(t, store.ExecuteTransaction(context.Background(), func(tx *gorm.DB) error {
		return store.ReconcileCredentialsAfterMCPChangeTx(context.Background(), tx, "mcp-atomic", true)
	}))
	oauthStatus, headerStatus := credentialStatuses(t, store)
	require.Equal(t, "active", oauthStatus)
	require.Equal(t, "needs_update", headerStatus)
}

func TestUpdateMCPClientConfigRejectsStalePatchSnapshot(t *testing.T) {
	store := setupRDBTestStore(t)
	ctx := context.Background()
	require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableMCPClient{
		ClientID: "mcp-cas", Name: "before", ConnectionType: "stdio",
	}).Error)

	snapshot, err := store.GetMCPClientByID(ctx, "mcp-cas")
	require.NoError(t, err)
	first := &tables.TableMCPClient{
		Name: "first", ConnectionType: "stdio", UpdatedAt: snapshot.UpdatedAt,
	}
	require.NoError(t, store.UpdateMCPClientConfig(ctx, "mcp-cas", first))

	stale := &tables.TableMCPClient{
		Name: "stale", ConnectionType: "stdio", UpdatedAt: snapshot.UpdatedAt,
	}
	err = store.UpdateMCPClientConfig(ctx, "mcp-cas", stale)
	require.ErrorIs(t, err, ErrMCPConcurrentUpdate)

	got, err := store.GetMCPClientByID(ctx, "mcp-cas")
	require.NoError(t, err)
	require.Equal(t, "first", got.Name, "stale PATCH must not overwrite the committed update")
}

func TestReconcileCredentialsAfterMCPChangeTxTracksDisabledAuthority(t *testing.T) {
	store := setupRDBTestStore(t)
	ctx := context.Background()
	seedMCPReconcileAtomicFixture(t, store, true)

	setDisabled := func(disabled bool) {
		t.Helper()
		current, err := store.GetMCPClientByID(ctx, "mcp-atomic")
		require.NoError(t, err)
		require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
			if err := store.UpdateMCPClientConfig(ctx, "mcp-atomic", &tables.TableMCPClient{
				Name: "Atomic MCP", ConnectionType: "stdio", Disabled: disabled, UpdatedAt: current.UpdatedAt,
			}, tx); err != nil {
				return err
			}
			return store.ReconcileCredentialsAfterMCPChangeTx(ctx, tx, "mcp-atomic", false)
		}))
	}

	setDisabled(true)
	oauthStatus, headerStatus := credentialStatuses(t, store)
	require.Equal(t, "orphaned", oauthStatus)
	require.Equal(t, "orphaned", headerStatus)

	setDisabled(false)
	oauthStatus, headerStatus = credentialStatuses(t, store)
	require.Equal(t, "active", oauthStatus)
	require.Equal(t, "active", headerStatus)
}
