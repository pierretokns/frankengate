package agentcard

import (
	"bytes"
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestCatalogEntityKindsValidate(t *testing.T) {
	kinds := []EntityKind{
		EntityKindModel,
		EntityKindA2AAgent,
		EntityKindA2ACapability,
		EntityKindMCPServer,
		EntityKindMCPTool,
		EntityKindProceduralSkill,
	}
	for _, kind := range kinds {
		entity := testEntity(kind)
		if err := entity.Validate(); err != nil {
			t.Fatalf("%s should validate: %v", kind, err)
		}
	}
}

func TestProvenanceStatusesValidate(t *testing.T) {
	statuses := []ProvenanceStatus{
		ProvenanceVerified,
		ProvenanceSelfReported,
		ProvenanceInferred,
		ProvenanceStale,
		ProvenanceUnknown,
		ProvenanceQuarantined,
	}
	for _, status := range statuses {
		card := testCard(EntityKindA2AAgent)
		card.Entity.Provenance.Status = status
		card.Evaluations = []EvaluationEvidence{{Name: "smoke", Status: status}}
		if err := card.Validate(); err != nil {
			t.Fatalf("%s should validate: %v", status, err)
		}
	}
}

func TestAgentModelCardRoundTripPreservesUnknownFields(t *testing.T) {
	payload := []byte(`{
		"schema_version":"bifrost.agent_model_card.v1",
		"entity":{
			"schema_version":"bifrost.agent_model_card.v1",
			"kind":"MCP_TOOL",
			"identity":{"id":"mcp.tool.search","namespace":"mcp/demo","name":"search"},
			"version":{"version":"2026-08-04"},
			"digest":{"algorithm":"sha256","value":"abc123"},
			"source":{"type":"mcp_library","uri":"https://example.test/mcp/search"},
			"publisher":{"name":"Example"},
			"capabilities":{
				"modalities":["text","tool"],
				"operations":["mcp_tool"],
				"limits":{"payload_bytes":4096,"timeout_millis":5000}
			},
			"provenance":{"status":"verified","confidence":0.91},
			"relationships":[{"type":"hosted_by","target_kind":"MCP_SERVER","target_id":"mcp.server.demo"}],
			"extensions":{"com.example.entity":{"tier":"beta"}},
			"x-entity-field":{"kept":true}
		},
		"narrative":{"display_name":"Search Tool","summary":"Searches a bounded corpus."},
		"interfaces":[{"type":"mcp","protocol_version":"2025-06-18","operations":["mcp_tool"]}],
		"security":[{"type":"api_key"}],
		"evaluations":[{"name":"tool schema smoke","status":"verified","score":1}],
		"health":{"status":"healthy","latency_p50_millis":12},
		"policy":{"license":"MIT"},
		"extensions":{"com.example.card":{"admission":"preview"}},
		"x-card-field":["kept"]
	}`)

	var card AgentModelCard
	if err := json.Unmarshal(payload, &card); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if _, ok := card.UnknownFields["x-card-field"]; !ok {
		t.Fatalf("card unknown field was not preserved")
	}
	if _, ok := card.Entity.UnknownFields["x-entity-field"]; !ok {
		t.Fatalf("entity unknown field was not preserved")
	}
	if err := card.Validate(); err != nil {
		t.Fatalf("validate: %v", err)
	}

	encoded, err := json.Marshal(card)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if !bytes.Contains(encoded, []byte(`"x-card-field"`)) {
		t.Fatalf("encoded card lost top-level unknown field: %s", encoded)
	}
	if !bytes.Contains(encoded, []byte(`"x-entity-field"`)) {
		t.Fatalf("encoded card lost entity unknown field: %s", encoded)
	}

	var roundTrip AgentModelCard
	if err := json.Unmarshal(encoded, &roundTrip); err != nil {
		t.Fatalf("round trip unmarshal: %v", err)
	}
	if string(roundTrip.UnknownFields["x-card-field"]) != `["kept"]` {
		t.Fatalf("unexpected card unknown field: %s", roundTrip.UnknownFields["x-card-field"])
	}
	if string(roundTrip.Entity.UnknownFields["x-entity-field"]) != `{"kept":true}` {
		t.Fatalf("unexpected entity unknown field: %s", roundTrip.Entity.UnknownFields["x-entity-field"])
	}
}

func TestMarshalIsDeterministic(t *testing.T) {
	card := testCard(EntityKindModel)
	card.Entity.Identity.Labels = map[string]string{"z": "last", "a": "first"}
	card.Extensions = ExtensionData{
		"z.example": json.RawMessage(`{"z":true}`),
		"a.example": json.RawMessage(`{"a":true}`),
	}
	card.UnknownFields = map[string]json.RawMessage{
		"x-z": json.RawMessage(`{"z":1}`),
		"x-a": json.RawMessage(`{"a":1}`),
	}

	first, err := json.Marshal(card)
	if err != nil {
		t.Fatalf("first marshal: %v", err)
	}
	second, err := json.Marshal(card)
	if err != nil {
		t.Fatalf("second marshal: %v", err)
	}
	if !bytes.Equal(first, second) {
		t.Fatalf("marshal output is not deterministic:\n%s\n%s", first, second)
	}
}

func TestValidationRejectsInvalidContractsAndUnboundedExtensions(t *testing.T) {
	invalid := testCard(EntityKindModel)
	invalid.SchemaVersion = "old"
	invalid.Entity.Kind = EntityKind("BAD_KIND")
	invalid.Entity.Capabilities.Limits.ContextTokens = -1
	invalid.Extensions = ExtensionData{"broken": json.RawMessage(`{`)}
	err := invalid.Validate()
	if err == nil {
		t.Fatalf("expected invalid card to fail validation")
	}
	message := err.Error()
	for _, fragment := range []string{"schema_version", "kind", "context_tokens", "valid JSON"} {
		if !strings.Contains(message, fragment) {
			t.Fatalf("expected validation error to contain %q, got %q", fragment, message)
		}
	}

	oversized := testCard(EntityKindModel)
	oversized.Extensions = ExtensionData{
		"too_big": json.RawMessage(`"` + strings.Repeat("a", MaxExtensionValueBytes+1) + `"`),
	}
	err = oversized.Validate()
	if err == nil || !strings.Contains(err.Error(), "too_big exceeds") {
		t.Fatalf("expected oversized extension failure, got %v", err)
	}
}

func TestJSONSchemaFixtureMatchesExportedConstants(t *testing.T) {
	data, err := os.ReadFile("testdata/agentmodelcard.schema.json")
	if err != nil {
		t.Fatalf("read schema fixture: %v", err)
	}
	if !json.Valid(data) {
		t.Fatalf("schema fixture is not valid JSON")
	}
	if !bytes.Contains(data, []byte(`"$id": "`+JSONSchemaID+`"`)) {
		t.Fatalf("schema fixture does not contain JSONSchemaID %q", JSONSchemaID)
	}
	if !bytes.Contains(data, []byte(`"const": "`+SchemaVersion+`"`)) {
		t.Fatalf("schema fixture does not contain SchemaVersion %q", SchemaVersion)
	}
}

func testCard(kind EntityKind) AgentModelCard {
	amount := 0.000001
	score := 0.99
	return AgentModelCard{
		SchemaVersion: SchemaVersion,
		Entity:        testEntity(kind),
		Narrative: Narrative{
			DisplayName: "Test card",
			Summary:     "A compact test card.",
		},
		Interfaces: []Interface{{
			Type:       InterfaceHTTP,
			URL:        "https://example.test",
			Operations: []Operation{OperationChat},
		}},
		Skills: []Skill{{
			ID:               "skill.test",
			Name:             "Test skill",
			InputModalities:  []Modality{ModalityText},
			OutputModalities: []Modality{ModalityText},
			Operations:       []Operation{OperationSkillExecute},
		}},
		Security: []SecurityScheme{{Type: "api_key"}},
		Pricing:  []PricingEntry{{Unit: "input_token", Currency: "USD", Amount: &amount}},
		Evaluations: []EvaluationEvidence{{
			Name:   "smoke",
			Status: ProvenanceVerified,
			Score:  &score,
		}},
		Health: &Health{Status: HealthHealthy},
		Policy: &Policy{License: "MIT"},
	}
}

func testEntity(kind EntityKind) CatalogEntity {
	return CatalogEntity{
		SchemaVersion: SchemaVersion,
		Kind:          kind,
		Identity: Identity{
			ID:        "entity.test",
			Namespace: "test",
			Name:      "test entity",
			Provider:  "test-provider",
		},
		Version: VersionInfo{Version: "2026-08-04"},
		Digest:  &Digest{Algorithm: "sha256", Value: "abc123"},
		Source: Source{
			Type: SourceUser,
			URI:  "https://example.test/catalog/entity.test",
		},
		Publisher: Publisher{Name: "Example"},
		Capabilities: CapabilitySet{
			Modalities: []Modality{ModalityText},
			Operations: []Operation{OperationChat},
			Limits:     Limits{ContextTokens: 128000, MaxOutputTokens: 4096},
		},
		Provenance: Provenance{Status: ProvenanceVerified},
	}
}
