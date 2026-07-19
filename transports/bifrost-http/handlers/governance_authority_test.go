package handlers

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/valyala/fasthttp"
	"gorm.io/gorm"
)

type authorityValidationStore struct{ err error }

func (s authorityValidationStore) GetPrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal) (*configstoreTables.TablePrincipalAuthorizationEpoch, error) {
	return nil, nil
}
func (s authorityValidationStore) ActivatePrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal, uint64, ...*gorm.DB) (*configstoreTables.TablePrincipalAuthorizationEpoch, error) {
	return nil, nil
}
func (s authorityValidationStore) AdvancePrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal, authorityepoch.Reason, ...*gorm.DB) (*configstoreTables.TablePrincipalAuthorizationEpochEvent, error) {
	return nil, nil
}
func (s authorityValidationStore) DeactivatePrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal, authorityepoch.Reason, ...*gorm.DB) (*configstoreTables.TablePrincipalAuthorizationEpochEvent, error) {
	return nil, nil
}
func (s authorityValidationStore) ValidatePrincipalAuthorizationEpoch(context.Context, authorityepoch.Reference) error {
	return s.err
}
func (authorityValidationStore) ListPrincipalAuthorizationEpochEventsAfter(context.Context, uint64, int) ([]configstoreTables.TablePrincipalAuthorizationEpochEvent, error) {
	return nil, nil
}
func (authorityValidationStore) GetPrincipalAuthorizationEpochHighWatermark(context.Context) (uint64, error) {
	return 0, nil
}
func (authorityValidationStore) PrincipalAuthorizationEpochWakeups(context.Context) <-chan struct{} {
	return nil
}

func TestVirtualKeyManagementAuthorityAbsentSnapshotRemainsAdminCompatible(t *testing.T) {
	ctx := &fasthttp.RequestCtx{}
	if err := (&GovernanceHandler{}).validateVirtualKeyManagementAuthority(ctx); err != nil {
		t.Fatalf("absent authority snapshot should defer to management authentication: %v", err)
	}
}

func TestVirtualKeyManagementAuthorityRejectsMalformedIdentitySnapshot(t *testing.T) {
	ctx := &fasthttp.RequestCtx{}
	ctx.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{
		Tenant: "tenant-a", Issuer: "https://idp.example", Subject: "user-a",
	})
	// A principal without its matching epoch reference must never reach a
	// secret-bearing reveal or rotation operation.
	if err := (&GovernanceHandler{}).validateVirtualKeyManagementAuthority(ctx); err == nil {
		t.Fatal("malformed authority snapshot was accepted")
	}
}

func TestVirtualKeyManagementAuthorityRejectsStaleEpoch(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	principal := authorityepoch.Principal{Tenant: "tenant-a", Issuer: "https://idp.example", Subject: "user-a"}
	if err := schemas.SetAuthorizationEpochReference(ctx, authorityepoch.Reference{
		Principal: principal, Epoch: 4, Kind: authorityepoch.ArtifactUnary, ID: "request-a",
	}); err != nil {
		t.Fatal(err)
	}
	if err := validateVirtualKeyManagementAuthority(ctx, authorityValidationStore{err: authorityepoch.ErrStaleEpoch}); err == nil {
		t.Fatal("stale authorization epoch was accepted")
	}
}
