package vectorstore

import (
	"errors"
	"fmt"
	"sort"
)

// AuthorizationMetadataKey is the stable metadata namespace used by every
// derived vector index. Backends may store these fields differently, but they
// must preserve their meaning and must not silently drop them.
const (
	AuthorizationTenantKey      = "fg_auth_tenant"
	AuthorizationPrincipalsKey  = "fg_auth_principals"
	AuthorizationClassification = "fg_auth_classification"
	AuthorizationPolicyVersion  = "fg_auth_policy_version"
	AuthorizationSourceRevision = "fg_auth_source_revision"
	AuthorizationDeletionEpoch  = "fg_auth_deletion_epoch"
	AuthorizationIndexRevision  = "fg_auth_index_revision"
)

// AuthorizationEnvelope is the minimum authority context that must accompany
// a classified vector or derived cache entry. It is intentionally independent
// of a particular database so pgvector, Qdrant, Redis, and FrankenSearch can
// receive the same authenticated projection.
type AuthorizationEnvelope struct {
	TenantID       string
	Principals     []string
	Classification int
	PolicyVersion  string
	SourceRevision string
	DeletionEpoch  int64
	IndexRevision  string
}

// Validate rejects incomplete or ambiguous authority metadata. Classification
// is an ordered non-negative lattice value; higher values require at least as
// much clearance and are never treated as public by omission.
func (e AuthorizationEnvelope) Validate() error {
	if e.TenantID == "" {
		return errors.New("vectorstore: authorization tenant is required")
	}
	if len(e.Principals) == 0 {
		return errors.New("vectorstore: authorization principal is required")
	}
	if e.Classification < 0 {
		return errors.New("vectorstore: authorization classification must be non-negative")
	}
	if e.PolicyVersion == "" {
		return errors.New("vectorstore: authorization policy version is required")
	}
	if e.SourceRevision == "" {
		return errors.New("vectorstore: authorization source revision is required")
	}
	if e.DeletionEpoch < 0 {
		return errors.New("vectorstore: authorization deletion epoch must be non-negative")
	}
	if e.IndexRevision == "" {
		return errors.New("vectorstore: authorization index revision is required")
	}
	seen := make(map[string]struct{}, len(e.Principals))
	for _, principal := range e.Principals {
		if principal == "" {
			return errors.New("vectorstore: authorization principal cannot be empty")
		}
		if _, ok := seen[principal]; ok {
			return fmt.Errorf("vectorstore: duplicate authorization principal %q", principal)
		}
		seen[principal] = struct{}{}
	}
	return nil
}

// Metadata returns a deterministic backend-neutral representation. Principals
// are sorted in the copy so cache keys and serialized projections do not vary
// with caller ordering.
func (e AuthorizationEnvelope) Metadata() (map[string]interface{}, error) {
	if err := e.Validate(); err != nil {
		return nil, err
	}
	principals := append([]string(nil), e.Principals...)
	sort.Strings(principals)
	return map[string]interface{}{
		AuthorizationTenantKey:      e.TenantID,
		AuthorizationPrincipalsKey:  principals,
		AuthorizationClassification: e.Classification,
		AuthorizationPolicyVersion:  e.PolicyVersion,
		AuthorizationSourceRevision: e.SourceRevision,
		AuthorizationDeletionEpoch:  e.DeletionEpoch,
		AuthorizationIndexRevision:  e.IndexRevision,
	}, nil
}

// Queries returns the mandatory equality predicates for backend-side filtering
// where the backend supports metadata filters. Callers must still enforce the
// same envelope before exposing candidates; this is defense in depth, not a
// post-filter authorization substitute.
func (e AuthorizationEnvelope) Queries() ([]Query, error) {
	metadata, err := e.Metadata()
	if err != nil {
		return nil, err
	}
	return []Query{
		{Field: AuthorizationTenantKey, Operator: QueryOperatorEqual, Value: metadata[AuthorizationTenantKey]},
		{Field: AuthorizationPolicyVersion, Operator: QueryOperatorEqual, Value: metadata[AuthorizationPolicyVersion]},
		{Field: AuthorizationIndexRevision, Operator: QueryOperatorEqual, Value: metadata[AuthorizationIndexRevision]},
		{Field: AuthorizationDeletionEpoch, Operator: QueryOperatorGreaterThanOrEqual, Value: metadata[AuthorizationDeletionEpoch]},
		{Field: AuthorizationClassification, Operator: QueryOperatorLessThanOrEqual, Value: metadata[AuthorizationClassification]},
	}, nil
}
