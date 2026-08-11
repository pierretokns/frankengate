package a2adiscovery

import (
	"encoding/json"
	"fmt"
	"mime"
	"net/url"
	"strings"
	"unicode"
	"unicode/utf8"
)

const (
	SupportedSchemaVersion = "a2a.agent-card.v1"

	MaxNameBytes        = 256
	MaxDescriptionBytes = 8192
	MaxURLBytes         = 2048
	MaxVersionBytes     = 128
	MaxTagBytes         = 128
	MaxExampleBytes     = 2048
	MaxModeBytes        = 128
)

type ValidationErrors []string

func (e ValidationErrors) Error() string {
	return "a2a agent card validation failed: " + strings.Join(e, "; ")
}

func (e ValidationErrors) appendf(format string, args ...any) ValidationErrors {
	return append(e, fmt.Sprintf(format, args...))
}

func (e ValidationErrors) err() error {
	if len(e) == 0 {
		return nil
	}
	return e
}

func ValidateAgentCard(card *AgentCard, sourceURL *url.URL, httpsPolicy HTTPSPolicy) error {
	var errs ValidationErrors
	if card == nil {
		return ValidationErrors{"card is required"}
	}
	if sourceURL == nil {
		return ValidationErrors{"source url is required"}
	}
	if card.SchemaVersion != "" && card.SchemaVersion != SupportedSchemaVersion {
		errs = errs.appendf("schemaVersion must be %q when present", SupportedSchemaVersion)
	}
	if card.ProtocolVersion != "" && !IsSupportedProtocolVersion(card.ProtocolVersion) {
		errs = errs.appendf("protocolVersion must be %q, %q, or %q", SupportedProtocolVersion, LegacyProtocolVersion, ShortProtocolVersion)
	}
	errs = validateString(errs, "name", card.Name, true, MaxNameBytes)
	errs = validateString(errs, "description", card.Description, false, MaxDescriptionBytes)
	errs = validateString(errs, "version", card.Version, true, MaxVersionBytes)

	if card.URL != "" {
		endpoint, err := parseCardEndpoint(card.URL, "url")
		if err != nil {
			errs = append(errs, err.Error())
		} else {
			if httpsPolicy == HTTPSOnly && endpoint.Scheme != "https" {
				errs = errs.appendf("url must use https")
			}
			if !sameOrigin(endpoint, sourceURL) {
				errs = errs.appendf("url origin %q must match fetched card origin %q", origin(endpoint), origin(sourceURL))
			}
		}
	}

	if card.PreferredTransport != "" && !validTransportBinding(card.PreferredTransport) {
		errs = errs.appendf("preferredTransport is invalid")
	}
	interfaces := card.SupportedInterfaces
	if len(interfaces) == 0 {
		interfaces = append([]AgentInterface(nil), card.AdditionalInterfaces...)
		if card.URL != "" {
			interfaces = append([]AgentInterface{{URL: card.URL, Transport: card.PreferredTransport}}, interfaces...)
		}
	}
	if len(interfaces) == 0 {
		errs = errs.appendf("supportedInterfaces or url is required")
	}
	if card.ProtocolVersion == "" && len(card.SupportedInterfaces) == 0 {
		errs = errs.appendf("protocolVersion is required when supportedInterfaces is absent")
	}
	for i, iface := range interfaces {
		path := fmt.Sprintf("supportedInterfaces[%d]", i)
		binding := iface.ProtocolBinding
		if binding == "" {
			binding = iface.Transport
		}
		if !validTransportBinding(binding) {
			errs = errs.appendf("%s.protocolBinding is invalid", path)
		}
		if iface.ProtocolVersion != "" && !IsSupportedProtocolVersion(iface.ProtocolVersion) {
			errs = errs.appendf("%s.protocolVersion is unsupported", path)
		}
		ifaceURL, err := parseCardEndpoint(iface.URL, path+".url")
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		if httpsPolicy == HTTPSOnly && ifaceURL.Scheme != "https" {
			errs = errs.appendf("%s.url must use https", path)
		}
		if !sameOrigin(ifaceURL, sourceURL) {
			errs = errs.appendf("%s.url origin %q must match fetched card origin %q", path, origin(ifaceURL), origin(sourceURL))
		}
	}
	for i, iface := range card.AdditionalInterfaces {
		path := fmt.Sprintf("additionalInterfaces[%d]", i)
		if !validTransportBinding(iface.Transport) {
			errs = errs.appendf("%s.transport is invalid", path)
		}
		ifaceURL, err := parseCardEndpoint(iface.URL, path+".url")
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		if httpsPolicy == HTTPSOnly && ifaceURL.Scheme != "https" {
			errs = errs.appendf("%s.url must use https", path)
		}
		if !sameOrigin(ifaceURL, sourceURL) {
			errs = errs.appendf("%s.url origin %q must match fetched card origin %q", path, origin(ifaceURL), origin(sourceURL))
		}
	}

	errs = validateModes(errs, "defaultInputModes", card.DefaultInputModes)
	errs = validateModes(errs, "defaultOutputModes", card.DefaultOutputModes)
	if len(card.Skills) == 0 {
		errs = errs.appendf("skills must contain at least one skill")
	}
	if len(card.Skills) > MaxSkills {
		errs = errs.appendf("skills has %d items, max %d", len(card.Skills), MaxSkills)
	}
	for i, skill := range card.Skills {
		errs = validateSkill(errs, i, skill)
	}

	errs = validateSecuritySchemes(errs, card.SecuritySchemes)
	securityRequirements := card.Security
	if len(securityRequirements) == 0 {
		securityRequirements = card.SecurityRequirements
	}
	errs = validateSecurityRequirements(errs, "securityRequirements", securityRequirements, card.SecuritySchemes)
	if card.Provider != nil {
		errs = validateString(errs, "provider.organization", card.Provider.Organization, false, MaxNameBytes)
		errs = validateString(errs, "provider.url", card.Provider.URL, false, MaxURLBytes)
		if card.Provider.URL != "" {
			if parsed, err := url.Parse(card.Provider.URL); err != nil || parsed.Scheme == "" || parsed.Host == "" {
				errs = errs.appendf("provider.url must be absolute when present")
			}
		}
	}
	errs = validateExtensions(errs, "extensions", card.Extensions)
	return errs.err()
}

