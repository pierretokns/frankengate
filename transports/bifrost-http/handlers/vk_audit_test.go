package handlers

import (
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/valyala/fasthttp"
)

func TestVirtualKeyAuditIdentityUsesVerifiedPrincipal(t *testing.T) {
	var ctx fasthttp.RequestCtx
	ctx.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{
		Tenant: "corp", Issuer: "https://issuer.example", Subject: "user-7",
	})
	ctx.SetUserValue(schemas.BifrostContextKeyUserID, "legacy-user")
	tenant, subject, issuer := virtualKeyAuditIdentity(&ctx)
	if tenant != "corp" || subject != "user-7" || issuer != "https://issuer.example" {
		t.Fatalf("identity = (%q, %q, %q), want verified principal", tenant, subject, issuer)
	}
}

func TestVirtualKeyAuditIdentityFallsBackToUserID(t *testing.T) {
	var ctx fasthttp.RequestCtx
	ctx.SetUserValue(schemas.BifrostContextKeyUserID, "user-9")
	_, subject, issuer := virtualKeyAuditIdentity(&ctx)
	if subject != "user-9" || issuer != "" {
		t.Fatalf("identity = (%q, %q), want user fallback and empty issuer", subject, issuer)
	}
}
