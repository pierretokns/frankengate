package vectorstore

import (
	"context"
	"fmt"
)

// AuthorizedStore is the backend-neutral authorization boundary for vector
// search. It deliberately wraps VectorStore rather than teaching every
// backend (PGVector, FrankenSearch, Qdrant, Redis, etc.) a different policy
// language. Backend predicates are applied first and the returned candidates
// are checked again locally before they can be exposed, reranked, cached, or
// replayed.
type AuthorizedStore struct {
	backend VectorStore
}

// NewAuthorizedStore returns a fail-closed authorization wrapper. A nil
// backend is rejected so a misconfigured adapter cannot silently become an
// empty, permissive store.
func NewAuthorizedStore(backend VectorStore) (*AuthorizedStore, error) {
	if backend == nil {
		return nil, fmt.Errorf("vectorstore: authorized backend is required")
	}
	return &AuthorizedStore{backend: backend}, nil
}

// Backend exposes the wrapped store for lifecycle operations and metrics. It
// does not bypass authorization for search methods on this type.
func (s *AuthorizedStore) Backend() VectorStore { return s.backend }

// GetNearest applies mandatory authority predicates and post-filters results.
func (s *AuthorizedStore) GetNearest(ctx context.Context, authority AuthorizationEnvelope, namespace string, vector []float32, queries []Query, selectFields []string, threshold float64, limit int64) ([]SearchResult, error) {
	if err := authority.Validate(); err != nil {
		return nil, err
	}
	authQueries, err := authority.Queries()
	if err != nil {
		return nil, err
	}
	results, err := s.backend.GetNearest(ctx, namespace, vector, appendQueries(authQueries, queries), selectFields, threshold, limit)
	if err != nil {
		return nil, err
	}
	return FilterAuthorizedResults(results, authority)
}

// GetAll applies mandatory authority predicates and post-filters results.
func (s *AuthorizedStore) GetAll(ctx context.Context, authority AuthorizationEnvelope, namespace string, queries []Query, selectFields []string, cursor *string, limit int64) ([]SearchResult, *string, error) {
	if err := authority.Validate(); err != nil {
		return nil, cursor, err
	}
	authQueries, err := authority.Queries()
	if err != nil {
		return nil, cursor, err
	}
	results, next, err := s.backend.GetAll(ctx, namespace, appendQueries(authQueries, queries), selectFields, cursor, limit)
	if err != nil {
		return nil, next, err
	}
	filtered, err := FilterAuthorizedResults(results, authority)
	return filtered, next, err
}

// GetChunk applies the post-filter authorization check to point lookups.
// Point lookup APIs have no portable metadata-filter argument, so rejecting a
// candidate after retrieval is mandatory.
func (s *AuthorizedStore) GetChunk(ctx context.Context, authority AuthorizationEnvelope, namespace, id string) (SearchResult, error) {
	if err := authority.Validate(); err != nil {
		return SearchResult{}, err
	}
	result, err := s.backend.GetChunk(ctx, namespace, id)
	if err != nil {
		return SearchResult{}, err
	}
	if !authority.AllowsMetadata(result.Properties) {
		return SearchResult{}, ErrNotFound
	}
	return result, nil
}

// GetChunks applies the post-filter authorization check to point lookups.
func (s *AuthorizedStore) GetChunks(ctx context.Context, authority AuthorizationEnvelope, namespace string, ids []string) ([]SearchResult, error) {
	if err := authority.Validate(); err != nil {
		return nil, err
	}
	results, err := s.backend.GetChunks(ctx, namespace, ids)
	if err != nil {
		return nil, err
	}
	return FilterAuthorizedResults(results, authority)
}

// Add stores an entry only after validating and embedding the complete
// authority envelope. Caller metadata cannot override the reserved fields.
func (s *AuthorizedStore) Add(ctx context.Context, authority AuthorizationEnvelope, namespace, id string, embedding []float32, metadata map[string]interface{}) error {
	authMetadata, err := authority.Metadata()
	if err != nil {
		return err
	}
	merged := make(map[string]interface{}, len(metadata)+len(authMetadata))
	for key, value := range metadata {
		merged[key] = value
	}
	for key, value := range authMetadata {
		merged[key] = value
	}
	return s.backend.Add(ctx, namespace, id, embedding, merged)
}

func appendQueries(required, optional []Query) []Query {
	queries := make([]Query, 0, len(required)+len(optional))
	queries = append(queries, required...)
	queries = append(queries, optional...)
	return queries
}
