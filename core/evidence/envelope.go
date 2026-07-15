// Package evidence defines the canonical schema contract for agent evidence.
package evidence

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"regexp"
	"strings"
	"time"
)

const VersionV1 = "agent-evidence-envelope/v1"

const (
	maxIDLen             = 128
	maxRevisionLen       = 256
	maxReasonCodeLen     = 64
	maxMediaTypeLen      = 128
	maxACLReaders        = 64
	maxDerivedArtifacts  = 64
	maxContentReferences = 16
	maxGatewayRequestIDs = 64
	maxBehavioralSignals = 32
	maxJudgeScores       = 32
	maxBehavioralCount   = 1_000_000
	maxPerceivedScore    = 100
	maxJSONEnvelopeBytes = 1 << 20
)

var (
	safeTokenRe     = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:@/+~-]*$`)
	safeCodeRe      = regexp.MustCompile(`^[a-z][a-z0-9_-]*$`)
	safeDigestRe    = regexp.MustCompile(`^sha256:[a-fA-F0-9]{6,128}$`)
	safeVaultURIRe  = regexp.MustCompile(`^vault://[A-Za-z0-9][A-Za-z0-9._:@/+~-]{0,240}$`)
	safeMediaTypeRe = regexp.MustCompile(`^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$`)
)

type ProducerKind string

const (
	ProducerGateway   ProducerKind = "gateway"
	ProducerCollector ProducerKind = "collector"
	ProducerEvaluator ProducerKind = "evaluator"
)

type EvidencePurpose string

const (
	PurposeOperations EvidencePurpose = "operations"
	PurposeEvaluation EvidencePurpose = "evaluation"
	PurposeRecall     EvidencePurpose = "recall"
	PurposeProposal   EvidencePurpose = "proposal"
	PurposeAudit      EvidencePurpose = "audit"
)

type SubjectKind string

const (
	SubjectUser       SubjectKind = "user"
	SubjectService    SubjectKind = "service"
	SubjectTeam       SubjectKind = "team"
	SubjectRepository SubjectKind = "repository"
)

type Visibility string

const (
	VisibilityPrivate Visibility = "private"
	VisibilityTeam    Visibility = "team"
	VisibilityTenant  Visibility = "tenant"
)

type PrivacyDisposition string

const (
	PrivacyMetadataOnly PrivacyDisposition = "metadata_only"
	PrivacyRedacted     PrivacyDisposition = "redacted"
	PrivacyDerivedOnly  PrivacyDisposition = "derived_only"
	PrivacyVaultOnly    PrivacyDisposition = "vault_only"
)

type SamplingDecision string

const (
	SamplingIncluded SamplingDecision = "included"
	SamplingExcluded SamplingDecision = "excluded"
)

type MissingnessStatus string

const (
	MissingnessComplete MissingnessStatus = "complete"
	MissingnessPartial  MissingnessStatus = "partial"
	MissingnessAbsent   MissingnessStatus = "absent"
)

type DeletionState string

const (
	DeletionActive      DeletionState = "active"
	DeletionTombstoned  DeletionState = "tombstoned"
	DeletionPending     DeletionState = "pending"
	DeletionLegalHold   DeletionState = "legal_hold"
	DeletionCryptoShred DeletionState = "crypto_shredded"
)

type ObservationType string

const (
	ObservationGatewayAttempt     ObservationType = "gateway_attempt"
	ObservationTerminalOutcome    ObservationType = "terminal_outcome"
	ObservationDeterministicTest  ObservationType = "deterministic_test"
	ObservationUserReport         ObservationType = "user_report"
	ObservationBehavioralFriction ObservationType = "behavioral_friction"
	ObservationPerceivedFriction  ObservationType = "perceived_friction"
	ObservationJudgeEvidence      ObservationType = "judge_evidence"
)

type AttemptOutcome string

const (
	AttemptSucceeded AttemptOutcome = "succeeded"
	AttemptFailed    AttemptOutcome = "failed"
	AttemptCancelled AttemptOutcome = "cancelled"
)

type TerminalOutcome string

const (
	TerminalOutcomeSucceeded TerminalOutcome = "succeeded"
	TerminalOutcomeFailed    TerminalOutcome = "failed"
	TerminalOutcomeAbandoned TerminalOutcome = "abandoned"
	TerminalOutcomeUnknown   TerminalOutcome = "unknown"
)

type TerminalOutcomeSource string

const (
	TerminalOutcomeCollector TerminalOutcomeSource = "collector"
	TerminalOutcomeUser      TerminalOutcomeSource = "user"
	TerminalOutcomeCI        TerminalOutcomeSource = "ci"
)

type TestStatus string

