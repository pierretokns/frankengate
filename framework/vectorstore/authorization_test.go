package vectorstore

import (
	"context"
	"reflect"
	"testing"
	"time"
)

func validAuthorizationEnvelope() AuthorizationEnvelope {
	return AuthorizationEnvelope{
		TenantID: "tenant-a", Principals: []string{"team:research", "user:alice"},
		Classification: 2, PolicyVersion: "policy-7", SourceRevision: "source-9",
		DeletionEpoch: 4, IndexRevision: "index-3",
	}
}

func TestFilterAuthorizedResultsRejectsExpiredRetentionAndWrongProvenance(t *testing.T) {
	a := validAuthorizationEnvelope()
	a.RetentionUntil = time.Now().Add(time.Hour)
	a.ProvenanceSignature = "sig-current"
	props, err := a.Metadata()
	if err != nil {
		t.Fatal(err)
	}
	props[AuthorizationRetentionUntil] = time.Now().Add(-time.Minute).Format(time.RFC3339Nano)
	if got, err := FilterAuthorizedResults([]SearchResult{{ID: "expired", Properties: props}}, a); err != nil || len(got) != 0 {
		t.Fatalf("expired result was accepted: got=%#v err=%v", got, err)
	}
	props[AuthorizationRetentionUntil] = time.Now().Add(time.Hour).Format(time.RFC3339Nano)
	props[AuthorizationProvenanceSig] = "sig-old"
	if got, err := FilterAuthorizedResults([]SearchResult{{ID: "wrong-provenance", Properties: props}}, a); err != nil || len(got) != 0 {
		t.Fatalf("wrong provenance was accepted: got=%#v err=%v", got, err)
	}
}

func TestAuthorizationEnvelopeMetadataIsDeterministic(t *testing.T) {
	e := validAuthorizationEnvelope()
	first, err := e.Metadata()
	if err != nil {
		t.Fatal(err)
	}
	e.Principals = []string{"user:alice", "team:research"}
	second, err := e.Metadata()
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("metadata changed with principal ordering: %#v != %#v", first, second)
	}
}

func TestAuthorizationEnvelopeRejectsIncompleteAuthority(t *testing.T) {
	cases := []AuthorizationEnvelope{
		{},
		func() AuthorizationEnvelope { e := validAuthorizationEnvelope(); e.TenantID = ""; return e }(),
		func() AuthorizationEnvelope { e := validAuthorizationEnvelope(); e.Principals = nil; return e }(),
		func() AuthorizationEnvelope { e := validAuthorizationEnvelope(); e.Classification = -1; return e }(),
		func() AuthorizationEnvelope { e := validAuthorizationEnvelope(); e.PolicyVersion = ""; return e }(),
		func() AuthorizationEnvelope {
			e := validAuthorizationEnvelope()
			e.Principals = []string{"user:alice", "user:alice"}
			return e
		}(),
	}
	for i, e := range cases {
		if err := e.Validate(); err == nil {
			t.Errorf("case %d unexpectedly validated", i)
		}
	}
}

func TestAuthorizationEnvelopeQueriesIncludeMandatoryPredicates(t *testing.T) {
	queries, err := validAuthorizationEnvelope().Queries()
	if err != nil {
		t.Fatal(err)
	}
	if len(queries) != 6 {
		t.Fatalf("got %d mandatory predicates, want 6", len(queries))
	}
	if queries[0].Field != AuthorizationTenantKey || queries[1].Field != AuthorizationPrincipalsKey || queries[1].Operator != QueryOperatorContainsAny || queries[5].Field != AuthorizationClassification {
		t.Fatalf("unexpected query ordering: %#v", queries)
	}
}

func TestAuthorizationQueriesReachEveryConfiguredAdapter(t *testing.T) {
	queries, err := validAuthorizationEnvelope().Queries()
	if err != nil {
		t.Fatalf("Queries() error = %v", err)
	}
	props := validAuthorizationEnvelopeProperties()
	if !matchesQueries(props, queries) {
		t.Fatal("Pinecone-style metadata matching rejected a valid authority envelope")
	}
	if !matchesQueriesForScan(props, queries) {
		t.Fatal("Redis scan fallback rejected a valid authority envelope")
	}
	if buildQdrantFilter(queries) == nil {
		t.Fatal("Qdrant adapter dropped the authority filter")
	}
	if buildWeaviateFilter(queries) == nil {
		t.Fatal("Weaviate adapter dropped the authority filter")
	}
	if filter, err := buildPineconeFilter(queries); err != nil || filter == nil {
		t.Fatalf("Pinecone adapter dropped the authority filter: filter=%v err=%v", filter, err)
	}

	props[AuthorizationDeletionEpoch] = int64(2)
	if matchesQueriesForScan(props, queries) {
		t.Fatal("adapter fallback accepted a stale deletion epoch")
	}
}

