package handlers

import (
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/valyala/fasthttp"
)

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
