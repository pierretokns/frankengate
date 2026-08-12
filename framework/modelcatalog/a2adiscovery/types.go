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
		Schemes map[string]json.RawMessage `json:"schemes"`
	}
	if err := json.Unmarshal(wire.SecurityRequirements, &wrapped); err != nil {
		return fmt.Errorf("decode securityRequirements: %w", err)
	}
	c.SecurityRequirements = make([]map[string][]string, 0, len(wrapped))
	for _, requirement := range wrapped {
		flatRequirement := make(map[string][]string, len(requirement.Schemes))
		for id, rawScopes := range requirement.Schemes {
			var scopes []string
			if err := json.Unmarshal(rawScopes, &scopes); err != nil {
				var object struct {
					List []string `json:"list"`
				}
				if objectErr := json.Unmarshal(rawScopes, &object); objectErr != nil {
					return fmt.Errorf("decode securityRequirements scheme %q: %w", id, err)
				}
				scopes = object.List
			}
			flatRequirement[id] = append([]string(nil), scopes...)
		}
		c.SecurityRequirements = append(c.SecurityRequirements, flatRequirement)
	}
	return nil
}

// MarshalJSON emits only the released A2A 1.0 AgentCard fields. The internal
// model retains legacy aliases so older cards can still be decoded and mapped,
// but publishing those aliases makes a v1.0 card fail strict validators.
func (c AgentCard) MarshalJSON() ([]byte, error) {
	type released struct {
		Name                 string                        `json:"name"`
		Description          string                        `json:"description,omitempty"`
		SupportedInterfaces  []AgentInterface              `json:"supportedInterfaces"`
		Provider             *AgentProvider                `json:"provider,omitempty"`
		Version              string                        `json:"version"`
		DocumentationURL     string                        `json:"documentationUrl,omitempty"`
		Capabilities         AgentCapabilities             `json:"capabilities"`
		SecuritySchemes      map[string]SecurityScheme     `json:"securitySchemes,omitempty"`
		SecurityRequirements []releasedSecurityRequirement `json:"securityRequirements,omitempty"`
		DefaultInputModes    []string                      `json:"defaultInputModes"`
		DefaultOutputModes   []string                      `json:"defaultOutputModes"`
		Skills               []AgentSkill                  `json:"skills"`
		IconURL              string                        `json:"iconUrl,omitempty"`
	}
	interfaces := append([]AgentInterface(nil), c.SupportedInterfaces...)
	if len(interfaces) == 0 && strings.TrimSpace(c.URL) != "" {
		protocolVersion := c.ProtocolVersion
		if protocolVersion == "" {
			protocolVersion = ShortProtocolVersion
		}
		interfaces = append(interfaces, AgentInterface{URL: c.URL, ProtocolBinding: c.PreferredTransport, ProtocolVersion: protocolVersion})
		for _, legacy := range c.AdditionalInterfaces {
			binding := legacy.ProtocolBinding
			if binding == "" {
				binding = legacy.Transport
			}
			interfaces = append(interfaces, AgentInterface{URL: legacy.URL, ProtocolBinding: binding, ProtocolVersion: protocolVersion})
		}
	}
	requirements := c.SecurityRequirements
	if len(requirements) == 0 {
		requirements = c.Security
	}
	capabilities := c.Capabilities
	if c.SupportsAuthenticatedExtendedCard {
		capabilities.ExtendedAgentCard = true
	}
	wrappedRequirements := make([]releasedSecurityRequirement, 0, len(requirements))
	for _, requirement := range requirements {
		wrapped := releasedSecurityRequirement{Schemes: make(map[string][]string, len(requirement))}
		for scheme, scopes := range requirement {
			if scopes == nil {
				scopes = []string{}
			}
			wrapped.Schemes[scheme] = append([]string{}, scopes...)
		}
		wrappedRequirements = append(wrappedRequirements, wrapped)
	}
	return json.Marshal(released{
		Name:                 c.Name,
		Description:          c.Description,
		SupportedInterfaces:  interfaces,
		Provider:             c.Provider,
		Version:              c.Version,
		DocumentationURL:     c.DocumentationURL,
		Capabilities:         capabilities,
		SecuritySchemes:      c.SecuritySchemes,
		SecurityRequirements: wrappedRequirements,
		DefaultInputModes:    c.DefaultInputModes,
		DefaultOutputModes:   c.DefaultOutputModes,
		Skills:               c.Skills,
		IconURL:              c.IconURL,
	})
}