// IsSupportedProtocolVersion accepts the released version and the immediately
// preceding draft so operators can upgrade agents without a flag day.
func IsSupportedProtocolVersion(version string) bool {
	return version == SupportedProtocolVersion || version == LegacyProtocolVersion || version == ShortProtocolVersion
}

func validateSkill(errs ValidationErrors, index int, skill AgentSkill) ValidationErrors {
	path := fmt.Sprintf("skills[%d]", index)
	errs = validateString(errs, path+".id", skill.ID, true, MaxNameBytes)
	errs = validateString(errs, path+".name", skill.Name, true, MaxNameBytes)
	errs = validateString(errs, path+".description", skill.Description, false, MaxDescriptionBytes)
	for i, tag := range skill.Tags {
		errs = validateString(errs, fmt.Sprintf("%s.tags[%d]", path, i), tag, true, MaxTagBytes)
	}
	for i, example := range skill.Examples {
		errs = validateString(errs, fmt.Sprintf("%s.examples[%d]", path, i), example, true, MaxExampleBytes)
	}
	errs = validateModes(errs, path+".inputModes", skill.InputModes)
	errs = validateModes(errs, path+".outputModes", skill.OutputModes)
	errs = validateExtensions(errs, path+".extensions", skill.Extensions)
	return errs
}

func validateSecuritySchemes(errs ValidationErrors, schemes map[string]SecurityScheme) ValidationErrors {
	if len(schemes) > MaxSecuritySchemes {
		errs = errs.appendf("securitySchemes has %d entries, max %d", len(schemes), MaxSecuritySchemes)
	}
	for name, scheme := range schemes {
		path := "securitySchemes." + name
		errs = validateString(errs, path+".name", name, true, MaxNameBytes)
		switch scheme.Type {
		case "apiKey":
			errs = validateString(errs, path+".name", scheme.Name, true, MaxNameBytes)
			if scheme.In != "query" && scheme.In != "header" && scheme.In != "cookie" {
				errs = errs.appendf("%s.in must be query, header, or cookie", path)
			}
		case "http":
			errs = validateString(errs, path+".scheme", scheme.Scheme, true, MaxNameBytes)
		case "oauth2":
			if len(scheme.Flows) == 0 || !json.Valid(scheme.Flows) {
				errs = errs.appendf("%s.flows must be valid JSON for oauth2", path)
			}
		case "openIdConnect":
			errs = validateString(errs, path+".openIdConnectUrl", scheme.OpenIDConnectURL, true, MaxURLBytes)
			if parsed, err := url.Parse(scheme.OpenIDConnectURL); err != nil || parsed.Scheme == "" || parsed.Host == "" {
				errs = errs.appendf("%s.openIdConnectUrl must be absolute", path)
			}
		case "mutualTLS":
		default:
			errs = errs.appendf("%s.type is invalid", path)
		}
		errs = validateString(errs, path+".description", scheme.Description, false, MaxDescriptionBytes)
		if len(scheme.Flows) > 0 && len(scheme.Flows) > MaxExtensionValueBytes {
			errs = errs.appendf("%s.flows exceeds %d bytes", path, MaxExtensionValueBytes)
		}
	}
	return errs
}

