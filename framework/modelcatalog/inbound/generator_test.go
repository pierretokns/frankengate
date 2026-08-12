package inbound

import (
	"bytes"
	"encoding/json"
	"net/url"
	"slices"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
)

func TestGenerateAgentCardCanonicalizesOrderedSections(t *testing.T) {
	record := testRecord()
	card, err := GenerateAgentCard(record)
	if err != nil {
		t.Fatalf("generate card: %v", err)
	}
	if card.URL != "https://agent.example/a2a/rpc" || card.PreferredTransport != a2adiscovery.TransportJSONRPC {
		t.Fatalf("preferred interface = %s/%s", card.URL, card.PreferredTransport)
	}
	wantInterfaces := []a2adiscovery.AgentInterface{
		{URL: "https://agent.example/a2a/http", Transport: a2adiscovery.TransportHTTPJSON},
		{URL: "https://agent.example/a2a/grpc", Transport: a2adiscovery.TransportGRPC},
	}
	if !slices.Equal(card.AdditionalInterfaces, wantInterfaces) {
		t.Fatalf("additional interfaces = %#v, want %#v", card.AdditionalInterfaces, wantInterfaces)
	}
	if len(card.SupportedInterfaces) != 3 || card.SupportedInterfaces[0].ProtocolBinding != a2adiscovery.TransportJSONRPC || card.SupportedInterfaces[0].ProtocolVersion != "1.0" {
		t.Fatalf("supported interfaces = %#v", card.SupportedInterfaces)
	}
	if got := []string{card.Skills[0].ID, card.Skills[1].ID}; !slices.Equal(got, []string{"triage", "research"}) {
		t.Fatalf("skills ordered by workflow record = %v", got)
	}
	if !slices.Equal(card.Skills[0].Tags, []string{"handoff", "triage"}) {
		t.Fatalf("skill tags = %v", card.Skills[0].Tags)
	}
	if !slices.Equal(card.Skills[0].InputModes, []string{"application/json", "text"}) {
		t.Fatalf("skill input modes = %v", card.Skills[0].InputModes)
	}
	if !slices.Equal(card.Security[0]["api_key"], []string{}) {
		t.Fatalf("api key scopes = %#v", card.Security[0]["api_key"])
	}
	if !slices.Equal(card.Security[1]["bearer"], []string{"agent:read", "agent:write"}) {
		t.Fatalf("bearer scopes = %#v", card.Security[1]["bearer"])
	}
	if err := a2adiscovery.ValidateAgentCard(&card, mustURL(t, card.URL), a2adiscovery.HTTPSOnly); err != nil {
		t.Fatalf("generated card should validate: %v", err)
	}
	if record.Card.Interfaces[0].URL != "https://agent.example/a2a/grpc" {
		t.Fatalf("input record was mutated: %#v", record.Card.Interfaces)
	}
}

func TestMarshalAgentCardJSONIsDeterministic(t *testing.T) {
	record := testRecord()
	first, err := MarshalAgentCardJSON(record)
	if err != nil {
		t.Fatalf("first marshal: %v", err)
	}
	second, err := MarshalAgentCardJSON(record)
	if err != nil {
		t.Fatalf("second marshal: %v", err)
	}
	if !bytes.Equal(first, second) {
		t.Fatalf("expected deterministic JSON:\n%s\n%s", first, second)
	}

	expected := compactJSON(t, `{
		"schemaVersion":"a2a.agent-card.v1",
		"protocolVersion":"1.0.0",
		"name":"FrankenGate Research Agent",
		"description":"Delegates approved internal research workflows.",
		"url":"https://agent.example/a2a/rpc",
		"preferredTransport":"JSONRPC",
		"additionalInterfaces":[
			{"url":"https://agent.example/a2a/http","transport":"HTTP+JSON"},
			{"url":"https://agent.example/a2a/grpc","transport":"GRPC"}
		],
		"supportedInterfaces":[
			{"url":"https://agent.example/a2a/rpc","protocolBinding":"JSONRPC","protocolVersion":"1.0"},
			{"url":"https://agent.example/a2a/http","protocolBinding":"HTTP+JSON","protocolVersion":"1.0"},
			{"url":"https://agent.example/a2a/grpc","protocolBinding":"GRPC","protocolVersion":"1.0"}
		],
		"provider":{"organization":"FrankenGate","url":"https://agent.example"},
		"version":"2026.08.04",
		"capabilities":{"streaming":true,"stateTransitionHistory":true,"extendedAgentCard":true},
		"securitySchemes":{
			"api_key":{"type":"apiKey","description":"gateway virtual key","name":"x-bf-vk","in":"header"},
			"bearer":{"type":"http","description":"audience-bound inbound task token","scheme":"bearer","bearerFormat":"JWT"}
		},
		"security":[{"api_key":[]},{"bearer":["agent:read","agent:write"]}],
		"defaultInputModes":["application/json","text"],
		"defaultOutputModes":["application/json","text"],
		"skills":[
			{
				"id":"triage",
				"name":"Triage",
				"description":"Classifies and routes approved task intake.",
				"tags":["handoff","triage"],
				"examples":["Classify this support issue","Prepare a handoff summary"],
				"inputModes":["application/json","text"],
				"outputModes":["application/json","text"],
				"extensions":{"com.frankengate.workflow":{"version":"v3"}}
			},
			{
				"id":"research",
				"name":"Research",
				"description":"Runs a bounded research workflow.",
				"tags":["analysis","research"],
				"inputModes":["text"],
				"outputModes":["application/json"],
				"extensions":{"com.frankengate.workflow":{"version":"v2"}}
			}
		],
		"supportsAuthenticatedExtendedCard":true,
		"extensions":{"com.frankengate.card":{"visibility":"internal"}},
		"securityRequirements":[{"schemes":{"api_key":{"list":[]}}},{"schemes":{"bearer":{"list":["agent:read","agent:write"]}}}]
	}`)
	if string(first) != expected {
		t.Fatalf("unexpected canonical JSON:\n%s\nwant:\n%s", first, expected)
	}
}

