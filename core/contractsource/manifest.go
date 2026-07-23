// Package contractsource validates the immutable source registry used to build
// deterministic Bedrock and Bedrock Mantle conformance artifacts.
package contractsource

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"regexp"
	"sort"
	"strings"
	"time"
)

const SchemaV1 = "bedrock-mantle-source-lock/v1"

var digestPattern = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)

type Manifest struct {
	Schema             string          `json:"schema"`
	RegistryReviewedAt time.Time       `json:"registry_reviewed_at"`
	Sources            []Source        `json:"sources"`
	AbsenceRecords     []AbsenceRecord `json:"absence_records"`
	Discrepancies      []Discrepancy   `json:"discrepancies"`
}

type Source struct {
	ID               string    `json:"id"`
	AuthorityClass   string    `json:"authority_class"`
	AuthorityCeiling string    `json:"authority_ceiling"`
	Revision         string    `json:"revision"`
	Locator          string    `json:"locator"`
	ArtifactDigest   string    `json:"artifact_digest"`
	ContentDigest    string    `json:"content_digest,omitempty"`
	RetrievedAt      time.Time `json:"retrieved_at"`
	LicenseOrTerms   string    `json:"license_or_terms"`
	Redistribution   string    `json:"redistribution"`
	ExtractionRecipe string    `json:"extraction_recipe"`
	Paths            []string  `json:"paths"`
	CoveredSurfaces  []string  `json:"covered_surfaces"`
	Omissions        []string  `json:"omissions"`
}

type AbsenceRecord struct {
	ID               string    `json:"id"`
	Revision         string    `json:"revision"`
	Locator          string    `json:"locator"`
	ArtifactDigest   string    `json:"artifact_digest"`
	SearchDigest     string    `json:"search_digest"`
	RetrievedAt      time.Time `json:"retrieved_at"`
	LicenseOrTerms   string    `json:"license_or_terms"`
	SearchRecipe     string    `json:"search_recipe"`
	Commit           string    `json:"commit"`
	Version          string    `json:"version"`
	Subject          string    `json:"subject"`
	Scope            string    `json:"scope"`
	CaseSensitive    *bool     `json:"case_sensitive"`
	FilesConsidered  int       `json:"files_considered"`
	Patterns         []string  `json:"patterns"`
	Result           string    `json:"result"`
	Capability       string    `json:"capability"`
	AuthorityCeiling string    `json:"authority_ceiling"`
}

type canonicalAbsenceSearch struct {
	ArtifactSHA256  string        `json:"artifact_sha256"`
	CaseSensitive   bool          `json:"case_sensitive"`
	Commit          string        `json:"commit"`
	FilesConsidered int           `json:"files_considered"`
	Matches         []interface{} `json:"matches"`
	Patterns        []string      `json:"patterns"`
	Schema          string        `json:"schema"`
	Scope           string        `json:"scope"`
	Subject         string        `json:"subject"`
	Version         string        `json:"version"`
}

type Discrepancy struct {
	ID                   string   `json:"id"`
	Subject              string   `json:"subject"`
	ConflictingSourceIDs []string `json:"conflicting_source_ids"`
	Status               string   `json:"status"`
	Resolution           string   `json:"resolution"`
	Evidence             string   `json:"evidence"`
}

var allowedAuthority = map[string]bool{
	"native-aws-service-model":      true,
	"protocol-specification":        true,
	"generic-api-schema":            true,
	"official-client-serialization": true,
	"official-doc-derived":          true,
	"aws-observed-sample":           true,
	"inferred":                      true,
	"intentional-fault":             true,
}