func validateSecurityRequirements(errs ValidationErrors, path string, requirements []map[string][]string, schemes map[string]SecurityScheme) ValidationErrors {
	for i, requirement := range requirements {
		for name, scopes := range requirement {
			if _, ok := schemes[name]; !ok {
				errs = errs.appendf("%s[%d] references unknown security scheme %q", path, i, name)
			}
			for j, scope := range scopes {
				errs = validateString(errs, fmt.Sprintf("%s[%d].%s[%d]", path, i, name, j), scope, false, MaxNameBytes)
			}
		}
	}
	return errs
}

func validateModes(errs ValidationErrors, path string, modes []string) ValidationErrors {
	if len(modes) > MaxModalities {
		errs = errs.appendf("%s has %d items, max %d", path, len(modes), MaxModalities)
	}
	for i, mode := range modes {
		field := fmt.Sprintf("%s[%d]", path, i)
		errs = validateString(errs, field, mode, true, MaxModeBytes)
		if mode != "" && !validModality(mode) {
			errs = errs.appendf("%s is not a recognized modality or media type", field)
		}
	}
	return errs
}

func validateExtensions(errs ValidationErrors, path string, fields map[string]json.RawMessage) ValidationErrors {
	if len(fields) > MaxExtensions {
		return errs.appendf("%s has %d fields, max %d", path, len(fields), MaxExtensions)
	}
	total := 0
	for key, value := range fields {
		if key == "" {
			errs = errs.appendf("%s contains an empty key", path)
			continue
		}
		if len(key) > MaxExtensionKeyBytes {
			errs = errs.appendf("%s key %q exceeds %d bytes", path, key, MaxExtensionKeyBytes)
		}
		if !json.Valid(value) {
			errs = errs.appendf("%s.%s must be valid JSON", path, key)
		}
		if len(value) > MaxExtensionValueBytes {
			errs = errs.appendf("%s.%s exceeds %d bytes", path, key, MaxExtensionValueBytes)
		}
		total += len(key) + len(value)
	}
	if total > MaxExtensionTotalBytes {
		errs = errs.appendf("%s exceeds %d total bytes", path, MaxExtensionTotalBytes)
	}
	return errs
}

func parseCardEndpoint(rawURL, path string) (*url.URL, error) {
	if rawURL == "" {
		return nil, fmt.Errorf("%s is required", path)
	}
	if len(rawURL) > MaxURLBytes {
		return nil, fmt.Errorf("%s exceeds %d bytes", path, MaxURLBytes)
	}
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return nil, fmt.Errorf("%s is invalid: %w", path, err)
	}
	if parsed.Scheme != "https" && parsed.Scheme != "http" {
		return nil, fmt.Errorf("%s scheme must be http or https", path)
	}
	if parsed.Host == "" {
		return nil, fmt.Errorf("%s host is required", path)
	}
	if parsed.User != nil {
		return nil, fmt.Errorf("%s must not contain userinfo", path)
	}
	if parsed.Fragment != "" {
		return nil, fmt.Errorf("%s must not contain a fragment", path)
	}
	return parsed, nil
}

func validateString(errs ValidationErrors, path, value string, required bool, maxBytes int) ValidationErrors {
	if value == "" {
		if required {
			return errs.appendf("%s is required", path)
		}
		return errs
	}
	if !utf8.ValidString(value) {
		errs = errs.appendf("%s must be valid utf-8", path)
	}
	if len(value) > maxBytes {
		errs = errs.appendf("%s exceeds %d bytes", path, maxBytes)
	}
	for _, r := range value {
		if unicode.IsControl(r) && r != '\n' && r != '\r' && r != '\t' {
			errs = errs.appendf("%s contains control characters", path)
			break
		}
	}
	return errs
}

func validTransportBinding(value TransportBinding) bool {
	switch value {
	case TransportJSONRPC, TransportHTTPJSON, TransportGRPC:
		return true
	default:
		return false
	}
}

func validModality(value string) bool {
	switch value {
	case "text", "image", "audio", "video", "file", "data":
		return true
	}
	mediaType, _, err := mime.ParseMediaType(value)
	return err == nil && strings.Contains(mediaType, "/") && !strings.Contains(mediaType, "*")
}

func origin(u *url.URL) string {
	if u == nil {
		return ""
	}
	return u.Scheme + "://" + normalizeHost(u.Hostname()) + ":" + effectivePort(u)
}
