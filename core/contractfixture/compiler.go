package contractfixture

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"
)

type CompileOptions struct {
	MetaSchema      []byte
	SourceDateEpoch string
}

func Compile(input []byte, options CompileOptions) (*SealedArtifacts, *IR, error) {
	var manifest Manifest
	if err := decodeStrict(input, &manifest, "contract fixture input"); err != nil {
		return nil, nil, err
	}
	sourceDateEpoch := options.SourceDateEpoch
	if sourceDateEpoch == "" {
		sourceDateEpoch = os.Getenv("SOURCE_DATE_EPOCH")
	}
	if sourceDateEpoch == "" {
		return nil, nil, fmt.Errorf("SOURCE_DATE_EPOCH is required")
	}
	epoch, err := strconv.ParseInt(sourceDateEpoch, 10, 64)
	if err != nil || epoch <= 0 {
		return nil, nil, fmt.Errorf("SOURCE_DATE_EPOCH must be a positive Unix timestamp")
	}
	compiled, err := compileManifest(manifest, options.MetaSchema, epoch)
	if err != nil {
		return nil, nil, err
	}
	return compiled.artifacts, compiled.ir, nil
}

type compiledCorpus struct {
	artifacts *SealedArtifacts
	ir        *IR
}

func compileManifest(manifest Manifest, metaSchemaBytes []byte, epoch int64) (*compiledCorpus, error) {
	if err := validateMetaSchema(manifest, metaSchemaBytes); err != nil {
		return nil, err
	}
	if manifest.Schema != ManifestSchemaV1 {
		return nil, fmt.Errorf("contract fixture input requires schema %q", ManifestSchemaV1)
	}
	if err := validateToolchain(manifest.ToolchainLock, epoch); err != nil {
		return nil, err
	}
	sources, sourceByID, err := validateSources(manifest.Sources)
	if err != nil {
		return nil, err
	}
	schemas, schemaByID, err := validateRequestSchemas(manifest.RequestSchemas, sourceByID)
	if err != nil {
		return nil, err
	}
	vectors, err := validateRequestVectors(manifest.RequestVectors, sourceByID, schemaByID)
	if err != nil {
		return nil, err
	}
	observations, err := validateObservations(manifest.Observations, sourceByID)
	if err != nil {
		return nil, err
	}
	faults, err := validateFaults(manifest.IntentionalFaults, sourceByID, schemaByID)
	if err != nil {
		return nil, err
	}
	discrepancies, err := validateDiscrepancies(manifest.Discrepancies, sourceByID)
	if err != nil {
		return nil, err
	}
	if manifest.Compatibility.MinReaderVersion < 1 || manifest.Compatibility.MinReaderVersion > ReaderVersion {
		return nil, fmt.Errorf("unsupported min_reader_version %d", manifest.Compatibility.MinReaderVersion)
	}
	if !sortedUnique(manifest.Compatibility.PriorVersions) || !containsString(manifest.Compatibility.PriorVersions, "bedrock-mantle-corpus/v0") {
		return nil, fmt.Errorf("compatibility must list sorted prior version bedrock-mantle-corpus/v0")
	}

	generatedAt := time.Unix(epoch, 0).UTC().Format(time.RFC3339)
	toolchainDigest, err := digestValue(manifest.ToolchainLock)
	if err != nil {
		return nil, err
	}
	entries := buildEntries(schemas, vectors, observations, faults)
	ir := &IR{
		Schema:           IRSchemaV1,
		GeneratedAt:      generatedAt,
		MetaSchemaDigest: manifest.MetaSchemaDigest,
		ToolchainDigest:  toolchainDigest,
		Sources:          sources,
		Entries:          entries,
		Discrepancies:    discrepancies,
		Compatibility:    manifest.Compatibility,
	}
	irDigest, err := digestValue(ir)
	if err != nil {
		return nil, err
	}
	provenance, err := buildProvenance(generatedAt, manifest.MetaSchemaDigest, manifest.ToolchainLock, sources)
	if err != nil {
		return nil, err
	}
	coverage, err := buildCoverage(entries, sources)
	if err != nil {
		return nil, err
	}
	discrepancyBytes, err := marshalArtifact(DiscrepancyArtifact{Schema: DiscrepancySchemaV1, Discrepancies: discrepancies})
	if err != nil {
		return nil, err
	}
	bundle, indexEntries, err := buildBundle(entries)
	if err != nil {
		return nil, err
	}
	artifactRefs := []ArtifactRef{
		{Name: artifactCoverage, Length: len(coverage), Digest: digestBytes(coverage)},
		{Name: artifactDiscrepancies, Length: len(discrepancyBytes), Digest: digestBytes(discrepancyBytes)},
		{Name: artifactProvenance, Length: len(provenance), Digest: digestBytes(provenance)},
	}
	index := Index{
		Schema:              IndexSchemaV1,
		FormatVersion:       1,
		MinReaderVersion:    manifest.Compatibility.MinReaderVersion,
		GeneratedAt:         generatedAt,
		BundleDigest:        digestBytes(bundle),
		BundleLength:        len(bundle),
		IRDigest:            irDigest,
		ToolchainLockDigest: toolchainDigest,
		Entries:             indexEntries,
		Artifacts:           artifactRefs,
		PriorVersions:       append([]string(nil), manifest.Compatibility.PriorVersions...),
	}
	indexBytes, err := marshalArtifact(index)
	if err != nil {
		return nil, err
	}
	return &compiledCorpus{
		artifacts: &SealedArtifacts{
			Bundle:        bundle,
			Index:         indexBytes,
			Provenance:    provenance,
			Coverage:      coverage,
			Discrepancies: discrepancyBytes,
		},
		ir: ir,
	}, nil
}

