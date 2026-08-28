package autoeval

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

const (
	CanonicalTrajectoryVersion = "canonical-trajectory-v1"
	JudgmentVersion            = "autoeval-judgment-v1"
	MaxTraceEvents             = 10000
	MaxFieldBytes              = 256 * 1024
)

// Trace is the sanitized admission contract. Raw fields are accepted only as
// transient input; PreparedTrace never contains them and is the only type the
// persistence layer accepts.
type Trace struct {
	SchemaVersion   string          `json:"schema_version"`
	TraceID         string          `json:"trace_id"`
	TenantID        string          `json:"tenant_id"`
	Source          string          `json:"source"`
	SourceRevision  string          `json:"source_revision"`
	SourceDigest    string          `json:"source_digest"`
	TaskFamily      string          `json:"task_family"`
	HarnessRevision string          `json:"harness_revision"`
	ModelRevision   string          `json:"model_revision"`
	SkillRevision   string          `json:"skill_revision,omitempty"`
	KBRevision      string          `json:"kb_revision,omitempty"`
	Privacy         PrivacyReceipt  `json:"privacy"`
	Authorization   Authorization   `json:"authorization"`
	Deletion        DeletionLineage `json:"deletion"`
	Loss            LossReceipt     `json:"loss_receipt"`
	Events          []Event         `json:"events"`
	Outcome         *Outcome        `json:"outcome,omitempty"`
	CreatedAt       time.Time       `json:"created_at,omitempty"`
}

type PrivacyReceipt struct {
	ReceiptID  string `json:"receipt_id"`
	Policy     string `json:"policy"`
	Transform  string `json:"transform"`
	Version    string `json:"version"`
	RawAllowed bool   `json:"raw_allowed"`
}

type Authorization struct {
	SourceAuthorized bool   `json:"source_authorized"`
	Purpose          string `json:"purpose"`
	Actor            string `json:"actor"`
}

type DeletionLineage struct {
	SubjectID string `json:"subject_id"`
	Revision  string `json:"revision"`
	Active    bool   `json:"active"`
}

type LossReceipt struct {
	SourceEventCount     int      `json:"source_event_count"`
	CanonicalEventCount  int      `json:"canonical_event_count"`
	SilentlyDroppedCount int      `json:"silently_dropped_event_count"`
	ReconstructedFields  []string `json:"reconstructed_fields,omitempty"`
	KnownMissingFields   []string `json:"known_missing_fields,omitempty"`
}

type Event struct {
	EventID         string          `json:"event_id"`
	TraceID         string          `json:"trace_id"`
	Sequence        int             `json:"sequence"`
	ParentEventID   string          `json:"parent_event_id,omitempty"`
	Kind            string          `json:"kind"`
	Observation     string          `json:"observation_status"`
	SourceRole      string          `json:"source_role"`
	ToolName        string          `json:"tool_name,omitempty"`
	SkillName       string          `json:"skill_name,omitempty"`
	KnowledgeBase   string          `json:"knowledge_base,omitempty"`
	Content         string          `json:"content,omitempty"`   // transient; never persisted
	Arguments       json.RawMessage `json:"arguments,omitempty"` // transient; never persisted
	Result          json.RawMessage `json:"result,omitempty"`    // transient; never persisted
	ContentDigest   string          `json:"content_digest,omitempty"`
	ArgumentsDigest string          `json:"arguments_digest,omitempty"`
	ResultDigest    string          `json:"result_digest,omitempty"`
	ObservedAt      time.Time       `json:"observed_at,omitempty"`
}

type Outcome struct {
	Status     string `json:"status"`
	EvidenceID string `json:"evidence_id"`
	Observed   bool   `json:"observed"`
	Success    *bool  `json:"success,omitempty"`
}

type PreparedTrace struct {
	SchemaVersion   string
	TraceID         string
	TenantID        string
	Source          string
	SourceRevision  string
	SourceDigest    string
	TaskFamily      string
	HarnessRevision string
	ModelRevision   string
	SkillRevision   string
	KBRevision      string
	PrivacyReceipt  string
	LossReceipt     string
	DeletionSubject string
	OutcomeStatus   string
	OutcomeObserved bool
	Eligible        bool
	Events          []PreparedEvent
	CreatedAt       time.Time
}

type PreparedEvent struct {
	TraceID         string
	EventID         string
	Sequence        int
	ParentEventID   string
	Kind            string
	Observation     string
	SourceRole      string
	ToolName        string
	SkillName       string
	KnowledgeBase   string
	ContentDigest   string
	ArgumentsDigest string
	ResultDigest    string
	ObservedAt      time.Time
}

type AdmissionReport struct {
	Eligible          bool     `json:"eligible"`
	OutcomeMissing    bool     `json:"outcome_missing"`
	RedactedFields    int      `json:"redacted_fields"`
	RejectedFields    []string `json:"rejected_fields,omitempty"`
	AbstentionReasons []string `json:"abstention_reasons,omitempty"`
}

