package agentcard

import (
	"encoding/json"
	"fmt"
	"strings"
)

type ValidationErrors []string

func (e ValidationErrors) Error() string {
	return "agent model card validation failed: " + strings.Join(e, "; ")
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

func (e CatalogEntity) Validate() error {
	var errs ValidationErrors
	errs = validateCatalogEntity(e, "entity", errs)
	if len(e.UnknownFields) > 0 {
		errs = appendRawFieldErrors(errs, "entity.unknown_fields", e.UnknownFields, MaxUnknownFields, MaxUnknownFieldKeyBytes, MaxUnknownFieldBytes, MaxUnknownTotalBytes)
	}
	if err := validatePayloadSize("entity", e, MaxCatalogEntityJSONBytes); err != nil {
		errs = append(errs, err.Error())
	}
	return errs.err()
}

func (c AgentModelCard) Validate() error {
	var errs ValidationErrors
	if c.SchemaVersion != SchemaVersion {
		errs = errs.appendf("schema_version must be %q", SchemaVersion)
	}
	errs = validateCatalogEntity(c.Entity, "entity", errs)
	for i, iface := range c.Interfaces {
		if !validInterfaceType(iface.Type) {
			errs = errs.appendf("interfaces[%d].type is invalid", i)
		}
		errs = appendOperationErrors(errs, fmt.Sprintf("interfaces[%d].operations", i), iface.Operations)
	}
	for i, skill := range c.Skills {
		if skill.ID == "" {
			errs = errs.appendf("skills[%d].id is required", i)
		}
		if skill.Name == "" {
			errs = errs.appendf("skills[%d].name is required", i)
		}
		errs = appendModalityErrors(errs, fmt.Sprintf("skills[%d].input_modalities", i), skill.InputModalities)
		errs = appendModalityErrors(errs, fmt.Sprintf("skills[%d].output_modalities", i), skill.OutputModalities)
		errs = appendOperationErrors(errs, fmt.Sprintf("skills[%d].operations", i), skill.Operations)
		errs = validateLimits(skill.Limits, fmt.Sprintf("skills[%d].limits", i), errs)
	}
	for i, signature := range c.Signatures {
		if signature.KeyID == "" {
			errs = errs.appendf("signatures[%d].key_id is required", i)
		}
		if signature.Algorithm == "" {
			errs = errs.appendf("signatures[%d].algorithm is required", i)
		}
		errs = validateDigest(signature.Digest, fmt.Sprintf("signatures[%d].digest", i), errs)
		if signature.Value == "" {
			errs = errs.appendf("signatures[%d].value is required", i)
		}
	}
	for i, price := range c.Pricing {
		if price.Unit == "" {
			errs = errs.appendf("pricing[%d].unit is required", i)
		}
		if price.Amount != nil && *price.Amount < 0 {
			errs = errs.appendf("pricing[%d].amount must be non-negative", i)
		}
		if price.InputRate != nil && *price.InputRate < 0 {
			errs = errs.appendf("pricing[%d].input_rate must be non-negative", i)
		}
		if price.OutputRate != nil && *price.OutputRate < 0 {
			errs = errs.appendf("pricing[%d].output_rate must be non-negative", i)
		}
	}
	for i, evaluation := range c.Evaluations {
		if evaluation.Name == "" {
			errs = errs.appendf("evaluations[%d].name is required", i)
		}
		if !validProvenanceStatus(evaluation.Status) {
			errs = errs.appendf("evaluations[%d].status is invalid", i)
		}
		if evaluation.Score != nil && (*evaluation.Score < 0 || *evaluation.Score > 1) {
			errs = errs.appendf("evaluations[%d].score must be between 0 and 1", i)
		}
		if evaluation.Confidence != nil && (*evaluation.Confidence < 0 || *evaluation.Confidence > 1) {
			errs = errs.appendf("evaluations[%d].confidence must be between 0 and 1", i)
		}
		errs = validateContentRef(evaluation.DatasetRef, fmt.Sprintf("evaluations[%d].dataset_ref", i), errs)
		errs = validateContentRef(evaluation.ReportRef, fmt.Sprintf("evaluations[%d].report_ref", i), errs)
		errs = validateContentRef(evaluation.Source, fmt.Sprintf("evaluations[%d].source", i), errs)
		if len(evaluation.Slice) > 32 {
			errs = errs.appendf("evaluations[%d].slice must contain at most 32 entries", i)
		}
		for key, value := range evaluation.Slice {
			if key == "" || len(key) > 96 {
				errs = errs.appendf("evaluations[%d].slice contains an invalid key", i)
			}
			if len(value) > 256 {
				errs = errs.appendf("evaluations[%d].slice[%q] exceeds 256 bytes", i, key)
			}
		}
	}
	if c.Health != nil {
		if !validHealthStatus(c.Health.Status) {
			errs = errs.appendf("health.status is invalid")
		}
		if c.Health.LatencyP50Millis < 0 {
			errs = errs.appendf("health.latency_p50_millis must be non-negative")
		}
		if c.Health.LatencyP95Millis < 0 {
			errs = errs.appendf("health.latency_p95_millis must be non-negative")
		}
		if c.Health.ErrorRate != nil && (*c.Health.ErrorRate < 0 || *c.Health.ErrorRate > 1) {
			errs = errs.appendf("health.error_rate must be between 0 and 1")
		}
	}
	if len(c.Extensions) > 0 {
		errs = appendRawFieldErrors(errs, "extensions", c.Extensions, MaxExtensions, MaxExtensionKeyBytes, MaxExtensionValueBytes, MaxExtensionTotalBytes)
	}
	if len(c.UnknownFields) > 0 {
		errs = appendRawFieldErrors(errs, "unknown_fields", c.UnknownFields, MaxUnknownFields, MaxUnknownFieldKeyBytes, MaxUnknownFieldBytes, MaxUnknownTotalBytes)
	}
	if err := validatePayloadSize("agent_model_card", c, MaxAgentModelCardJSONBytes); err != nil {
		errs = append(errs, err.Error())
	}
	return errs.err()
}

func validateCatalogEntity(e CatalogEntity, prefix string, errs ValidationErrors) ValidationErrors {
	if e.SchemaVersion != SchemaVersion {
		errs = errs.appendf("%s.schema_version must be %q", prefix, SchemaVersion)
	}
	if !validEntityKind(e.Kind) {
		errs = errs.appendf("%s.kind is invalid", prefix)
	}
	if e.Identity.ID == "" {
		errs = errs.appendf("%s.identity.id is required", prefix)
	}
	if e.Identity.Name == "" {
		errs = errs.appendf("%s.identity.name is required", prefix)
	}
	if e.Version.Version == "" {
		errs = errs.appendf("%s.version.version is required", prefix)
	}
	if e.Digest != nil {
		errs = validateDigest(*e.Digest, prefix+".digest", errs)
	}
	if !validSourceType(e.Source.Type) {
		errs = errs.appendf("%s.source.type is invalid", prefix)
	}
	if e.Source.Digest != nil {
		errs = validateDigest(*e.Source.Digest, prefix+".source.digest", errs)
	}
	if e.Publisher.Name == "" {
		errs = errs.appendf("%s.publisher.name is required", prefix)
	}
	errs = appendModalityErrors(errs, prefix+".capabilities.modalities", e.Capabilities.Modalities)
	errs = appendOperationErrors(errs, prefix+".capabilities.operations", e.Capabilities.Operations)
	errs = validateLimits(e.Capabilities.Limits, prefix+".capabilities.limits", errs)
	errs = validateProvenance(e.Provenance, prefix+".provenance", errs)
	for i, relationship := range e.Relationships {
		path := fmt.Sprintf("%s.relationships[%d]", prefix, i)
		if !validRelationshipType(relationship.Type) {
			errs = errs.appendf("%s.type is invalid", path)
		}
		if !validEntityKind(relationship.TargetKind) {
			errs = errs.appendf("%s.target_kind is invalid", path)
		}
		if relationship.TargetID == "" {
			errs = errs.appendf("%s.target_id is required", path)
		}
		if relationship.Status != "" && !validProvenanceStatus(relationship.Status) {
			errs = errs.appendf("%s.status is invalid", path)
		}
	}
	if len(e.Extensions) > 0 {
		errs = appendRawFieldErrors(errs, prefix+".extensions", e.Extensions, MaxExtensions, MaxExtensionKeyBytes, MaxExtensionValueBytes, MaxExtensionTotalBytes)
	}
	if len(e.UnknownFields) > 0 {
		errs = appendRawFieldErrors(errs, prefix+".unknown_fields", e.UnknownFields, MaxUnknownFields, MaxUnknownFieldKeyBytes, MaxUnknownFieldBytes, MaxUnknownTotalBytes)
	}
	return errs
}

func validateProvenance(p Provenance, prefix string, errs ValidationErrors) ValidationErrors {
	if !validProvenanceStatus(p.Status) {
		errs = errs.appendf("%s.status is invalid", prefix)
	}
	if p.Confidence != nil && (*p.Confidence < 0 || *p.Confidence > 1) {
		errs = errs.appendf("%s.confidence must be between 0 and 1", prefix)
	}
	for i := range p.Evidence {
		errs = validateContentRef(&p.Evidence[i], fmt.Sprintf("%s.evidence[%d]", prefix, i), errs)
	}
	return errs
}

func validateDigest(d Digest, prefix string, errs ValidationErrors) ValidationErrors {
	if d.Algorithm == "" {
		errs = errs.appendf("%s.algorithm is required", prefix)
	}
	if d.Value == "" {
		errs = errs.appendf("%s.value is required", prefix)
	}
	return errs
}

func validateContentRef(ref *ContentRef, prefix string, errs ValidationErrors) ValidationErrors {
	if ref == nil {
		return errs
	}
	if ref.URI == "" {
		errs = errs.appendf("%s.uri is required", prefix)
	}
	if ref.Bytes < 0 {
		errs = errs.appendf("%s.bytes must be non-negative", prefix)
	}
	if ref.Digest != nil {
		errs = validateDigest(*ref.Digest, prefix+".digest", errs)
	}
	return errs
}

func validateLimits(l Limits, prefix string, errs ValidationErrors) ValidationErrors {
	values := []struct {
		name  string
		value int64
	}{
		{name: "context_tokens", value: l.ContextTokens},
		{name: "max_input_tokens", value: l.MaxInputTokens},
		{name: "max_output_tokens", value: l.MaxOutputTokens},
		{name: "max_tool_calls", value: l.MaxToolCalls},
		{name: "requests_per_minute", value: l.RequestsPerMinute},
		{name: "tokens_per_minute", value: l.TokensPerMinute},
		{name: "payload_bytes", value: l.PayloadBytes},
		{name: "timeout_millis", value: l.TimeoutMillis},
	}
	for _, field := range values {
		if field.value < 0 {
			errs = errs.appendf("%s.%s must be non-negative", prefix, field.name)
		}
	}
	return errs
}

func appendModalityErrors(errs ValidationErrors, prefix string, values []Modality) ValidationErrors {
	for i, value := range values {
		if !validModality(value) {
			errs = errs.appendf("%s[%d] is invalid", prefix, i)
		}
	}
	return errs
}

func appendOperationErrors(errs ValidationErrors, prefix string, values []Operation) ValidationErrors {
	for i, value := range values {
		if !validOperation(value) {
			errs = errs.appendf("%s[%d] is invalid", prefix, i)
		}
	}
	return errs
}

func appendRawFieldErrors(errs ValidationErrors, prefix string, fields map[string]json.RawMessage, maxFields, maxKeyBytes, maxValueBytes, maxTotalBytes int) ValidationErrors {
	if err := validateRawFields(prefix, fields, maxFields, maxKeyBytes, maxValueBytes, maxTotalBytes); err != nil {
		return append(errs, err.Error())
	}
	return errs
}

func validateRawFields(prefix string, fields map[string]json.RawMessage, maxFields, maxKeyBytes, maxValueBytes, maxTotalBytes int) error {
	if len(fields) > maxFields {
		return fmt.Errorf("%s has %d fields, max %d", prefix, len(fields), maxFields)
	}
	total := 0
	for key, value := range fields {
		if key == "" {
			return fmt.Errorf("%s contains an empty key", prefix)
		}
		if len(key) > maxKeyBytes {
			return fmt.Errorf("%s key %q exceeds %d bytes", prefix, key, maxKeyBytes)
		}
		if !json.Valid(value) {
			return fmt.Errorf("%s.%s is not valid JSON", prefix, key)
		}
		if len(value) > maxValueBytes {
			return fmt.Errorf("%s.%s exceeds %d bytes", prefix, key, maxValueBytes)
		}
		total += len(key) + len(value)
	}
	if total > maxTotalBytes {
		return fmt.Errorf("%s exceeds %d total bytes", prefix, maxTotalBytes)
	}
	return nil
}

func validatePayloadSize(prefix string, value any, maxBytes int) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("%s is not JSON serializable: %w", prefix, err)
	}
	if len(data) > maxBytes {
		return fmt.Errorf("%s exceeds %d bytes", prefix, maxBytes)
	}
	return nil
}

