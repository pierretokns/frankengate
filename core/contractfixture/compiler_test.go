package contractfixture

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const fixtureEpoch = int64(1800000000)

func TestCompileFixtureCorpusDeterministicAndComplete(t *testing.T) {
	meta := readMetaSchema(t)
	manifest := validManifest(t, meta)
	input := marshalManifest(t, manifest)

	artifactsA, irA, err := Compile(input, CompileOptions{MetaSchema: meta, SourceDateEpoch: "1800000000"})
	if err != nil {
		t.Fatalf("compile valid fixture corpus: %v", err)
	}
	artifactsB, irB, err := Compile(input, CompileOptions{MetaSchema: meta, SourceDateEpoch: "1800000000"})
	if err != nil {
		t.Fatalf("compile valid fixture corpus second time: %v", err)
	}
	assertSameBytes(t, "bundle", artifactsA.Bundle, artifactsB.Bundle)
	assertSameBytes(t, "index", artifactsA.Index, artifactsB.Index)
	assertSameBytes(t, "provenance", artifactsA.Provenance, artifactsB.Provenance)
	assertSameBytes(t, "coverage", artifactsA.Coverage, artifactsB.Coverage)
	assertSameBytes(t, "discrepancies", artifactsA.Discrepancies, artifactsB.Discrepancies)
	if irA.GeneratedAt != "2027-01-15T08:00:00Z" || irB.GeneratedAt != irA.GeneratedAt {
		t.Fatalf("generated_at is not pinned by SOURCE_DATE_EPOCH: %q %q", irA.GeneratedAt, irB.GeneratedAt)
	}

	scrambled := validManifest(t, meta)
	reverseSources(scrambled.Sources)
	reverseSchemas(scrambled.RequestSchemas)
	reverseVectors(scrambled.RequestVectors)
	reverseObservations(scrambled.Observations)
	reverseFaults(scrambled.IntentionalFaults)
	scrambledArtifacts, _, err := Compile(marshalManifest(t, scrambled), CompileOptions{MetaSchema: meta, SourceDateEpoch: "1800000000"})
	if err != nil {
		t.Fatalf("compile scrambled fixture corpus: %v", err)
	}
	assertSameBytes(t, "scrambled bundle", artifactsA.Bundle, scrambledArtifacts.Bundle)
	assertSameBytes(t, "scrambled index", artifactsA.Index, scrambledArtifacts.Index)

	corpus, err := ReadSealedCorpus(*artifactsA)
	if err != nil {
		t.Fatalf("read sealed corpus: %v", err)
	}
	if len(corpus.Entries) != 9 {
		t.Fatalf("entry count = %d, want 9", len(corpus.Entries))
	}
	if !strings.Contains(string(artifactsA.Bundle), `"aws_request_id"`) {
		t.Fatal("observed-absent field should remain admissible when the pinned schema allows extensions")
	}
	if !strings.Contains(string(artifactsA.Coverage), `"required-field"`) ||
		!strings.Contains(string(artifactsA.Coverage), `"union-enum"`) ||
		!strings.Contains(string(artifactsA.Coverage), `"route-authority"`) ||
		!strings.Contains(string(artifactsA.Coverage), `"provenance"`) {
		t.Fatal("coverage does not expose mutation targets for required fields, enums, routes, and provenance")
	}
}

func TestCompileUsesEnvironmentSourceDateEpoch(t *testing.T) {
	t.Setenv("SOURCE_DATE_EPOCH", "1800000000")
	meta := readMetaSchema(t)
	_, _, err := Compile(marshalManifest(t, validManifest(t, meta)), CompileOptions{MetaSchema: meta})
	if err != nil {
		t.Fatalf("compile with SOURCE_DATE_EPOCH from environment: %v", err)
	}
}

