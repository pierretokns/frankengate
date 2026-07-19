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
		// A vector is readable only when the caller's principal set overlaps
		// the principals recorded on the vector.  Every configured adapter
		// supports ContainsAny; omitting this predicate would reduce the
		// envelope to tenant/classification isolation and leak same-tenant
		// classified chunks across users or teams.
		{Field: AuthorizationPrincipalsKey, Operator: QueryOperatorContainsAny, Value: metadata[AuthorizationPrincipalsKey]},
		{Field: AuthorizationPolicyVersion, Operator: QueryOperatorEqual, Value: metadata[AuthorizationPolicyVersion]},
		{Field: AuthorizationIndexRevision, Operator: QueryOperatorEqual, Value: metadata[AuthorizationIndexRevision]},
		{Field: AuthorizationDeletionEpoch, Operator: QueryOperatorGreaterThanOrEqual, Value: metadata[AuthorizationDeletionEpoch]},
		{Field: AuthorizationClassification, Operator: QueryOperatorLessThanOrEqual, Value: metadata[AuthorizationClassification]},
	}, nil
}

// FilterAuthorizedResults applies the same authority envelope used to build
// backend filters to returned search results. Backend predicates are required
// for efficiency, but this bounded post-filter is the defense-in-depth check
// that keeps a permissive or newly added adapter (for example a FrankenSearch
// bridge) from leaking a classified chunk when its native filter semantics
// differ. Results that are missing mandatory authority metadata are rejected.
// The input order is preserved and the returned slice does not alias it.
func FilterAuthorizedResults(results []SearchResult, authority AuthorizationEnvelope) ([]SearchResult, error) {
	if err := authority.Validate(); err != nil {
		return nil, err
	}
	allowedPrincipals := make(map[string]struct{}, len(authority.Principals))
	for _, principal := range authority.Principals {
		allowedPrincipals[principal] = struct{}{}
	}
	filtered := make([]SearchResult, 0, len(results))
	for _, result := range results {
		if authorizedResult(result, authority, allowedPrincipals) {
			filtered = append(filtered, result)
		}
	}
	return filtered, nil
}

func authorizedResult(result SearchResult, authority AuthorizationEnvelope, principals map[string]struct{}) bool {
	props := result.Properties
	if props == nil || stringValue(props[AuthorizationTenantKey]) != authority.TenantID ||
		stringValue(props[AuthorizationPolicyVersion]) != authority.PolicyVersion ||
		stringValue(props[AuthorizationIndexRevision]) != authority.IndexRevision {
		return false
	}
	classification, ok := integerValue(props[AuthorizationClassification])
	if !ok || classification > int64(authority.Classification) {
		return false
	}
	deletionEpoch, ok := integerValue(props[AuthorizationDeletionEpoch])
	if !ok || deletionEpoch < authority.DeletionEpoch {
		return false
	}
	for _, principal := range stringSlice(props[AuthorizationPrincipalsKey]) {
		if _, allowed := principals[principal]; allowed {
			return true
		}
	}
	return false
}

func stringValue(value interface{}) string {
	switch typed := value.(type) {
	case string:
		return typed
	case []byte:
		return string(typed)
	default:
		return ""
	}
}

func stringSlice(value interface{}) []string {
	switch typed := value.(type) {
	case []string:
		return typed
	case []interface{}:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			if text, ok := item.(string); ok {
				out = append(out, text)
			}
		}
		return out
	default:
		return nil
	}
}

func integerValue(value interface{}) (int64, bool) {
	switch typed := value.(type) {
	case int:
		return int64(typed), true
	case int8:
		return int64(typed), true
	case int16:
		return int64(typed), true
	case int32:
		return int64(typed), true
	case int64:
		return typed, true
	case uint:
		return int64(typed), true
	case uint8:
		return int64(typed), true
	case uint16:
		return int64(typed), true
	case uint32:
		return int64(typed), true
	case uint64:
		if typed > uint64(^uint64(0)>>1) {
			return 0, false
		}
		return int64(typed), true
	case float64:
		return int64(typed), typed == float64(int64(typed))
	default:
		return 0, false
	}
}

// AllowsMetadata performs the mandatory post-filter authorization check for a
// candidate returned by a vector backend. Backend filters are defense in depth:
// some adapters can fall back to scans, and external indexes may lag policy
// updates. Callers must run this check before exposing, reranking, caching, or
// replaying a candidate. Missing or malformed authority metadata fails closed.
func (e AuthorizationEnvelope) AllowsMetadata(properties map[string]interface{}) bool {
	if properties == nil {
		return false
	}
	allowed := make(map[string]struct{}, len(e.Principals))
	for _, principal := range e.Principals {
		allowed[principal] = struct{}{}
	}
	return authorizedResult(SearchResult{Properties: properties}, e, allowed)
}