const (
	TestPassed  TestStatus = "passed"
	TestFailed  TestStatus = "failed"
	TestSkipped TestStatus = "skipped"
)

type UserReportType string

const (
	UserReportCorrection UserReportType = "correction"
	UserReportApproval   UserReportType = "approval"
	UserReportRejection  UserReportType = "rejection"
	UserReportEscalation UserReportType = "escalation"
)

type BehavioralSignalType string

const (
	BehavioralRetry       BehavioralSignalType = "retry"
	BehavioralRegenerate  BehavioralSignalType = "regenerate"
	BehavioralToolFailure BehavioralSignalType = "tool_failure"
	BehavioralAbandonment BehavioralSignalType = "abandonment"
	BehavioralEscalation  BehavioralSignalType = "escalation"
)

type PerceivedFrictionScale string

const (
	PerceivedEase       PerceivedFrictionScale = "ease"
	PerceivedTrust      PerceivedFrictionScale = "trust"
	PerceivedConfidence PerceivedFrictionScale = "confidence"
	PerceivedEffort     PerceivedFrictionScale = "effort"
)

type JudgeOutcome string

const (
	JudgePassed       JudgeOutcome = "passed"
	JudgeFailed       JudgeOutcome = "failed"
	JudgeInconclusive JudgeOutcome = "inconclusive"
)

type ContentTier string

const (
	ContentMetadataOnly  ContentTier = "metadata_only"
	ContentRedacted      ContentTier = "redacted"
	ContentDerivedDigest ContentTier = "derived_digest"
	ContentVaultRef      ContentTier = "vault_ref"
)

type AgentEvidenceEnvelope struct {
	Version     string           `json:"version"`
	ID          string           `json:"id"`
	ObservedAt  time.Time        `json:"observed_at"`
	Producer    ProducerRef      `json:"producer"`
	Tenant      TenantScope      `json:"tenant"`
	Privacy     PrivacyReceipt   `json:"privacy"`
	Sampling    SamplingInfo     `json:"sampling"`
	Missingness MissingnessInfo  `json:"missingness"`
	Deletion    DeletionLineage  `json:"deletion"`
	Revisions   RevisionJoinKeys `json:"revisions"`
	Observation Observation      `json:"observation"`
}

type ProducerRef struct {
	Kind     ProducerKind `json:"kind"`
	ID       string       `json:"id"`
	Revision string       `json:"revision"`
}

type TenantScope struct {
	TenantID  string          `json:"tenant_id"`
	Purpose   EvidencePurpose `json:"purpose"`
	Residency string          `json:"residency"`
	Subject   SubjectRef      `json:"subject"`
	ACL       AccessControl   `json:"acl"`
}

type SubjectRef struct {
	Kind SubjectKind `json:"kind"`
	ID   string      `json:"id"`
}

type AccessControl struct {
	Visibility Visibility `json:"visibility"`
	Readers    []string   `json:"readers"`
}

type PrivacyReceipt struct {
	ID                string             `json:"id"`
	PolicyRevision    string             `json:"policy_revision"`
	TransformRevision string             `json:"transform_revision"`
	Disposition       PrivacyDisposition `json:"disposition"`
	RetentionClass    string             `json:"retention_class"`
	DeletionPolicyID  string             `json:"deletion_policy_id"`
}

type SamplingInfo struct {
	Decision SamplingDecision `json:"decision"`
	Rate     float64          `json:"rate"`
	Seed     string           `json:"seed"`
}

type MissingnessInfo struct {
	Status MissingnessStatus `json:"status"`
	Reason string            `json:"reason,omitempty"`
}

type DeletionLineage struct {
	LineageID        string        `json:"lineage_id"`
	DeletionState    DeletionState `json:"deletion_state"`
	SubjectToDelete  bool          `json:"subject_to_delete"`
	DerivedArtifacts []string      `json:"derived_artifacts,omitempty"`
}

type RevisionJoinKeys struct {
	Authority    string `json:"authority"`
	Policy       string `json:"policy"`
	Privacy      string `json:"privacy"`
	Route        string `json:"route,omitempty"`
	Gateway      string `json:"gateway,omitempty"`
	Collector    string `json:"collector,omitempty"`
	TestHarness  string `json:"test_harness,omitempty"`
	Judge        string `json:"judge,omitempty"`
	Evaluator    string `json:"evaluator,omitempty"`
	Skill        string `json:"skill,omitempty"`
	Tool         string `json:"tool,omitempty"`
	ModelCatalog string `json:"model_catalog,omitempty"`
}

