package inbound

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/url"
	"slices"
	"strings"

	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
)

// GenerateAgentCard converts an internal card/workflow record into the A2A
// Agent Card wire shape. It canonicalizes all repeated declaration surfaces so
// equivalent records serialize identically.
func GenerateAgentCard(record Record) (a2adiscovery.AgentCard, error) {
	interfaces, err := orderedInterfaces(record.Card.Interfaces)
	if err != nil {
		return a2adiscovery.AgentCard{}, err
	}
	skills, err := orderedSkills(record.Workflows)
	if err != nil {
		return a2adiscovery.AgentCard{}, err
	}
	securitySchemes, err := keyedSecuritySchemes(record.Card.SecuritySchemes)
	if err != nil {
		return a2adiscovery.AgentCard{}, err
	}
	security, err := orderedSecurity(record.Card.Security, securitySchemes)
	if err != nil {
		return a2adiscovery.AgentCard{}, err
	}

	card := a2adiscovery.AgentCard{
		SchemaVersion:                     a2adiscovery.SupportedSchemaVersion,
		ProtocolVersion:                   a2adiscovery.SupportedProtocolVersion,
		Name:                              strings.TrimSpace(record.Card.Name),
		Description:                       strings.TrimSpace(record.Card.Description),
		URL:                               interfaces[0].URL,
		PreferredTransport:                interfaces[0].Transport,
		Provider:                          cloneProvider(record.Card.Provider),
		Version:                           strings.TrimSpace(record.Card.Version),
		Capabilities:                      record.Card.Capabilities,
		SecuritySchemes:                   securitySchemes,
		Security:                          security,
		DefaultInputModes:                 dedupeSortedStrings(record.Card.DefaultInputModes),
		DefaultOutputModes:                dedupeSortedStrings(record.Card.DefaultOutputModes),
		Skills:                            skills,
		SupportsAuthenticatedExtendedCard: record.Card.SupportsAuthenticatedExtendedCard,
		Extensions:                        cloneRawMap(record.Card.Extensions),
	}
	if len(interfaces) > 1 {
		card.AdditionalInterfaces = make([]a2adiscovery.AgentInterface, 0, len(interfaces)-1)
		for _, iface := range interfaces[1:] {
			card.AdditionalInterfaces = append(card.AdditionalInterfaces, a2adiscovery.AgentInterface{
				URL:       iface.URL,
				Transport: iface.Transport,
			})
		}
	}
	if err := validateGeneratedCard(card); err != nil {
		return a2adiscovery.AgentCard{}, err
	}
	return card, nil
}

func MarshalAgentCardJSON(record Record) ([]byte, error) {
	card, err := GenerateAgentCard(record)
	if err != nil {
		return nil, err
	}
	return json.Marshal(card)
}

func orderedInterfaces(in []InterfaceRecord) ([]InterfaceRecord, error) {
	if len(in) == 0 {
		return nil, fmt.Errorf("card.interfaces must contain at least one interface")
	}
	out := make([]InterfaceRecord, len(in))
	copy(out, in)
	for i := range out {
		out[i].URL = strings.TrimSpace(out[i].URL)
		if out[i].URL == "" {
			return nil, fmt.Errorf("card.interfaces[%d].url is required", i)
		}
		if out[i].Transport == "" {
			return nil, fmt.Errorf("card.interfaces[%d].transport is required", i)
		}
	}
	slices.SortStableFunc(out, func(a, b InterfaceRecord) int {
		if a.Order != b.Order {
			return compareInt(a.Order, b.Order)
		}
		if a.Transport != b.Transport {
			return strings.Compare(string(a.Transport), string(b.Transport))
		}
		return strings.Compare(a.URL, b.URL)
	})
	return out, nil
}

func orderedSkills(in []WorkflowRecord) ([]a2adiscovery.AgentSkill, error) {
	if len(in) == 0 {
		return nil, fmt.Errorf("workflows must contain at least one workflow")
	}
	workflows := make([]WorkflowRecord, len(in))
	copy(workflows, in)
	slices.SortStableFunc(workflows, func(a, b WorkflowRecord) int {
		if a.Order != b.Order {
			return compareInt(a.Order, b.Order)
		}
		if a.ID != b.ID {
			return strings.Compare(a.ID, b.ID)
		}
		return strings.Compare(a.Name, b.Name)
	})

	seen := make(map[string]struct{}, len(workflows))
	out := make([]a2adiscovery.AgentSkill, 0, len(workflows))
	for i, workflow := range workflows {
		id := strings.TrimSpace(workflow.ID)
		if id == "" {
			return nil, fmt.Errorf("workflows[%d].id is required", i)
		}
		if _, exists := seen[id]; exists {
			return nil, fmt.Errorf("workflow id %q is declared more than once", id)
		}
		seen[id] = struct{}{}
		out = append(out, a2adiscovery.AgentSkill{
			ID:          id,
			Name:        strings.TrimSpace(workflow.Name),
			Description: strings.TrimSpace(workflow.Description),
			Tags:        dedupeSortedStrings(workflow.Tags),
			Examples:    cloneStrings(workflow.Examples),
			InputModes:  dedupeSortedStrings(workflow.InputModes),
			OutputModes: dedupeSortedStrings(workflow.OutputModes),
			Extensions:  cloneRawMap(workflow.Extensions),
		})
	}
	return out, nil
}