func validateMetaSchema(manifest Manifest, metaSchemaBytes []byte) error {
	if len(metaSchemaBytes) == 0 {
		return fmt.Errorf("checked-in meta-schema bytes are required")
	}
	if manifest.MetaSchemaDigest == "" || manifest.MetaSchemaDigest != digestBytes(metaSchemaBytes) {
		return fmt.Errorf("meta-schema digest mismatch")
	}
	var meta MetaSchema
	if err := decodeStrict(metaSchemaBytes, &meta, "contract fixture meta-schema"); err != nil {
		return err
	}
	if meta.Schema != MetaSchemaV1 || meta.InputSchema != ManifestSchemaV1 || meta.IRSchema != IRSchemaV1 || meta.ReaderVersion != ReaderVersion {
		return fmt.Errorf("meta-schema is not the checked contract fixture v1 schema")
	}
	expected := []string{artifactBundle, artifactCoverage, artifactDiscrepancies, artifactIndex, artifactProvenance}
	if len(meta.RequiredArtifacts) != len(expected) {
		return fmt.Errorf("meta-schema required_artifacts is incomplete")
	}
	for index := range expected {
		if meta.RequiredArtifacts[index] != expected[index] {
			return fmt.Errorf("meta-schema required_artifacts must be sorted and complete")
		}
	}
	return nil
}

func validateToolchain(lock ToolchainLock, epoch int64) error {
	if lock.Schema != "bedrock-mantle-contract-toolchain-lock/v1" || lock.GoVersion == "" || lock.Compiler == "" {
		return fmt.Errorf("toolchain lock is incomplete")
	}
	if lock.SourceDateEpoch != epoch {
		return fmt.Errorf("toolchain lock SOURCE_DATE_EPOCH %d does not match build epoch %d", lock.SourceDateEpoch, epoch)
	}
	switch lock.Reproducibility {
	case reproByteIdentical:
		if len(lock.ArchitectureDigests) != 0 {
			return fmt.Errorf("byte-identical toolchain lock must not record architecture digests")
		}
	case reproArchDigests:
		if len(lock.ArchitectureDigests) != 2 {
			return fmt.Errorf("architecture-digests toolchain lock must record amd64 and arm64")
		}
		required := []string{"linux/amd64", "linux/arm64"}
		for index, platform := range required {
			item := lock.ArchitectureDigests[index]
			if item.Platform != platform || !validDigest(item.Digest) {
				return fmt.Errorf("architecture digest[%d] must be %s with sha256 digest", index, platform)
			}
		}
	default:
		return fmt.Errorf("unknown reproducibility mode %q", lock.Reproducibility)
	}
	return nil
}