type Observation struct {
	Type               ObservationType             `json:"type"`
	Content            []ContentReference          `json:"content,omitempty"`
	GatewayAttempt     *GatewayAttemptEvidence     `json:"gateway_attempt,omitempty"`
	TerminalOutcome    *TerminalOutcomeEvidence    `json:"terminal_outcome,omitempty"`
	DeterministicTest  *DeterministicTestEvidence  `json:"deterministic_test,omitempty"`
	UserReport         *UserReportEvidence         `json:"user_report,omitempty"`
	BehavioralFriction *BehavioralFrictionEvidence `json:"behavioral_friction,omitempty"`
	PerceivedFriction  *PerceivedFrictionEvidence  `json:"perceived_friction,omitempty"`
	JudgeEvidence      *JudgeEvidence              `json:"judge_evidence,omitempty"`
}

type GatewayAttemptEvidence struct {
	RequestID    string         `json:"request_id"`
	AttemptID    string         `json:"attempt_id"`
	Provider     string         `json:"provider"`
	Model        string         `json:"model"`
	RequestType  string         `json:"request_type"`
	Outcome      AttemptOutcome `json:"outcome"`
	FallbackSlot int            `json:"fallback_slot"`
}

type TerminalOutcomeEvidence struct {
	SessionID         string                `json:"session_id"`
	TaskID            string                `json:"task_id"`
	Outcome           TerminalOutcome       `json:"outcome"`
	Source            TerminalOutcomeSource `json:"source"`
	CompletedAt       time.Time             `json:"completed_at"`
	GatewayRequestIDs []string              `json:"gateway_request_ids,omitempty"`
}

type DeterministicTestEvidence struct {
	RunID            string     `json:"run_id"`
	Suite            string     `json:"suite"`
	Case             string     `json:"case"`
	Status           TestStatus `json:"status"`
	ToolRevision     string     `json:"tool_revision"`
	ArtifactDigest   string     `json:"artifact_digest"`
	TranscriptDigest string     `json:"transcript_digest,omitempty"`
}

type UserReportEvidence struct {
	ReportID            string         `json:"report_id"`
	ReportType          UserReportType `json:"report_type"`
	ReasonCode          string         `json:"reason_code"`
	TargetObservationID string         `json:"target_observation_id,omitempty"`
}

type BehavioralFrictionEvidence struct {
	WindowID string             `json:"window_id"`
	Signals  []BehavioralSignal `json:"signals"`
}

type BehavioralSignal struct {
	Type  BehavioralSignalType `json:"type"`
	Count int                  `json:"count"`
}

type PerceivedFrictionEvidence struct {
	InstrumentID string                 `json:"instrument_id"`
	Scale        PerceivedFrictionScale `json:"scale"`
	Score        float64                `json:"score"`
	MaxScore     float64                `json:"max_score"`
}

type JudgeEvidence struct {
	JudgeID           string             `json:"judge_id"`
	RubricRevision    string             `json:"rubric_revision"`
	Outcome           JudgeOutcome       `json:"outcome"`
	Scores            map[string]float64 `json:"scores,omitempty"`
	ExplanationDigest string             `json:"explanation_digest,omitempty"`
}

type ContentReference struct {
	Tier      ContentTier `json:"tier"`
	Digest    string      `json:"digest"`
	VaultURI  string      `json:"vault_uri,omitempty"`
	MediaType string      `json:"media_type,omitempty"`
}

func DecodeStrict(data []byte) (AgentEvidenceEnvelope, error) {
	if len(data) > maxJSONEnvelopeBytes {
		return AgentEvidenceEnvelope{}, fmt.Errorf("evidence envelope exceeds %d bytes", maxJSONEnvelopeBytes)
	}
	if err := rejectDuplicateKeys(data); err != nil {
		return AgentEvidenceEnvelope{}, err
	}
	var env AgentEvidenceEnvelope
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&env); err != nil {
		return AgentEvidenceEnvelope{}, err
	}
	var extra struct{}
	if err := dec.Decode(&extra); err != io.EOF {
		if err == nil {
			return AgentEvidenceEnvelope{}, errors.New("multiple JSON values are not allowed")
		}
		return AgentEvidenceEnvelope{}, err
	}
	if dec.More() {
		return AgentEvidenceEnvelope{}, errors.New("multiple JSON values are not allowed")
	}
	if err := env.Validate(); err != nil {
		return AgentEvidenceEnvelope{}, err
	}
	return env, nil
}

func EncodeCanonical(env AgentEvidenceEnvelope) ([]byte, error) {
	if err := env.Validate(); err != nil {
		return nil, err
	}
	return json.Marshal(env)
}