func keyedSecuritySchemes(in []SecuritySchemeRecord) (map[string]a2adiscovery.SecurityScheme, error) {
	if len(in) == 0 {
		return nil, nil
	}
	records := make([]SecuritySchemeRecord, len(in))
	copy(records, in)
	slices.SortStableFunc(records, func(a, b SecuritySchemeRecord) int {
		if a.Order != b.Order {
			return compareInt(a.Order, b.Order)
		}
		return strings.Compare(a.ID, b.ID)
	})
	out := make(map[string]a2adiscovery.SecurityScheme, len(records))
	for i, record := range records {
		id := strings.TrimSpace(record.ID)
		if id == "" {
			return nil, fmt.Errorf("card.security_schemes[%d].id is required", i)
		}
		if _, exists := out[id]; exists {
			return nil, fmt.Errorf("security scheme %q is declared more than once", id)
		}
		record.Scheme.Description = strings.TrimSpace(record.Scheme.Description)
		record.Scheme.Name = strings.TrimSpace(record.Scheme.Name)
		record.Scheme.In = strings.TrimSpace(record.Scheme.In)
		record.Scheme.Scheme = strings.TrimSpace(record.Scheme.Scheme)
		record.Scheme.BearerFormat = strings.TrimSpace(record.Scheme.BearerFormat)
		record.Scheme.OpenIDConnectURL = strings.TrimSpace(record.Scheme.OpenIDConnectURL)
		if len(record.Scheme.Flows) > 0 {
			record.Scheme.Flows = append(json.RawMessage(nil), record.Scheme.Flows...)
		}
		out[id] = record.Scheme
	}
	return out, nil
}

func orderedSecurity(in []SecurityRequirementRecord, schemes map[string]a2adiscovery.SecurityScheme) ([]map[string][]string, error) {
	if len(in) == 0 {
		return nil, nil
	}
	requirements := make([]SecurityRequirementRecord, len(in))
	copy(requirements, in)
	slices.SortStableFunc(requirements, func(a, b SecurityRequirementRecord) int {
		if a.Order != b.Order {
			return compareInt(a.Order, b.Order)
		}
		return strings.Compare(firstSecuritySchemeID(a), firstSecuritySchemeID(b))
	})

	out := make([]map[string][]string, 0, len(requirements))
	for i, requirement := range requirements {
		schemeRefs := make([]SecurityRequirementScheme, len(requirement.Schemes))
		copy(schemeRefs, requirement.Schemes)
		if len(schemeRefs) == 0 {
			return nil, fmt.Errorf("card.security[%d].schemes must contain at least one scheme", i)
		}
		slices.SortStableFunc(schemeRefs, func(a, b SecurityRequirementScheme) int {
			if a.Order != b.Order {
				return compareInt(a.Order, b.Order)
			}
			return strings.Compare(a.ID, b.ID)
		})
		item := make(map[string][]string, len(schemeRefs))
		for j, scheme := range schemeRefs {
			id := strings.TrimSpace(scheme.ID)
			if id == "" {
				return nil, fmt.Errorf("card.security[%d].schemes[%d].id is required", i, j)
			}
			if _, ok := schemes[id]; !ok {
				return nil, fmt.Errorf("card.security[%d] references unknown security scheme %q", i, id)
			}
			if _, exists := item[id]; exists {
				return nil, fmt.Errorf("card.security[%d] references security scheme %q more than once", i, id)
			}
			scopes := dedupeSortedStrings(scheme.Scopes)
			if scopes == nil {
				scopes = []string{}
			}
			item[id] = scopes
		}
		out = append(out, item)
	}
	return out, nil
}

func validateGeneratedCard(card a2adiscovery.AgentCard) error {
	sourceURL, err := url.Parse(card.URL)
	if err != nil {
		return err
	}
	if err := a2adiscovery.ValidateAgentCard(&card, sourceURL, a2adiscovery.HTTPSOnly); err != nil {
		return err
	}
	return nil
}

func firstSecuritySchemeID(requirement SecurityRequirementRecord) string {
	if len(requirement.Schemes) == 0 {
		return ""
	}
	schemes := make([]SecurityRequirementScheme, len(requirement.Schemes))
	copy(schemes, requirement.Schemes)
	slices.SortStableFunc(schemes, func(a, b SecurityRequirementScheme) int {
		if a.Order != b.Order {
			return compareInt(a.Order, b.Order)
		}
		return strings.Compare(a.ID, b.ID)
	})
	return schemes[0].ID
}

func cloneProvider(in *a2adiscovery.AgentProvider) *a2adiscovery.AgentProvider {
	if in == nil {
		return nil
	}
	out := *in
	out.Organization = strings.TrimSpace(out.Organization)
	out.URL = strings.TrimSpace(out.URL)
	return &out
}

func cloneRawMap(in map[string]json.RawMessage) map[string]json.RawMessage {
	if len(in) == 0 {
		return nil
	}
	out := make(map[string]json.RawMessage, len(in))
	for key, value := range in {
		out[key] = append(json.RawMessage(nil), bytes.TrimSpace(value)...)
	}
	return out
}

func cloneStrings(in []string) []string {
	if len(in) == 0 {
		return nil
	}
	out := make([]string, 0, len(in))
	for _, value := range in {
		value = strings.TrimSpace(value)
		if value != "" {
			out = append(out, value)
		}
	}
	return out
}

func dedupeSortedStrings(in []string) []string {
	if len(in) == 0 {
		return nil
	}
	out := cloneStrings(in)
	slices.Sort(out)
	out = slices.Compact(out)
	if len(out) == 0 {
		return nil
	}
	return out
}

func compareInt(a, b int) int {
	if a < b {
		return -1
	}
	if a > b {
		return 1
	}
	return 0
}