func validateSources(input []Source) ([]IRSource, map[string]Source, error) {
	if len(input) == 0 {
		return nil, nil, fmt.Errorf("at least one source is required")
	}
	seen := map[string]bool{}
	byID := map[string]Source{}
	output := make([]IRSource, 0, len(input))
	for index, source := range input {
		normalized, err := validateSource(source)
		if err != nil {
			return nil, nil, fmt.Errorf("source[%d]: %w", index, err)
		}
		if seen[normalized.ID] {
			return nil, nil, fmt.Errorf("duplicate source id %q", normalized.ID)
		}
		seen[normalized.ID] = true
		byID[normalized.ID] = normalized
		output = append(output, IRSource{
			ID:               normalized.ID,
			Class:            normalized.Class,
			AuthorityCeiling: normalized.AuthorityCeiling,
			Revision:         normalized.Revision,
			ArtifactDigest:   normalized.ArtifactDigest,
			ContentDigest:    normalized.ContentDigest,
			LicenseOrTerms:   normalized.LicenseOrTerms,
			Redistribution:   normalized.Redistribution,
			CoveredRoutes:    append([]string(nil), normalized.CoveredRoutes...),
			CoveredSurfaces:  append([]string(nil), normalized.CoveredSurfaces...),
			Omissions:        append([]string(nil), normalized.Omissions...),
		})
	}
	sort.Slice(output, func(i, j int) bool { return output[i].ID < output[j].ID })
	return output, byID, nil
}

func validateSource(source Source) (Source, error) {
	if source.ID == "" || !allowedSourceClass(source.Class) || source.AuthorityCeiling == "" || source.Revision == "" || source.Locator == "" || source.LicenseOrTerms == "" || source.ExtractionRecipe == "" {
		return source, fmt.Errorf("source %q is incomplete", source.ID)
	}
	if !validDigest(source.ArtifactDigest) {
		return source, fmt.Errorf("source %q has invalid artifact digest", source.ID)
	}
	if len(source.ContentDigest) > 0 && !validDigest(source.ContentDigest) {
		return source, fmt.Errorf("source %q has invalid content digest", source.ID)
	}
	if !sortedUnique(source.CoveredRoutes) || !sortedUnique(source.CoveredSurfaces) || !sortedUnique(source.Omissions) {
		return source, fmt.Errorf("source %q coverage and omissions must be sorted non-empty unique arrays", source.ID)
	}
	for _, route := range source.CoveredRoutes {
		if !allowedRoute(route) {
			return source, fmt.Errorf("source %q covers unknown route %q", source.ID, route)
		}
	}
	lowerCoordinate := strings.ToLower(strings.Join([]string{source.ID, source.Revision, source.Locator}, " "))
	for _, forbidden := range []string{"localstack", "github models", "github-models", "/blob/main/", "/blob/master/", "/tree/main/", "/tree/master/"} {
		if strings.Contains(lowerCoordinate, forbidden) {
			return source, fmt.Errorf("source %q contains forbidden or moving coordinate %q", source.ID, forbidden)
		}
	}
	if strings.Contains(strings.ToLower(source.Revision), "latest") {
		return source, fmt.Errorf("source %q uses moving latest revision", source.ID)
	}
	if source.Class == "official-client-serialization" && strings.Contains(strings.ToLower(source.AuthorityCeiling), "server acceptance") {
		return source, fmt.Errorf("source %q escalates client serialization to server acceptance", source.ID)
	}
	switch source.Redistribution {
	case redistributionPermitted:
		if len(source.Content) == 0 || source.ContentDigest == "" {
			return source, fmt.Errorf("source %q with permitted redistribution must include checked content and content digest", source.ID)
		}
		normalized, err := normalizeRawJSON(source.Content)
		if err != nil {
			return source, fmt.Errorf("source %q content is not canonical JSON: %w", source.ID, err)
		}
		if digestBytes(normalized) != source.ContentDigest {
			return source, fmt.Errorf("source %q content digest mismatch", source.ID)
		}
		source.Content = normalized
	case redistributionDerived, redistributionProhibited:
		if len(source.Content) != 0 {
			return source, fmt.Errorf("source %q may not vendor source content with redistribution %q", source.ID, source.Redistribution)
		}
		if len(source.DerivedAssertions) == 0 {
			return source, fmt.Errorf("source %q requires reviewed derived assertions", source.ID)
		}
	default:
		return source, fmt.Errorf("source %q has invalid redistribution %q", source.ID, source.Redistribution)
	}
	for index, assertion := range source.DerivedAssertions {
		if err := validateAssertion(source.ID, assertion); err != nil {
			return source, fmt.Errorf("source %q assertion[%d]: %w", source.ID, index, err)
		}
	}
	return source, nil
}