func (e AgentEvidenceEnvelope) Validate() error {
	if e.Version != VersionV1 {
		return fmt.Errorf("unsupported evidence envelope version %q", e.Version)
	}
	if err := requireSafeToken("evidence envelope id", e.ID, maxIDLen); err != nil {
		return err
	}
	if e.ObservedAt.IsZero() {
		return errors.New("observed_at is required")
	}
	if err := e.Producer.validate(); err != nil {
		return err
	}
	if err := e.Tenant.validate(); err != nil {
		return err
	}
	if err := e.Privacy.validate(); err != nil {
		return err
	}
	if err := e.Sampling.validate(); err != nil {
		return err
	}
	if err := e.Missingness.validate(); err != nil {
		return err
	}
	if err := e.Deletion.validate(); err != nil {
		return err
	}
	if err := e.Revisions.validate(); err != nil {
		return err
	}
	return e.Observation.validate(e.Privacy.Disposition)
}

func (p ProducerRef) validate() error {
	if !validProducerKind(p.Kind) {
		return fmt.Errorf("unsupported producer kind %q", p.Kind)
	}
	if err := requireSafeToken("producer id", p.ID, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("producer revision", p.Revision, maxRevisionLen); err != nil {
		return err
	}
	return nil
}

func (t TenantScope) validate() error {
	if err := requireSafeToken("tenant id", t.TenantID, maxIDLen); err != nil {
		return err
	}
	if !validEvidencePurpose(t.Purpose) {
		return fmt.Errorf("unsupported evidence purpose %q", t.Purpose)
	}
	if err := requireSafeToken("residency", t.Residency, 32); err != nil {
		return err
	}
	if !validSubjectKind(t.Subject.Kind) {
		return fmt.Errorf("unsupported subject kind %q", t.Subject.Kind)
	}
	if err := requireSafeToken("subject id", t.Subject.ID, maxIDLen); err != nil {
		return err
	}
	if !validVisibility(t.ACL.Visibility) {
		return fmt.Errorf("unsupported acl visibility %q", t.ACL.Visibility)
	}
	if len(t.ACL.Readers) == 0 {
		return errors.New("acl readers are required")
	}
	if len(t.ACL.Readers) > maxACLReaders {
		return fmt.Errorf("acl readers exceed maximum %d", maxACLReaders)
	}
	for i, reader := range t.ACL.Readers {
		if err := requireSafeToken(fmt.Sprintf("acl reader[%d]", i), reader, maxIDLen); err != nil {
			return err
		}
	}
	return nil
}

func (p PrivacyReceipt) validate() error {
	if err := requireSafeToken("privacy receipt id", p.ID, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("privacy policy revision", p.PolicyRevision, maxRevisionLen); err != nil {
		return err
	}
	if err := requireSafeToken("privacy transform revision", p.TransformRevision, maxRevisionLen); err != nil {
		return err
	}
	if !validPrivacyDisposition(p.Disposition) {
		return fmt.Errorf("unsupported privacy disposition %q", p.Disposition)
	}
	if err := requireSafeToken("privacy retention class", p.RetentionClass, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("privacy deletion policy id", p.DeletionPolicyID, maxIDLen); err != nil {
		return err
	}
	return nil
}

func (s SamplingInfo) validate() error {
	if !validSamplingDecision(s.Decision) {
		return fmt.Errorf("unsupported sampling decision %q", s.Decision)
	}
	if s.Rate < 0 || s.Rate > 1 {
		return errors.New("sampling rate must be between 0 and 1")
	}
	if s.Seed != "" {
		if err := requireSafeToken("sampling seed", s.Seed, maxIDLen); err != nil {
			return err
		}
	}
	return nil
}

func (m MissingnessInfo) validate() error {
	if !validMissingnessStatus(m.Status) {
		return fmt.Errorf("unsupported missingness status %q", m.Status)
	}
	if m.Reason != "" {
		if err := requireSafeCode("missingness reason", m.Reason, maxReasonCodeLen); err != nil {
			return err
		}
	}
	return nil
}

func (d DeletionLineage) validate() error {
	if err := requireSafeToken("deletion lineage id", d.LineageID, maxIDLen); err != nil {
		return err
	}
	if !validDeletionState(d.DeletionState) {
		return fmt.Errorf("unsupported deletion state %q", d.DeletionState)
	}
	if len(d.DerivedArtifacts) > maxDerivedArtifacts {
		return fmt.Errorf("derived artifacts exceed maximum %d", maxDerivedArtifacts)
	}
	for i, artifact := range d.DerivedArtifacts {
		if err := requireSafeToken(fmt.Sprintf("derived artifact[%d]", i), artifact, maxRevisionLen); err != nil {
			return err
		}
	}
	return nil
}

func (r RevisionJoinKeys) validate() error {
	if err := requireSafeToken("authority revision", r.Authority, maxRevisionLen); err != nil {
		return err
	}
	if err := requireSafeToken("policy revision", r.Policy, maxRevisionLen); err != nil {
		return err
	}
	if err := requireSafeToken("privacy revision", r.Privacy, maxRevisionLen); err != nil {
		return err
	}
	if r.Route == "" && r.Gateway == "" && r.Collector == "" && r.TestHarness == "" && r.Judge == "" && r.Evaluator == "" && r.Skill == "" && r.Tool == "" && r.ModelCatalog == "" {
		return errors.New("at least one immutable source revision join key is required")
	}
	optional := map[string]string{
		"route revision":         r.Route,
		"gateway revision":       r.Gateway,
		"collector revision":     r.Collector,
		"test harness revision":  r.TestHarness,
		"judge revision":         r.Judge,
		"evaluator revision":     r.Evaluator,
		"skill revision":         r.Skill,
		"tool revision":          r.Tool,
		"model catalog revision": r.ModelCatalog,
	}
	for name, value := range optional {
		if value == "" {
			continue
		}
		if err := requireSafeToken(name, value, maxRevisionLen); err != nil {
			return err
		}
	}
	return nil
}

func (o Observation) validate(disposition PrivacyDisposition) error {
	if err := validateContentReferences(o.Content); err != nil {
		return err
	}
	if err := validatePrivacyDispositionContent(disposition, o.Content); err != nil {
		return err
	}
	bodyCount := 0
	if o.GatewayAttempt != nil {
		bodyCount++
	}
	if o.TerminalOutcome != nil {
		bodyCount++
	}
	if o.DeterministicTest != nil {
		bodyCount++
	}
	if o.UserReport != nil {
		bodyCount++
	}
	if o.BehavioralFriction != nil {
		bodyCount++
	}
	if o.PerceivedFriction != nil {
		bodyCount++
	}
	if o.JudgeEvidence != nil {
		bodyCount++
	}
	if bodyCount != 1 {
		return fmt.Errorf("exactly one observation body is required, got %d", bodyCount)
	}

	switch o.Type {
	case ObservationGatewayAttempt:
		if o.GatewayAttempt == nil {
			return errors.New("gateway attempt evidence is required")
		}
		return o.GatewayAttempt.validate()
	case ObservationTerminalOutcome:
		if o.TerminalOutcome == nil {
			return errors.New("terminal outcome evidence is required")
		}
		return o.TerminalOutcome.validate()
	case ObservationDeterministicTest:
		if o.DeterministicTest == nil {
			return errors.New("deterministic test evidence is required")
		}
		return o.DeterministicTest.validate()
	case ObservationUserReport:
		if o.UserReport == nil {
			return errors.New("user report evidence is required")
		}
		return o.UserReport.validate()
	case ObservationBehavioralFriction:
		if o.BehavioralFriction == nil {
			return errors.New("behavioral friction evidence is required")
		}
		return o.BehavioralFriction.validate()
	case ObservationPerceivedFriction:
		if o.PerceivedFriction == nil {
			return errors.New("perceived friction evidence is required")
		}
		return o.PerceivedFriction.validate()
	case ObservationJudgeEvidence:
		if o.JudgeEvidence == nil {
			return errors.New("judge evidence is required")
		}
		return o.JudgeEvidence.validate()
	default:
		return fmt.Errorf("unsupported observation type %q", o.Type)
	}
}

func validateContentReferences(refs []ContentReference) error {
	if len(refs) > maxContentReferences {
		return fmt.Errorf("content references exceed maximum %d", maxContentReferences)
	}
	for i, ref := range refs {
		switch ref.Tier {
		case ContentMetadataOnly:
			if ref.Digest != "" || ref.VaultURI != "" {
				return errors.New("metadata-only content references cannot carry digest or vault uri")
			}
		case ContentRedacted, ContentDerivedDigest:
			if err := requireSafeDigest(fmt.Sprintf("content[%d].digest", i), ref.Digest); err != nil {
				return err
			}
			if ref.VaultURI != "" {
				return errors.New("redacted and derived content references cannot carry vault uri")
			}
		case ContentVaultRef:
			if err := requireSafeDigest(fmt.Sprintf("content[%d].digest", i), ref.Digest); err != nil {
				return err
			}
			if err := requireSafeVaultURI(fmt.Sprintf("content[%d].vault_uri", i), ref.VaultURI); err != nil {
				return err
			}
		default:
			return fmt.Errorf("unsupported or raw content tier %q", ref.Tier)
		}
		if ref.MediaType != "" {
			if err := requireSafeMediaType(fmt.Sprintf("content[%d].media_type", i), ref.MediaType); err != nil {
				return err
			}
		}
	}
	return nil
}

func (g GatewayAttemptEvidence) validate() error {
	if err := requireSafeToken("gateway attempt request id", g.RequestID, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("gateway attempt attempt id", g.AttemptID, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("gateway attempt provider", g.Provider, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("gateway attempt model", g.Model, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("gateway attempt request type", g.RequestType, maxIDLen); err != nil {
		return err
	}
	if !validAttemptOutcome(g.Outcome) {
		return fmt.Errorf("unsupported attempt outcome %q", g.Outcome)
	}
	if g.FallbackSlot < 0 || g.FallbackSlot > 64 {
		return errors.New("fallback slot must be between 0 and 64")
	}
	return nil
}

func (t TerminalOutcomeEvidence) validate() error {
	if err := requireSafeToken("terminal outcome session id", t.SessionID, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("terminal outcome task id", t.TaskID, maxIDLen); err != nil {
		return err
	}
	if !validTerminalOutcome(t.Outcome) {
		return fmt.Errorf("unsupported terminal outcome %q", t.Outcome)
	}
	if !validTerminalOutcomeSource(t.Source) {
		return fmt.Errorf("unsupported terminal outcome source %q", t.Source)
	}
	if t.CompletedAt.IsZero() {
		return errors.New("terminal outcome completion time is required")
	}
	if len(t.GatewayRequestIDs) > maxGatewayRequestIDs {
		return fmt.Errorf("gateway request ids exceed maximum %d", maxGatewayRequestIDs)
	}
	for i, id := range t.GatewayRequestIDs {
		if err := requireSafeToken(fmt.Sprintf("gateway request id[%d]", i), id, maxIDLen); err != nil {
			return err
		}
	}
	return nil
}

func (d DeterministicTestEvidence) validate() error {
	if err := requireSafeToken("deterministic test run id", d.RunID, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("deterministic test suite", d.Suite, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("deterministic test case", d.Case, maxIDLen); err != nil {
		return err
	}
	if !validTestStatus(d.Status) {
		return fmt.Errorf("unsupported deterministic test status %q", d.Status)
	}
	if err := requireSafeToken("deterministic test tool revision", d.ToolRevision, maxRevisionLen); err != nil {
		return err
	}
	if err := requireSafeDigest("deterministic test artifact digest", d.ArtifactDigest); err != nil {
		return err
	}
	if d.TranscriptDigest != "" {
		if err := requireSafeDigest("deterministic test transcript digest", d.TranscriptDigest); err != nil {
			return err
		}
	}
	return nil
}

func (u UserReportEvidence) validate() error {
	if err := requireSafeToken("user report id", u.ReportID, maxIDLen); err != nil {
		return err
	}
	if !validUserReportType(u.ReportType) {
		return fmt.Errorf("unsupported user report type %q", u.ReportType)
	}
	if err := requireSafeCode("user report reason code", u.ReasonCode, maxReasonCodeLen); err != nil {
		return err
	}
	if u.TargetObservationID != "" {
		if err := requireSafeToken("user report target observation id", u.TargetObservationID, maxIDLen); err != nil {
			return err
		}
	}
	return nil
}

func (b BehavioralFrictionEvidence) validate() error {
	if err := requireSafeToken("behavioral friction window id", b.WindowID, maxIDLen); err != nil {
		return err
	}
	if len(b.Signals) == 0 {
		return errors.New("behavioral friction requires at least one signal")
	}
	if len(b.Signals) > maxBehavioralSignals {
		return fmt.Errorf("behavioral friction signals exceed maximum %d", maxBehavioralSignals)
	}
	for i, signal := range b.Signals {
		if !validBehavioralSignalType(signal.Type) {
			return fmt.Errorf("unsupported behavioral signal type %q", signal.Type)
		}
		if signal.Count <= 0 || signal.Count > maxBehavioralCount {
			return fmt.Errorf("behavioral friction signal[%d] count must be between 1 and %d", i, maxBehavioralCount)
		}
	}
	return nil
}

func (p PerceivedFrictionEvidence) validate() error {
	if err := requireSafeToken("perceived friction instrument id", p.InstrumentID, maxIDLen); err != nil {
		return err
	}
	if !validPerceivedFrictionScale(p.Scale) {
		return fmt.Errorf("unsupported perceived friction scale %q", p.Scale)
	}
	if p.MaxScore <= 0 || p.MaxScore > maxPerceivedScore || p.Score < 0 || p.Score > p.MaxScore {
		return errors.New("perceived friction score must be between 0 and max score")
	}
	return nil
}

func (j JudgeEvidence) validate() error {
	if err := requireSafeToken("judge id", j.JudgeID, maxIDLen); err != nil {
		return err
	}
	if err := requireSafeToken("judge rubric revision", j.RubricRevision, maxRevisionLen); err != nil {
		return err
	}
	if !validJudgeOutcome(j.Outcome) {
		return fmt.Errorf("unsupported judge outcome %q", j.Outcome)
	}
	if len(j.Scores) > maxJudgeScores {
		return fmt.Errorf("judge scores exceed maximum %d", maxJudgeScores)
	}
	for name, score := range j.Scores {
		if err := requireSafeCode("judge score name", name, maxReasonCodeLen); err != nil {
			return err
		}
		if score < 0 || score > 1 {
			return errors.New("judge scores must be between 0 and 1")
		}
	}
	if j.ExplanationDigest != "" {
		if err := requireSafeDigest("judge explanation digest", j.ExplanationDigest); err != nil {
			return err
		}
	}
	return nil
}

func validatePrivacyDispositionContent(disposition PrivacyDisposition, refs []ContentReference) error {
	for _, ref := range refs {
		switch disposition {
		case PrivacyMetadataOnly:
			return errors.New("metadata-only privacy disposition cannot carry content references")
		case PrivacyRedacted:
			if ref.Tier != ContentRedacted && ref.Tier != ContentDerivedDigest {
				return fmt.Errorf("privacy disposition %q cannot carry content tier %q", disposition, ref.Tier)
			}
		case PrivacyDerivedOnly:
			if ref.Tier != ContentDerivedDigest {
				return fmt.Errorf("privacy disposition %q cannot carry content tier %q", disposition, ref.Tier)
			}
		case PrivacyVaultOnly:
			if ref.Tier != ContentVaultRef {
				return fmt.Errorf("privacy disposition %q cannot carry content tier %q", disposition, ref.Tier)
			}
		default:
			return fmt.Errorf("unsupported privacy disposition %q", disposition)
		}
	}
	return nil
}

func rejectDuplicateKeys(data []byte) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	if err := scanJSONValue(dec, "$"); err != nil {
		return err
	}
	if _, err := dec.Token(); err != io.EOF {
		if err == nil {
			return errors.New("multiple JSON values are not allowed")
		}
		return err
	}
	return nil
}

func scanJSONValue(dec *json.Decoder, path string) error {
	tok, err := dec.Token()
	if err != nil {
		return err
	}
	delim, ok := tok.(json.Delim)
	if !ok {
		return nil
	}
	switch delim {
	case '{':
		seen := make(map[string]struct{})
		for dec.More() {
			keyTok, err := dec.Token()
			if err != nil {
				return err
			}
			key, ok := keyTok.(string)
			if !ok {
				return fmt.Errorf("object key at %s is not a string", path)
			}
			if _, exists := seen[key]; exists {
				return fmt.Errorf("duplicate JSON key %q at %s", key, path)
			}
			seen[key] = struct{}{}
			if err := scanJSONValue(dec, path+"."+key); err != nil {
				return err
			}
		}
		closeTok, err := dec.Token()
		if err != nil {
			return err
		}
		if closeTok != json.Delim('}') {
			return fmt.Errorf("expected object close at %s", path)
		}
	case '[':
		idx := 0
		for dec.More() {
			if err := scanJSONValue(dec, fmt.Sprintf("%s[%d]", path, idx)); err != nil {
				return err
			}
			idx++
		}
		closeTok, err := dec.Token()
		if err != nil {
			return err
		}
		if closeTok != json.Delim(']') {
			return fmt.Errorf("expected array close at %s", path)
		}
	default:
		return fmt.Errorf("unexpected delimiter %q at %s", delim, path)
	}
	return nil
}

func requireSafeToken(name, value string, maxLen int) error {
	if value == "" {
		return fmt.Errorf("%s is required", name)
	}
	if len(value) > maxLen {
		return fmt.Errorf("%s exceeds maximum length %d", name, maxLen)
	}
	if !safeTokenRe.MatchString(value) {
		return fmt.Errorf("%s contains unsafe characters", name)
	}
	if looksLikeRawContent(value) {
		return fmt.Errorf("%s looks like raw content", name)
	}
	return nil
}

func requireSafeCode(name, value string, maxLen int) error {
	if value == "" {
		return fmt.Errorf("%s is required", name)
	}
	if len(value) > maxLen {
		return fmt.Errorf("%s exceeds maximum length %d", name, maxLen)
	}
	if !safeCodeRe.MatchString(value) {
		return fmt.Errorf("%s must be a safe code", name)
	}
	if looksLikeRawContent(value) {
		return fmt.Errorf("%s looks like raw content", name)
	}
	return nil
}

func requireSafeDigest(name, value string) error {
	if value == "" {
		return fmt.Errorf("%s is required", name)
	}
	if !safeDigestRe.MatchString(value) {
		return fmt.Errorf("%s must be a sha256 digest reference", name)
	}
	return nil
}

func requireSafeVaultURI(name, value string) error {
	if value == "" {
		return fmt.Errorf("%s is required", name)
	}
	if len(value) > maxRevisionLen || !safeVaultURIRe.MatchString(value) {
		return fmt.Errorf("%s must be a safe vault URI", name)
	}
	return nil
}

func requireSafeMediaType(name, value string) error {
	if len(value) > maxMediaTypeLen || !safeMediaTypeRe.MatchString(value) {
		return fmt.Errorf("%s must be a safe media type", name)
	}
	return nil
}

func looksLikeRawContent(value string) bool {
	lowered := strings.ToLower(value)
	return strings.Contains(lowered, "password") ||
		strings.Contains(lowered, "secret") ||
		strings.Contains(lowered, "token=") ||
		strings.Contains(lowered, "api_key") ||
		strings.Contains(lowered, "raw=") ||
		strings.Contains(lowered, "-----begin")
}

func validProducerKind(v ProducerKind) bool {
	switch v {
	case ProducerGateway, ProducerCollector, ProducerEvaluator:
		return true
	default:
		return false
	}
}

func validEvidencePurpose(v EvidencePurpose) bool {
	switch v {
	case PurposeOperations, PurposeEvaluation, PurposeRecall, PurposeProposal, PurposeAudit:
		return true
	default:
		return false
	}
}

func validSubjectKind(v SubjectKind) bool {
	switch v {
	case SubjectUser, SubjectService, SubjectTeam, SubjectRepository:
		return true
	default:
		return false
	}
}

func validVisibility(v Visibility) bool {
	switch v {
	case VisibilityPrivate, VisibilityTeam, VisibilityTenant:
		return true
	default:
		return false
	}
}

func validPrivacyDisposition(v PrivacyDisposition) bool {
	switch v {
	case PrivacyMetadataOnly, PrivacyRedacted, PrivacyDerivedOnly, PrivacyVaultOnly:
		return true
	default:
		return false
	}
}

func validSamplingDecision(v SamplingDecision) bool {
	switch v {
	case SamplingIncluded, SamplingExcluded:
		return true
	default:
		return false
	}
}

func validMissingnessStatus(v MissingnessStatus) bool {
	switch v {
	case MissingnessComplete, MissingnessPartial, MissingnessAbsent:
		return true
	default:
		return false
	}
}

func validDeletionState(v DeletionState) bool {
	switch v {
	case DeletionActive, DeletionTombstoned, DeletionPending, DeletionLegalHold, DeletionCryptoShred:
		return true
	default:
		return false
	}
}

func validAttemptOutcome(v AttemptOutcome) bool {
	switch v {
	case AttemptSucceeded, AttemptFailed, AttemptCancelled:
		return true
	default:
		return false
	}
}

func validTerminalOutcome(v TerminalOutcome) bool {
	switch v {
	case TerminalOutcomeSucceeded, TerminalOutcomeFailed, TerminalOutcomeAbandoned, TerminalOutcomeUnknown:
		return true
	default:
		return false
	}
}

func validTerminalOutcomeSource(v TerminalOutcomeSource) bool {
	switch v {
	case TerminalOutcomeCollector, TerminalOutcomeUser, TerminalOutcomeCI:
		return true
	default:
		return false
	}
}

func validTestStatus(v TestStatus) bool {
	switch v {
	case TestPassed, TestFailed, TestSkipped:
		return true
	default:
		return false
	}
}

func validUserReportType(v UserReportType) bool {
	switch v {
	case UserReportCorrection, UserReportApproval, UserReportRejection, UserReportEscalation:
		return true
	default:
		return false
	}
}

func validBehavioralSignalType(v BehavioralSignalType) bool {
	switch v {
	case BehavioralRetry, BehavioralRegenerate, BehavioralToolFailure, BehavioralAbandonment, BehavioralEscalation:
		return true
	default:
		return false
	}
}

func validPerceivedFrictionScale(v PerceivedFrictionScale) bool {
	switch v {
	case PerceivedEase, PerceivedTrust, PerceivedConfidence, PerceivedEffort:
		return true
	default:
		return false
	}
}

func validJudgeOutcome(v JudgeOutcome) bool {
	switch v {
	case JudgePassed, JudgeFailed, JudgeInconclusive:
		return true
	default:
		return false
	}
}
