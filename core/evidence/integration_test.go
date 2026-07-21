package evidence_test

import (
	"bytes"
	"encoding/json"
	"encoding/xml"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/evidence"
)

const gateNow = "2026-01-02T03:04:05Z"

func TestIntegrationEvidenceValidFixturePassesGate(t *testing.T) {
	report := validateFixture(t, "valid/normal-pass.jsonl", false)
	if !report.Summary.Pass {
		t.Fatalf("valid fixture failed gate: %#v", report.Diagnostics)
	}
	if report.Summary.Records != 1 || report.Summary.Evaluated != 1 || report.Summary.Passed != 1 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func TestIntegrationEvidenceOptionalRealAWSIsExcludedFromNormalGate(t *testing.T) {
	report := validateFixture(t, "valid/optional-real-aws.jsonl", false)
	if !report.Summary.Pass {
		t.Fatalf("optional real-AWS exclusion should not fail normal gate: %#v", report.Diagnostics)
	}
	if report.Summary.OptionalExcluded != 1 || report.Summary.Evaluated != 0 {
		t.Fatalf("unexpected optional exclusion summary: %#v", report.Summary)
	}
	assertDiagnosticCode(t, report, evidence.DiagnosticOptionalRealAWSExcluded)
}

func TestIntegrationEvidenceNegativeFixturesFailWithStableCodes(t *testing.T) {
	tests := map[string]string{
		"negative/all-skipped.jsonl":                evidence.DiagnosticAllScenariosSkipped,
		"negative/expired-waiver.jsonl":             evidence.DiagnosticWaiverExpired,
		"negative/floating-artifact.jsonl":          evidence.DiagnosticFloatingArtifact,
		"negative/forbidden-egress.jsonl":           evidence.DiagnosticForbiddenEgress,
		"negative/invalid-schema.jsonl":             evidence.DiagnosticSchemaInvalid,
		"negative/missing-mandatory-artifact.jsonl": evidence.DiagnosticMissingMandatoryArtifact,
		"negative/paid-inference.jsonl":             evidence.DiagnosticPaidInference,
		"negative/secret-leak.jsonl":                evidence.DiagnosticSecretLeak,
		"negative/silent-skip.jsonl":                evidence.DiagnosticSilentSkip,
	}
	for fixture, wantCode := range tests {
		t.Run(strings.TrimSuffix(filepath.Base(fixture), ".jsonl"), func(t *testing.T) {
			report := validateFixture(t, fixture, false)
			if report.Summary.Pass {
				t.Fatalf("negative fixture %s passed unexpectedly", fixture)
			}
			assertDiagnosticCode(t, report, wantCode)

			var a, b bytes.Buffer
			if err := evidence.WriteIntegrationGateReportJSONL(&a, report); err != nil {
				t.Fatalf("write first report: %v", err)
			}
			if err := evidence.WriteIntegrationGateReportJSONL(&b, report); err != nil {
				t.Fatalf("write second report: %v", err)
			}
			if !bytes.Equal(a.Bytes(), b.Bytes()) {
				t.Fatalf("report output is not deterministic:\nfirst:\n%s\nsecond:\n%s", a.String(), b.String())
			}
		})
	}
}

func TestIntegrationGateReportIsJSONLOnlyWithSummaryLast(t *testing.T) {
	report := validateFixture(t, "negative/paid-inference.jsonl", false)
	var out bytes.Buffer
	if err := evidence.WriteIntegrationGateReportJSONL(&out, report); err != nil {
		t.Fatalf("write report: %v", err)
	}
	lines := strings.Split(strings.TrimSpace(out.String()), "\n")
	if len(lines) < 2 {
		t.Fatalf("expected diagnostics plus summary, got %q", out.String())
	}
	for i, line := range lines {
		var decoded map[string]any
		if err := json.Unmarshal([]byte(line), &decoded); err != nil {
			t.Fatalf("line %d is not JSON: %v\n%s", i+1, err, line)
		}
	}
	var summary map[string]any
	if err := json.Unmarshal([]byte(lines[len(lines)-1]), &summary); err != nil {
		t.Fatalf("decode summary: %v", err)
	}
	if summary["type"] != "summary" || summary["pass"] != false {
		t.Fatalf("last line is not failing summary: %#v", summary)
	}
}

func TestIntegrationGateJUnitProjection(t *testing.T) {
	report := validateFixture(t, "negative/paid-inference.jsonl", false)
	data, err := evidence.IntegrationGateJUnitXML(report)
	if err != nil {
		t.Fatalf("junit projection: %v", err)
	}
	var suite struct {
		XMLName  xml.Name `xml:"testsuite"`
		Failures int      `xml:"failures,attr"`
		Cases    []struct {
			Name    string `xml:"name,attr"`
			Failure *struct {
				Type string `xml:"type,attr"`
			} `xml:"failure"`
		} `xml:"testcase"`
	}
	if err := xml.Unmarshal(data, &suite); err != nil {
		t.Fatalf("decode junit: %v\n%s", err, string(data))
	}
	if suite.XMLName.Local != "testsuite" || suite.Failures == 0 {
		t.Fatalf("unexpected junit suite: %#v", suite)
	}
	found := false
	for _, tc := range suite.Cases {
		if tc.Failure != nil && tc.Failure.Type == evidence.DiagnosticPaidInference {
			found = true
		}
	}
	if !found {
		t.Fatalf("paid inference failure missing from junit:\n%s", string(data))
	}
}

func TestIntegrationEvidenceSchemaPublishesRequiredContractFields(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("schemas", "integration-evidence-v1.schema.json"))
	if err != nil {
		t.Fatalf("read schema: %v", err)
	}
	var schema struct {
		ID       string   `json:"$id"`
		Title    string   `json:"title"`
		Required []string `json:"required"`
	}
	if err := json.Unmarshal(data, &schema); err != nil {
		t.Fatalf("schema is not JSON: %v", err)
	}
	if schema.ID == "" || !strings.Contains(schema.Title, "integration evidence") {
		t.Fatalf("schema metadata is incomplete: %#v", schema)
	}
	required := map[string]bool{}
	for _, name := range schema.Required {
		required[name] = true
	}
	for _, name := range []string{
		"run_id", "scenario_id", "versions", "confidence_tier", "provider", "route",
		"models", "lite_request", "redacted_hashes", "auth_mode", "network", "result", "artifacts",
	} {
		if !required[name] {
			t.Fatalf("published schema does not require %q", name)
		}
	}
}

func validateFixture(t *testing.T, name string, includeOptionalRealAWS bool) evidence.IntegrationGateReport {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("testdata", "integration", name))
	if err != nil {
		t.Fatalf("read fixture %s: %v", name, err)
	}
	now, err := time.Parse(time.RFC3339, gateNow)
	if err != nil {
		t.Fatalf("parse test time: %v", err)
	}
	return evidence.ValidateIntegrationEvidenceJSONL(bytes.NewReader(data), evidence.IntegrationGateOptions{
		Now:                    now,
		IncludeOptionalRealAWS: includeOptionalRealAWS,
	})
}

func assertDiagnosticCode(t *testing.T, report evidence.IntegrationGateReport, want string) {
	t.Helper()
	for _, diagnostic := range report.Diagnostics {
		if diagnostic.Code == want {
			return
		}
	}
	t.Fatalf("diagnostic %s not found in %#v", want, report.Diagnostics)
}
