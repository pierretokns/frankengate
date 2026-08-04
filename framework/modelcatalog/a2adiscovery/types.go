// Package a2adiscovery fetches and validates A2A Agent Cards using an
// SSRF-resistant, operator-scoped HTTP client.
package a2adiscovery

import "encoding/json"

const (
	SupportedProtocolVersion = "1.0.1"
	DefaultMaxResponseBytes  = 64 * 1024
	DefaultTimeoutMillis     = 5000
	DefaultMaxRedirects      = 3

	MaxExtensions          = 16
	MaxExtensionKeyBytes   = 96
	MaxExtensionValueBytes = 8 * 1024
	MaxExtensionTotalBytes = 32 * 1024

	MaxSkills          = 64
	MaxModalities      = 32
	MaxSecuritySchemes = 16
)

const (
	WellKnownAgentCardPath = "/.well-known/agent-card.json"
	LegacyAgentCardPath    = "/.well-known/agent.json"
)

type AgentCard struct {
	SchemaVersion                     string                     `json:"schemaVersion,omitempty"`
	ProtocolVersion                   string                     `json:"protocolVersion"`
	Name                              string                     `json:"name"`
	Description                       string                     `json:"description,omitempty"`
	URL                               string                     `json:"url"`
	PreferredTransport                TransportBinding           `json:"preferredTransport,omitempty"`
	AdditionalInterfaces              []AgentInterface           `json:"additionalInterfaces,omitempty"`
	Provider                          *AgentProvider             `json:"provider,omitempty"`
	Version                           string                     `json:"version"`
	Capabilities                      AgentCapabilities          `json:"capabilities,omitempty"`
	SecuritySchemes                   map[string]SecurityScheme  `json:"securitySchemes,omitempty"`
	Security                          []map[string][]string      `json:"security,omitempty"`
	DefaultInputModes                 []string                   `json:"defaultInputModes,omitempty"`
	DefaultOutputModes                []string                   `json:"defaultOutputModes,omitempty"`
	Skills                            []AgentSkill               `json:"skills"`
	SupportsAuthenticatedExtendedCard bool                       `json:"supportsAuthenticatedExtendedCard,omitempty"`
	Extensions                        map[string]json.RawMessage `json:"extensions,omitempty"`
}

type AgentProvider struct {
	Organization string `json:"organization,omitempty"`
	URL          string `json:"url,omitempty"`
}

type AgentCapabilities struct {
	Streaming              bool `json:"streaming,omitempty"`
	PushNotifications      bool `json:"pushNotifications,omitempty"`
	StateTransitionHistory bool `json:"stateTransitionHistory,omitempty"`
}

type TransportBinding string

const (
	TransportJSONRPC  TransportBinding = "JSONRPC"
	TransportHTTPJSON TransportBinding = "HTTP+JSON"
	TransportGRPC     TransportBinding = "GRPC"
)

type AgentInterface struct {
	URL       string           `json:"url"`
	Transport TransportBinding `json:"transport"`
}

type AgentSkill struct {
	ID          string                     `json:"id"`
	Name        string                     `json:"name"`
	Description string                     `json:"description,omitempty"`
	Tags        []string                   `json:"tags,omitempty"`
	Examples    []string                   `json:"examples,omitempty"`
	InputModes  []string                   `json:"inputModes,omitempty"`
	OutputModes []string                   `json:"outputModes,omitempty"`
	Extensions  map[string]json.RawMessage `json:"extensions,omitempty"`
}

type SecurityScheme struct {
	Type             string          `json:"type"`
	Description      string          `json:"description,omitempty"`
	Name             string          `json:"name,omitempty"`
	In               string          `json:"in,omitempty"`
	Scheme           string          `json:"scheme,omitempty"`
	BearerFormat     string          `json:"bearerFormat,omitempty"`
	OpenIDConnectURL string          `json:"openIdConnectUrl,omitempty"`
	Flows            json.RawMessage `json:"flows,omitempty"`
}

type FetchResult struct {
	URL  string
	Card *AgentCard
}
