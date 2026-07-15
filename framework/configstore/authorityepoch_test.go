package configstore

import (
	"context"
	"errors"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

func setupAuthorityEpochTestStore(t *testing.T) *RDBConfigStore {
	t.Helper()
	store := setupRDBTestStore(t)
	require.NoError(t, store.DB().AutoMigrate(
		&tables.TablePrincipalAuthorizationEpoch{},
		&tables.TablePrincipalAuthorizationEpochEvent{},
	))
	return store
}

func setupAuthorityEpochSQLiteFileStore(t *testing.T, dsn string) *RDBConfigStore {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	require.NoError(t, err)
	require.NoError(t, db.AutoMigrate(
		&tables.TablePrincipalAuthorizationEpoch{},
		&tables.TablePrincipalAuthorizationEpochEvent{},
	))
	store := &RDBConfigStore{}
	store.db.Store(db)
	store.migrateOnFreshFn = func(ctx context.Context, fn func(context.Context, *gorm.DB) error) error {
		return fn(ctx, store.DB())
	}
	store.refreshPoolFn = func(ctx context.Context) error { return nil }
	t.Cleanup(func() {
		sqlDB, err := db.DB()
		if err == nil {
			_ = sqlDB.Close()
		}
	})
	return store
}

func testAuthorityPrincipal() authorityepoch.Principal {
	return authorityepoch.Principal{
		Tenant:  "tenant-a",
		Issuer:  "https://okta.example.com/oauth2/default",
		Subject: "00uprincipal",
	}
}

func TestPrincipalAuthorizationEpochSQLitePersistsAcrossRestartAndFailsClosed(t *testing.T) {
	ctx := context.Background()
	dsn := filepath.Join(t.TempDir(), "authority-epochs.db")
	principal := testAuthorityPrincipal()

	first := setupAuthorityEpochSQLiteFileStore(t, dsn)
	_, err := first.ActivatePrincipalAuthorizationEpoch(ctx, principal, 7)
	require.NoError(t, err)
	require.NoError(t, first.ValidatePrincipalAuthorizationEpoch(ctx, authorityepoch.Reference{
		Principal: principal,
		Epoch:     7,
		Kind:      authorityepoch.ArtifactKey,
		ID:        "key-1",
	}))
	events, err := first.ListPrincipalAuthorizationEpochEventsAfter(ctx, 0, 10)
	require.NoError(t, err)
	require.Len(t, events, 1)
	require.Zero(t, events[0].OldEpoch)
	require.Equal(t, uint64(7), events[0].NewEpoch)
	require.True(t, events[0].Active)
	require.Equal(t, PrincipalAuthorizationEpochReasonActivated, events[0].Reason)
	sqlDB, err := first.DB().DB()
	require.NoError(t, err)
	require.NoError(t, sqlDB.Close())

	second := setupAuthorityEpochSQLiteFileStore(t, dsn)
	row, err := second.GetPrincipalAuthorizationEpoch(ctx, principal)
	require.NoError(t, err)
	require.Equal(t, uint64(7), row.Epoch)
	require.True(t, row.Active)

	err = second.ValidatePrincipalAuthorizationEpoch(ctx, authorityepoch.Reference{
		Principal: principal,
		Epoch:     6,
		Kind:      authorityepoch.ArtifactKey,
		ID:        "key-1",
	})
	require.ErrorIs(t, err, authorityepoch.ErrStaleEpoch)

	missing := authorityepoch.Reference{
		Principal: authorityepoch.Principal{Tenant: "tenant-a", Issuer: principal.Issuer, Subject: "missing"},
		Epoch:     1,
		Kind:      authorityepoch.ArtifactKey,
		ID:        "key-missing",
	}
	err = second.ValidatePrincipalAuthorizationEpoch(ctx, missing)
	require.ErrorIs(t, err, authorityepoch.ErrUnknownPrincipal)
}

func TestPrincipalAuthorizationEpochSQLiteDeactivateIsAtomicAndInvalidates(t *testing.T) {
	store := setupAuthorityEpochTestStore(t)
	ctx := context.Background()
	principal := testAuthorityPrincipal()
	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1, tx)
		return err
	}))
	before, err := store.GetPrincipalAuthorizationEpochHighWatermark(ctx)
	require.NoError(t, err)

	rollback := errors.New("rollback deactivation")
	err = store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		_, err := store.DeactivatePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonDeactivated, tx)
		require.NoError(t, err)
		return rollback
	})
	require.ErrorIs(t, err, rollback)
	row, err := store.GetPrincipalAuthorizationEpoch(ctx, principal)
	require.NoError(t, err)
	require.Equal(t, uint64(1), row.Epoch)
	require.True(t, row.Active)
	events, err := store.ListPrincipalAuthorizationEpochEventsAfter(ctx, before, 10)
	require.NoError(t, err)
	require.Empty(t, events)

	event, err := store.DeactivatePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonDeactivated)
	require.NoError(t, err)
	require.Equal(t, uint64(1), event.OldEpoch)
	require.Equal(t, uint64(2), event.NewEpoch)
	require.False(t, event.Active)
	require.Equal(t, string(authorityepoch.ReasonDeactivated), event.Reason)

	err = store.ValidatePrincipalAuthorizationEpoch(ctx, authorityepoch.Reference{
		Principal: principal,
		Epoch:     2,
		Kind:      authorityepoch.ArtifactKey,
		ID:        "key-2",
	})
	require.ErrorIs(t, err, authorityepoch.ErrInactivePrincipal)
	beforeAdvance, err := store.GetPrincipalAuthorizationEpochHighWatermark(ctx)
	require.NoError(t, err)
	_, err = store.AdvancePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonGroupRemoved)
	require.ErrorIs(t, err, authorityepoch.ErrInactivePrincipal)
	afterAdvance, err := store.GetPrincipalAuthorizationEpochHighWatermark(ctx)
	require.NoError(t, err)
	require.Equal(t, beforeAdvance, afterAdvance)

	row, err = store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 3)
	require.NoError(t, err)
	require.Equal(t, uint64(3), row.Epoch)
	require.True(t, row.Active)
	events, err = store.ListPrincipalAuthorizationEpochEventsAfter(ctx, event.ID, 10)
	require.NoError(t, err)
	require.Len(t, events, 1)
	require.Equal(t, uint64(2), events[0].OldEpoch)
	require.Equal(t, uint64(3), events[0].NewEpoch)
	require.True(t, events[0].Active)
	require.Equal(t, PrincipalAuthorizationEpochReasonReactivated, events[0].Reason)
}