type Rubric struct {
	SchemaVersion   string             `json:"schema_version"`
	RubricID        string             `json:"rubric_id"`
	TaskFamily      string             `json:"task_family"`
	Objective       string             `json:"objective"`
	HardConstraints []string           `json:"hard_constraints,omitempty"`
	Weights         map[string]float64 `json:"weights"`
	AbstainWhen     []string           `json:"abstain_when,omitempty"`
}

type ActionAssessment struct {
	CaseID            string             `json:"case_id"`
	CandidateID       string             `json:"candidate_id"`
	TraceID           string             `json:"trace_id"`
	ActionType        string             `json:"action_type"`
	ToolName          string             `json:"tool_name,omitempty"`
	SkillName         string             `json:"skill_name,omitempty"`
	KBQuery           string             `json:"kb_query,omitempty"` // transient; never persisted
	Authorized        bool               `json:"authorized"`
	ValidSchema       bool               `json:"valid_schema"`
	FutureLeak        bool               `json:"future_leak"`
	InsufficientState bool               `json:"insufficient_state"`
	HardViolations    []string           `json:"hard_violations,omitempty"`
	Dimensions        map[string]float64 `json:"dimensions"`
	EvidenceEventIDs  []string           `json:"evidence_event_ids"`
}

type Judgment struct {
	SchemaVersion    string             `json:"schema_version"`
	CaseID           string             `json:"case_id"`
	CandidateID      string             `json:"candidate_id"`
	TraceID          string             `json:"trace_id"`
	RubricID         string             `json:"rubric_id"`
	Value            int                `json:"value"`
	Confidence       float64            `json:"confidence"`
	Abstain          bool               `json:"abstain"`
	HardViolations   []string           `json:"hard_violations,omitempty"`
	DimensionScores  map[string]float64 `json:"dimension_scores,omitempty"`
	EvidenceEventIDs []string           `json:"evidence_event_ids"`
	ReasonCodes      []string           `json:"reason_codes,omitempty"`
	CreatedAt        time.Time          `json:"created_at"`
}

type EvaluationReport struct {
	TenantID           string      `json:"tenant_id"`
	TraceID            string      `json:"trace_id,omitempty"`
	JudgmentCount      int         `json:"judgment_count"`
	ScoredCount        int         `json:"scored_count"`
	AbstentionCount    int         `json:"abstention_count"`
	HardViolationCount int         `json:"hard_violation_count"`
	MeanValue          float64     `json:"mean_value"`
	ValueHistogram     map[int]int `json:"value_histogram"`
}

func DigestBytes(b []byte) string {
	sum := sha256.Sum256(b)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func DigestString(s string) string { return DigestBytes([]byte(s)) }

func normalizedDigest(raw []byte) string {
	return DigestBytes([]byte(strings.TrimSpace(string(raw))))
}

func receiptDigest(t Trace) string {
	b, _ := json.Marshal(struct {
		Privacy PrivacyReceipt  `json:"privacy"`
		Loss    LossReceipt     `json:"loss"`
		Delete  DeletionLineage `json:"deletion"`
	}{t.Privacy, t.Loss, t.Deletion})
	return normalizedDigest(b)
}

func (t Trace) validateEnvelope() error {
	if t.SchemaVersion != CanonicalTrajectoryVersion {
		return fmt.Errorf("schema_version must be %q", CanonicalTrajectoryVersion)
	}
	for name, value := range map[string]string{
		"trace_id": t.TraceID, "tenant_id": t.TenantID, "source": t.Source,
		"source_revision": t.SourceRevision, "source_digest": t.SourceDigest,
		"task_family": t.TaskFamily, "harness_revision": t.HarnessRevision,
		"model_revision": t.ModelRevision, "privacy.receipt_id": t.Privacy.ReceiptID,
		"privacy.policy": t.Privacy.Policy, "privacy.transform": t.Privacy.Transform,
		"authorization.purpose": t.Authorization.Purpose, "deletion.subject_id": t.Deletion.SubjectID,
		"deletion.revision": t.Deletion.Revision,
	} {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", name)
		}
	}
	if !t.Authorization.SourceAuthorized {
		return fmt.Errorf("source_authorized must be true")
	}
	if !t.Deletion.Active {
		return fmt.Errorf("deletion lineage is inactive")
	}
	if t.Privacy.RawAllowed {
		return fmt.Errorf("raw_allowed must be false for analytics admission")
	}
	if len(t.Events) == 0 || len(t.Events) > MaxTraceEvents {
		return fmt.Errorf("events must contain 1..%d entries", MaxTraceEvents)
	}
	if t.Loss.SilentlyDroppedCount != 0 {
		return fmt.Errorf("silent projection loss is not admissible")
	}
	return nil
}
