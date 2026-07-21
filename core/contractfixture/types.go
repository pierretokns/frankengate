// Package contractfixture compiles reviewed Bedrock and Mantle contract inputs
// into sealed deterministic corpus artifacts.
package contractfixture

import "encoding/json"

const (
	ManifestSchemaV1         = "bedrock-mantle-contract-fixture-input/v1"
	MetaSchemaV1             = "bedrock-mantle-contract-fixture-meta-schema/v1"
	IRSchemaV1               = "bedrock-mantle-contract-ir/v1"
	EntrySchemaV1            = "bedrock-mantle-corpus-entry/v1"
	IndexSchemaV1            = "bedrock-mantle-corpus-index/v1"
	LegacyIndexSchemaV0      = "bedrock-mantle-corpus-index/v0"
	ProvenanceSchemaV1       = "bedrock-mantle-corpus-provenance/v1"
	CoverageSchemaV1         = "bedrock-mantle-corpus-coverage/v1"
	DiscrepancySchemaV1      = "bedrock-mantle-corpus-discrepancies/v1"
	ReaderVersion            = 1
	artifactBundle           = "corpus.bundle"
	artifactCoverage         = "coverage.json"
	artifactDiscrepancies    = "discrepancies.json"
	artifactIndex            = "corpus.index.json"
	artifactProvenance       = "provenance.json"
	reproByteIdentical       = "byte-identical"
	reproArchDigests         = "architecture-digests"
	redistributionPermitted  = "permitted"
	redistributionDerived    = "derived-only"
	redistributionProhibited = "prohibited"
)

type MetaSchema struct {
	Schema            string   `json:"schema"`
	InputSchema       string   `json:"input_schema"`
	IRSchema          string   `json:"ir_schema"`
	ReaderVersion     int      `json:"reader_version"`
	RequiredArtifacts []string `json:"required_artifacts"`
}

type Manifest struct {
	Schema            string                 `json:"schema"`
	MetaSchemaDigest  string                 `json:"meta_schema_digest"`
	ToolchainLock     ToolchainLock          `json:"toolchain_lock"`
	Sources           []Source               `json:"sources"`
	RequestSchemas    []RequestSchema        `json:"request_schemas"`
	RequestVectors    []RequestVector        `json:"request_vectors"`
	Observations      []SanitizedObservation `json:"observations"`
	IntentionalFaults []IntentionalFault     `json:"intentional_faults"`
	Discrepancies     []Discrepancy          `json:"discrepancies"`
	Compatibility     Compatibility          `json:"compatibility"`
}

type ToolchainLock struct {
	Schema              string               `json:"schema"`
	GoVersion           string               `json:"go_version"`
	Compiler            string               `json:"compiler"`
	SourceDateEpoch     int64                `json:"source_date_epoch"`
	Reproducibility     string               `json:"reproducibility"`
	ArchitectureDigests []ArchitectureDigest `json:"architecture_digests,omitempty"`
}

type ArchitectureDigest struct {
	Platform string `json:"platform"`
	Digest   string `json:"digest"`
}

type Source struct {
	ID                string             `json:"id"`
	Class             string             `json:"class"`
	AuthorityCeiling  string             `json:"authority_ceiling"`
	Revision          string             `json:"revision"`
	Locator           string             `json:"locator"`
	ArtifactDigest    string             `json:"artifact_digest"`
	ContentDigest     string             `json:"content_digest,omitempty"`
	LicenseOrTerms    string             `json:"license_or_terms"`
	Redistribution    string             `json:"redistribution"`
	ExtractionRecipe  string             `json:"extraction_recipe"`
	Content           json.RawMessage    `json:"content,omitempty"`
	DerivedAssertions []DerivedAssertion `json:"derived_assertions,omitempty"`
	CoveredRoutes     []string           `json:"covered_routes"`
	CoveredSurfaces   []string           `json:"covered_surfaces"`
	Omissions         []string           `json:"omissions"`
}

type DerivedAssertion struct {
	ID              string `json:"id"`
	Assertion       string `json:"assertion"`
	Citation        string `json:"citation"`
	AssertionDigest string `json:"assertion_digest"`
}

type RequestSchema struct {
	ID                   string           `json:"id"`
	SourceID             string           `json:"source_id"`
	Route                string           `json:"route"`
	Authority            string           `json:"authority"`
	AdditionalProperties bool             `json:"additional_properties"`
	Required             []string         `json:"required"`
	ExactAbsent          []string         `json:"exact_absent,omitempty"`
	Properties           []PropertySchema `json:"properties"`
}

type PropertySchema struct {
	Name string   `json:"name"`
	Type string   `json:"type"`
	Enum []string `json:"enum,omitempty"`
}

type RequestVector struct {
	ID         string                     `json:"id"`
	SourceID   string                     `json:"source_id"`
	SchemaID   string                     `json:"schema_id"`
	Route      string                     `json:"route"`
	Authority  string                     `json:"authority"`
	Family     string                     `json:"family"`
	Request    map[string]json.RawMessage `json:"request"`
	Expected   ExpectedValidation         `json:"expected"`
	Invariants []string                   `json:"invariants"`
}

type ExpectedValidation struct {
	Valid      bool   `json:"valid"`
	Diagnostic string `json:"diagnostic"`
}

type SanitizedObservation struct {
	ID             string                     `json:"id"`
	SourceID       string                     `json:"source_id"`
	Route          string                     `json:"route"`
	Authority      string                     `json:"authority"`
	Reviewed       bool                       `json:"reviewed"`
	RequestShape   map[string]json.RawMessage `json:"request_shape"`
	ObservedAbsent []string                   `json:"observed_absent,omitempty"`
	Assertions     []DerivedAssertion         `json:"assertions"`
}

