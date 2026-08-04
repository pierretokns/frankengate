// Package agentcard defines the stable, bounded contract used to describe
// catalog entities that can participate in model, agent, MCP, and skill
// discovery flows.
package agentcard

import "encoding/json"

const (
	// SchemaVersion is the current Agent Model Card wire contract version.
	SchemaVersion = "bifrost.agent_model_card.v1"

	// JSONSchemaID is the canonical identifier for the JSON Schema fixture
	// shipped with this package.
	JSONSchemaID = "https://schemas.maxim.ai/bifrost/agent-model-card/v1/schema.json"

	// MaxAgentModelCardJSONBytes bounds a single serialized card payload.
	MaxAgentModelCardJSONBytes = 256 * 1024

	// MaxCatalogEntityJSONBytes bounds a standalone serialized entity payload.
	MaxCatalogEntityJSONBytes = 128 * 1024

	MaxExtensions           = 16
	MaxExtensionKeyBytes    = 96
	MaxExtensionValueBytes  = 8 * 1024
	MaxExtensionTotalBytes  = 32 * 1024
	MaxUnknownFields        = 32
	MaxUnknownFieldKeyBytes = 96
	MaxUnknownFieldBytes    = 8 * 1024
	MaxUnknownTotalBytes    = 32 * 1024
)

type EntityKind string

const (
	EntityKindModel           EntityKind = "MODEL"
	EntityKindA2AAgent        EntityKind = "A2A_AGENT"
	EntityKindA2ACapability   EntityKind = "A2A_CAPABILITY"
	EntityKindMCPServer       EntityKind = "MCP_SERVER"
	EntityKindMCPTool         EntityKind = "MCP_TOOL"
	EntityKindProceduralSkill EntityKind = "PROCEDURAL_SKILL"
)

type ProvenanceStatus string

const (
	ProvenanceVerified     ProvenanceStatus = "verified"
	ProvenanceSelfReported ProvenanceStatus = "self-reported"
	ProvenanceInferred     ProvenanceStatus = "inferred"
	ProvenanceStale        ProvenanceStatus = "stale"
	ProvenanceUnknown      ProvenanceStatus = "unknown"
	ProvenanceQuarantined  ProvenanceStatus = "quarantined"
)

type SourceType string

const (
	SourceProviderAPI SourceType = "provider_api"
	SourceA2ACard     SourceType = "a2a_card"
	SourceMCPLibrary  SourceType = "mcp_library"
	SourceUser        SourceType = "user"
	SourceBenchmark   SourceType = "benchmark"
	SourceImport      SourceType = "import"
)

type Modality string

const (
	ModalityText      Modality = "text"
	ModalityImage     Modality = "image"
	ModalityAudio     Modality = "audio"
	ModalityVideo     Modality = "video"
	ModalityEmbedding Modality = "embedding"
	ModalityFile      Modality = "file"
	ModalityTool      Modality = "tool"
	ModalityCode      Modality = "code"
)

type Operation string

const (
	OperationChat            Operation = "chat"
	OperationResponses       Operation = "responses"
	OperationTextCompletion  Operation = "text_completion"
	OperationEmbedding       Operation = "embedding"
	OperationImageGeneration Operation = "image_generation"
	OperationImageEdit       Operation = "image_edit"
	OperationImageVariation  Operation = "image_variation"
	OperationSpeech          Operation = "speech"
	OperationTranscription   Operation = "transcription"
	OperationToolCall        Operation = "tool_call"
	OperationMCPTool         Operation = "mcp_tool"
	OperationA2AMessage      Operation = "a2a_message"
	OperationA2ATask         Operation = "a2a_task"
	OperationSkillExecute    Operation = "skill_execute"
	OperationTokenCount      Operation = "token_count"
)

type RelationshipType string

const (
	RelationshipProvides    RelationshipType = "provides"
	RelationshipRequires    RelationshipType = "requires"
	RelationshipHostedBy    RelationshipType = "hosted_by"
	RelationshipExposes     RelationshipType = "exposes"
	RelationshipImplements  RelationshipType = "implements"
	RelationshipEquivalent  RelationshipType = "equivalent_to"
	RelationshipSupersedes  RelationshipType = "supersedes"
	RelationshipDerivedFrom RelationshipType = "derived_from"
)