func validateAssertion(sourceID string, assertion DerivedAssertion) error {
	if assertion.ID == "" || assertion.Assertion == "" || assertion.Citation == "" || !validDigest(assertion.AssertionDigest) {
		return fmt.Errorf("derived assertion is incomplete")
	}
	if assertion.AssertionDigest != digestAssertion(sourceID, assertion) {
		return fmt.Errorf("derived assertion digest mismatch")
	}
	return nil
}

func validateRequestSchemas(input []RequestSchema, sources map[string]Source) ([]RequestSchema, map[string]RequestSchema, error) {
	if len(input) == 0 {
		return nil, nil, fmt.Errorf("at least one request schema is required")
	}
	seen := map[string]bool{}
	byID := map[string]RequestSchema{}
	output := make([]RequestSchema, 0, len(input))
	for index, schema := range input {
		normalized, err := validateRequestSchema(schema, sources)
		if err != nil {
			return nil, nil, fmt.Errorf("request_schema[%d]: %w", index, err)
		}
		if seen[normalized.ID] {
			return nil, nil, fmt.Errorf("duplicate request schema id %q", normalized.ID)
		}
		seen[normalized.ID] = true
		byID[normalized.ID] = normalized
		output = append(output, normalized)
	}
	sort.Slice(output, func(i, j int) bool { return output[i].ID < output[j].ID })
	return output, byID, nil
}

func validateRequestSchema(schema RequestSchema, sources map[string]Source) (RequestSchema, error) {
	source, ok := sources[schema.SourceID]
	if schema.ID == "" || !ok || schema.Route == "" || schema.Authority == "" {
		return schema, fmt.Errorf("schema %q is incomplete or references an unknown source", schema.ID)
	}
	if !schemaSourceClass(source.Class) {
		return schema, fmt.Errorf("schema %q source %q is not schema authority", schema.ID, source.ID)
	}
	if schema.Authority != source.Class {
		return schema, fmt.Errorf("schema %q authority %q does not match source class %q", schema.ID, schema.Authority, source.Class)
	}
	if !allowedRoute(schema.Route) || !containsString(source.CoveredRoutes, schema.Route) {
		return schema, fmt.Errorf("schema %q uses route %q outside source coverage", schema.ID, schema.Route)
	}
	if !sortedUnique(schema.Required) {
		return schema, fmt.Errorf("schema %q required fields must be sorted and non-empty", schema.ID)
	}
	if len(schema.ExactAbsent) > 0 && !sortedUnique(schema.ExactAbsent) {
		return schema, fmt.Errorf("schema %q exact_absent fields must be sorted unique", schema.ID)
	}
	if len(schema.Properties) == 0 {
		return schema, fmt.Errorf("schema %q must declare properties", schema.ID)
	}
	propertyNames := map[string]PropertySchema{}
	for index, property := range schema.Properties {
		if property.Name == "" || !allowedType(property.Type) {
			return schema, fmt.Errorf("schema %q property[%d] is invalid", schema.ID, index)
		}
		if index > 0 && schema.Properties[index-1].Name >= property.Name {
			return schema, fmt.Errorf("schema %q properties must be sorted by unique name", schema.ID)
		}
		if len(property.Enum) > 0 && !sortedUnique(property.Enum) {
			return schema, fmt.Errorf("schema %q property %q enum must be sorted unique", schema.ID, property.Name)
		}
		propertyNames[property.Name] = property
	}
	for _, required := range schema.Required {
		if _, ok := propertyNames[required]; !ok {
			return schema, fmt.Errorf("schema %q requires unknown field %q", schema.ID, required)
		}
	}
	return schema, nil
}

func validateRequestVectors(input []RequestVector, sources map[string]Source, schemas map[string]RequestSchema) ([]RequestVector, error) {
	if len(input) == 0 {
		return nil, fmt.Errorf("at least one request vector is required")
	}
	output := make([]RequestVector, 0, len(input))
	seen := map[string]bool{}
	for index, vector := range input {
		normalized, err := validateRequestVector(vector, sources, schemas)
		if err != nil {
			return nil, fmt.Errorf("request_vector[%d]: %w", index, err)
		}
		if seen[normalized.ID] {
			return nil, fmt.Errorf("duplicate request vector id %q", normalized.ID)
		}
		seen[normalized.ID] = true
		output = append(output, normalized)
	}
	sort.Slice(output, func(i, j int) bool { return output[i].ID < output[j].ID })
	return output, nil
}

