package vectorstore

import (
	"context"
	"testing"
)

type authorizedBackend struct {
	results []SearchResult
	queries []Query
	added   map[string]interface{}
}

func (b *authorizedBackend) Ping(context.Context) error { return nil }
func (b *authorizedBackend) CreateNamespace(context.Context, string, int, map[string]VectorStoreProperties) error {
	return nil
}
func (b *authorizedBackend) DeleteNamespace(context.Context, string) error { return nil }
func (b *authorizedBackend) GetChunk(context.Context, string, string) (SearchResult, error) {
	return b.results[0], nil
}
func (b *authorizedBackend) GetChunks(context.Context, string, []string) ([]SearchResult, error) {
	return b.results, nil
}
func (b *authorizedBackend) GetAll(_ context.Context, _ string, q []Query, _ []string, cursor *string, _ int64) ([]SearchResult, *string, error) {
	b.queries = q
	return b.results, cursor, nil
}
func (b *authorizedBackend) GetNearest(_ context.Context, _ string, _ []float32, q []Query, _ []string, _ float64, _ int64) ([]SearchResult, error) {
	b.queries = q
	return b.results, nil
}
func (b *authorizedBackend) RequiresVectors() bool { return true }
func (b *authorizedBackend) Add(_ context.Context, _, _ string, _ []float32, metadata map[string]interface{}) error {
	b.added = metadata
	return nil
}
func (b *authorizedBackend) Delete(context.Context, string, string) error { return nil }
func (b *authorizedBackend) DeleteAll(context.Context, string, []Query) ([]DeleteResult, error) {
	return nil, nil
}
func (b *authorizedBackend) Close(context.Context, string) error { return nil }

func testAuthority() AuthorizationEnvelope {
	return AuthorizationEnvelope{TenantID: "t1", Principals: []string{"team:r", "user:a"}, Classification: 2, PolicyVersion: "p1", SourceRevision: "s1", DeletionEpoch: 3, IndexRevision: "i1"}
}

func authorizedProps() map[string]interface{} {
	a := testAuthority()
	m, _ := a.Metadata()
	return m
}

func TestAuthorizedStoreEnforcesEnvelopeAndAddsPredicates(t *testing.T) {
	props := authorizedProps()
	backend := &authorizedBackend{results: []SearchResult{{ID: "ok", Properties: props}, {ID: "missing", Properties: map[string]interface{}{}}}}
	store, err := NewAuthorizedStore(backend)
	if err != nil {
		t.Fatal(err)
	}
	results, err := store.GetNearest(context.Background(), testAuthority(), "docs", []float32{1}, []Query{{Field: "kind", Operator: QueryOperatorEqual, Value: "memo"}}, nil, 0, 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 1 || results[0].ID != "ok" {
		t.Fatalf("authorized results = %#v", results)
	}
	if len(backend.queries) != 7 || backend.queries[0].Field != AuthorizationTenantKey {
		t.Fatalf("mandatory predicates missing: %#v", backend.queries)
	}
}

func TestAuthorizedStoreAddOverwritesReservedMetadata(t *testing.T) {
	backend := &authorizedBackend{}
	store, _ := NewAuthorizedStore(backend)
	if err := store.Add(context.Background(), testAuthority(), "docs", "id", []float32{1}, map[string]interface{}{AuthorizationTenantKey: "attacker", "kind": "memo"}); err != nil {
		t.Fatal(err)
	}
	if backend.added[AuthorizationTenantKey] != "t1" || backend.added[AuthorizationPolicyVersion] != "p1" {
		t.Fatalf("reserved metadata was not controlled: %#v", backend.added)
	}
}

func TestAuthorizedStorePointLookupFailsClosed(t *testing.T) {
	backend := &authorizedBackend{results: []SearchResult{{ID: "secret", Properties: map[string]interface{}{AuthorizationTenantKey: "other"}}}}
	store, _ := NewAuthorizedStore(backend)
	if _, err := store.GetChunk(context.Background(), testAuthority(), "docs", "secret"); err != ErrNotFound {
		t.Fatalf("error = %v, want ErrNotFound", err)
	}
}
