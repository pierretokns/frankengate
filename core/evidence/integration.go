package evidence

import (
	"bufio"
	"bytes"
	"encoding/json"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"path"
	"reflect"
	"regexp"
	"sort"
	"strings"
	"time"
)

const IntegrationEvidenceVersionV1 = "frankengate-integration-evidence/v1"

const (
	maxIntegrationRecordBytes = 1 << 20
	maxArtifactRefs           = 32
)

const (
	DiagnosticOK                       = "IE_OK"
	DiagnosticSchemaInvalid            = "IE_SCHEMA_INVALID"
	DiagnosticSecretLeak               = "IE_SECRET_LEAK"
	DiagnosticPaidInference            = "IE_PAID_INFERENCE"
	DiagnosticForbiddenEgress          = "IE_FORBIDDEN_EGRESS"
	DiagnosticFloatingArtifact         = "IE_FLOATING_ARTIFACT"
	DiagnosticMissingMandatoryArtifact = "IE_MISSING_MANDATORY_ARTIFACT"
	DiagnosticSilentSkip               = "IE_SILENT_SKIP"
	DiagnosticWaiverExpired            = "IE_WAIVER_EXPIRED"
	DiagnosticAllScenariosSkipped      = "IE_ALL_SCENARIOS_SKIPPED"
	DiagnosticOptionalRealAWSExcluded  = "IE_OPTIONAL_REAL_AWS_EXCLUDED"
	DiagnosticWaivedResult             = "IE_WAIVED_RESULT"
)

var (
	safeDiagnosticCodeRe = regexp.MustCompile(`^IE_[A-Z0-9_]{2,61}$`)
	safeHeaderNameRe     = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,126}$`)
	safeHTTPMethodRe     = regexp.MustCompile(`^[A-Z]{3,10}$`)
	safeRoutePathRe      = regexp.MustCompile(`^/[A-Za-z0-9._~:/{}+-]*$`)
	safeArtifactPathRe   = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._/+~-]{0,240}$`)
	secretValueRes       = []*regexp.Regexp{
		regexp.MustCompile(`sk-[A-Za-z0-9_-]{20,}`),
		regexp.MustCompile(`AKIA[0-9A-Z]{16}`),
		regexp.MustCompile(`(?i)api[_-]?key\s*[:=]`),
		regexp.MustCompile(`(?i)password\s*[:=]`),
		regexp.MustCompile(`(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}`),
		regexp.MustCompile(`-----BEGIN (?:RSA |OPENSSH |EC |)PRIVATE KEY-----`),
	}
)

var mandatoryIntegrationArtifacts = []string{
	"network_recording",
	"stderr_log",
	"stdout_jsonl",
	"wire_recording",
}

type IntegrationEvidenceProfile string

const (
	IntegrationProfileNormalCI        IntegrationEvidenceProfile = "normal_ci"
	IntegrationProfileOptionalRealAWS IntegrationEvidenceProfile = "optional_real_aws"
)

type ConfidenceTier string

const (
	ConfidenceContractOnly    ConfidenceTier = "contract_only"
	ConfidenceHermeticReplay  ConfidenceTier = "hermetic_replay"
	ConfidenceWireObserved    ConfidenceTier = "wire_observed"
	ConfidenceOptionalRealAWS ConfidenceTier = "optional_real_aws"
)

type AuthMode string

const (
	AuthModeDummy  AuthMode = "dummy"
	AuthModeStatic AuthMode = "static"
	AuthModeIAM    AuthMode = "iam"
	AuthModeSTS    AuthMode = "sts"
	AuthModeOAuth  AuthMode = "oauth"
	AuthModeNone   AuthMode = "none"
)

type IntegrationResultStatus string

const (
	IntegrationResultPass  IntegrationResultStatus = "pass"
	IntegrationResultFail  IntegrationResultStatus = "fail"
	IntegrationResultError IntegrationResultStatus = "error"
	IntegrationResultSkip  IntegrationResultStatus = "skip"
)

type IntegrationEvidenceRecord struct {
	SchemaVersion  string                     `json:"schema_version"`
	Profile        IntegrationEvidenceProfile `json:"profile"`
	CiRequired     bool                       `json:"ci_required"`
	RunID          string                     `json:"run_id"`
	ScenarioID     string                     `json:"scenario_id"`
	StartedAt      time.Time                  `json:"started_at"`
	CompletedAt    time.Time                  `json:"completed_at"`
	Versions       IntegrationVersions        `json:"versions"`
	ConfidenceTier ConfidenceTier             `json:"confidence_tier"`
	Provider       string                     `json:"provider"`
	Route          string                     `json:"route"`
	Models         ModelResolutionEvidence    `json:"models"`
	LiteRequest    LiteRequestShape           `json:"lite_request"`
	RedactedHashes []NamedDigest              `json:"redacted_hashes"`
	AuthMode       AuthMode                   `json:"auth_mode"`
	Network        NetworkRecorderCounters    `json:"network"`
	Result         IntegrationResult          `json:"result"`
	Waiver         *IntegrationWaiver         `json:"waiver,omitempty"`
	Artifacts      []ArtifactRef              `json:"artifacts"`
}