func validateRequestVector(vector RequestVector, sources map[string]Source, schemas map[string]RequestSchema) (RequestVector, error) {
	source, ok := sources[vector.SourceID]
	schema, schemaOK := schemas[vector.SchemaID]
	if vector.ID == "" || !ok || !schemaOK || vector.Route == "" || vector.Authority == "" || vector.Family == "" {
		return vector, fmt.Errorf("vector %q is incomplete or references unknown source/schema", vector.ID)
	}
	if source.Class != "official-client-serialization" {
		return vector, fmt.Errorf("vector %q source %q is not official client serialization authority", vector.ID, source.ID)
	}
	if !allowedFamily(vector.Family) {
		return vector, fmt.Errorf("vector %q has unknown family %q", vector.ID, vector.Family)
	}
	if vector.Route != schema.Route || vector.Authority != source.Class || !containsString(source.CoveredRoutes, vector.Route) {
		return vector, fmt.Errorf("vector %q route or authority is outside source/schema coverage", vector.ID)
	}
	request, err := normalizeObject(vector.Request, "request_vector."+vector.ID+".request")
	if err != nil {
		return vector, err
	}
	vector.Request = request
	diagnostic := validateRequestAgainstSchema(schema, vector.Request)
	if !vector.Expected.Valid || vector.Expected.Diagnostic != "ok" {
		return vector, fmt.Errorf("vector %q must be an expected-valid SDK vector", vector.ID)
	}
	if diagnostic != "ok" {
		return vector, fmt.Errorf("vector %q failed request schema validation: %s", vector.ID, diagnostic)
	}
	if len(vector.Invariants) == 0 || !sortedUnique(vector.Invariants) {
		return vector, fmt.Errorf("vector %q invariants must be sorted non-empty unique array", vector.ID)
	}
	return vector, nil
}

func validateObservations(input []SanitizedObservation, sources map[string]Source) ([]SanitizedObservation, error) {
	if len(input) == 0 {
		return nil, fmt.Errorf("at least one sanitized observation is required")
	}
	output := make([]SanitizedObservation, 0, len(input))
	seen := map[string]bool{}
	for index, observation := range input {
		normalized, err := validateObservation(observation, sources)
		if err != nil {
			return nil, fmt.Errorf("observation[%d]: %w", index, err)
		}
		if seen[normalized.ID] {
			return nil, fmt.Errorf("duplicate observation id %q", normalized.ID)
		}
		seen[normalized.ID] = true
		output = append(output, normalized)
	}
	sort.Slice(output, func(i, j int) bool { return output[i].ID < output[j].ID })
	return output, nil
}

func validateObservation(observation SanitizedObservation, sources map[string]Source) (SanitizedObservation, error) {
	source, ok := sources[observation.SourceID]
	if observation.ID == "" || !ok || observation.Route == "" {
		return observation, fmt.Errorf("observation %q is incomplete or references unknown source", observation.ID)
	}
	if source.Class != "aws-observed-sample" || observation.Authority != "aws-observed-sample" {
		return observation, fmt.Errorf("observation %q must remain aws-observed-sample authority", observation.ID)
	}
	if !observation.Reviewed {
		return observation, fmt.Errorf("observation %q is not reviewed", observation.ID)
	}
	if !allowedRoute(observation.Route) || !containsString(source.CoveredRoutes, observation.Route) {
		return observation, fmt.Errorf("observation %q route is outside source coverage", observation.ID)
	}
	shape, err := normalizeObject(observation.RequestShape, "observation."+observation.ID+".request_shape")
	if err != nil {
		return observation, err
	}
	observation.RequestShape = shape
	if len(observation.ObservedAbsent) > 0 && !sortedUnique(observation.ObservedAbsent) {
		return observation, fmt.Errorf("observation %q observed_absent must be sorted unique", observation.ID)
	}
	if len(observation.Assertions) == 0 {
		return observation, fmt.Errorf("observation %q requires reviewed assertions", observation.ID)
	}
	for index, assertion := range observation.Assertions {
		if err := validateAssertion(source.ID, assertion); err != nil {
			return observation, fmt.Errorf("observation %q assertion[%d]: %w", observation.ID, index, err)
		}
	}
	return observation, nil
}

