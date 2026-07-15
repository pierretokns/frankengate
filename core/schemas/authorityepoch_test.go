package schemas

import (
	"context"
	"errors"
	"testing"

	"github.com/maximhq/bifrost/core/authorityepoch"
)

func testAuthorizationPrincipal() authorityepoch.Principal {
	return authorityepoch.Principal{
		Tenant:  "tenant-a",
		Issuer:  "https://idp.example.com",
		Subject: "user-1",
	}
}

func TestAuthorizationPrincipalContextRoundTripAndFailClosed(t *testing.T) {
	principal := testAuthorizationPrincipal()
	ctx := NewBifrostContext(context.Background(), NoDeadline)
	if err := SetAuthorizationPrincipal(ctx, principal); err != nil {
		t.Fatalf("set principal: %v", err)
	}
	got, err := AuthorizationPrincipalFromContext(ctx)
	if err != nil || got != principal {
		t.Fatalf("principal = %#v, err = %v", got, err)
	}

	invalid := []authorityepoch.Principal{
		{},
		{Issuer: principal.Issuer, Subject: principal.Subject},
		{Tenant: principal.Tenant, Subject: principal.Subject},
		{Tenant: principal.Tenant, Issuer: principal.Issuer},
		{Tenant: "  ", Issuer: principal.Issuer, Subject: principal.Subject},
	}
	for _, candidate := range invalid {
		candidate := candidate
		t.Run(candidate.Tenant+candidate.Issuer+candidate.Subject, func(t *testing.T) {
			invalidCtx := NewBifrostContext(context.Background(), NoDeadline)
			if err := SetAuthorizationPrincipal(invalidCtx, candidate); !errors.Is(err, authorityepoch.ErrInvalidPrincipal) {
				t.Fatalf("set error = %v, want ErrInvalidPrincipal", err)
			}
		})
	}

	missing := NewBifrostContext(context.Background(), NoDeadline)
	if _, err := AuthorizationPrincipalFromContext(missing); !errors.Is(err, authorityepoch.ErrInvalidPrincipal) {
		t.Fatalf("missing error = %v, want ErrInvalidPrincipal", err)
	}
	missing.SetValue(BifrostContextKeyAuthorizationPrincipal, &principal)
	if _, err := AuthorizationPrincipalFromContext(missing); !errors.Is(err, authorityepoch.ErrInvalidPrincipal) {
		t.Fatalf("pointer value error = %v, want ErrInvalidPrincipal", err)
	}
}

func TestAuthorizationEpochReferenceContextRequiresMatchingPrincipal(t *testing.T) {
	principal := testAuthorizationPrincipal()
	ref := authorityepoch.Reference{
		Principal: principal,
		Epoch:     7,
		Kind:      authorityepoch.ArtifactSSE,
		ID:        "request-1",
	}
	ctx := NewBifrostContext(context.Background(), NoDeadline)
	if err := SetAuthorizationEpochReference(ctx, ref); err != nil {
		t.Fatalf("set reference: %v", err)
	}
	got, err := AuthorizationEpochReferenceFromContext(ctx)
	if err != nil || got != ref {
		t.Fatalf("reference = %#v, err = %v", got, err)
	}

	ctx.SetValue(BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{
		Tenant: "tenant-b", Issuer: principal.Issuer, Subject: principal.Subject,
	})
	if _, err := AuthorizationEpochReferenceFromContext(ctx); !errors.Is(err, authorityepoch.ErrInvalidReference) {
		t.Fatalf("mismatch error = %v, want ErrInvalidReference", err)
	}
}

func TestAuthorizationContextRejectsIncompleteReferenceAndRestrictedWrite(t *testing.T) {
	principal := testAuthorizationPrincipal()
	for _, ref := range []authorityepoch.Reference{
		{Principal: principal, Kind: authorityepoch.ArtifactUnary, ID: "request-1"},
		{Principal: principal, Epoch: 1, ID: "request-1"},
		{Principal: principal, Epoch: 1, Kind: authorityepoch.ArtifactKind("unknown"), ID: "request-1"},
		{Principal: principal, Epoch: 1, Kind: authorityepoch.ArtifactUnary},
	} {
		ctx := NewBifrostContext(context.Background(), NoDeadline)
		if err := SetAuthorizationEpochReference(ctx, ref); !errors.Is(err, authorityepoch.ErrInvalidReference) {
			t.Fatalf("reference %#v error = %v, want ErrInvalidReference", ref, err)
		}
	}

	blocked := NewBifrostContext(context.Background(), NoDeadline)
	blocked.BlockRestrictedWrites()
	if err := SetAuthorizationPrincipal(blocked, principal); !errors.Is(err, authorityepoch.ErrInvalidPrincipal) {
		t.Fatalf("blocked principal error = %v, want ErrInvalidPrincipal", err)
	}
}