type IntegrationVersions struct {
	Git        GitVersionRef       `json:"git"`
	Image      ImageVersionRef     `json:"image"`
	CLI        ComponentVersionRef `json:"cli"`
	Backend    ComponentVersionRef `json:"backend"`
	PostgreSQL ComponentVersionRef `json:"postgresql"`
}

type GitVersionRef struct {
	Commit     string `json:"commit"`
	TreeDigest string `json:"tree_digest"`
	Dirty      bool   `json:"dirty"`
}

type ImageVersionRef struct {
	Repository string `json:"repository"`
	Tag        string `json:"tag"`
	Digest     string `json:"digest"`
}

type ComponentVersionRef struct {
	Name    string `json:"name"`
	Version string `json:"version"`
	Digest  string `json:"digest"`
}

type ModelResolutionEvidence struct {
	Advertised string `json:"advertised"`
	Selected   string `json:"selected"`
	Resolved   string `json:"resolved"`
}

type LiteRequestShape struct {
	Method           string        `json:"method"`
	Path             string        `json:"path"`
	HeaderNames      []string      `json:"header_names"`
	QueryShapeDigest string        `json:"query_shape_digest,omitempty"`
	BodyShapeDigest  string        `json:"body_shape_digest"`
	RedactedHashes   []NamedDigest `json:"redacted_hashes,omitempty"`
	Streaming        bool          `json:"streaming"`
}

type NamedDigest struct {
	Name   string `json:"name"`
	Digest string `json:"digest"`
}

type NetworkRecorderCounters struct {
	RecorderID              string `json:"recorder_id"`
	RecorderDigest          string `json:"recorder_digest"`
	TotalOutboundRequests   int    `json:"total_outbound_requests"`
	LoopbackRequests        int    `json:"loopback_requests"`
	AllowedExternalRequests int    `json:"allowed_external_requests"`
	ForbiddenEgressRequests int    `json:"forbidden_egress_requests"`
	PaidInferenceRequests   int    `json:"paid_inference_requests"`
	DNSQueries              int    `json:"dns_queries"`
}

type IntegrationResult struct {
	Status         IntegrationResultStatus `json:"status"`
	DiagnosticCode string                  `json:"diagnostic_code"`
}

type IntegrationWaiver struct {
	Owner     string    `json:"owner"`
	Reason    string    `json:"reason"`
	ExpiresAt time.Time `json:"expires_at"`
}

type ArtifactRef struct {
	Name      string `json:"name"`
	Path      string `json:"path"`
	Digest    string `json:"digest"`
	MediaType string `json:"media_type"`
	Required  bool   `json:"required"`
}

type IntegrationDiagnostic struct {
	Type       string `json:"type"`
	Severity   string `json:"severity"`
	Code       string `json:"code"`
	Line       int    `json:"line,omitempty"`
	RunID      string `json:"run_id,omitempty"`
	ScenarioID string `json:"scenario_id,omitempty"`
	Field      string `json:"field,omitempty"`
	Message    string `json:"message"`
}

type IntegrationGateSummary struct {
	Type             string `json:"type"`
	Pass             bool   `json:"pass"`
	Records          int    `json:"records"`
	Evaluated        int    `json:"evaluated"`
	Passed           int    `json:"passed"`
	Failed           int    `json:"failed"`
	Skipped          int    `json:"skipped"`
	OptionalExcluded int    `json:"optional_excluded"`
}

type IntegrationGateReport struct {
	Summary     IntegrationGateSummary
	Diagnostics []IntegrationDiagnostic
}

type IntegrationGateOptions struct {
	Now                    time.Time
	IncludeOptionalRealAWS bool
}

type integrationValidationError struct {
	code    string
	field   string
	message string
}

func (e integrationValidationError) Error() string {
	if e.field == "" {
		return e.message
	}
	return e.field + ": " + e.message
}

