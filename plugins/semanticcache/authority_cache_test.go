package semanticcache

import (
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
)

func TestAuthorityMetadataForCachingIncludesEpochAndScope(t *testing.T) {
	ctx := schemas.NewBifrostContext(nil, schemas.NoDeadline)
	ref := authorityepoch.Reference{
		Principal: authorityepoch.Principal{Tenant: "tenant-a", Issuer: "okta", Subject: "alice"},
		Epoch:     7, Kind: authorityepoch.ArtifactCache, ID: "cache-scope",
	}
	if err := schemas.SetAuthorizationEpochReference(ctx, ref); err != nil {
		t.Fatal(err)
	}
	ctx.SetValue(schemas.BifrostContextKeyGovernanceTeamID, "team-research")
	metadata, err := authorityMetadataForCaching(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if metadata["authorization_tenant"] != "tenant-a" || metadata["authorization_epoch"] != uint64(7) || metadata["authorization_team_id"] != "team-research" {
		t.Fatalf("unexpected authority metadata: %#v", metadata)
	}
}

func TestAuthorityMetadataForCachingFailsClosedOnMismatchedReference(t *testing.T) {
	ctx := schemas.NewBifrostContext(nil, schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyAuthorizationEpochReference, authorityepoch.Reference{
		Principal: authorityepoch.Principal{Tenant: "tenant-a", Issuer: "okta", Subject: "alice"},
		Epoch:     1, Kind: authorityepoch.ArtifactCache, ID: "cache-scope",
	})
	if _, err := authorityMetadataForCaching(ctx); err == nil {
		t.Fatal("expected missing principal to fail closed")
	}
}