func TestGenerateAgentCardRejectsInvalidRecords(t *testing.T) {
	tests := []struct {
		name    string
		mutate  func(*Record)
		wantErr string
	}{
		{
			name:    "missing interface",
			mutate:  func(r *Record) { r.Card.Interfaces = nil },
			wantErr: "interfaces",
		},
		{
			name:    "missing workflow",
			mutate:  func(r *Record) { r.Workflows = nil },
			wantErr: "workflows",
		},
		{
			name: "duplicate workflow id",
			mutate: func(r *Record) {
				r.Workflows[1].ID = r.Workflows[0].ID
			},
			wantErr: "declared more than once",
		},
		{
			name: "unknown security scheme",
			mutate: func(r *Record) {
				r.Card.Security[0].Schemes[0].ID = "missing"
			},
			wantErr: "unknown security scheme",
		},
		{
			name: "cross origin interface",
			mutate: func(r *Record) {
				r.Card.Interfaces[0].URL = "https://other.example/a2a/grpc"
			},
			wantErr: "must match fetched card origin",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			record := testRecord()
			tt.mutate(&record)
			_, err := GenerateAgentCard(record)
			if err == nil || !strings.Contains(err.Error(), tt.wantErr) {
				t.Fatalf("expected %q error, got %v", tt.wantErr, err)
			}
		})
	}
}

func testRecord() Record {
	return Record{
		Card: CardRecord{
			Name:        " FrankenGate Research Agent ",
			Description: " Delegates approved internal research workflows. ",
			Version:     " 2026.08.04 ",
			Provider: &a2adiscovery.AgentProvider{
				Organization: " FrankenGate ",
				URL:          " https://agent.example ",
			},
			Interfaces: []InterfaceRecord{
				{Order: 30, URL: "https://agent.example/a2a/grpc", Transport: a2adiscovery.TransportGRPC},
				{Order: 10, URL: "https://agent.example/a2a/rpc", Transport: a2adiscovery.TransportJSONRPC},
				{Order: 20, URL: "https://agent.example/a2a/http", Transport: a2adiscovery.TransportHTTPJSON},
			},
			Capabilities: a2adiscovery.AgentCapabilities{
				Streaming:              true,
				StateTransitionHistory: true,
			},
			DefaultInputModes:  []string{"text", "application/json", "text"},
			DefaultOutputModes: []string{"text", "application/json"},
			SecuritySchemes: []SecuritySchemeRecord{
				{
					Order: 20,
					ID:    "bearer",
					Scheme: a2adiscovery.SecurityScheme{
						Type:         "http",
						Description:  " audience-bound inbound task token ",
						Scheme:       " bearer ",
						BearerFormat: " JWT ",
					},
				},
				{
					Order: 10,
					ID:    "api_key",
					Scheme: a2adiscovery.SecurityScheme{
						Type:        "apiKey",
						Description: " gateway virtual key ",
						Name:        " x-bf-vk ",
						In:          " header ",
					},
				},
			},
			Security: []SecurityRequirementRecord{
				{Order: 20, Schemes: []SecurityRequirementScheme{{ID: "bearer", Scopes: []string{"agent:write", "agent:read", "agent:read"}}}},
				{Order: 10, Schemes: []SecurityRequirementScheme{{ID: "api_key"}}},
			},
			SupportsAuthenticatedExtendedCard: true,
			Extensions: map[string]json.RawMessage{
				"com.frankengate.card": json.RawMessage(` { "visibility" : "internal" } `),
			},
		},
		Workflows: []WorkflowRecord{
			{
				Order:       20,
				ID:          "research",
				Name:        "Research",
				Description: "Runs a bounded research workflow.",
				Tags:        []string{"research", "analysis", "analysis"},
				InputModes:  []string{"text"},
				OutputModes: []string{"application/json"},
				Extensions: map[string]json.RawMessage{
					"com.frankengate.workflow": json.RawMessage(`{"version":"v2"}`),
				},
			},
			{
				Order:       10,
				ID:          "triage",
				Name:        " Triage ",
				Description: " Classifies and routes approved task intake. ",
				Tags:        []string{"triage", "handoff", "triage"},
				Examples:    []string{" Classify this support issue ", "Prepare a handoff summary"},
				InputModes:  []string{"text", "application/json", "text"},
				OutputModes: []string{"application/json", "text"},
				Extensions: map[string]json.RawMessage{
					"com.frankengate.workflow": json.RawMessage(`{"version":"v3"}`),
				},
			},
		},
	}
}

func compactJSON(t *testing.T, raw string) string {
	t.Helper()
	var buf bytes.Buffer
	if err := json.Compact(&buf, []byte(raw)); err != nil {
		t.Fatalf("compact expected JSON: %v", err)
	}
	return buf.String()
}

func mustURL(t *testing.T, raw string) *url.URL {
	t.Helper()
	parsed, err := url.Parse(raw)
	if err != nil {
		t.Fatalf("parse url: %v", err)
	}
	return parsed
}