func DecodeIntegrationEvidenceStrict(data []byte) (IntegrationEvidenceRecord, error) {
	if len(data) > maxIntegrationRecordBytes {
		return IntegrationEvidenceRecord{}, validationError(DiagnosticSchemaInvalid, "", fmt.Sprintf("integration evidence record exceeds %d bytes", maxIntegrationRecordBytes))
	}
	if err := rejectDuplicateKeys(data); err != nil {
		return IntegrationEvidenceRecord{}, validationError(DiagnosticSchemaInvalid, "", err.Error())
	}
	var record IntegrationEvidenceRecord
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&record); err != nil {
		return IntegrationEvidenceRecord{}, validationError(DiagnosticSchemaInvalid, "", err.Error())
	}
	var extra struct{}
	if err := dec.Decode(&extra); err != io.EOF {
		if err == nil {
			return IntegrationEvidenceRecord{}, validationError(DiagnosticSchemaInvalid, "", "multiple JSON values are not allowed")
		}
		return IntegrationEvidenceRecord{}, validationError(DiagnosticSchemaInvalid, "", err.Error())
	}
	if err := record.Validate(); err != nil {
		return IntegrationEvidenceRecord{}, err
	}
	return record, nil
}

func (r IntegrationEvidenceRecord) Validate() error {
	if r.SchemaVersion != IntegrationEvidenceVersionV1 {
		return validationError(DiagnosticSchemaInvalid, "schema_version", fmt.Sprintf("unsupported integration evidence version %q", r.SchemaVersion))
	}
	if !validIntegrationProfile(r.Profile) {
		return validationError(DiagnosticSchemaInvalid, "profile", fmt.Sprintf("unsupported profile %q", r.Profile))
	}
	if r.Profile == IntegrationProfileOptionalRealAWS && r.CiRequired {
		return validationError(DiagnosticSchemaInvalid, "ci_required", "optional real-AWS evidence cannot be normal-CI required")
	}
	if r.Profile == IntegrationProfileNormalCI && r.ConfidenceTier == ConfidenceOptionalRealAWS {
		return validationError(DiagnosticSchemaInvalid, "confidence_tier", "normal CI evidence cannot use optional real-AWS confidence")
	}
	if r.Profile == IntegrationProfileOptionalRealAWS && r.ConfidenceTier != ConfidenceOptionalRealAWS {
		return validationError(DiagnosticSchemaInvalid, "confidence_tier", "optional real-AWS evidence must use optional_real_aws confidence")
	}
	if err := requireSafeToken("run id", r.RunID, maxIDLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "run_id", err.Error())
	}
	if err := requireSafeToken("scenario id", r.ScenarioID, maxIDLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "scenario_id", err.Error())
	}
	if r.StartedAt.IsZero() {
		return validationError(DiagnosticSchemaInvalid, "started_at", "started_at is required")
	}
	if r.CompletedAt.IsZero() {
		return validationError(DiagnosticSchemaInvalid, "completed_at", "completed_at is required")
	}
	if r.CompletedAt.Before(r.StartedAt) {
		return validationError(DiagnosticSchemaInvalid, "completed_at", "completed_at must not be before started_at")
	}
	if err := r.Versions.validate(); err != nil {
		return err
	}
	if !validConfidenceTier(r.ConfidenceTier) {
		return validationError(DiagnosticSchemaInvalid, "confidence_tier", fmt.Sprintf("unsupported confidence tier %q", r.ConfidenceTier))
	}
	if err := requireSafeToken("provider", r.Provider, maxIDLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "provider", err.Error())
	}
	if err := requireSafeToken("route", r.Route, maxIDLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "route", err.Error())
	}
	if err := r.Models.validate(); err != nil {
		return err
	}
	if err := r.LiteRequest.validate(); err != nil {
		return err
	}
	if err := validateNamedDigests("redacted_hashes", r.RedactedHashes); err != nil {
		return err
	}
	if !validAuthMode(r.AuthMode) {
		return validationError(DiagnosticSchemaInvalid, "auth_mode", fmt.Sprintf("unsupported auth mode %q", r.AuthMode))
	}
	if err := r.Network.validate(); err != nil {
		return err
	}
	if err := r.Result.validate(); err != nil {
		return err
	}
	if r.Waiver != nil {
		if err := r.Waiver.validate(); err != nil {
			return err
		}
	}
	if err := validateArtifactRefs(r.Artifacts); err != nil {
		return err
	}
	if field := firstSecretField(r); field != "" {
		return validationError(DiagnosticSecretLeak, field, "field value looks like an unredacted secret")
	}
	return nil
}