func TestCompilerRejectsPolicySchemaAndMutationFailures(t *testing.T) {
	meta := readMetaSchema(t)
	tests := []struct {
		name   string
		mutate func(*Manifest)
		want   string
	}{
		{
			name: "unknown source class",
			mutate: func(m *Manifest) {
				m.Sources[0].Class = "github-models"
			},
			want: "source[0]",
		},
		{
			name: "source content digest mismatch",
			mutate: func(m *Manifest) {
				m.Sources[0].ContentDigest = digestBytes([]byte("wrong"))
			},
			want: "content digest mismatch",
		},
		{
			name: "missing license terms",
			mutate: func(m *Manifest) {
				m.Sources[0].LicenseOrTerms = ""
			},
			want: "incomplete",
		},
		{
			name: "prohibited source content",
			mutate: func(m *Manifest) {
				m.Sources[3].Content = json.RawMessage(`{"raw":"not redistributable"}`)
			},
			want: "may not vendor source content",
		},
		{
			name: "derived assertion digest mismatch",
			mutate: func(m *Manifest) {
				m.Sources[1].DerivedAssertions[0].AssertionDigest = digestBytes([]byte("wrong"))
			},
			want: "derived assertion digest mismatch",
		},
		{
			name: "unknown route",
			mutate: func(m *Manifest) {
				m.RequestSchemas[0].Route = "/v1/responses"
			},
			want: "outside source coverage",
		},
		{
			name: "schema sourced from observation",
			mutate: func(m *Manifest) {
				m.RequestSchemas[0].SourceID = "mantle-access-denied-observation"
				m.RequestSchemas[0].Authority = "aws-observed-sample"
			},
			want: "not schema authority",
		},
		{
			name: "unreviewed observation",
			mutate: func(m *Manifest) {
				m.Observations[0].Reviewed = false
			},
			want: "not reviewed",
		},
		{
			name: "observation authority escalation",
			mutate: func(m *Manifest) {
				m.Observations[0].Authority = "server-acceptance"
			},
			want: "aws-observed-sample",
		},
		{
			name: "sdk vector from non-client source",
			mutate: func(m *Manifest) {
				m.RequestVectors[0].SourceID = "generic-openai-responses-schema"
				m.RequestVectors[0].Authority = "generic-api-schema"
			},
			want: "not official client serialization",
		},
		{
			name: "valid vector missing required field",
			mutate: func(m *Manifest) {
				delete(m.RequestVectors[0].Request, "model")
			},
			want: "missing_required:model",
		},
		{
			name: "required field relaxation detected by fault",
			mutate: func(m *Manifest) {
				m.RequestSchemas[1].Required = []string{"input"}
			},
			want: "fault",
		},
		{
			name: "enum relaxation detected by fault",
			mutate: func(m *Manifest) {
				m.RequestSchemas[1].Properties[3].Enum = nil
			},
			want: "fault",
		},
		{
			name: "additional property relaxation detected by fault",
			mutate: func(m *Manifest) {
				m.RequestSchemas[0].AdditionalProperties = true
			},
			want: "fault",
		},
		{
			name: "exact absence relaxation detected by fault",
			mutate: func(m *Manifest) {
				m.RequestSchemas[0].ExactAbsent = nil
			},
			want: "fault",
		},
		{
			name: "route authority mutation",
			mutate: func(m *Manifest) {
				m.IntentionalFaults[0].Authority = "official-client-serialization"
			},
			want: "intentional-fault authority",
		},
		{
			name: "unknown discrepancy source",
			mutate: func(m *Manifest) {
				m.Discrepancies[0].ConflictingSourceIDs = []string{"missing-source", "openai-ruby-route-discrepancy"}
			},
			want: "unknown source",
		},
		{
			name: "stale toolchain lock",
			mutate: func(m *Manifest) {
				m.ToolchainLock.SourceDateEpoch = fixtureEpoch - 1
			},
			want: "SOURCE_DATE_EPOCH",
		},
		{
			name: "missing prior compatibility",
			mutate: func(m *Manifest) {
				m.Compatibility.PriorVersions = []string{"bedrock-mantle-corpus/v1"}
			},
			want: "prior version",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			manifest := validManifest(t, meta)
			tt.mutate(&manifest)
			_, _, err := Compile(marshalManifest(t, manifest), CompileOptions{MetaSchema: meta, SourceDateEpoch: "1800000000"})
			if err == nil {
				t.Fatal("mutated fixture input unexpectedly compiled")
			}
			if !strings.Contains(err.Error(), tt.want) {
				t.Fatalf("error %q does not contain %q", err, tt.want)
			}
		})
	}
}