func TestPrincipalAuthorizationEpochSQLiteAdvanceCursorAndStaleReference(t *testing.T) {
	store := setupAuthorityEpochTestStore(t)
	ctx := context.Background()
	principal := testAuthorityPrincipal()
	_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1)
	require.NoError(t, err)
	before, err := store.GetPrincipalAuthorizationEpochHighWatermark(ctx)
	require.NoError(t, err)

	first, err := store.AdvancePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonGroupRemoved)
	require.NoError(t, err)
	second, err := store.AdvancePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonGroupRemoved)
	require.NoError(t, err)
	require.Equal(t, uint64(2), first.NewEpoch)
	require.Equal(t, uint64(3), second.NewEpoch)

	err = store.ValidatePrincipalAuthorizationEpoch(ctx, authorityepoch.Reference{
		Principal: principal,
		Epoch:     1,
		Kind:      authorityepoch.ArtifactMCPGrant,
		ID:        "grant-old",
	})
	require.ErrorIs(t, err, authorityepoch.ErrStaleEpoch)
	require.NoError(t, store.ValidatePrincipalAuthorizationEpoch(ctx, authorityepoch.Reference{
		Principal: principal,
		Epoch:     3,
		Kind:      authorityepoch.ArtifactMCPGrant,
		ID:        "grant-new",
	}))

	batch, err := store.ListPrincipalAuthorizationEpochEventsAfter(ctx, before, 1)
	require.NoError(t, err)
	require.Len(t, batch, 1)
	require.Equal(t, first.ID, batch[0].ID)
	replayed, err := store.ListPrincipalAuthorizationEpochEventsAfter(ctx, before, 1)
	require.NoError(t, err)
	require.Equal(t, batch, replayed)
	next, err := store.ListPrincipalAuthorizationEpochEventsAfter(ctx, first.ID, 1)
	require.NoError(t, err)
	require.Len(t, next, 1)
	require.Equal(t, second.ID, next[0].ID)
	highWatermark, err := store.GetPrincipalAuthorizationEpochHighWatermark(ctx)
	require.NoError(t, err)
	require.Equal(t, second.ID, highWatermark)

	_, err = store.ListPrincipalAuthorizationEpochEventsAfter(ctx, 0, 0)
	require.Error(t, err)
}