func TestFilterAuthorizedResultsDefendsAgainstPermissiveAdapters(t *testing.T) {
	authority := validAuthorizationEnvelope()
	valid := validAuthorizationEnvelopeProperties()
	validResult := SearchResult{ID: "valid", Properties: valid}
	wrongTenant := cloneProperties(valid)
	wrongTenant[AuthorizationTenantKey] = "tenant-b"
	wrongPrincipal := cloneProperties(valid)
	wrongPrincipal[AuthorizationPrincipalsKey] = []string{"team:other"}
	stale := cloneProperties(valid)
	stale[AuthorizationDeletionEpoch] = int64(3)
	tooClassified := cloneProperties(valid)
	tooClassified[AuthorizationClassification] = int64(3)
	missing := cloneProperties(valid)
	delete(missing, AuthorizationIndexRevision)

	got, err := FilterAuthorizedResults([]SearchResult{
		validResult,
		{ID: "tenant", Properties: wrongTenant},
		{ID: "principal", Properties: wrongPrincipal},
		{ID: "stale", Properties: stale},
		{ID: "classified", Properties: tooClassified},
		{ID: "missing", Properties: missing},
	}, authority)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].ID != "valid" {
		t.Fatalf("authorized results = %#v, want only valid result", got)
	}
}

func TestFilterAuthorizedResultsAcceptsJSONDecodedMetadata(t *testing.T) {
	authority := validAuthorizationEnvelope()
	props := validAuthorizationEnvelopeProperties()
	props[AuthorizationClassification] = float64(2)
	props[AuthorizationDeletionEpoch] = float64(4)
	props[AuthorizationPrincipalsKey] = []interface{}{"user:alice"}
	got, err := FilterAuthorizedResults([]SearchResult{{ID: "json", Properties: props}}, authority)
	if err != nil || len(got) != 1 {
		t.Fatalf("JSON-shaped metadata was rejected: got=%#v err=%v", got, err)
	}
}

func cloneProperties(input map[string]interface{}) map[string]interface{} {
	clone := make(map[string]interface{}, len(input))
	for key, value := range input {
		clone[key] = value
	}
	return clone
}

func TestAuthorizationEnvelopePostFilterFailsClosed(t *testing.T) {
	e := validAuthorizationEnvelope()
	props := validAuthorizationEnvelopeProperties()
	if !e.AllowsMetadata(props) {
		t.Fatal("valid candidate was rejected")
	}
	cases := []struct {
		name   string
		mutate func(map[string]interface{})
	}{
		{"wrong tenant", func(p map[string]interface{}) { p[AuthorizationTenantKey] = "tenant-b" }},
		{"wrong policy", func(p map[string]interface{}) { p[AuthorizationPolicyVersion] = "policy-old" }},
		{"stale source", func(p map[string]interface{}) { p[AuthorizationSourceRevision] = "source-old" }},
		{"stale deletion", func(p map[string]interface{}) { p[AuthorizationDeletionEpoch] = int64(3) }},
		{"over-classified", func(p map[string]interface{}) { p[AuthorizationClassification] = int64(3) }},
		{"no principal overlap", func(p map[string]interface{}) { p[AuthorizationPrincipalsKey] = []interface{}{"team:other"} }},
		{"missing index revision", func(p map[string]interface{}) { delete(p, AuthorizationIndexRevision) }},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			candidate := validAuthorizationEnvelopeProperties()
			tc.mutate(candidate)
			if e.AllowsMetadata(candidate) {
				t.Fatal("unauthorized candidate was accepted")
			}
		})
	}
}