func ValidateIntegrationEvidenceJSONL(r io.Reader, opts IntegrationGateOptions) IntegrationGateReport {
	if opts.Now.IsZero() {
		opts.Now = time.Now().UTC()
	}
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 0, 64*1024), maxIntegrationRecordBytes)

	var records []IntegrationEvidenceRecord
	var diagnostics []IntegrationDiagnostic
	line := 0
	for scanner.Scan() {
		line++
		data := bytes.TrimSpace(scanner.Bytes())
		if len(data) == 0 {
			diagnostics = append(diagnostics, diagnosticFromError(line, IntegrationEvidenceRecord{}, validationError(DiagnosticSchemaInvalid, "", "blank JSONL records are not allowed")))
			continue
		}
		record, err := DecodeIntegrationEvidenceStrict(data)
		if err != nil {
			diagnostics = append(diagnostics, diagnosticFromError(line, record, err))
			continue
		}
		records = append(records, record)
	}
	if err := scanner.Err(); err != nil {
		diagnostics = append(diagnostics, diagnosticFromError(line+1, IntegrationEvidenceRecord{}, validationError(DiagnosticSchemaInvalid, "", err.Error())))
	}
	report := EvaluateIntegrationEvidenceGate(records, opts)
	report.Diagnostics = append(diagnostics, report.Diagnostics...)
	sortDiagnostics(report.Diagnostics)
	report.Summary.Records += len(diagnostics)
	report.Summary.Pass = report.Summary.Pass && len(errorDiagnostics(diagnostics)) == 0
	return report
}

func EvaluateIntegrationEvidenceGate(records []IntegrationEvidenceRecord, opts IntegrationGateOptions) IntegrationGateReport {
	if opts.Now.IsZero() {
		opts.Now = time.Now().UTC()
	}
	report := IntegrationGateReport{
		Summary: IntegrationGateSummary{
			Type:    "summary",
			Pass:    true,
			Records: len(records),
		},
	}
	for _, record := range records {
		if record.Profile == IntegrationProfileOptionalRealAWS && !opts.IncludeOptionalRealAWS {
			report.Summary.OptionalExcluded++
			report.Diagnostics = append(report.Diagnostics, IntegrationDiagnostic{
				Type:       "diagnostic",
				Severity:   "info",
				Code:       DiagnosticOptionalRealAWSExcluded,
				RunID:      record.RunID,
				ScenarioID: record.ScenarioID,
				Field:      "profile",
				Message:    "optional real-AWS evidence is labeled separately and excluded from the normal-CI release gate",
			})
			continue
		}

		report.Summary.Evaluated++
		switch record.Result.Status {
		case IntegrationResultPass:
			report.Summary.Passed++
		case IntegrationResultSkip:
			report.Summary.Skipped++
		case IntegrationResultFail, IntegrationResultError:
			if record.Waiver != nil && !record.Waiver.ExpiresAt.Before(opts.Now) {
				report.Diagnostics = append(report.Diagnostics, IntegrationDiagnostic{
					Type:       "diagnostic",
					Severity:   "warning",
					Code:       DiagnosticWaivedResult,
					RunID:      record.RunID,
					ScenarioID: record.ScenarioID,
					Field:      "waiver",
					Message:    "non-egress result is waived until " + record.Waiver.ExpiresAt.UTC().Format(time.RFC3339),
				})
			} else {
				report.Summary.Failed++
				report.Summary.Pass = false
				report.Diagnostics = append(report.Diagnostics, IntegrationDiagnostic{
					Type:       "diagnostic",
					Severity:   "error",
					Code:       record.Result.DiagnosticCode,
					RunID:      record.RunID,
					ScenarioID: record.ScenarioID,
					Field:      "result.status",
					Message:    "scenario result blocks release",
				})
			}
		}

		if record.Waiver != nil && record.Waiver.ExpiresAt.Before(opts.Now) {
			report.Summary.Pass = false
			report.Diagnostics = append(report.Diagnostics, IntegrationDiagnostic{
				Type:       "diagnostic",
				Severity:   "error",
				Code:       DiagnosticWaiverExpired,
				RunID:      record.RunID,
				ScenarioID: record.ScenarioID,
				Field:      "waiver.expires_at",
				Message:    "waiver is expired",
			})
		}
		if record.Network.PaidInferenceRequests > 0 {
			report.Summary.Pass = false
			report.Diagnostics = append(report.Diagnostics, IntegrationDiagnostic{
				Type:       "diagnostic",
				Severity:   "error",
				Code:       DiagnosticPaidInference,
				RunID:      record.RunID,
				ScenarioID: record.ScenarioID,
				Field:      "network.paid_inference_requests",
				Message:    "zero-paid-inference gate requires paid_inference_requests to be 0",
			})
		}
		if record.Network.ForbiddenEgressRequests > 0 {
			report.Summary.Pass = false
			report.Diagnostics = append(report.Diagnostics, IntegrationDiagnostic{
				Type:       "diagnostic",
				Severity:   "error",
				Code:       DiagnosticForbiddenEgress,
				RunID:      record.RunID,
				ScenarioID: record.ScenarioID,
				Field:      "network.forbidden_egress_requests",
				Message:    "release gate requires forbidden_egress_requests to be 0",
			})
		}
	}
	if report.Summary.Evaluated == 0 && report.Summary.OptionalExcluded == len(records) && len(records) > 0 {
		sortDiagnostics(report.Diagnostics)
		return report
	}
	if report.Summary.Evaluated == 0 || (report.Summary.Passed == 0 && report.Summary.Failed == 0) {
		report.Summary.Pass = false
		report.Diagnostics = append(report.Diagnostics, IntegrationDiagnostic{
			Type:     "diagnostic",
			Severity: "error",
			Code:     DiagnosticAllScenariosSkipped,
			Field:    "result.status",
			Message:  "normal-CI evidence must include at least one non-skipped scenario",
		})
	}
	sortDiagnostics(report.Diagnostics)
	return report
}