func TestPrincipalAuthorizationEpochSQLiteRejectsInvalidTransitions(t *testing.T) {
	store := setupAuthorityEpochTestStore(t)
	ctx := context.Background()
	principal := testAuthorityPrincipal()

	_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, authorityepoch.Principal{Tenant: "tenant-a"}, 1)
	require.ErrorIs(t, err, authorityepoch.ErrInvalidPrincipal)
	_, err = store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 0)
	require.ErrorIs(t, err, authorityepoch.ErrInvalidReference)
	_, err = store.ActivatePrincipalAuthorizationEpoch(ctx, principal, principalAuthorizationEpochMaxSigned+1)
	require.ErrorIs(t, err, authorityepoch.ErrInvalidReference)
	_, err = store.AdvancePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonGroupRemoved)
	require.ErrorIs(t, err, authorityepoch.ErrUnknownPrincipal)
	_, err = store.DeactivatePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonDeactivated)
	require.ErrorIs(t, err, authorityepoch.ErrUnknownPrincipal)

	_, err = store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1)
	require.NoError(t, err)
	_, err = store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1)
	require.ErrorIs(t, err, authorityepoch.ErrStaleEpoch)
	_, err = store.AdvancePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.Reason(""))
	require.Error(t, err)

	row, err := store.GetPrincipalAuthorizationEpoch(ctx, principal)
	require.NoError(t, err)
	row.Epoch = principalAuthorizationEpochMaxSigned
	row.Revision = principalAuthorizationEpochMaxSigned
	require.NoError(t, store.DB().WithContext(ctx).Save(row).Error)
	_, err = store.AdvancePrincipalAuthorizationEpoch(ctx, principal, authorityepoch.ReasonGroupRemoved)
	require.ErrorIs(t, err, authorityepoch.ErrInvalidReference)
}

func TestPrincipalAuthorizationEpochPrincipalLengthValidation(t *testing.T) {
	store := setupAuthorityEpochTestStore(t)
	ctx := context.Background()

	valid := authorityepoch.Principal{
		Tenant:  strings.Repeat("t", 255),
		Issuer:  strings.Repeat("i", 255),
		Subject: strings.Repeat("s", 255),
	}
	_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, valid, 1)
	require.NoError(t, err)

	tests := []authorityepoch.Principal{
		{Tenant: strings.Repeat("t", 256), Issuer: valid.Issuer, Subject: valid.Subject},
		{Tenant: valid.Tenant, Issuer: strings.Repeat("i", 256), Subject: valid.Subject},
		{Tenant: valid.Tenant, Issuer: valid.Issuer, Subject: strings.Repeat("s", 256)},
	}
	for _, principal := range tests {
		_, err = store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1)
		require.ErrorIs(t, err, authorityepoch.ErrInvalidPrincipal)
	}
}

func TestListPrincipalAuthorizationEpochsAfterPagesCompositeKey(t *testing.T) {
	store := setupAuthorityEpochTestStore(t)
	ctx := context.Background()
	principals := []authorityepoch.Principal{
		{Tenant: "a", Issuer: "issuer", Subject: "one"},
		{Tenant: "a", Issuer: "issuer", Subject: "two"},
		{Tenant: "b", Issuer: "issuer", Subject: "one"},
	}
	for _, principal := range principals {
		_, err := store.ActivatePrincipalAuthorizationEpoch(ctx, principal, 1)
		require.NoError(t, err)
	}
	first, err := store.ListPrincipalAuthorizationEpochsAfter(ctx, "", "", "", 2)
	require.NoError(t, err)
	require.Len(t, first, 2)
	last := first[len(first)-1]
	second, err := store.ListPrincipalAuthorizationEpochsAfter(ctx, last.TenantID, last.Issuer, last.Subject, 2)
	require.NoError(t, err)
	require.Len(t, second, 1)
	require.Equal(t, "b", second[0].TenantID)
}
