package authorityepoch

import (
	"fmt"
	"strings"
)

// ValidatePrincipal validates the complete, stable identity tuple used to
// scope authorization epochs. Callers must not substitute a bare user ID: the
// tenant and issuer prevent identities from colliding across organizations and
// identity providers.
func ValidatePrincipal(principal Principal) error {
	if strings.TrimSpace(principal.Tenant) == "" ||
		strings.TrimSpace(principal.Issuer) == "" ||
		strings.TrimSpace(principal.Subject) == "" {
		return ErrInvalidPrincipal
	}
	return nil
}

// ValidateReferenceShape validates the immutable fields of an authorization
// reference without consulting the current epoch registry. Runtime callers
// must still compare the reference with the authoritative current epoch.
func ValidateReferenceShape(ref Reference) error {
	if err := ValidatePrincipal(ref.Principal); err != nil {
		return err
	}
	if ref.Epoch == 0 || strings.TrimSpace(ref.ID) == "" || !isSupportedArtifactKind(ref.Kind) {
		return fmt.Errorf("%w: epoch, supported kind, and id are required", ErrInvalidReference)
	}
	return nil
}