func WriteIntegrationGateReportJSONL(w io.Writer, report IntegrationGateReport) error {
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	for _, diagnostic := range report.Diagnostics {
		if err := enc.Encode(diagnostic); err != nil {
			return err
		}
	}
	return enc.Encode(report.Summary)
}

func IntegrationGateJUnitXML(report IntegrationGateReport) ([]byte, error) {
	testCases := make([]junitTestCase, 0, len(report.Diagnostics)+1)
	for _, d := range report.Diagnostics {
		name := d.Code
		if d.ScenarioID != "" {
			name = d.ScenarioID + "/" + d.Code
		}
		tc := junitTestCase{
			ClassName: "integration-evidence-gate",
			Name:      name,
			Time:      "0",
		}
		switch d.Severity {
		case "error":
			tc.Failure = &junitFailure{Message: d.Message, Type: d.Code, Body: d.Field}
		case "warning":
			tc.Skipped = &junitSkipped{Message: d.Message}
		}
		testCases = append(testCases, tc)
	}
	if len(testCases) == 0 {
		testCases = append(testCases, junitTestCase{ClassName: "integration-evidence-gate", Name: DiagnosticOK, Time: "0"})
	}
	failures := 0
	skipped := 0
	for _, tc := range testCases {
		if tc.Failure != nil {
			failures++
		}
		if tc.Skipped != nil {
			skipped++
		}
	}
	suite := junitTestSuite{
		Name:      "integration-evidence-gate",
		Tests:     len(testCases),
		Failures:  failures,
		Skipped:   skipped,
		TestCases: testCases,
	}
	out, err := xml.MarshalIndent(suite, "", "  ")
	if err != nil {
		return nil, err
	}
	return append([]byte(xml.Header), out...), nil
}

func (v IntegrationVersions) validate() error {
	if err := requireSafeToken("git commit", v.Git.Commit, 64); err != nil {
		return validationError(DiagnosticSchemaInvalid, "versions.git.commit", err.Error())
	}
	if err := requireSafeDigest("git tree digest", v.Git.TreeDigest); err != nil {
		return validationError(DiagnosticSchemaInvalid, "versions.git.tree_digest", err.Error())
	}
	if err := requireSafeToken("image repository", v.Image.Repository, maxRevisionLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "versions.image.repository", err.Error())
	}
	if err := requireSafeToken("image tag", v.Image.Tag, maxRevisionLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "versions.image.tag", err.Error())
	}
	if isFloatingReference(v.Image.Tag) {
		return validationError(DiagnosticFloatingArtifact, "versions.image.tag", "image tag is a floating reference")
	}
	if err := requireSafeDigest("image digest", v.Image.Digest); err != nil {
		return validationError(DiagnosticSchemaInvalid, "versions.image.digest", err.Error())
	}
	for name, component := range map[string]ComponentVersionRef{
		"cli":        v.CLI,
		"backend":    v.Backend,
		"postgresql": v.PostgreSQL,
	} {
		if err := component.validate("versions." + name); err != nil {
			return err
		}
	}
	return nil
}

func (c ComponentVersionRef) validate(prefix string) error {
	if err := requireSafeToken(prefix+" name", c.Name, maxIDLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, prefix+".name", err.Error())
	}
	if err := requireSafeToken(prefix+" version", c.Version, maxRevisionLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, prefix+".version", err.Error())
	}
	if isFloatingReference(c.Version) {
		return validationError(DiagnosticFloatingArtifact, prefix+".version", "component version is a floating reference")
	}
	if err := requireSafeDigest(prefix+" digest", c.Digest); err != nil {
		return validationError(DiagnosticSchemaInvalid, prefix+".digest", err.Error())
	}
	return nil
}

func (m ModelResolutionEvidence) validate() error {
	if err := requireSafeToken("advertised model", m.Advertised, maxRevisionLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "models.advertised", err.Error())
	}
	if err := requireSafeToken("selected model", m.Selected, maxRevisionLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "models.selected", err.Error())
	}
	if err := requireSafeToken("resolved model", m.Resolved, maxRevisionLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "models.resolved", err.Error())
	}
	return nil
}