type InterfaceType string

const (
	InterfaceOpenAICompatible InterfaceType = "openai_compatible"
	InterfaceA2A              InterfaceType = "a2a"
	InterfaceMCP              InterfaceType = "mcp"
	InterfaceHTTP             InterfaceType = "http"
)

type HealthStatus string

const (
	HealthUnknown  HealthStatus = "unknown"
	HealthHealthy  HealthStatus = "healthy"
	HealthDegraded HealthStatus = "degraded"
	HealthDown     HealthStatus = "down"
)

// ExtensionData is intentionally bounded by Validate. Store large bodies,
// traces, transcripts, and evaluation artifacts behind ContentRef values
// instead of embedding them here.
type ExtensionData map[string]json.RawMessage

type CatalogEntity struct {
	SchemaVersion string                     `json:"schema_version"`
	Kind          EntityKind                 `json:"kind"`
	Identity      Identity                   `json:"identity"`
	Version       VersionInfo                `json:"version"`
	Digest        *Digest                    `json:"digest,omitempty"`
	Source        Source                     `json:"source"`
	Publisher     Publisher                  `json:"publisher"`
	Capabilities  CapabilitySet              `json:"capabilities,omitempty"`
	Provenance    Provenance                 `json:"provenance"`
	Relationships []Relationship             `json:"relationships,omitempty"`
	Extensions    ExtensionData              `json:"extensions,omitempty"`
	UnknownFields map[string]json.RawMessage `json:"-"`
}

type AgentModelCard struct {
	SchemaVersion string                     `json:"schema_version"`
	Entity        CatalogEntity              `json:"entity"`
	Narrative     Narrative                  `json:"narrative,omitempty"`
	Interfaces    []Interface                `json:"interfaces,omitempty"`
	Skills        []Skill                    `json:"skills,omitempty"`
	Security      []SecurityScheme           `json:"security,omitempty"`
	Signatures    []Signature                `json:"signatures,omitempty"`
	Pricing       []PricingEntry             `json:"pricing,omitempty"`
	Evaluations   []EvaluationEvidence       `json:"evaluations,omitempty"`
	Health        *Health                    `json:"health,omitempty"`
	Policy        *Policy                    `json:"policy,omitempty"`
	Extensions    ExtensionData              `json:"extensions,omitempty"`
	UnknownFields map[string]json.RawMessage `json:"-"`
}

type Identity struct {
	ID        string            `json:"id"`
	Namespace string            `json:"namespace,omitempty"`
	Name      string            `json:"name"`
	Provider  string            `json:"provider,omitempty"`
	Labels    map[string]string `json:"labels,omitempty"`
}

type VersionInfo struct {
	Version    string `json:"version"`
	Revision   string `json:"revision,omitempty"`
	ReleasedAt string `json:"released_at,omitempty"`
	UpdatedAt  string `json:"updated_at,omitempty"`
}

type Digest struct {
	Algorithm string `json:"algorithm"`
	Value     string `json:"value"`
}

type Source struct {
	Type        SourceType `json:"type"`
	URI         string     `json:"uri,omitempty"`
	RetrievedAt string     `json:"retrieved_at,omitempty"`
	ETag        string     `json:"etag,omitempty"`
	Digest      *Digest    `json:"digest,omitempty"`
}

type Publisher struct {
	Name    string `json:"name"`
	URL     string `json:"url,omitempty"`
	Contact string `json:"contact,omitempty"`
}

type CapabilitySet struct {
	Modalities []Modality  `json:"modalities,omitempty"`
	Operations []Operation `json:"operations,omitempty"`
	Features   []string    `json:"features,omitempty"`
	Limits     Limits      `json:"limits,omitempty"`
}

type Limits struct {
	ContextTokens     int64 `json:"context_tokens,omitempty"`
	MaxInputTokens    int64 `json:"max_input_tokens,omitempty"`
	MaxOutputTokens   int64 `json:"max_output_tokens,omitempty"`
	MaxToolCalls      int64 `json:"max_tool_calls,omitempty"`
	RequestsPerMinute int64 `json:"requests_per_minute,omitempty"`
	TokensPerMinute   int64 `json:"tokens_per_minute,omitempty"`
	PayloadBytes      int64 `json:"payload_bytes,omitempty"`
	TimeoutMillis     int64 `json:"timeout_millis,omitempty"`
}