func validEntityKind(value EntityKind) bool {
	switch value {
	case EntityKindModel, EntityKindA2AAgent, EntityKindA2ACapability, EntityKindMCPServer, EntityKindMCPTool, EntityKindProceduralSkill:
		return true
	default:
		return false
	}
}

func validProvenanceStatus(value ProvenanceStatus) bool {
	switch value {
	case ProvenanceVerified, ProvenanceSelfReported, ProvenanceInferred, ProvenanceStale, ProvenanceUnknown, ProvenanceQuarantined:
		return true
	default:
		return false
	}
}

func validSourceType(value SourceType) bool {
	switch value {
	case SourceProviderAPI, SourceA2ACard, SourceMCPLibrary, SourceUser, SourceBenchmark, SourceImport:
		return true
	default:
		return false
	}
}

func validModality(value Modality) bool {
	switch value {
	case ModalityText, ModalityImage, ModalityAudio, ModalityVideo, ModalityEmbedding, ModalityFile, ModalityTool, ModalityCode:
		return true
	default:
		return false
	}
}

func validOperation(value Operation) bool {
	switch value {
	case OperationChat, OperationResponses, OperationTextCompletion, OperationEmbedding, OperationImageGeneration, OperationImageEdit, OperationImageVariation, OperationSpeech, OperationTranscription, OperationToolCall, OperationMCPTool, OperationA2AMessage, OperationA2ATask, OperationSkillExecute, OperationTokenCount:
		return true
	default:
		return false
	}
}

func validRelationshipType(value RelationshipType) bool {
	switch value {
	case RelationshipProvides, RelationshipRequires, RelationshipHostedBy, RelationshipExposes, RelationshipImplements, RelationshipEquivalent, RelationshipSupersedes, RelationshipDerivedFrom:
		return true
	default:
		return false
	}
}

func validInterfaceType(value InterfaceType) bool {
	switch value {
	case InterfaceOpenAICompatible, InterfaceA2A, InterfaceMCP, InterfaceHTTP:
		return true
	default:
		return false
	}
}

func validHealthStatus(value HealthStatus) bool {
	switch value {
	case HealthUnknown, HealthHealthy, HealthDegraded, HealthDown:
		return true
	default:
		return false
	}
}