type IntentionalFault struct {
	ID                 string                     `json:"id"`
	SourceID           string                     `json:"source_id"`
	SchemaID           string                     `json:"schema_id"`
	Route              string                     `json:"route"`
	Authority          string                     `json:"authority"`
	Request            map[string]json.RawMessage `json:"request"`
	ExpectedDiagnostic string                     `json:"expected_diagnostic"`
	MutationTargets    []string                   `json:"mutation_targets"`
}

type Discrepancy struct {
	ID                   string   `json:"id"`
	Subject              string   `json:"subject"`
	ConflictingSourceIDs []string `json:"conflicting_source_ids"`
	Status               string   `json:"status"`
	Resolution           string   `json:"resolution"`
	Evidence             string   `json:"evidence"`
}

type Compatibility struct {
	MinReaderVersion int      `json:"min_reader_version"`
	PriorVersions    []string `json:"prior_versions"`
}

type SealedArtifacts struct {
	Bundle        []byte
	Index         []byte
	Provenance    []byte
	Coverage      []byte
	Discrepancies []byte
}

type IR struct {
	Schema           string        `json:"schema"`
	GeneratedAt      string        `json:"generated_at"`
	MetaSchemaDigest string        `json:"meta_schema_digest"`
	ToolchainDigest  string        `json:"toolchain_digest"`
	Sources          []IRSource    `json:"sources"`
	Entries          []CorpusEntry `json:"entries"`
	Discrepancies    []Discrepancy `json:"discrepancies"`
	Compatibility    Compatibility `json:"compatibility"`
}

type IRSource struct {
	ID               string   `json:"id"`
	Class            string   `json:"class"`
	AuthorityCeiling string   `json:"authority_ceiling"`
	Revision         string   `json:"revision"`
	ArtifactDigest   string   `json:"artifact_digest"`
	ContentDigest    string   `json:"content_digest,omitempty"`
	LicenseOrTerms   string   `json:"license_or_terms"`
	Redistribution   string   `json:"redistribution"`
	CoveredRoutes    []string `json:"covered_routes"`
	CoveredSurfaces  []string `json:"covered_surfaces"`
	Omissions        []string `json:"omissions"`
}

type CorpusEntry struct {
	Schema          string                     `json:"schema"`
	ID              string                     `json:"id"`
	Kind            string                     `json:"kind"`
	Route           string                     `json:"route"`
	Authority       string                     `json:"authority"`
	SourceIDs       []string                   `json:"source_ids"`
	Request         map[string]json.RawMessage `json:"request,omitempty"`
	Validation      *RequestValidation         `json:"validation,omitempty"`
	Expected        *ExpectedValidation        `json:"expected,omitempty"`
	ObservedAbsent  []string                   `json:"observed_absent,omitempty"`
	Assertions      []DerivedAssertion         `json:"assertions,omitempty"`
	Invariants      []string                   `json:"invariants,omitempty"`
	MutationTargets []string                   `json:"mutation_targets,omitempty"`
}

type RequestValidation struct {
	SchemaID             string           `json:"schema_id"`
	AdditionalProperties bool             `json:"additional_properties"`
	Required             []string         `json:"required"`
	ExactAbsent          []string         `json:"exact_absent,omitempty"`
	Properties           []PropertySchema `json:"properties"`
}

type Index struct {
	Schema              string        `json:"schema"`
	FormatVersion       int           `json:"format_version"`
	MinReaderVersion    int           `json:"min_reader_version"`
	GeneratedAt         string        `json:"generated_at"`
	BundleDigest        string        `json:"bundle_digest"`
	BundleLength        int           `json:"bundle_length"`
	IRDigest            string        `json:"ir_digest"`
	ToolchainLockDigest string        `json:"toolchain_lock_digest"`
	Entries             []IndexEntry  `json:"entries"`
	Artifacts           []ArtifactRef `json:"artifacts"`
	PriorVersions       []string      `json:"prior_versions"`
}

type IndexEntry struct {
	ID     string `json:"id"`
	Offset int    `json:"offset"`
	Length int    `json:"length"`
	Digest string `json:"digest"`
}

type ArtifactRef struct {
	Name   string `json:"name"`
	Length int    `json:"length"`
	Digest string `json:"digest"`
}

type ProvenanceArtifact struct {
	Schema           string        `json:"schema"`
	GeneratedAt      string        `json:"generated_at"`
	MetaSchemaDigest string        `json:"meta_schema_digest"`
	ToolchainLock    ToolchainLock `json:"toolchain_lock"`
	Sources          []IRSource    `json:"sources"`
}

type CoverageArtifact struct {
	Schema           string          `json:"schema"`
	Routes           []RouteCoverage `json:"routes"`
	AuthorityClasses []ClassCoverage `json:"authority_classes"`
	MutationTargets  []string        `json:"mutation_targets"`
}

type RouteCoverage struct {
	Route        string   `json:"route"`
	Schemas      []string `json:"schemas"`
	Vectors      []string `json:"vectors"`
	Observations []string `json:"observations"`
	Faults       []string `json:"faults"`
}

type ClassCoverage struct {
	Class   string   `json:"class"`
	Sources []string `json:"sources"`
}

type DiscrepancyArtifact struct {
	Schema        string        `json:"schema"`
	Discrepancies []Discrepancy `json:"discrepancies"`
}
