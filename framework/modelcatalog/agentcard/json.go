package agentcard

import (
	"encoding/json"
	"fmt"
)

var catalogEntityKnownFields = map[string]struct{}{
	"schema_version": {},
	"kind":           {},
	"identity":       {},
	"version":        {},
	"digest":         {},
	"source":         {},
	"publisher":      {},
	"capabilities":   {},
	"provenance":     {},
	"relationships":  {},
	"extensions":     {},
}

var agentModelCardKnownFields = map[string]struct{}{
	"schema_version": {},
	"entity":         {},
	"narrative":      {},
	"interfaces":     {},
	"skills":         {},
	"security":       {},
	"signatures":     {},
	"pricing":        {},
	"evaluations":    {},
	"health":         {},
	"policy":         {},
	"extensions":     {},
}

func (e CatalogEntity) MarshalJSON() ([]byte, error) {
	type alias CatalogEntity
	data, err := json.Marshal(alias(e))
	if err != nil {
		return nil, err
	}
	return mergeUnknownFields(data, e.UnknownFields, catalogEntityKnownFields)
}

func (e *CatalogEntity) UnmarshalJSON(data []byte) error {
	if len(data) > MaxCatalogEntityJSONBytes {
		return fmt.Errorf("catalog entity exceeds %d bytes", MaxCatalogEntityJSONBytes)
	}
	type alias CatalogEntity
	var decoded alias
	if err := json.Unmarshal(data, &decoded); err != nil {
		return err
	}
	unknown, err := collectUnknownFields(data, catalogEntityKnownFields)
	if err != nil {
		return err
	}
	*e = CatalogEntity(decoded)
	e.UnknownFields = unknown
	return nil
}

func (c AgentModelCard) MarshalJSON() ([]byte, error) {
	type alias AgentModelCard
	data, err := json.Marshal(alias(c))
	if err != nil {
		return nil, err
	}
	return mergeUnknownFields(data, c.UnknownFields, agentModelCardKnownFields)
}

func (c *AgentModelCard) UnmarshalJSON(data []byte) error {
	if len(data) > MaxAgentModelCardJSONBytes {
		return fmt.Errorf("agent model card exceeds %d bytes", MaxAgentModelCardJSONBytes)
	}
	type alias AgentModelCard
	var decoded alias
	if err := json.Unmarshal(data, &decoded); err != nil {
		return err
	}
	unknown, err := collectUnknownFields(data, agentModelCardKnownFields)
	if err != nil {
		return err
	}
	*c = AgentModelCard(decoded)
	c.UnknownFields = unknown
	return nil
}

func collectUnknownFields(data []byte, known map[string]struct{}) (map[string]json.RawMessage, error) {
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}
	unknown := make(map[string]json.RawMessage)
	for key, value := range raw {
		if _, ok := known[key]; ok {
			continue
		}
		unknown[key] = append(json.RawMessage(nil), value...)
	}
	if len(unknown) == 0 {
		return nil, nil
	}
	if err := validateRawFields("unknown_fields", unknown, MaxUnknownFields, MaxUnknownFieldKeyBytes, MaxUnknownFieldBytes, MaxUnknownTotalBytes); err != nil {
		return nil, err
	}
	return unknown, nil
}

func mergeUnknownFields(data []byte, unknown map[string]json.RawMessage, known map[string]struct{}) ([]byte, error) {
	if len(unknown) == 0 {
		return data, nil
	}
	var merged map[string]json.RawMessage
	if err := json.Unmarshal(data, &merged); err != nil {
		return nil, err
	}
	for key, value := range unknown {
		if _, ok := known[key]; ok {
			continue
		}
		merged[key] = value
	}
	return json.Marshal(merged)
}