func validateFaults(input []IntentionalFault, sources map[string]Source, schemas map[string]RequestSchema) ([]IntentionalFault, error) {
	if len(input) == 0 {
		return nil, fmt.Errorf("at least one intentional fault is required")
	}
	output := make([]IntentionalFault, 0, len(input))
	seen := map[string]bool{}
	for index, fault := range input {
		normalized, err := validateFault(fault, sources, schemas)
		if err != nil {
			return nil, fmt.Errorf("intentional_fault[%d]: %w", index, err)
		}
		if seen[normalized.ID] {
			return nil, fmt.Errorf("duplicate intentional fault id %q", normalized.ID)
		}
		seen[normalized.ID] = true
		output = append(output, normalized)
	}
	sort.Slice(output, func(i, j int) bool { return output[i].ID < output[j].ID })
	return output, nil
}

func validateFault(fault IntentionalFault, sources map[string]Source, schemas map[string]RequestSchema) (IntentionalFault, error) {
	source, ok := sources[fault.SourceID]
	schema, schemaOK := schemas[fault.SchemaID]
	if fault.ID == "" || !ok || !schemaOK || fault.Route == "" || fault.Authority == "" || fault.ExpectedDiagnostic == "" {
		return fault, fmt.Errorf("fault %q is incomplete or references unknown source/schema", fault.ID)
	}
	if source.Class != "intentional-fault" || fault.Authority != "intentional-fault" {
		return fault, fmt.Errorf("fault %q must use intentional-fault authority", fault.ID)
	}
	if fault.Route != schema.Route || !containsString(source.CoveredRoutes, fault.Route) {
		return fault, fmt.Errorf("fault %q route is outside source/schema coverage", fault.ID)
	}
	request, err := normalizeObject(fault.Request, "intentional_fault."+fault.ID+".request")
	if err != nil {
		return fault, err
	}
	fault.Request = request
	diagnostic := validateRequestAgainstSchema(schema, fault.Request)
	if diagnostic == "ok" || diagnostic != fault.ExpectedDiagnostic {
		return fault, fmt.Errorf("fault %q expected diagnostic %q, got %q", fault.ID, fault.ExpectedDiagnostic, diagnostic)
	}
	if len(fault.MutationTargets) == 0 || !sortedUnique(fault.MutationTargets) {
		return fault, fmt.Errorf("fault %q mutation targets must be sorted non-empty unique array", fault.ID)
	}
	return fault, nil
}

func validateDiscrepancies(input []Discrepancy, sources map[string]Source) ([]Discrepancy, error) {
	output := append([]Discrepancy(nil), input...)
	for index, discrepancy := range output {
		if discrepancy.ID == "" || discrepancy.Subject == "" || len(discrepancy.ConflictingSourceIDs) < 2 || discrepancy.Resolution == "" || discrepancy.Evidence == "" {
			return nil, fmt.Errorf("discrepancy[%d] is incomplete", index)
		}
		if discrepancy.Status != "resolved" && discrepancy.Status != "investigating" {
			return nil, fmt.Errorf("discrepancy %q has invalid status %q", discrepancy.ID, discrepancy.Status)
		}
		if index > 0 && output[index-1].ID >= discrepancy.ID {
			return nil, fmt.Errorf("discrepancies must be sorted by unique id")
		}
		if !sortedUnique(discrepancy.ConflictingSourceIDs) {
			return nil, fmt.Errorf("discrepancy %q source ids must be sorted unique", discrepancy.ID)
		}
		for _, sourceID := range discrepancy.ConflictingSourceIDs {
			if _, ok := sources[sourceID]; !ok {
				return nil, fmt.Errorf("discrepancy %q references unknown source %q", discrepancy.ID, sourceID)
			}
		}
	}
	return output, nil
}