func (l LiteRequestShape) validate() error {
	if !safeHTTPMethodRe.MatchString(l.Method) {
		return validationError(DiagnosticSchemaInvalid, "lite_request.method", "method must be an uppercase HTTP method")
	}
	if !safeRoutePathRe.MatchString(l.Path) {
		return validationError(DiagnosticSchemaInvalid, "lite_request.path", "path must be a redacted absolute route path")
	}
	if len(l.HeaderNames) == 0 {
		return validationError(DiagnosticSchemaInvalid, "lite_request.header_names", "header_names are required")
	}
	seen := map[string]struct{}{}
	for i, header := range l.HeaderNames {
		if !safeHeaderNameRe.MatchString(header) {
			return validationError(DiagnosticSchemaInvalid, fmt.Sprintf("lite_request.header_names[%d]", i), "header name must be lowercase and redacted")
		}
		if _, ok := seen[header]; ok {
			return validationError(DiagnosticSchemaInvalid, fmt.Sprintf("lite_request.header_names[%d]", i), "header name is duplicated")
		}
		seen[header] = struct{}{}
	}
	if !sort.StringsAreSorted(l.HeaderNames) {
		return validationError(DiagnosticSchemaInvalid, "lite_request.header_names", "header_names must be sorted for deterministic evidence")
	}
	if l.QueryShapeDigest != "" {
		if err := requireSafeDigest("query shape digest", l.QueryShapeDigest); err != nil {
			return validationError(DiagnosticSchemaInvalid, "lite_request.query_shape_digest", err.Error())
		}
	}
	if err := requireSafeDigest("body shape digest", l.BodyShapeDigest); err != nil {
		return validationError(DiagnosticSchemaInvalid, "lite_request.body_shape_digest", err.Error())
	}
	return validateNamedDigests("lite_request.redacted_hashes", l.RedactedHashes)
}

func validateNamedDigests(field string, values []NamedDigest) error {
	seen := map[string]struct{}{}
	for i, value := range values {
		if err := requireSafeCode(field+" name", value.Name, maxReasonCodeLen); err != nil {
			return validationError(DiagnosticSchemaInvalid, fmt.Sprintf("%s[%d].name", field, i), err.Error())
		}
		if _, ok := seen[value.Name]; ok {
			return validationError(DiagnosticSchemaInvalid, fmt.Sprintf("%s[%d].name", field, i), "name is duplicated")
		}
		seen[value.Name] = struct{}{}
		if err := requireSafeDigest(field+" digest", value.Digest); err != nil {
			return validationError(DiagnosticSchemaInvalid, fmt.Sprintf("%s[%d].digest", field, i), err.Error())
		}
	}
	if !namedDigestsSorted(values) {
		return validationError(DiagnosticSchemaInvalid, field, "named digests must be sorted by name for deterministic evidence")
	}
	return nil
}

func (n NetworkRecorderCounters) validate() error {
	if err := requireSafeToken("network recorder id", n.RecorderID, maxIDLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "network.recorder_id", err.Error())
	}
	if err := requireSafeDigest("network recorder digest", n.RecorderDigest); err != nil {
		return validationError(DiagnosticSchemaInvalid, "network.recorder_digest", err.Error())
	}
	counters := map[string]int{
		"network.total_outbound_requests":   n.TotalOutboundRequests,
		"network.loopback_requests":         n.LoopbackRequests,
		"network.allowed_external_requests": n.AllowedExternalRequests,
		"network.forbidden_egress_requests": n.ForbiddenEgressRequests,
		"network.paid_inference_requests":   n.PaidInferenceRequests,
		"network.dns_queries":               n.DNSQueries,
	}
	for field, value := range counters {
		if value < 0 {
			return validationError(DiagnosticSchemaInvalid, field, "network counters cannot be negative")
		}
	}
	accounted := n.LoopbackRequests + n.AllowedExternalRequests + n.ForbiddenEgressRequests
	if accounted > n.TotalOutboundRequests {
		return validationError(DiagnosticSchemaInvalid, "network.total_outbound_requests", "network subtype counters exceed total outbound requests")
	}
	return nil
}

func (r IntegrationResult) validate() error {
	if !validIntegrationResultStatus(r.Status) {
		return validationError(DiagnosticSchemaInvalid, "result.status", fmt.Sprintf("unsupported result status %q", r.Status))
	}
	if !safeDiagnosticCodeRe.MatchString(r.DiagnosticCode) {
		return validationError(DiagnosticSchemaInvalid, "result.diagnostic_code", "diagnostic_code must be a stable IE_* code")
	}
	if r.Status == IntegrationResultPass && r.DiagnosticCode != DiagnosticOK {
		return validationError(DiagnosticSchemaInvalid, "result.diagnostic_code", "passing records must use IE_OK")
	}
	if r.Status == IntegrationResultSkip && r.DiagnosticCode == DiagnosticOK {
		return validationError(DiagnosticSilentSkip, "result.diagnostic_code", "skipped records require a non-IE_OK diagnostic code")
	}
	if (r.Status == IntegrationResultFail || r.Status == IntegrationResultError) && r.DiagnosticCode == DiagnosticOK {
		return validationError(DiagnosticSchemaInvalid, "result.diagnostic_code", "failing records require a non-IE_OK diagnostic code")
	}
	return nil
}