func TestCompilerRejectsDuplicateAndUnknownJSON(t *testing.T) {
	meta := readMetaSchema(t)
	valid := string(marshalManifest(t, validManifest(t, meta)))
	for _, test := range []struct {
		name string
		body string
		want string
	}{
		{
			name: "duplicate top-level key",
			body: strings.Replace(valid, `"schema":"bedrock-mantle-contract-fixture-input/v1"`, `"schema":"bedrock-mantle-contract-fixture-input/v1","schema":"bedrock-mantle-contract-fixture-input/v1"`, 1),
			want: "duplicate JSON key",
		},
		{
			name: "unknown top-level key",
			body: strings.TrimSuffix(valid, "}") + `,"surprise":true}`,
			want: "unknown field",
		},
		{
			name: "trailing JSON",
			body: valid + `{}`,
			want: "trailing",
		},
	} {
		t.Run(test.name, func(t *testing.T) {
			_, _, err := Compile([]byte(test.body), CompileOptions{MetaSchema: meta, SourceDateEpoch: "1800000000"})
			if err == nil {
				t.Fatal("malformed JSON unexpectedly compiled")
			}
			if !strings.Contains(err.Error(), test.want) {
				t.Fatalf("error %q does not contain %q", err, test.want)
			}
		})
	}
}

func readMetaSchema(t *testing.T) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("testdata", "metaschema.v1.json"))
	if err != nil {
		t.Fatalf("read meta-schema fixture: %v", err)
	}
	return data
}

