package semanticcache

import (
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/vectorstore"
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

func TestRequireGovernedCacheAuthorityFailsClosedBeforeLookup(t *testing.T) {
	ctx := schemas.NewBifrostContext(nil, schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyGovernanceTeamID, "team-research")
	if err := requireGovernedCacheAuthority(ctx); err == nil {
		t.Fatal("expected governed cache lookup without authority reference to fail closed")
	}
}

func TestAuthorizationCacheQueriesIncludeTenantAndPrincipalScope(t *testing.T) {
	queries := authorizationCacheQueries(map[string]any{
		"authorization_tenant":  "tenant-a",
		"authorization_subject": "alice",
		"authorization_epoch":   uint64(4),
		"authorization_team_id": "team-research",
	})
	if len(queries) != 4 {
		t.Fatalf("expected four authorization predicates, got %d", len(queries))
	}
	for _, want := range []string{"authorization_tenant", "authorization_subject", "authorization_epoch", "authorization_team_id"} {
		found := false
		for _, query := range queries {
			if query.Field == want {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("missing authorization predicate %q: %#v", want, queries)
		}
	}
}

func TestRoutingMetadataForCachingIncludesFamilyAndRegion(t *testing.T) {
	ctx := schemas.NewBifrostContext(nil, schemas.NoDeadline)
	family := schemas.ModelFamilyAnthropic
	ctx.SetValue(schemas.BifrostContextKeyResolvedAlias, &schemas.ResolvedAlias{
		Key:    "claude-gpt-soul",
		Config: &schemas.AliasConfig{ModelID: "mantle-soul", ModelFamily: &family},
	})
	ctx.SetValue(schemas.BifrostContextKeyRequiredDestinationRegion, "us-west-2")
	metadata := routingMetadataForCaching(ctx, schemas.BedrockMantle, "mantle-soul")
	if metadata["routing_provider"] != string(schemas.BedrockMantle) ||
		metadata["routing_model_family"] != "anthropic" ||
		metadata["routing_region"] != "us-west-2" {
		t.Fatalf("unexpected routing metadata: %#v", metadata)
	}
	queries := routingCacheQueries(metadata)
	if len(queries) != 4 {
		t.Fatalf("expected four routing predicates, got %d: %#v", len(queries), queries)
	}
}

func TestRoutingMetadataSeparatesUnpinnedAndPinnedRegion(t *testing.T) {
	model := "claude-gpt-soul"
	unpinned := routingMetadataForCaching(nil, schemas.BedrockMantle, model)
	ctx := schemas.NewBifrostContext(nil, schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyRequiredDestinationRegion, "us-east-1")
	pinned := routingMetadataForCaching(ctx, schemas.BedrockMantle, model)
	if unpinned["routing_region"] == pinned["routing_region"] {
		t.Fatalf("pinned and unpinned routing scopes collided: %#v vs %#v", unpinned, pinned)
	}
}

func TestCacheResultRejectsRevokedAuthorityEpoch(t *testing.T) {
	result := vectorstore.SearchResult{Properties: map[string]interface{}{
		"authorization_tenant": "tenant-a", "authorization_subject": "alice",
		"authorization_epoch": float64(3), "response": "cached",
	}}
	want := map[string]any{"authorization_tenant": "tenant-a", "authorization_subject": "alice", "authorization_epoch": uint64(4)}
	if cacheResultMatchesAuthority(result, want) {
		t.Fatal("cache entry from revoked epoch was accepted")
	}
	result.Properties["authorization_epoch"] = float64(4)
	if !cacheResultMatchesAuthority(result, want) {
		t.Fatal("current authority epoch was rejected after numeric normalization")
	}
}

func TestCacheResultRequiresAllAuthorityFields(t *testing.T) {
	result := vectorstore.SearchResult{Properties: map[string]interface{}{"authorization_epoch": uint64(2)}}
	if cacheResultMatchesAuthority(result, map[string]any{"authorization_epoch": uint64(2), "authorization_subject": "alice"}) {
		t.Fatal("cache entry missing subject metadata was accepted")
	}
}

func TestCacheResultRejectsEntryWithNarrowerScopeClaim(t *testing.T) {
	// The principal and epoch can remain unchanged while team membership is
	// removed.  An entry carrying the old team claim must not remain readable
	// (or deletable) by the now-unscoped snapshot.
	result := vectorstore.SearchResult{Properties: map[string]interface{}{
		"authorization_tenant": "tenant-a", "authorization_subject": "alice",
		"authorization_epoch": uint64(2), "authorization_team_id": "team-old",
	}}
	want := map[string]any{
		"authorization_tenant": "tenant-a", "authorization_subject": "alice",
		"authorization_epoch": uint64(2),
	}
	if cacheResultMatchesAuthority(result, want) {
		t.Fatal("cache entry with stale team scope was accepted")
	}
}

func TestSemanticCacheEntryRequiresStrictPluginMarker(t *testing.T) {
	if isSemanticCacheEntry(vectorstore.SearchResult{Properties: map[string]interface{}{
		"from_bifrost_semantic_cache_plugin": true,
	}}) == false {
		t.Fatal("expected entries with the strict ownership marker to be accepted")
	}
	for _, marker := range []interface{}{nil, false, "true", 1} {
		if isSemanticCacheEntry(vectorstore.SearchResult{Properties: map[string]interface{}{
			"from_bifrost_semantic_cache_plugin": marker,
		}}) {
			t.Fatalf("accepted non-boolean ownership marker %#v", marker)
		}
	}
	if isSemanticCacheEntry(vectorstore.SearchResult{}) {
		t.Fatal("accepted cache entry with missing ownership marker")
	}
}