type releasedSecurityRequirement struct {
	Schemes map[string][]string `json:"schemes"`
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

// MarshalJSON omits the pre-1.0 stateTransitionHistory alias. v1.0 uses the
// task history itself and does not declare that legacy capability bit.
func (c AgentCapabilities) MarshalJSON() ([]byte, error) {
	type released struct {
		Streaming         bool `json:"streaming,omitempty"`
		PushNotifications bool `json:"pushNotifications,omitempty"`
		ExtendedAgentCard bool `json:"extendedAgentCard,omitempty"`
	}
	return json.Marshal(released{
		Streaming:         c.Streaming,
		PushNotifications: c.PushNotifications,
		ExtendedAgentCard: c.ExtendedAgentCard,
	})
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

// MarshalJSON emits the released A2A 1.0 interface vocabulary when the
// protocolBinding field is present, while retaining the legacy transport-only
// shape for additionalInterfaces during the migration window. Emitting both
// vocabularies makes a released Agent Card fail the official schema.
func (i AgentInterface) MarshalJSON() ([]byte, error) {
	type released struct {
		URL             string           `json:"url"`
		ProtocolBinding TransportBinding `json:"protocolBinding"`
		ProtocolVersion string           `json:"protocolVersion,omitempty"`
	}
	type legacy struct {
		URL       string           `json:"url"`
		Transport TransportBinding `json:"transport"`
	}
	if i.ProtocolBinding != "" {
		return json.Marshal(released{URL: i.URL, ProtocolBinding: i.ProtocolBinding, ProtocolVersion: i.ProtocolVersion})
	}
	return json.Marshal(legacy{URL: i.URL, Transport: i.Transport})
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

// MarshalJSON emits the released A2A 1.0 oneof wrapper vocabulary. The
// decoder above remains liberal for legacy flat cards, but official Go/TS
// SDKs use the released discriminated form and reject a flat {type:http}
// security scheme.
func (s SecurityScheme) MarshalJSON() ([]byte, error) {
	type fields struct {
		Description      string          `json:"description,omitempty"`
		Name             string          `json:"name,omitempty"`
		Location         string          `json:"location,omitempty"`
		Scheme           string          `json:"scheme,omitempty"`
		BearerFormat     string          `json:"bearerFormat,omitempty"`
		OpenIDConnectURL string          `json:"openIdConnectUrl,omitempty"`
		Flows            json.RawMessage `json:"flows,omitempty"`
	}
	f := fields{Description: s.Description, Name: s.Name, Location: s.In, Scheme: s.Scheme, BearerFormat: s.BearerFormat, OpenIDConnectURL: s.OpenIDConnectURL, Flows: s.Flows}
	key := ""
	switch s.Type {
	case "apiKey":
		key = "apiKeySecurityScheme"
	case "http":
		key = "httpAuthSecurityScheme"
	case "oauth2":
		key = "oauth2SecurityScheme"
	case "openIdConnect":
		key = "openIdConnectSecurityScheme"
	case "mutualTLS":
		key = "mtlsSecurityScheme"
	default:
		return json.Marshal(struct {
			Type string `json:"type"`
		}{Type: s.Type})
	}
	return json.Marshal(map[string]fields{key: f})
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
			Location         string          `json:"location,omitempty"`
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
		s.In = nested.Location
		if s.In == "" {
			s.In = nested.In
		}
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