type Provenance struct {
	Status     ProvenanceStatus `json:"status"`
	Method     string           `json:"method,omitempty"`
	ObservedAt string           `json:"observed_at,omitempty"`
	Confidence *float64         `json:"confidence,omitempty"`
	Evidence   []ContentRef     `json:"evidence,omitempty"`
}

type Relationship struct {
	Type       RelationshipType `json:"type"`
	TargetKind EntityKind       `json:"target_kind"`
	TargetID   string           `json:"target_id"`
	Status     ProvenanceStatus `json:"status,omitempty"`
}

type Narrative struct {
	DisplayName string      `json:"display_name,omitempty"`
	Summary     string      `json:"summary,omitempty"`
	Description string      `json:"description,omitempty"`
	DetailsRef  *ContentRef `json:"details_ref,omitempty"`
}

type Interface struct {
	Type            InterfaceType `json:"type"`
	URL             string        `json:"url,omitempty"`
	ProtocolVersion string        `json:"protocol_version,omitempty"`
	Operations      []Operation   `json:"operations,omitempty"`
}

type Skill struct {
	ID               string      `json:"id"`
	Name             string      `json:"name"`
	Description      string      `json:"description,omitempty"`
	InputModalities  []Modality  `json:"input_modalities,omitempty"`
	OutputModalities []Modality  `json:"output_modalities,omitempty"`
	Operations       []Operation `json:"operations,omitempty"`
	Limits           Limits      `json:"limits,omitempty"`
}

type SecurityScheme struct {
	Type        string   `json:"type"`
	Description string   `json:"description,omitempty"`
	Scopes      []string `json:"scopes,omitempty"`
}

type Signature struct {
	KeyID     string `json:"key_id"`
	Algorithm string `json:"algorithm"`
	Digest    Digest `json:"digest"`
	Value     string `json:"value"`
	SignedAt  string `json:"signed_at,omitempty"`
}

type PricingEntry struct {
	Unit       string   `json:"unit"`
	Currency   string   `json:"currency,omitempty"`
	Amount     *float64 `json:"amount,omitempty"`
	InputRate  *float64 `json:"input_rate,omitempty"`
	OutputRate *float64 `json:"output_rate,omitempty"`
}

type EvaluationEvidence struct {
	Name            string            `json:"name"`
	Metric          string            `json:"metric,omitempty"`
	Score           *float64          `json:"score,omitempty"`
	Status          ProvenanceStatus  `json:"status"`
	DatasetRef      *ContentRef       `json:"dataset_ref,omitempty"`
	DatasetRevision string            `json:"dataset_revision,omitempty"`
	ReportRef       *ContentRef       `json:"report_ref,omitempty"`
	Methodology     string            `json:"methodology,omitempty"`
	Source          *ContentRef       `json:"source,omitempty"`
	Verifier        string            `json:"verifier,omitempty"`
	Confidence      *float64          `json:"confidence,omitempty"`
	RunRevision     string            `json:"run_revision,omitempty"`
	Reproducible    *bool             `json:"reproducible,omitempty"`
	Slice           map[string]string `json:"slice,omitempty"`
	ObservedAt      string            `json:"observed_at,omitempty"`
	Stale           bool              `json:"stale,omitempty"`
}

type Health struct {
	Status           HealthStatus `json:"status"`
	LastCheckedAt    string       `json:"last_checked_at,omitempty"`
	LatencyP50Millis int64        `json:"latency_p50_millis,omitempty"`
	LatencyP95Millis int64        `json:"latency_p95_millis,omitempty"`
	ErrorRate        *float64     `json:"error_rate,omitempty"`
}

type Policy struct {
	License           string   `json:"license,omitempty"`
	TermsURL          string   `json:"terms_url,omitempty"`
	DataRetention     string   `json:"data_retention,omitempty"`
	UsageRestrictions []string `json:"usage_restrictions,omitempty"`
	Safety            []string `json:"safety,omitempty"`
}

type ContentRef struct {
	URI       string  `json:"uri"`
	Digest    *Digest `json:"digest,omitempty"`
	MediaType string  `json:"media_type,omitempty"`
	Bytes     int64   `json:"bytes,omitempty"`
}
