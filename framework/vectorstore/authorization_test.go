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