func marshalManifest(t *testing.T, manifest Manifest) []byte {
	t.Helper()
	data, err := canonicalJSON(manifest)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func validManifest(t *testing.T, meta []byte) Manifest {
	t.Helper()
	openAISchemaContent := json.RawMessage(`{"additionalProperties":true,"properties":{"input":{"type":"string"},"model":{"type":"string"},"parallel_tool_calls":{"type":"boolean"},"reasoning_effort":{"enum":["high","low","medium"],"type":"string"},"stream":{"type":"boolean"}},"required":["input","model"],"type":"object"}`)
	nativeSchemaContent := json.RawMessage(`{"additionalProperties":false,"properties":{"inferenceConfig":{"type":"object"},"messages":{"type":"array"},"modelId":{"type":"string"}},"required":["messages","modelId"],"type":"object"}`)
	openAISchemaDigest := mustDigestRaw(t, openAISchemaContent)
	nativeSchemaDigest := mustDigestRaw(t, nativeSchemaContent)
	openAICitation := "source-lock:openai-python-mantle-vector#responses-lite"
	nativeCitation := "source-lock:botocore-native-client-vector#converse"
	observeCitation := "observation:mantle-frontier-access-denied#reviewed"
	rubyCitation := "source-lock:openai-ruby-route-discrepancy#route"

	sources := []Source{
		{
			ID:               "generic-openai-responses-schema",
			Class:            "generic-api-schema",
			AuthorityCeiling: "generic OpenAI request shape only; never Mantle server acceptance",
			Revision:         "openapi-db3e5319",
			Locator:          "repo://fixtures/openai/responses.schema.json@db3e5319",
			ArtifactDigest:   digestBytes([]byte("openai-openapi-db3e5319")),
			ContentDigest:    openAISchemaDigest,
			LicenseOrTerms:   "MIT; fixture digest sha256:1111111111111111111111111111111111111111111111111111111111111111",
			Redistribution:   redistributionPermitted,
			ExtractionRecipe: "checked-in minimal schema distilled from pinned OpenAI OpenAPI revision",
			Content:          openAISchemaContent,
			CoveredRoutes:    []string{"/openai/v1/responses"},
			CoveredSurfaces:  []string{"generic-openai-responses"},
			Omissions:        []string{"mantle-route", "server-acceptance"},
		},
		{
			ID:               "openai-python-mantle-vector",
			Class:            "official-client-serialization",
			AuthorityCeiling: "emitted request routing and serialization only",
			Revision:         "v2.46.0@0e6adb15adc1e74087bcb402de7a75e4fbc0aecb",
			Locator:          "repo://fixtures/openai-python/bedrock.py@0e6adb15adc1e74087bcb402de7a75e4fbc0aecb",
			ArtifactDigest:   digestBytes([]byte("openai-python-mantle-vector")),
			LicenseOrTerms:   "Apache-2.0; license digest sha256:2222222222222222222222222222222222222222222222222222222222222222",
			Redistribution:   redistributionDerived,
			ExtractionRecipe: "review pinned client and derive only emitted route/header/request assertions",
			DerivedAssertions: assertionsForSource("openai-python-mantle-vector", []DerivedAssertion{
				{ID: "responses-lite-route", Assertion: "OpenAI Python Bedrock provider emits /openai/v1/responses for namespaced frontier models.", Citation: openAICitation},
			}),
			CoveredRoutes:   []string{"/openai/v1/responses"},
			CoveredSurfaces: []string{"mantle-openai-route-openai-v1", "responses-lite-client-profile"},
			Omissions:       []string{"exhaustive-server-acceptance", "raw-client-source"},
		},
		{
			ID:               "botocore-native-bedrock-schema",
			Class:            "native-aws-service-model",
			AuthorityCeiling: "AWS native Bedrock Converse request model only; not Mantle",
			Revision:         "botocore-1.43.52@39540f4745b272f51a9fe34a4957f761fd1c25f6",
			Locator:          "repo://fixtures/botocore/bedrock-runtime/service-2.json@39540f4745b272f51a9fe34a4957f761fd1c25f6",
			ArtifactDigest:   digestBytes([]byte("botocore-native-bedrock-schema")),
			ContentDigest:    nativeSchemaDigest,
			LicenseOrTerms:   "Apache-2.0; license digest sha256:3333333333333333333333333333333333333333333333333333333333333333",
			Redistribution:   redistributionPermitted,
			ExtractionRecipe: "checked-in minimal shape distilled from pinned botocore service model",
			Content:          nativeSchemaContent,
			CoveredRoutes:    []string{"/model/{modelId}/converse"},
			CoveredSurfaces:  []string{"native-bedrock-converse", "native-bedrock-shapes"},
			Omissions:        []string{"mantle", "server-acceptance"},
		},
		{
			ID:               "mantle-access-denied-observation",
			Class:            "aws-observed-sample",
			AuthorityCeiling: "sanitized AWS observation only; never request acceptance",
			Revision:         "observed-2026-07-21T00:05:58Z",
			Locator:          "repo://fixtures/observations/mantle-frontier-access-denied.v1.json",
			ArtifactDigest:   digestBytes([]byte("mantle-access-denied-observation")),
			LicenseOrTerms:   "operator-reviewed observation; no AWS response body redistributed",
			Redistribution:   redistributionProhibited,
			ExtractionRecipe: "redact request IDs and credentials; retain only status/error classes and derived assertions",
			DerivedAssertions: assertionsForSource("mantle-access-denied-observation", []DerivedAssertion{
				{ID: "access-denied-not-acceptance", Assertion: "A 401 access_denied observation does not prove request body acceptance or rejection.", Citation: observeCitation},
			}),
			CoveredRoutes:   []string{"/openai/v1/responses"},
			CoveredSurfaces: []string{"mantle-frontier-access-denied"},
			Omissions:       []string{"authorization", "request-id-values", "sigv4-signature"},
		},
		{
			ID:               "intentional-fault-catalog",
			Class:            "intentional-fault",
			AuthorityCeiling: "negative compiler conformance only",
			Revision:         "fixture-faults-v1",
			Locator:          "repo://fixtures/faults/intentional-faults.v1.json",
			ArtifactDigest:   digestBytes([]byte("intentional-fault-catalog")),
			ContentDigest:    digestBytes([]byte(`{"faults":["bad-enum","exact-absent","missing-required","unknown-field"]}`)),
			LicenseOrTerms:   "project-owned test fixture",
			Redistribution:   redistributionPermitted,
			ExtractionRecipe: "hand-authored negative fixtures reviewed with the compiler schema",
			Content:          json.RawMessage(`{"faults":["bad-enum","exact-absent","missing-required","unknown-field"]}`),
			CoveredRoutes:    []string{"/model/{modelId}/converse", "/openai/v1/responses"},
			CoveredSurfaces:  []string{"compiler-negative-tests"},
			Omissions:        []string{"paid-inference", "provider-network"},
		},
		{
			ID:               "botocore-native-client-vector",
			Class:            "official-client-serialization",
			AuthorityCeiling: "native SDK emitted request shape only",
			Revision:         "aws-sdk-go-v2-1.42.0",
			Locator:          "repo://fixtures/aws-sdk-go-v2/converse-vector@1.42.0",
			ArtifactDigest:   digestBytes([]byte("botocore-native-client-vector")),
			LicenseOrTerms:   "Apache-2.0; license digest sha256:4444444444444444444444444444444444444444444444444444444444444444",
			Redistribution:   redistributionDerived,
			ExtractionRecipe: "derive minimal native Converse request shape from pinned SDK vector",
			DerivedAssertions: assertionsForSource("botocore-native-client-vector", []DerivedAssertion{
				{ID: "native-converse-minimal", Assertion: "Native Converse requests carry modelId and messages without OpenAI project headers.", Citation: nativeCitation},
			}),
			CoveredRoutes:   []string{"/model/{modelId}/converse"},
			CoveredSurfaces: []string{"native-bedrock-converse-client-shape"},
			Omissions:       []string{"mantle", "server-acceptance"},
		},
		{
			ID:               "openai-ruby-route-discrepancy",
			Class:            "official-client-serialization",
			AuthorityCeiling: "client discrepancy only; not service authority",
			Revision:         "v0.71.0@7f0fb8f34a3a3c4b4b5d87c5cb2892653fde1670",
			Locator:          "repo://fixtures/openai-ruby/bedrock.rb@7f0fb8f34a3a3c4b4b5d87c5cb2892653fde1670",
			ArtifactDigest:   digestBytes([]byte("openai-ruby-route-discrepancy")),
			LicenseOrTerms:   "Apache-2.0; license digest sha256:5555555555555555555555555555555555555555555555555555555555555555",
			Redistribution:   redistributionDerived,
			ExtractionRecipe: "record route disagreement as discrepancy, not as normalized route authority",
			DerivedAssertions: assertionsForSource("openai-ruby-route-discrepancy", []DerivedAssertion{
				{ID: "ruby-v1-route", Assertion: "OpenAI Ruby emits /v1 but is recorded only as a client discrepancy.", Citation: rubyCitation},
			}),
			CoveredRoutes:   []string{"/openai/v1/responses"},
			CoveredSurfaces: []string{"mantle-openai-route-discrepancy"},
			Omissions:       []string{"server-acceptance"},
		},
	}

	return Manifest{
		Schema:           ManifestSchemaV1,
		MetaSchemaDigest: digestBytes(meta),
		ToolchainLock: ToolchainLock{
			Schema:          "bedrock-mantle-contract-toolchain-lock/v1",
			GoVersion:       "go1.26.5",
			Compiler:        "contractfixture-test-compiler",
			SourceDateEpoch: fixtureEpoch,
			Reproducibility: reproByteIdentical,
		},
		Sources: sources,
		RequestSchemas: []RequestSchema{
			{
				ID:                   "native-bedrock-converse",
				SourceID:             "botocore-native-bedrock-schema",
				Route:                "/model/{modelId}/converse",
				Authority:            "native-aws-service-model",
				AdditionalProperties: false,
				Required:             []string{"messages", "modelId"},
				ExactAbsent:          []string{"openai_project"},
				Properties: []PropertySchema{
					{Name: "inferenceConfig", Type: "object"},
					{Name: "messages", Type: "array"},
					{Name: "modelId", Type: "string"},
				},
			},
			{
				ID:                   "openai-responses-lite",
				SourceID:             "generic-openai-responses-schema",
				Route:                "/openai/v1/responses",
				Authority:            "generic-api-schema",
				AdditionalProperties: true,
				Required:             []string{"input", "model"},
				ExactAbsent:          []string{"top_level_tools"},
				Properties: []PropertySchema{
					{Name: "input", Type: "string"},
					{Name: "model", Type: "string"},
					{Name: "parallel_tool_calls", Type: "boolean"},
					{Name: "reasoning_effort", Type: "string", Enum: []string{"high", "low", "medium"}},
					{Name: "stream", Type: "boolean"},
				},
			},
		},
		RequestVectors: []RequestVector{
			{
				ID:        "codex-lite-frontier",
				SourceID:  "openai-python-mantle-vector",
				SchemaID:  "openai-responses-lite",
				Route:     "/openai/v1/responses",
				Authority: "official-client-serialization",
				Family:    "openai",
				Request: rawObject(map[string]string{
					"input":               `"hello"`,
					"model":               `"openai.gpt-5.6-sol"`,
					"parallel_tool_calls": "false",
					"reasoning_effort":    `"low"`,
					"stream":              "false",
					"aws_request_id":      `"sha256:redacted"`,
				}),
				Expected:   ExpectedValidation{Valid: true, Diagnostic: "ok"},
				Invariants: []string{"extension-fields-preserved", "responses-lite-header", "scalar-input"},
			},
			{
				ID:        "native-converse-minimal",
				SourceID:  "botocore-native-client-vector",
				SchemaID:  "native-bedrock-converse",
				Route:     "/model/{modelId}/converse",
				Authority: "official-client-serialization",
				Family:    "native-bedrock",
				Request: rawObject(map[string]string{
					"messages": `[{"role":"user","content":[{"text":"hello"}]}]`,
					"modelId":  `"anthropic.claude-3-5-sonnet-20241022-v2:0"`,
				}),
				Expected:   ExpectedValidation{Valid: true, Diagnostic: "ok"},
				Invariants: []string{"native-converse-shape", "no-openai-project"},
			},
		},
		Observations: []SanitizedObservation{
			{
				ID:        "frontier-access-denied",
				SourceID:  "mantle-access-denied-observation",
				Route:     "/openai/v1/responses",
				Authority: "aws-observed-sample",
				Reviewed:  true,
				RequestShape: rawObject(map[string]string{
					"model":                 `"exact-upstream-id"`,
					"responses_lite_header": "true",
					"status":                `"401-access-denied"`,
				}),
				ObservedAbsent: []string{"aws_request_id", "successful-invocation"},
				Assertions: assertionsForSource("mantle-access-denied-observation", []DerivedAssertion{
					{ID: "access-denied-not-acceptance", Assertion: "A 401 access_denied observation does not prove request body acceptance or rejection.", Citation: observeCitation},
				}),
			},
		},
		IntentionalFaults: []IntentionalFault{
			{
				ID:        "bad-openai-enum",
				SourceID:  "intentional-fault-catalog",
				SchemaID:  "openai-responses-lite",
				Route:     "/openai/v1/responses",
				Authority: "intentional-fault",
				Request: rawObject(map[string]string{
					"input":            `"hello"`,
					"model":            `"openai.gpt-5.6-sol"`,
					"reasoning_effort": `"extreme"`,
				}),
				ExpectedDiagnostic: "invalid_enum:reasoning_effort",
				MutationTargets:    []string{"provenance", "union-enum"},
			},
			{
				ID:        "forbidden-native-project",
				SourceID:  "intentional-fault-catalog",
				SchemaID:  "native-bedrock-converse",
				Route:     "/model/{modelId}/converse",
				Authority: "intentional-fault",
				Request: rawObject(map[string]string{
					"messages":       `[{"role":"user","content":[{"text":"hello"}]}]`,
					"modelId":        `"anthropic.claude-3-5-sonnet-20241022-v2:0"`,
					"openai_project": `"proj_forbidden"`,
				}),
				ExpectedDiagnostic: "exact_absent:openai_project",
				MutationTargets:    []string{"authority", "route-authority"},
			},
			{
				ID:        "missing-openai-model",
				SourceID:  "intentional-fault-catalog",
				SchemaID:  "openai-responses-lite",
				Route:     "/openai/v1/responses",
				Authority: "intentional-fault",
				Request: rawObject(map[string]string{
					"input": `"hello"`,
				}),
				ExpectedDiagnostic: "missing_required:model",
				MutationTargets:    []string{"provenance", "required-field"},
			},
			{
				ID:        "unknown-native-temperature",
				SourceID:  "intentional-fault-catalog",
				SchemaID:  "native-bedrock-converse",
				Route:     "/model/{modelId}/converse",
				Authority: "intentional-fault",
				Request: rawObject(map[string]string{
					"messages":    `[{"role":"user","content":[{"text":"hello"}]}]`,
					"modelId":     `"anthropic.claude-3-5-sonnet-20241022-v2:0"`,
					"temperature": "1",
				}),
				ExpectedDiagnostic: "unknown_field:temperature",
				MutationTargets:    []string{"provenance", "route-authority"},
			},
		},
		Discrepancies: []Discrepancy{
			{
				ID:                   "openai-ruby-v1-route",
				Subject:              "OpenAI Ruby Bedrock provider route disagrees with Python and Node",
				ConflictingSourceIDs: []string{"openai-python-mantle-vector", "openai-ruby-route-discrepancy"},
				Status:               "resolved",
				Resolution:           "record Ruby /v1 as client serialization discrepancy only; do not normalize into service authority",
				Evidence:             "reviewed derived assertions with source hashes",
			},
		},
		Compatibility: Compatibility{
			MinReaderVersion: 1,
			PriorVersions:    []string{"bedrock-mantle-corpus/v0"},
		},
	}
}

func assertionsForSource(sourceID string, assertions []DerivedAssertion) []DerivedAssertion {
	for index := range assertions {
		assertions[index].AssertionDigest = digestAssertion(sourceID, assertions[index])
	}
	return assertions
}

func mustDigestRaw(t *testing.T, raw json.RawMessage) string {
	t.Helper()
	normalized, err := normalizeRawJSON(raw)
	if err != nil {
		t.Fatal(err)
	}
	return digestBytes(normalized)
}

func rawObject(values map[string]string) map[string]json.RawMessage {
	object := make(map[string]json.RawMessage, len(values))
	for key, value := range values {
		object[key] = json.RawMessage(value)
	}
	return object
}

func assertSameBytes(t *testing.T, label string, a []byte, b []byte) {
	t.Helper()
	if string(a) != string(b) {
		t.Fatalf("%s differs\nA=%s\nB=%s", label, a, b)
	}
}

func reverseSources(values []Source) {
	for left, right := 0, len(values)-1; left < right; left, right = left+1, right-1 {
		values[left], values[right] = values[right], values[left]
	}
}

func reverseSchemas(values []RequestSchema) {
	for left, right := 0, len(values)-1; left < right; left, right = left+1, right-1 {
		values[left], values[right] = values[right], values[left]
	}
}

func reverseVectors(values []RequestVector) {
	for left, right := 0, len(values)-1; left < right; left, right = left+1, right-1 {
		values[left], values[right] = values[right], values[left]
	}
}

func reverseObservations(values []SanitizedObservation) {
	for left, right := 0, len(values)-1; left < right; left, right = left+1, right-1 {
		values[left], values[right] = values[right], values[left]
	}
}

func reverseFaults(values []IntentionalFault) {
	for left, right := 0, len(values)-1; left < right; left, right = left+1, right-1 {
		values[left], values[right] = values[right], values[left]
	}
}