func (w IntegrationWaiver) validate() error {
	if err := requireSafeToken("waiver owner", w.Owner, maxIDLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "waiver.owner", err.Error())
	}
	if err := requireSafeCode("waiver reason", w.Reason, maxReasonCodeLen); err != nil {
		return validationError(DiagnosticSchemaInvalid, "waiver.reason", err.Error())
	}
	if w.ExpiresAt.IsZero() {
		return validationError(DiagnosticSchemaInvalid, "waiver.expires_at", "waiver expiry is required")
	}
	return nil
}

func validateArtifactRefs(refs []ArtifactRef) error {
	if len(refs) == 0 {
		return validationError(DiagnosticMissingMandatoryArtifact, "artifacts", "artifact references are required")
	}
	if len(refs) > maxArtifactRefs {
		return validationError(DiagnosticSchemaInvalid, "artifacts", fmt.Sprintf("artifact references exceed maximum %d", maxArtifactRefs))
	}
	seen := map[string]ArtifactRef{}
	for i, ref := range refs {
		field := fmt.Sprintf("artifacts[%d]", i)
		if err := requireSafeCode("artifact name", ref.Name, maxReasonCodeLen); err != nil {
			return validationError(DiagnosticSchemaInvalid, field+".name", err.Error())
		}
		if _, ok := seen[ref.Name]; ok {
			return validationError(DiagnosticSchemaInvalid, field+".name", "artifact name is duplicated")
		}
		seen[ref.Name] = ref
		if err := validateArtifactPath(ref.Path); err != nil {
			return validationError(DiagnosticFloatingArtifact, field+".path", err.Error())
		}
		if err := requireSafeDigest("artifact digest", ref.Digest); err != nil {
			return validationError(DiagnosticFloatingArtifact, field+".digest", err.Error())
		}
		if err := requireSafeMediaType("artifact media type", ref.MediaType); err != nil {
			return validationError(DiagnosticSchemaInvalid, field+".media_type", err.Error())
		}
	}
	if !artifactRefsSorted(refs) {
		return validationError(DiagnosticSchemaInvalid, "artifacts", "artifact references must be sorted by name for deterministic evidence")
	}
	for _, name := range mandatoryIntegrationArtifacts {
		ref, ok := seen[name]
		if !ok {
			return validationError(DiagnosticMissingMandatoryArtifact, "artifacts."+name, "mandatory artifact reference is missing")
		}
		if !ref.Required {
			return validationError(DiagnosticMissingMandatoryArtifact, "artifacts."+name+".required", "mandatory artifact must be marked required")
		}
	}
	return nil
}