// TestAuthorizationAdversarialMatrix is intentionally backend-neutral. It is
// the local oracle for adapters whose native filter semantics may be weaker or
// whose indexes can lag an authority update. Every mutation must fail closed;
// this protects the boundary before reranking, semantic-cache insertion, or
// replay exposure.
func TestAuthorizationAdversarialMatrix(t *testing.T) {
	authority := validAuthorizationEnvelope()
	base := validAuthorizationEnvelopeProperties()
	cases := []struct {
		name   string
		mutate func(map[string]interface{})
	}{
		{"cross tenant", func(p map[string]interface{}) { p[AuthorizationTenantKey] = "tenant-b" }},
		{"cross principal", func(p map[string]interface{}) { p[AuthorizationPrincipalsKey] = []string{"team:secret"} }},
		{"stale policy", func(p map[string]interface{}) { p[AuthorizationPolicyVersion] = "policy-6" }},
		{"stale source", func(p map[string]interface{}) { p[AuthorizationSourceRevision] = "source-8" }},
		{"stale index", func(p map[string]interface{}) { p[AuthorizationIndexRevision] = "index-2" }},
		{"tombstoned deletion epoch", func(p map[string]interface{}) { p[AuthorizationDeletionEpoch] = int64(3) }},
		{"over-classified", func(p map[string]interface{}) { p[AuthorizationClassification] = int64(3) }},
		{"missing authority", func(p map[string]interface{}) { delete(p, AuthorizationTenantKey) }},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			candidate := cloneProperties(base)
			tc.mutate(candidate)
			if authority.AllowsMetadata(candidate) {
				t.Fatalf("adversarial candidate was accepted: %#v", candidate)
			}
		})
	}
}

func TestAuthorizedStorePreservesNamespaceAndCacheIsolationPredicates(t *testing.T) {
	backend := &namespaceRecordingBackend{results: []SearchResult{{ID: "same-id", Properties: validAuthorizationEnvelopeProperties()}}}
	store, err := NewAuthorizedStore(backend)
	if err != nil {
		t.Fatal(err)
	}
	for _, namespace := range []string{"tenant-a-cache", "tenant-b-cache"} {
		if _, _, err := store.GetAll(t.Context(), validAuthorizationEnvelope(), namespace, nil, nil, nil, 10); err != nil {
			t.Fatal(err)
		}
	}
	if len(backend.namespaces) != 2 || backend.namespaces[0] != "tenant-a-cache" || backend.namespaces[1] != "tenant-b-cache" {
		t.Fatalf("namespace boundary was not preserved: %#v", backend.namespaces)
	}
	for i, queries := range backend.queries {
		if len(queries) < 6 || queries[0].Field != AuthorizationTenantKey || queries[0].Value != "tenant-a" {
			t.Fatalf("request %d missing mandatory cache authorization predicates: %#v", i, queries)
		}
	}
}

type namespaceRecordingBackend struct {
	namespaces []string
	queries    [][]Query
	results    []SearchResult
}

func (b *namespaceRecordingBackend) Ping(context.Context) error { return nil }
func (b *namespaceRecordingBackend) CreateNamespace(context.Context, string, int, map[string]VectorStoreProperties) error {
	return nil
}
func (b *namespaceRecordingBackend) DeleteNamespace(context.Context, string) error { return nil }
func (b *namespaceRecordingBackend) GetChunk(context.Context, string, string) (SearchResult, error) {
	return b.results[0], nil
}
func (b *namespaceRecordingBackend) GetChunks(context.Context, string, []string) ([]SearchResult, error) {
	return b.results, nil
}
func (b *namespaceRecordingBackend) GetAll(_ context.Context, namespace string, queries []Query, _ []string, cursor *string, _ int64) ([]SearchResult, *string, error) {
	b.namespaces = append(b.namespaces, namespace)
	b.queries = append(b.queries, queries)
	return b.results, cursor, nil
}
func (b *namespaceRecordingBackend) GetNearest(context.Context, string, []float32, []Query, []string, float64, int64) ([]SearchResult, error) {
	return b.results, nil
}
func (b *namespaceRecordingBackend) RequiresVectors() bool { return true }
func (b *namespaceRecordingBackend) Add(context.Context, string, string, []float32, map[string]interface{}) error {
	return nil
}
func (b *namespaceRecordingBackend) Delete(context.Context, string, string) error { return nil }
func (b *namespaceRecordingBackend) DeleteAll(context.Context, string, []Query) ([]DeleteResult, error) {
	return nil, nil
}
func (b *namespaceRecordingBackend) Close(context.Context, string) error { return nil }

func TestAuthorizationEnvelopePostFilterAcceptsJSONMetadata(t *testing.T) {
	e := validAuthorizationEnvelope()
	props := validAuthorizationEnvelopeProperties()
	props[AuthorizationPrincipalsKey] = []interface{}{"user:alice"}
	props[AuthorizationClassification] = float64(2)
	props[AuthorizationDeletionEpoch] = float64(4)
	if !e.AllowsMetadata(props) {
		t.Fatal("JSON-decoded authority metadata was rejected")
	}
}

func validAuthorizationEnvelopeProperties() map[string]interface{} {
	e := validAuthorizationEnvelope()
	metadata, _ := e.Metadata()
	props := make(map[string]interface{}, len(metadata))
	for key, value := range metadata {
		props[key] = value
	}
	return props
}
