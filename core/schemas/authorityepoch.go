package schemas

import (
	"context"
	"fmt"

	"github.com/maximhq/bifrost/core/authorityepoch"
)

// SetAuthorizationPrincipal stores a validated principal as a value. Principal
// contains strings only, so storing it by value gives downstream code an
// immutable snapshot rather than a caller-owned pointer.
func SetAuthorizationPrincipal(ctx *BifrostContext, principal authorityepoch.Principal) error {
	if ctx == nil {
		return fmt.Errorf("authorization context is nil: %w", authorityepoch.ErrInvalidPrincipal)
	}
	if err := authorityepoch.ValidatePrincipal(principal); err != nil {
		return err
	}
	ctx.SetValue(BifrostContextKeyAuthorizationPrincipal, principal)
	if stored, ok := ctx.Value(BifrostContextKeyAuthorizationPrincipal).(authorityepoch.Principal); !ok || stored != principal {
		return fmt.Errorf("authorization principal was not accepted by context: %w", authorityepoch.ErrInvalidPrincipal)
	}
	return nil
}

// AuthorizationPrincipalFromContext returns the trusted, complete identity
// tuple or fails closed when it is missing, mistyped, or incomplete.
func AuthorizationPrincipalFromContext(ctx context.Context) (authorityepoch.Principal, error) {
	if ctx == nil {
		return authorityepoch.Principal{}, authorityepoch.ErrInvalidPrincipal
	}
	principal, ok := ctx.Value(BifrostContextKeyAuthorizationPrincipal).(authorityepoch.Principal)
	if !ok {
		return authorityepoch.Principal{}, authorityepoch.ErrInvalidPrincipal
	}
	if err := authorityepoch.ValidatePrincipal(principal); err != nil {
		return authorityepoch.Principal{}, err
	}
	return principal, nil
}

// SetAuthorizationEpochReference stores a validated reference and its matching
// principal as values. Keeping both keys lets request admission use the
// principal before an artifact is selected while reference consumers can later
// prove they refer to the same identity snapshot.
func SetAuthorizationEpochReference(ctx *BifrostContext, ref authorityepoch.Reference) error {
	if ctx == nil {
		return fmt.Errorf("authorization context is nil: %w", authorityepoch.ErrInvalidReference)
	}
	if err := authorityepoch.ValidateReferenceShape(ref); err != nil {
		return err
	}
	ctx.SetValue(BifrostContextKeyAuthorizationPrincipal, ref.Principal)
	ctx.SetValue(BifrostContextKeyAuthorizationEpochReference, ref)
	if storedPrincipal, ok := ctx.Value(BifrostContextKeyAuthorizationPrincipal).(authorityepoch.Principal); !ok || storedPrincipal != ref.Principal {
		return fmt.Errorf("authorization principal was not accepted by context: %w", authorityepoch.ErrInvalidReference)
	}
	if storedRef, ok := ctx.Value(BifrostContextKeyAuthorizationEpochReference).(authorityepoch.Reference); !ok || storedRef != ref {
		return fmt.Errorf("authorization reference was not accepted by context: %w", authorityepoch.ErrInvalidReference)
	}
	return nil
}

// AuthorizationEpochReferenceFromContext returns a structurally valid
// reference only when its embedded principal exactly matches the separately
// propagated principal. Any missing, mistyped, or inconsistent value fails
// closed.
func AuthorizationEpochReferenceFromContext(ctx context.Context) (authorityepoch.Reference, error) {
	if ctx == nil {
		return authorityepoch.Reference{}, authorityepoch.ErrInvalidReference
	}
	ref, ok := ctx.Value(BifrostContextKeyAuthorizationEpochReference).(authorityepoch.Reference)
	if !ok {
		return authorityepoch.Reference{}, authorityepoch.ErrInvalidReference
	}
	if err := authorityepoch.ValidateReferenceShape(ref); err != nil {
		return authorityepoch.Reference{}, err
	}
	principal, err := AuthorizationPrincipalFromContext(ctx)
	if err != nil || principal != ref.Principal {
		return authorityepoch.Reference{}, authorityepoch.ErrInvalidReference
	}
	return ref, nil
}
