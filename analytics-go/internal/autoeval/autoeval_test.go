package autoeval

import (
	"encoding/json"
	"strings"
	"testing"
)

func fixtureTrace() Trace {
	return Trace{
		SchemaVersion: CanonicalTrajectoryVersion, TraceID: "trace-1", TenantID: "tenant-1", Source: "fixture", SourceRevision: "fixture@1", SourceDigest: "sha256:fixture-source", TaskFamily: "support.refund", HarnessRevision: "harness@1", ModelRevision: "model@1",
		Privacy: PrivacyReceipt{ReceiptID: "privacy-1", Policy: "eval", Transform: "redact-v1", Version: "1", RawAllowed: false}, Authorization: Authorization{SourceAuthorized: true, Purpose: "autoeval", Actor: "test"}, Deletion: DeletionLineage{SubjectID: "subject-1", Revision: "delete-1", Active: true}, Loss: LossReceipt{SourceEventCount: 2, CanonicalEventCount: 2},
		Events: []Event{{EventID: "e0", TraceID: "trace-1", Sequence: 0, Kind: "user.task", Observation: "observed", Content: "email alice@example.com"}, {EventID: "e1", TraceID: "trace-1", Sequence: 1, ParentEventID: "e0", Kind: "tool.proposed", Observation: "observed", ToolName: "refund.check", Arguments: json.RawMessage(`{"customer":"alice@example.com"}`)}},
	}
}

func TestPrepareStripsRawContentAndRedactsBeforeDigest(t *testing.T) {
	prepared, report, err := Prepare(fixtureTrace())
	if err != nil {
		t.Fatal(err)
	}
	if report.RedactedFields == 0 {
		t.Fatal("expected a redaction")
	}
	if prepared.Events[0].ContentDigest == "" {
		t.Fatal("expected content digest")
	}
	if strings.Contains(prepared.Events[0].ContentDigest, "alice@example.com") {
		t.Fatal("raw email leaked into digest")
	}
	if ContainsRawPayload(prepared) {
		t.Fatal("prepared trace contains raw payload fields")
	}
}

func TestPrepareRejectsSecretsAndSilentLoss(t *testing.T) {
	trace := fixtureTrace()
	trace.Events[0].Content = "token sk-12345678901234567890"
	if _, _, err := Prepare(trace); err == nil {
		t.Fatal("expected secret rejection")
	}
	trace = fixtureTrace()
	trace.Loss.SilentlyDroppedCount = 1
	if _, _, err := Prepare(trace); err == nil {
		t.Fatal("expected silent-loss rejection")
	}
}

func TestScoreHardConstraintAndAbstention(t *testing.T) {
	rubric := Rubric{SchemaVersion: "autoeval-rubric-v1", RubricID: "support.refund@1", TaskFamily: "support.refund", Objective: "verify eligibility", Weights: map[string]float64{"goal_progress": 0.5, "risk": 0.5}}
	a := ActionAssessment{CaseID: "case-1", CandidateID: "candidate-1", TraceID: "trace-1", Authorized: false, ValidSchema: true, Dimensions: map[string]float64{"goal_progress": 4, "risk": 4}}
	j, err := Score(rubric, a)
	if err != nil {
		t.Fatal(err)
	}
	if j.Value != 0 || len(j.HardViolations) == 0 {
		t.Fatalf("expected hard violation: %+v", j)
	}
	a.Authorized = true
	a.InsufficientState = true
	j, err = Score(rubric, a)
	if err != nil {
		t.Fatal(err)
	}
	if !j.Abstain {
		t.Fatal("expected abstention")
	}
}

func TestValidateRubricWeights(t *testing.T) {
	rubric := Rubric{SchemaVersion: "autoeval-rubric-v1", RubricID: "x", TaskFamily: "x", Objective: "x", Weights: map[string]float64{"goal": 0.9}}
	if err := ValidateRubric(rubric); err == nil {
		t.Fatal("expected weight validation error")
	}
}