func validateRequestAgainstSchema(schema RequestSchema, request map[string]json.RawMessage) string {
	for _, field := range schema.Required {
		if _, ok := request[field]; !ok {
			return "missing_required:" + field
		}
	}
	for _, field := range schema.ExactAbsent {
		if _, ok := request[field]; ok {
			return "exact_absent:" + field
		}
	}
	properties := map[string]PropertySchema{}
	for _, property := range schema.Properties {
		properties[property.Name] = property
	}
	for key, raw := range request {
		property, ok := properties[key]
		if !ok {
			if schema.AdditionalProperties {
				continue
			}
			return "unknown_field:" + key
		}
		value, err := decodeRaw(raw)
		if err != nil {
			return "invalid_json:" + key
		}
		if !matchesType(value, property.Type) {
			return "invalid_type:" + key
		}
		if len(property.Enum) > 0 {
			stringValue, ok := value.(string)
			if !ok || !containsString(property.Enum, stringValue) {
				return "invalid_enum:" + key
			}
		}
	}
	return "ok"
}

func matchesType(value interface{}, propertyType string) bool {
	switch propertyType {
	case "array":
		_, ok := value.([]interface{})
		return ok
	case "boolean":
		_, ok := value.(bool)
		return ok
	case "number":
		_, ok := value.(json.Number)
		return ok
	case "object":
		_, ok := value.(map[string]interface{})
		return ok
	case "string":
		_, ok := value.(string)
		return ok
	default:
		return false
	}
}

func buildEntries(schemas []RequestSchema, vectors []RequestVector, observations []SanitizedObservation, faults []IntentionalFault) []CorpusEntry {
	entries := make([]CorpusEntry, 0, len(schemas)+len(vectors)+len(observations)+len(faults))
	schemaSourceByID := map[string]string{}
	for _, schema := range schemas {
		schema := schema
		schemaSourceByID[schema.ID] = schema.SourceID
		entries = append(entries, CorpusEntry{
			Schema:    EntrySchemaV1,
			ID:        "schema:" + schema.ID,
			Kind:      "request-schema",
			Route:     schema.Route,
			Authority: schema.Authority,
			SourceIDs: []string{schema.SourceID},
			Validation: &RequestValidation{
				SchemaID:             schema.ID,
				AdditionalProperties: schema.AdditionalProperties,
				Required:             append([]string(nil), schema.Required...),
				ExactAbsent:          append([]string(nil), schema.ExactAbsent...),
				Properties:           append([]PropertySchema(nil), schema.Properties...),
			},
		})
	}
	for _, vector := range vectors {
		expected := vector.Expected
		entries = append(entries, CorpusEntry{
			Schema:     EntrySchemaV1,
			ID:         "vector:" + vector.ID,
			Kind:       "request-vector",
			Route:      vector.Route,
			Authority:  vector.Authority,
			SourceIDs:  sortedUniqueCopy([]string{vector.SourceID, schemaSourceByID[vector.SchemaID]}),
			Request:    vector.Request,
			Expected:   &expected,
			Invariants: append([]string(nil), vector.Invariants...),
		})
	}
	for _, observation := range observations {
		entries = append(entries, CorpusEntry{
			Schema:         EntrySchemaV1,
			ID:             "observation:" + observation.ID,
			Kind:           "sanitized-observation",
			Route:          observation.Route,
			Authority:      observation.Authority,
			SourceIDs:      []string{observation.SourceID},
			Request:        observation.RequestShape,
			ObservedAbsent: append([]string(nil), observation.ObservedAbsent...),
			Assertions:     append([]DerivedAssertion(nil), observation.Assertions...),
		})
	}
	for _, fault := range faults {
		expected := ExpectedValidation{Valid: false, Diagnostic: fault.ExpectedDiagnostic}
		entries = append(entries, CorpusEntry{
			Schema:          EntrySchemaV1,
			ID:              "fault:" + fault.ID,
			Kind:            "intentional-fault",
			Route:           fault.Route,
			Authority:       fault.Authority,
			SourceIDs:       sortedUniqueCopy([]string{fault.SourceID, schemaSourceByID[fault.SchemaID]}),
			Request:         fault.Request,
			Expected:        &expected,
			MutationTargets: append([]string(nil), fault.MutationTargets...),
		})
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].ID < entries[j].ID })
	return entries
}

func sortedUniqueCopy(values []string) []string {
	seen := map[string]bool{}
	output := make([]string, 0, len(values))
	for _, value := range values {
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		output = append(output, value)
	}
	sort.Strings(output)
	return output
}

