// Package a2adiscovery fetches and validates A2A Agent Cards using an
// SSRF-resistant, operator-scoped HTTP client.
package a2adiscovery

import (
	"encoding/json"
	"fmt"
	"strings"
)

const (
	// SupportedProtocolVersion is the current released A2A version. 1.0.1 was
	// used by an earlier draft and remains accepted for inbound compatibility.
	SupportedProtocolVersion = "1.0.0"
	LegacyProtocolVersion    = "1.0.1"
	ShortProtocolVersion     = "1.0"
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
	SchemaVersion        string           `json:"schemaVersion,omitempty"`
	ProtocolVersion      string           `json:"protocolVersion"`
	Name                 string           `json:"name"`
	Description          string           `json:"description,omitempty"`
	URL                  string           `json:"url"`
	PreferredTransport   TransportBinding `json:"preferredTransport,omitempty"`
	AdditionalInterfaces []AgentInterface `json:"additionalInterfaces,omitempty"`
	// SupportedInterfaces is the released A2A 1.0 vocabulary. The legacy URL,
	// preferredTransport, and additionalInterfaces fields remain populated for
	// older clients and are accepted during migration.
	SupportedInterfaces               []AgentInterface           `json:"supportedInterfaces,omitempty"`
	IconURL                           string                     `json:"iconUrl,omitempty"`
	DocumentationURL                  string                     `json:"documentationUrl,omitempty"`
	Provider                          *AgentProvider             `json:"provider,omitempty"`
	Version                           string                     `json:"version"`
	Capabilities                      AgentCapabilities          `json:"capabilities,omitempty"`
	SecuritySchemes                   map[string]SecurityScheme  `json:"securitySchemes,omitempty"`
	Security                          []map[string][]string      `json:"security,omitempty"`
	SecurityRequirements              []map[string][]string      `json:"securityRequirements,omitempty"`
	DefaultInputModes                 []string                   `json:"defaultInputModes,omitempty"`
	DefaultOutputModes                []string                   `json:"defaultOutputModes,omitempty"`
	Skills                            []AgentSkill               `json:"skills"`
	SupportsAuthenticatedExtendedCard bool                       `json:"supportsAuthenticatedExtendedCard,omitempty"`
	Extensions                        map[string]json.RawMessage `json:"extensions,omitempty"`
}

// UnmarshalJSON accepts both the early flat requirement form and the
// released protobuf/ProtoJSON wrapper form:
// [{"bearer":["scope"]}] and
// [{"schemes":{"bearer":{"list":["scope"]}}}].
func (c *AgentCard) UnmarshalJSON(data []byte) error {
	type alias AgentCard
	var wire struct {
		*alias
		SecurityRequirements json.RawMessage `json:"securityRequirements"`
	}
	*c = AgentCard{}
	wire.alias = (*alias)(c)
	if err := json.Unmarshal(data, &wire); err != nil {
		return err
	}
	if len(wire.SecurityRequirements) == 0 || string(wire.SecurityRequirements) == "null" {
		return nil
	}
	var flat []map[string][]string
	if err := json.Unmarshal(wire.SecurityRequirements, &flat); err == nil {
		c.SecurityRequirements = flat
		return nil
	}
	var wrapped []struct {
		Schemes map[string]struct {
			List []string `json:"list"`
		} `json:"schemes"`
	}
	if err := json.Unmarshal(wire.SecurityRequirements, &wrapped); err != nil {
		return fmt.Errorf("decode securityRequirements: %w", err)
	}
	c.SecurityRequirements = make([]map[string][]string, 0, len(wrapped))
	for _, requirement := range wrapped {
		flatRequirement := make(map[string][]string, len(requirement.Schemes))
		for id, scheme := range requirement.Schemes {
			flatRequirement[id] = append([]string(nil), scheme.List...)
		}
		c.SecurityRequirements = append(c.SecurityRequirements, flatRequirement)
	}
	return nil
}