func Decode(r io.Reader) (*Manifest, error) {
	data, err := io.ReadAll(io.LimitReader(r, (1<<20)+1))
	if err != nil {
		return nil, fmt.Errorf("read source lock: %w", err)
	}
	if len(data) > 1<<20 {
		return nil, fmt.Errorf("source lock exceeds 1 MiB")
	}
	if err := rejectDuplicateJSONKeys(data); err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var manifest Manifest
	if err := decoder.Decode(&manifest); err != nil {
		return nil, fmt.Errorf("decode source lock: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return nil, fmt.Errorf("source lock contains trailing JSON")
	}
	if err := manifest.Validate(); err != nil {
		return nil, err
	}
	return &manifest, nil
}

func rejectDuplicateJSONKeys(data []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	var walk func() error
	walk = func() error {
		token, err := decoder.Token()
		if err != nil {
			return err
		}
		delim, ok := token.(json.Delim)
		if !ok {
			return nil
		}
		switch delim {
		case '{':
			seen := map[string]bool{}
			for decoder.More() {
				keyToken, err := decoder.Token()
				if err != nil {
					return err
				}
				key, ok := keyToken.(string)
				if !ok {
					return fmt.Errorf("JSON object key is not a string")
				}
				if seen[key] {
					return fmt.Errorf("duplicate JSON key %q", key)
				}
				seen[key] = true
				if err := walk(); err != nil {
					return err
				}
			}
			_, err = decoder.Token()
			return err
		case '[':
			for decoder.More() {
				if err := walk(); err != nil {
					return err
				}
			}
			_, err = decoder.Token()
			return err
		default:
			return fmt.Errorf("unexpected JSON delimiter %q", delim)
		}
	}
	if err := walk(); err != nil {
		return fmt.Errorf("validate source-lock JSON: %w", err)
	}
	if _, err := decoder.Token(); err != io.EOF {
		return fmt.Errorf("source lock contains trailing JSON")
	}
	return nil
}

func (m Manifest) Validate() error {
	if m.Schema != SchemaV1 || m.RegistryReviewedAt.IsZero() {
		return fmt.Errorf("source lock requires schema %q and review time", SchemaV1)
	}
	seen := map[string]bool{}
	classes := map[string]bool{}
	for index, source := range m.Sources {
		if err := validateSource(source); err != nil {
			return fmt.Errorf("source[%d]: %w", index, err)
		}
		if seen[source.ID] {
			return fmt.Errorf("duplicate source id %q", source.ID)
		}
		seen[source.ID] = true
		classes[source.AuthorityClass] = true
		if index > 0 && m.Sources[index-1].ID >= source.ID {
			return fmt.Errorf("sources must be sorted by unique id")
		}
	}
	for _, required := range []string{"native-aws-service-model", "protocol-specification", "official-client-serialization"} {
		if !classes[required] {
			return fmt.Errorf("missing required authority class %q", required)
		}
	}
	for _, surface := range []string{
		"eventstream-official-implementation", "generic-openai-responses", "mantle-anthropic-route",
		"mantle-openai-route-openai-v1", "native-bedrock-endpoint-rules", "native-bedrock-operations",
	} {
		if !manifestCovers(m.Sources, surface) {
			return fmt.Errorf("missing required contract surface %q", surface)
		}
	}
	for _, sourceID := range []string{
		"anthropic-go-mantle-1.58.0", "anthropic-java-mantle-2.49.0", "anthropic-php-mantle-0.37.0",
		"anthropic-python-mantle-0.117.0", "anthropic-ruby-mantle-1.56.0", "anthropic-typescript-mantle-0.6.1",
		"openai-node-mantle-6.48.0", "openai-python-mantle-2.46.0", "openai-ruby-mantle-0.71.0",
	} {
		if !seen[sourceID] {
			return fmt.Errorf("missing locked first-party client source %q", sourceID)
		}
	}
	if !manifestCovers(m.Sources, "codex-responses-lite-request") || !manifestCovers(m.Sources, "codex-namespaced-model-resolution") {
		return fmt.Errorf("missing pinned Codex Responses Lite negotiation and request coverage")
	}
	foundCLINegative := false
	seenAbsence := map[string]bool{}
	for index, record := range m.AbsenceRecords {
		if record.ID == "" || record.Revision == "" || record.Locator == "" || !digestPattern.MatchString(record.ArtifactDigest) || !digestPattern.MatchString(record.SearchDigest) || record.RetrievedAt.IsZero() || record.LicenseOrTerms == "" || record.SearchRecipe == "" || record.Commit == "" || record.Version == "" || record.Subject == "" || record.Scope == "" || record.CaseSensitive == nil || *record.CaseSensitive || record.FilesConsidered < 1 || record.Result != "absent" || record.Capability == "" {
			return fmt.Errorf("incomplete absence record %q", record.ID)
		}
		expectedPatterns := []string{"bedrock-mantle", "bedrock_mantle", "BedrockMantle", "BedrockOpenAI"}
		if len(record.Patterns) != len(expectedPatterns) {
			return fmt.Errorf("absence record %q has incomplete search patterns", record.ID)
		}
		for patternIndex := range expectedPatterns {
			if record.Patterns[patternIndex] != expectedPatterns[patternIndex] {
				return fmt.Errorf("absence record %q has noncanonical search patterns", record.ID)
			}
		}
		canonical := canonicalAbsenceSearch{
			ArtifactSHA256: strings.TrimPrefix(record.ArtifactDigest, "sha256:"), CaseSensitive: *record.CaseSensitive,
			Commit: record.Commit, FilesConsidered: record.FilesConsidered, Matches: []interface{}{}, Patterns: record.Patterns,
			Schema: "bifrost.source-lock.absence-search.v1", Scope: record.Scope, Subject: record.Subject, Version: record.Version,
		}
		canonicalBytes, err := json.Marshal(canonical)
		if err != nil {
			return fmt.Errorf("marshal absence record %q: %w", record.ID, err)
		}
		computed := sha256.Sum256(canonicalBytes)
		if record.SearchDigest != fmt.Sprintf("sha256:%x", computed[:]) {
			return fmt.Errorf("absence record %q search digest does not match canonical evidence", record.ID)
		}
		if record.AuthorityCeiling != "negative-capability-only" {
			return fmt.Errorf("absence record %q exceeds negative capability authority", record.ID)
		}
		if seenAbsence[record.ID] || (index > 0 && m.AbsenceRecords[index-1].ID >= record.ID) {
			return fmt.Errorf("absence records must be sorted by unique id")
		}
		seenAbsence[record.ID] = true
		if strings.Contains(strings.ToLower(record.Capability), "mantle") &&
			(strings.Contains(strings.ToLower(record.Locator), "aws-cli") || strings.Contains(strings.ToLower(record.ID), "aws-cli")) {
			foundCLINegative = true
		}
	}
	if !foundCLINegative {
		return fmt.Errorf("missing AWS CLI Mantle negative-capability record")
	}
	for _, absenceID := range []string{"openai-dotnet-no-mantle-2.12.0", "openai-go-no-mantle-3.44.0", "openai-java-no-mantle-4.44.0"} {
		if !seenAbsence[absenceID] {
			return fmt.Errorf("missing locked first-party client absence %q", absenceID)
		}
	}
	seenDiscrepancy := map[string]bool{}
	for index, discrepancy := range m.Discrepancies {
		if discrepancy.ID == "" || discrepancy.Subject == "" || len(discrepancy.ConflictingSourceIDs) < 2 || discrepancy.Status == "" || discrepancy.Resolution == "" || discrepancy.Evidence == "" {
			return fmt.Errorf("incomplete discrepancy %q", discrepancy.ID)
		}
		if discrepancy.Status != "resolved" && discrepancy.Status != "investigating" {
			return fmt.Errorf("discrepancy %q has invalid status", discrepancy.ID)
		}
		if seenDiscrepancy[discrepancy.ID] || (index > 0 && m.Discrepancies[index-1].ID >= discrepancy.ID) {
			return fmt.Errorf("discrepancies must be sorted by unique id")
		}
		seenDiscrepancy[discrepancy.ID] = true
		if !sort.StringsAreSorted(discrepancy.ConflictingSourceIDs) || hasDuplicate(discrepancy.ConflictingSourceIDs) {
			return fmt.Errorf("discrepancy %q source ids must be sorted and unique", discrepancy.ID)
		}
		for _, sourceID := range discrepancy.ConflictingSourceIDs {
			if !seen[sourceID] {
				return fmt.Errorf("discrepancy %q references unknown source %q", discrepancy.ID, sourceID)
			}
		}
	}
	return nil
}

func manifestCovers(sources []Source, surface string) bool {
	for _, source := range sources {
		for _, covered := range source.CoveredSurfaces {
			if covered == surface {
				return true
			}
		}
	}
	return false
}

func hasDuplicate(values []string) bool {
	for index := 1; index < len(values); index++ {
		if values[index-1] == values[index] {
			return true
		}
	}
	return false
}

func validateSource(source Source) error {
	if source.ID == "" || !allowedAuthority[source.AuthorityClass] || source.AuthorityCeiling == "" || source.Revision == "" || source.Locator == "" || source.RetrievedAt.IsZero() || source.LicenseOrTerms == "" || source.ExtractionRecipe == "" || len(source.Paths) == 0 || len(source.CoveredSurfaces) == 0 || len(source.Omissions) == 0 {
		return fmt.Errorf("source %q is incomplete", source.ID)
	}
	for _, digest := range []string{source.ArtifactDigest, source.ContentDigest} {
		if digest != "" && !digestPattern.MatchString(digest) {
			return fmt.Errorf("source %q has invalid digest %q", source.ID, digest)
		}
	}
	if source.ArtifactDigest == "" {
		return fmt.Errorf("source %q has no artifact digest", source.ID)
	}
	if source.Redistribution != "permitted" && source.Redistribution != "derived-only" && source.Redistribution != "prohibited" {
		return fmt.Errorf("source %q has invalid redistribution policy", source.ID)
	}
	lower := strings.ToLower(strings.Join([]string{source.ID, source.Revision, source.Locator}, " "))
	for _, forbidden := range []string{"localstack", "github models", "github-models"} {
		if strings.Contains(lower, forbidden) {
			return fmt.Errorf("source %q contains forbidden or moving coordinate %q", source.ID, forbidden)
		}
	}
	if strings.Contains(strings.ToLower(source.Revision), "latest") ||
		(source.AuthorityClass != "official-doc-derived" && strings.Contains(strings.ToLower(source.Locator), "latest")) {
		return fmt.Errorf("source %q contains a moving latest coordinate", source.ID)
	}
	locatorLower := strings.ToLower(source.Locator)
	for _, movingGitHubRef := range []string{"/blob/main/", "/blob/master/", "/tree/main/", "/tree/master/"} {
		if strings.Contains(locatorLower, movingGitHubRef) {
			return fmt.Errorf("source %q contains moving GitHub coordinate %q", source.ID, movingGitHubRef)
		}
	}
	if source.AuthorityClass == "official-client-serialization" && strings.Contains(strings.ToLower(source.AuthorityCeiling), "server acceptance") {
		return fmt.Errorf("client source %q claims server acceptance", source.ID)
	}
	if !sort.StringsAreSorted(source.Paths) || !sort.StringsAreSorted(source.CoveredSurfaces) || !sort.StringsAreSorted(source.Omissions) {
		return fmt.Errorf("source %q path, coverage, and omission arrays must be sorted", source.ID)
	}
	return nil
}