func buildBundle(entries []CorpusEntry) ([]byte, []IndexEntry, error) {
	var bundle bytes.Buffer
	indexEntries := make([]IndexEntry, 0, len(entries))
	for _, entry := range entries {
		line, err := canonicalJSON(entry)
		if err != nil {
			return nil, nil, err
		}
		line = append(line, '\n')
		offset := bundle.Len()
		if _, err := bundle.Write(line); err != nil {
			return nil, nil, err
		}
		indexEntries = append(indexEntries, IndexEntry{
			ID:     entry.ID,
			Offset: offset,
			Length: len(line),
			Digest: digestBytes(line),
		})
	}
	return bundle.Bytes(), indexEntries, nil
}

func buildProvenance(generatedAt string, metaSchemaDigest string, toolchain ToolchainLock, sources []IRSource) ([]byte, error) {
	return marshalArtifact(ProvenanceArtifact{
		Schema:           ProvenanceSchemaV1,
		GeneratedAt:      generatedAt,
		MetaSchemaDigest: metaSchemaDigest,
		ToolchainLock:    toolchain,
		Sources:          sources,
	})
}

func buildCoverage(entries []CorpusEntry, sources []IRSource) ([]byte, error) {
	routeMap := map[string]*RouteCoverage{}
	classMap := map[string][]string{}
	mutationTargets := map[string]bool{}
	for _, source := range sources {
		classMap[source.Class] = append(classMap[source.Class], source.ID)
	}
	for _, entry := range entries {
		coverage := routeMap[entry.Route]
		if coverage == nil {
			coverage = &RouteCoverage{Route: entry.Route}
			routeMap[entry.Route] = coverage
		}
		switch entry.Kind {
		case "request-schema":
			coverage.Schemas = append(coverage.Schemas, entry.ID)
		case "request-vector":
			coverage.Vectors = append(coverage.Vectors, entry.ID)
		case "sanitized-observation":
			coverage.Observations = append(coverage.Observations, entry.ID)
		case "intentional-fault":
			coverage.Faults = append(coverage.Faults, entry.ID)
			for _, target := range entry.MutationTargets {
				mutationTargets[target] = true
			}
		}
	}
	routes := make([]RouteCoverage, 0, len(routeMap))
	for _, coverage := range routeMap {
		coverage.Schemas = sortedCopy(coverage.Schemas)
		coverage.Vectors = sortedCopy(coverage.Vectors)
		coverage.Observations = sortedCopy(coverage.Observations)
		coverage.Faults = sortedCopy(coverage.Faults)
		routes = append(routes, *coverage)
	}
	sort.Slice(routes, func(i, j int) bool { return routes[i].Route < routes[j].Route })
	classes := make([]ClassCoverage, 0, len(classMap))
	for class, sourceIDs := range classMap {
		classes = append(classes, ClassCoverage{Class: class, Sources: sortedCopy(sourceIDs)})
	}
	sort.Slice(classes, func(i, j int) bool { return classes[i].Class < classes[j].Class })
	targets := make([]string, 0, len(mutationTargets))
	for target := range mutationTargets {
		targets = append(targets, target)
	}
	sort.Strings(targets)
	return marshalArtifact(CoverageArtifact{
		Schema:           CoverageSchemaV1,
		Routes:           routes,
		AuthorityClasses: classes,
		MutationTargets:  targets,
	})
}

func marshalArtifact(value interface{}) ([]byte, error) {
	data, err := canonicalJSON(value)
	if err != nil {
		return nil, err
	}
	return append(data, '\n'), nil
}

func allowedSourceClass(class string) bool {
	switch class {
	case "aws-observed-sample", "generic-api-schema", "inferred", "intentional-fault", "native-aws-service-model", "official-client-serialization", "official-doc-derived", "protocol-specification":
		return true
	default:
		return false
	}
}

func schemaSourceClass(class string) bool {
	switch class {
	case "generic-api-schema", "native-aws-service-model", "official-doc-derived", "protocol-specification":
		return true
	default:
		return false
	}
}

func allowedRoute(route string) bool {
	switch route {
	case "/anthropic/v1/messages", "/model/{modelId}/converse", "/openai/v1/chat/completions", "/openai/v1/responses":
		return true
	default:
		return false
	}
}

func allowedType(propertyType string) bool {
	switch propertyType {
	case "array", "boolean", "number", "object", "string":
		return true
	default:
		return false
	}
}

func allowedFamily(family string) bool {
	switch family {
	case "anthropic", "native-bedrock", "openai":
		return true
	default:
		return false
	}
}