// MarshalJSON emits the released wrapper form for securityRequirements while
// retaining the legacy flat security field for clients in the migration
// window. Internally the gateway keeps requirements in the compact flat form
// so policy and credential selection do not need protocol-specific branches.
func (c AgentCard) MarshalJSON() ([]byte, error) {
	type alias AgentCard
	type wrappedScheme struct {
		List []string `json:"list"`
	}
	type wrappedRequirement struct {
		Schemes map[string]wrappedScheme `json:"schemes"`
	}
	wrapped := make([]wrappedRequirement, 0, len(c.SecurityRequirements))
	for _, requirement := range c.SecurityRequirements {
		schemes := make(map[string]wrappedScheme, len(requirement))
		for id, scopes := range requirement {
			list := append([]string{}, scopes...)
			schemes[id] = wrappedScheme{List: list}
		}
		wrapped = append(wrapped, wrappedRequirement{Schemes: schemes})
	}
	return json.Marshal(struct {
		*alias
		SecurityRequirements []wrappedRequirement `json:"securityRequirements,omitempty"`
	}{alias: (*alias)(&c), SecurityRequirements: wrapped})
}

type AgentProvider struct {
	Organization string `json:"organization,omitempty"`
	URL          string `json:"url,omitempty"`
}

type AgentCapabilities struct {
	Streaming              bool `json:"streaming,omitempty"`
	PushNotifications      bool `json:"pushNotifications,omitempty"`
	StateTransitionHistory bool `json:"stateTransitionHistory,omitempty"`
	ExtendedAgentCard      bool `json:"extendedAgentCard,omitempty"`
}

type TransportBinding string

const (
	TransportJSONRPC  TransportBinding = "JSONRPC"
	TransportHTTPJSON TransportBinding = "HTTP+JSON"
	TransportGRPC     TransportBinding = "GRPC"
)

type AgentInterface struct {
	URL             string           `json:"url"`
	Transport       TransportBinding `json:"transport,omitempty"`
	ProtocolBinding TransportBinding `json:"protocolBinding,omitempty"`
	ProtocolVersion string           `json:"protocolVersion,omitempty"`
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

// UnmarshalJSON accepts both the early flat security-scheme shape and the
// released A2A 1.0 wrapper objects (httpAuthSecurityScheme,
// oauth2SecurityScheme, openIdConnectSecurityScheme, and so on).
func (s *SecurityScheme) UnmarshalJSON(data []byte) error {
	type alias SecurityScheme
	var flat alias
	if err := json.Unmarshal(data, &flat); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return err
	}
	*s = SecurityScheme(flat)
	for key, typ := range map[string]string{
		"apiKeySecurityScheme":        "apiKey",
		"httpAuthSecurityScheme":      "http",
		"oauth2SecurityScheme":        "oauth2",
		"openIdConnectSecurityScheme": "openIdConnect",
		"mtlsSecurityScheme":          "mutualTLS",
	} {
		raw, ok := fields[key]
		if !ok {
			continue
		}
		var nested struct {
			Description      string          `json:"description,omitempty"`
			Name             string          `json:"name,omitempty"`
			In               string          `json:"in,omitempty"`
			Scheme           string          `json:"scheme,omitempty"`
			BearerFormat     string          `json:"bearerFormat,omitempty"`
			OpenIDConnectURL string          `json:"openIdConnectUrl,omitempty"`
			Flows            json.RawMessage `json:"flows,omitempty"`
		}
		if err := json.Unmarshal(raw, &nested); err != nil {
			return err
		}
		s.Type = typ
		s.Description = nested.Description
		s.Name = nested.Name
		s.In = nested.In
		s.Scheme = nested.Scheme
		s.BearerFormat = nested.BearerFormat
		s.OpenIDConnectURL = nested.OpenIDConnectURL
		s.Flows = nested.Flows
		return nil
	}
	// A few early producers used wrapper names with different casing. Do not
	// accept arbitrary keys; normalize only the known suffixes.
	for key := range fields {
		if strings.EqualFold(key, "openIdConnectSecurityScheme") {
			var nested struct {
				OpenIDConnectURL string `json:"openIdConnectUrl"`
			}
			if err := json.Unmarshal(fields[key], &nested); err != nil {
				return err
			}
			s.Type, s.OpenIDConnectURL = "openIdConnect", nested.OpenIDConnectURL
			return nil
		}
	}
	return nil
}

type FetchResult struct {
	URL  string
	Card *AgentCard
}