func validateArtifactPath(value string) error {
	if value == "" {
		return errors.New("artifact path is required")
	}
	if strings.HasPrefix(value, "/") || strings.Contains(value, `\`) || strings.Contains(value, "://") {
		return errors.New("artifact path must be a relative local artifact reference")
	}
	cleaned := path.Clean(value)
	if cleaned == "." || strings.HasPrefix(cleaned, "../") || cleaned == ".." {
		return errors.New("artifact path must not escape the artifact root")
	}
	if cleaned != value {
		return errors.New("artifact path must be canonical")
	}
	if !safeArtifactPathRe.MatchString(value) {
		return errors.New("artifact path contains unsafe characters")
	}
	if isFloatingReference(value) {
		return errors.New("artifact path is a floating reference")
	}
	return nil
}

func validationError(code, field, message string) error {
	return integrationValidationError{code: code, field: field, message: message}
}

func diagnosticFromError(line int, record IntegrationEvidenceRecord, err error) IntegrationDiagnostic {
	var validation integrationValidationError
	code := DiagnosticSchemaInvalid
	field := ""
	message := err.Error()
	if errors.As(err, &validation) {
		code = validation.code
		field = validation.field
		message = validation.message
	}
	return IntegrationDiagnostic{
		Type:       "diagnostic",
		Severity:   "error",
		Code:       code,
		Line:       line,
		RunID:      record.RunID,
		ScenarioID: record.ScenarioID,
		Field:      field,
		Message:    message,
	}
}

func sortDiagnostics(d []IntegrationDiagnostic) {
	sort.SliceStable(d, func(i, j int) bool {
		a, b := d[i], d[j]
		if a.Line != b.Line {
			return a.Line < b.Line
		}
		if a.RunID != b.RunID {
			return a.RunID < b.RunID
		}
		if a.ScenarioID != b.ScenarioID {
			return a.ScenarioID < b.ScenarioID
		}
		if a.Code != b.Code {
			return a.Code < b.Code
		}
		return a.Field < b.Field
	})
}

func errorDiagnostics(in []IntegrationDiagnostic) []IntegrationDiagnostic {
	out := make([]IntegrationDiagnostic, 0, len(in))
	for _, diagnostic := range in {
		if diagnostic.Severity == "error" {
			out = append(out, diagnostic)
		}
	}
	return out
}

func firstSecretField(value any) string {
	return firstSecretFieldValue(reflect.ValueOf(value), "")
}

func firstSecretFieldValue(v reflect.Value, path string) string {
	if !v.IsValid() {
		return ""
	}
	if v.Kind() == reflect.Pointer {
		if v.IsNil() {
			return ""
		}
		return firstSecretFieldValue(v.Elem(), path)
	}
	switch v.Kind() {
	case reflect.String:
		if looksLikeSecretValue(v.String()) {
			return strings.TrimPrefix(path, ".")
		}
	case reflect.Struct:
		t := v.Type()
		for i := 0; i < v.NumField(); i++ {
			if !v.Field(i).CanInterface() {
				continue
			}
			name := jsonFieldName(t.Field(i))
			if name == "-" {
				continue
			}
			child := path + "." + name
			if found := firstSecretFieldValue(v.Field(i), child); found != "" {
				return found
			}
		}
	case reflect.Slice, reflect.Array:
		for i := 0; i < v.Len(); i++ {
			if found := firstSecretFieldValue(v.Index(i), fmt.Sprintf("%s[%d]", path, i)); found != "" {
				return found
			}
		}
	}
	return ""
}

func jsonFieldName(field reflect.StructField) string {
	tag := field.Tag.Get("json")
	if tag == "" {
		return field.Name
	}
	name, _, _ := strings.Cut(tag, ",")
	if name == "" {
		return field.Name
	}
	return name
}

func looksLikeSecretValue(value string) bool {
	for _, re := range secretValueRes {
		if re.MatchString(value) {
			return true
		}
	}
	return false
}

func validIntegrationProfile(v IntegrationEvidenceProfile) bool {
	return v == IntegrationProfileNormalCI || v == IntegrationProfileOptionalRealAWS
}

func validConfidenceTier(v ConfidenceTier) bool {
	switch v {
	case ConfidenceContractOnly, ConfidenceHermeticReplay, ConfidenceWireObserved, ConfidenceOptionalRealAWS:
		return true
	default:
		return false
	}
}

func validAuthMode(v AuthMode) bool {
	switch v {
	case AuthModeDummy, AuthModeStatic, AuthModeIAM, AuthModeSTS, AuthModeOAuth, AuthModeNone:
		return true
	default:
		return false
	}
}

func validIntegrationResultStatus(v IntegrationResultStatus) bool {
	switch v {
	case IntegrationResultPass, IntegrationResultFail, IntegrationResultError, IntegrationResultSkip:
		return true
	default:
		return false
	}
}

func namedDigestsSorted(values []NamedDigest) bool {
	return sort.SliceIsSorted(values, func(i, j int) bool {
		return values[i].Name < values[j].Name
	})
}

func artifactRefsSorted(values []ArtifactRef) bool {
	return sort.SliceIsSorted(values, func(i, j int) bool {
		return values[i].Name < values[j].Name
	})
}

func isFloatingReference(value string) bool {
	parts := strings.FieldsFunc(strings.ToLower(value), func(r rune) bool {
		return r == '/' || r == ':' || r == '@' || r == '.' || r == '_' || r == '-'
	})
	for _, part := range parts {
		switch part {
		case "latest", "head", "main", "master", "nightly", "snapshot":
			return true
		}
	}
	return false
}

type junitTestSuite struct {
	XMLName   xml.Name        `xml:"testsuite"`
	Name      string          `xml:"name,attr"`
	Tests     int             `xml:"tests,attr"`
	Failures  int             `xml:"failures,attr"`
	Skipped   int             `xml:"skipped,attr"`
	TestCases []junitTestCase `xml:"testcase"`
}

type junitTestCase struct {
	ClassName string        `xml:"classname,attr"`
	Name      string        `xml:"name,attr"`
	Time      string        `xml:"time,attr"`
	Failure   *junitFailure `xml:"failure,omitempty"`
	Skipped   *junitSkipped `xml:"skipped,omitempty"`
}

type junitFailure struct {
	Message string `xml:"message,attr"`
	Type    string `xml:"type,attr"`
	Body    string `xml:",chardata"`
}

type junitSkipped struct {
	Message string `xml:"message,attr"`
}
