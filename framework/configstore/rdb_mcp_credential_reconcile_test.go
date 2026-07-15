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

func TestReconcileCredentialsAfterVKChangeTxIsAtomicAcrossCredentialSurfaces(t *testing.T) {
	store := setupVKInvalidationTestStore(t)
	ctx := context.Background()
	vkID := "vk-credential-atomicity"
	mcpID := "mcp-revoked"
	require.NoError(t, store.CreateVirtualKey(ctx, &tables.TableVirtualKey{
		ID: vkID, Name: vkID, Value: *schemas.NewSecretVar("sk-bf-credential-atomicity"),
	}))
	require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableMCPClient{
		ClientID: mcpID, Name: mcpID, ConnectionType: string(schemas.MCPConnectionTypeHTTP),
	}).Error)
	require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableOauthUserToken{
		ID: "oauth-active", VirtualKeyID: &vkID, MCPClientID: mcpID,
		AuthMode: string(schemas.MCPAuthModeVK), Status: "active", OauthConfigID: "oauth-config",
		AccessToken: "token", TokenType: "Bearer", Scopes: "[]",
	}).Error)
	require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableMCPPerUserHeaderCredential{
		ID: "headers-active", VirtualKeyID: &vkID, MCPClientID: mcpID,
		AuthMode: string(schemas.MCPAuthModeVK), Status: "active", HeadersJSON: `{}`,
	}).Error)

	status := func(model any, id string) string {
		t.Helper()
		var got string
		require.NoError(t, store.DB().WithContext(ctx).Model(model).Select("status").Where("id = ?", id).Scan(&got).Error)
		return got
	}
	require.Error(t, store.ReconcileCredentialsAfterVKChangeTx(ctx, nil, vkID))

	wantRollback := errors.New("rollback authority mutation")
	err := store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		require.NoError(t, store.ReconcileCredentialsAfterVKChangeTx(ctx, tx, vkID))
		var oauthStatus, headerStatus string
		require.NoError(t, tx.Model(&tables.TableOauthUserToken{}).Select("status").Where("id = ?", "oauth-active").Scan(&oauthStatus).Error)
		require.NoError(t, tx.Model(&tables.TableMCPPerUserHeaderCredential{}).Select("status").Where("id = ?", "headers-active").Scan(&headerStatus).Error)
		require.Equal(t, "orphaned", oauthStatus)
		require.Equal(t, "orphaned", headerStatus)
		return wantRollback
	})
	require.ErrorIs(t, err, wantRollback)
	require.Equal(t, "active", status(&tables.TableOauthUserToken{}, "oauth-active"))
	require.Equal(t, "active", status(&tables.TableMCPPerUserHeaderCredential{}, "headers-active"))

	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		return store.ReconcileCredentialsAfterVKChangeTx(ctx, tx, vkID)
	}))
	require.Equal(t, "orphaned", status(&tables.TableOauthUserToken{}, "oauth-active"))
	require.Equal(t, "orphaned", status(&tables.TableMCPPerUserHeaderCredential{}, "headers-active"))
}

func TestVKCredentialWritersRecheckAuthorityInsideTransaction(t *testing.T) {
	store := setupVKInvalidationTestStore(t)
	ctx := context.Background()
	vkID := "vk-callback-race"
	require.NoError(t, store.CreateVirtualKey(ctx, &tables.TableVirtualKey{
		ID: vkID, Name: vkID, Value: *schemas.NewSecretVar("sk-bf-callback-race"),
	}))
	mcpClient := &tables.TableMCPClient{ClientID: "mcp-callback", Name: "mcp-callback", ConnectionType: string(schemas.MCPConnectionTypeHTTP)}
	require.NoError(t, store.DB().WithContext(ctx).Create(mcpClient).Error)

	newToken := func() *tables.TableOauthUserToken {
		return &tables.TableOauthUserToken{
			ID: "oauth-callback", VirtualKeyID: &vkID, MCPClientID: mcpClient.ClientID,
			AuthMode: string(schemas.MCPAuthModeVK), Status: "active", OauthConfigID: "oauth-config",
			AccessToken: "token", TokenType: "Bearer", Scopes: "[]",
		}
	}
	newHeaders := func() *tables.TableMCPPerUserHeaderCredential {
		return &tables.TableMCPPerUserHeaderCredential{
			ID: "headers-callback", VirtualKeyID: &vkID, MCPClientID: mcpClient.ClientID,
			AuthMode: string(schemas.MCPAuthModeVK), Status: "active", HeadersJSON: `{}`,
		}
	}
	require.ErrorIs(t, store.CreateOauthUserToken(ctx, newToken()), ErrMCPAccessDenied)
	require.ErrorIs(t, store.UpsertMCPPerUserHeaderCredential(ctx, newHeaders()), ErrMCPAccessDenied)

	require.NoError(t, store.DB().WithContext(ctx).Create(&tables.TableVirtualKeyMCPConfig{
		VirtualKeyID: vkID, MCPClientID: mcpClient.ID, ToolsToExecute: []string{"*"},
	}).Error)
	require.NoError(t, store.CreateOauthUserToken(ctx, newToken()))
	require.NoError(t, store.UpsertMCPPerUserHeaderCredential(ctx, newHeaders()))
	require.NoError(t, store.DB().WithContext(ctx).Model(&tables.TableMCPClient{}).
		Where("id = ?", mcpClient.ID).Update("disabled", true).Error)
	require.ErrorIs(t, store.CreateOauthUserToken(ctx, newToken()), ErrMCPAccessDenied)
	require.ErrorIs(t, store.UpsertMCPPerUserHeaderCredential(ctx, newHeaders()), ErrMCPAccessDenied)
	require.NoError(t, store.DB().WithContext(ctx).Model(&tables.TableMCPClient{}).
		Where("id = ?", mcpClient.ID).Update("disabled", false).Error)

	require.NoError(t, store.DB().WithContext(ctx).Where("virtual_key_id = ? AND mcp_client_id = ?", vkID, mcpClient.ID).Delete(&tables.TableVirtualKeyMCPConfig{}).Error)
	require.ErrorIs(t, store.CreateOauthUserToken(ctx, newToken()), ErrMCPAccessDenied)
	require.ErrorIs(t, store.UpsertMCPPerUserHeaderCredential(ctx, newHeaders()), ErrMCPAccessDenied)
}
