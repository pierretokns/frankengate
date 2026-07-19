package vectorstore

import (
	"reflect"
	"testing"
)

func validAuthorizationEnvelope() AuthorizationEnvelope {
	return AuthorizationEnvelope{
		TenantID: "tenant-a", Principals: []string{"team:research", "user:alice"},
		Classification: 2, PolicyVersion: "policy-7", SourceRevision: "source-9",
		DeletionEpoch: 4, IndexRevision: "index-3",
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
	if len(queries) != 5 {
		t.Fatalf("got %d mandatory predicates, want 5", len(queries))
	}
	if queries[0].Field != AuthorizationTenantKey || queries[4].Field != AuthorizationClassification {
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

func validAuthorizationEnvelopeProperties() map[string]interface{} {
	e := validAuthorizationEnvelope()
	metadata, _ := e.Metadata()
	props := make(map[string]interface{}, len(metadata))
	for key, value := range metadata {
		props[key] = value
	}
	return props
}
