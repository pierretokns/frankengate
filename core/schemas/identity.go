package schemas

import (
	"context"
	"fmt"

	"github.com/maximhq/bifrost/core/identity"
)

// SetIdentityEntitlements installs the immutable, verified IdP/SCIM snapshot
// used by governance. Callers must evaluate claims before setting it; request
// headers must never be accepted as an entitlement source.
func SetIdentityEntitlements(ctx *BifrostContext, entitlements identity.Entitlements) error {
	if ctx == nil {
		return fmt.Errorf("identity entitlements: nil context")
	}
	ctx.SetValue(BifrostContextKeyIdentityEntitlements, entitlements)
	return nil
}

func IdentityEntitlementsFromContext(ctx context.Context) (identity.Entitlements, bool) {
	if ctx == nil {
		return identity.Entitlements{}, false
	}
	entitlements, ok := ctx.Value(BifrostContextKeyIdentityEntitlements).(identity.Entitlements)
	return entitlements, ok
}

// SetIdentityEntitlementDecision stores sanitized authorization metadata for
// audit consumers. Callers must not include group names or token claims.
func SetIdentityEntitlementDecision(ctx *BifrostContext, decision identity.Decision) error {
	if ctx == nil {
		return fmt.Errorf("identity entitlement decision: nil context")
	}
	ctx.SetValue(BifrostContextKeyIdentityEntitlementDecision, decision)
	return nil
}

func IdentityEntitlementDecisionFromContext(ctx context.Context) (identity.Decision, bool) {
	if ctx == nil {
		return identity.Decision{}, false
	}
	decision, ok := ctx.Value(BifrostContextKeyIdentityEntitlementDecision).(identity.Decision)
	return decision, ok
}
