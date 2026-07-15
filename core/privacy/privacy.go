package privacy

import "fmt"

const PrivacyTransformReceiptVersion1 = "privacy_transform_receipt.v1"

type Purpose string

const (
	PurposeTrace    Purpose = "trace"
	PurposeEval     Purpose = "eval"
	PurposeTraining Purpose = "training"
	PurposeEvidence Purpose = "evidence"
)

type EntityClass string

const (
	EntityClassAny         EntityClass = "*"
	EntityClassEmail       EntityClass = "email"
	EntityClassPaymentCard EntityClass = "payment_card"
	EntityClassSecret      EntityClass = "secret"
	EntityClassPersonName  EntityClass = "person_name"
	EntityClassPhone       EntityClass = "phone"
	EntityClassLocation    EntityClass = "location"
)

type Transform string

const (
	TransformMetadataOnly         Transform = "metadata_only"
	TransformDrop                 Transform = "drop"
	TransformRedact               Transform = "redact"
	TransformPseudonymize         Transform = "pseudonymize"
	TransformRestrictedEncryption Transform = "restricted_encryption"
	TransformApprovedRetention    Transform = "approved_retention"
)

type Destination string

const (
	DestinationTraceStore    Destination = "trace_store"
	DestinationEvalStore     Destination = "eval_store"
	DestinationTrainingStore Destination = "training_store"
	DestinationEvidenceStore Destination = "evidence_store"
	DestinationAuditStore    Destination = "audit_store"
)

type DetectorStatus string

const (
	DetectorSuccess DetectorStatus = "success"
	DetectorFailure DetectorStatus = "failure"
)

type RetentionMode string

const (
	RetentionNone                RetentionMode = "none"
	RetentionMetadataOnly        RetentionMode = "metadata_only"
	RetentionRestrictedEncrypted RetentionMode = "restricted_encrypted"
	RetentionApproved            RetentionMode = "approved"
)

type DeletionMode string

const (
	DeletionImmediate  DeletionMode = "immediate"
	DeletionOnSchedule DeletionMode = "on_schedule"
	DeletionOnRequest  DeletionMode = "on_request"
)

type SourceHash struct {
	Algorithm string `json:"algorithm"`
	Value     string `json:"value"`
}

type EntityCount struct {
	Class EntityClass `json:"class"`
	Count int         `json:"count"`
}

type DestinationEligibility struct {
	Destination Destination `json:"destination"`
	Eligible    bool        `json:"eligible"`
	Reason      string      `json:"reason,omitempty"`
}

type RetentionPolicy struct {
	Mode         RetentionMode `json:"mode"`
	DurationDays int           `json:"duration_days,omitempty"`
}

type DeletionPolicy struct {
	Mode DeletionMode `json:"mode"`
}

type PrivacyTransformReceipt struct {
	Version               string                   `json:"version"`
	TenantID              string                   `json:"tenant_id"`
	DetectorVersion       string                   `json:"detector_version"`
	RuleVersion           string                   `json:"rule_version"`
	RuleIDs               []string                 `json:"rule_ids,omitempty"`
	ModelVersion          string                   `json:"model_version"`
	Purpose               Purpose                  `json:"purpose"`
	DetectorStatus        DetectorStatus           `json:"detector_status"`
	DetectorFailureReason string                   `json:"detector_failure_reason,omitempty"`
	EntityCounts          []EntityCount            `json:"entity_counts,omitempty"`
	Transform             Transform                `json:"transform"`
	Confidence            float64                  `json:"confidence"`
	SourceHash            SourceHash               `json:"source_hash"`
	Destinations          []DestinationEligibility `json:"destinations"`
	Retention             RetentionPolicy          `json:"retention"`
	Deletion              DeletionPolicy           `json:"deletion"`
}

type DetectionResult struct {
	DetectorVersion string
	ModelVersion    string
	Status          DetectorStatus
	FailureReason   string
	Confidence      float64
	SourceHash      SourceHash
	EntityCounts    []EntityCount
}

type EligibilityRequest struct {
	Purpose      Purpose
	Destinations []Destination
}

type TenantPolicy struct {
	TenantID    string
	RuleVersion string
	Rules       []TenantRule
}

type TenantRule struct {
	ID            string
	Purposes      []Purpose
	EntityClasses []EntityClass
	Transform     Transform
	Destinations  []Destination
	Retention     RetentionPolicy
	Deletion      DeletionPolicy
}

type Decision struct {
	Allowed bool
	Reason  string
}

type CompiledPolicy struct {
	tenantID    string
	ruleVersion string
	rules       []TenantRule
}

func CompilePolicy(policy TenantPolicy) (*CompiledPolicy, error) {
	if policy.TenantID == "" {
		return nil, fmt.Errorf("tenant_id is required")
	}
	if policy.RuleVersion == "" {
		return nil, fmt.Errorf("rule_version is required")
	}
	if len(policy.Rules) == 0 {
		return nil, fmt.Errorf("at least one rule is required")
	}
	compiled := &CompiledPolicy{
		tenantID:    policy.TenantID,
		ruleVersion: policy.RuleVersion,
		rules:       make([]TenantRule, len(policy.Rules)),
	}
	for i, rule := range policy.Rules {
		if err := validateRule(rule); err != nil {
			return nil, fmt.Errorf("rule %d: %w", i, err)
		}
		compiled.rules[i] = cloneRule(rule)
	}
	return compiled, nil
}

func (p *CompiledPolicy) Evaluate(result DetectionResult, request EligibilityRequest) (PrivacyTransformReceipt, Decision) {
	receipt := PrivacyTransformReceipt{
		Version:               PrivacyTransformReceiptVersion1,
		TenantID:              p.tenantID,
		DetectorVersion:       result.DetectorVersion,
		RuleVersion:           p.ruleVersion,
		ModelVersion:          result.ModelVersion,
		Purpose:               request.Purpose,
		DetectorStatus:        result.Status,
		DetectorFailureReason: result.FailureReason,
		EntityCounts:          cloneEntityCounts(result.EntityCounts),
		Confidence:            result.Confidence,
		SourceHash:            result.SourceHash,
	}

	if result.Status != DetectorSuccess {
		receipt.Transform = TransformDrop
		receipt.Confidence = 0
		receipt.Destinations = buildDestinationEligibility(request.Destinations, nil, false, "detector failure")
		receipt.Retention = RetentionPolicy{Mode: RetentionNone}
		receipt.Deletion = DeletionPolicy{Mode: DeletionImmediate}
		return receipt, Decision{Allowed: false, Reason: "detector failure; content capture denied"}
	}

	rule, ok := p.mostRestrictiveRule(request.Purpose, result.EntityCounts)
	if !ok {
		receipt.Transform = TransformDrop
		receipt.Destinations = buildDestinationEligibility(request.Destinations, nil, false, "no matching rule")
		receipt.Retention = RetentionPolicy{Mode: RetentionNone}
		receipt.Deletion = DeletionPolicy{Mode: DeletionImmediate}
		return receipt, Decision{Allowed: false, Reason: "no matching privacy rule"}
	}

	receipt.Transform = rule.Transform
	receipt.RuleIDs = []string{rule.ID}
	receipt.Destinations = buildDestinationEligibility(request.Destinations, rule.Destinations, rule.Transform != TransformDrop, "")
	receipt.Retention = rule.Retention
	receipt.Deletion = rule.Deletion

	allowed := rule.Transform != TransformDrop && anyEligible(receipt.Destinations)
	if !allowed {
		return receipt, Decision{Allowed: false, Reason: "content is not eligible for requested destinations"}
	}
	return receipt, Decision{Allowed: true, Reason: "content eligible after privacy transform"}
}

func (r PrivacyTransformReceipt) Validate() error {
	if r.Version != PrivacyTransformReceiptVersion1 {
		return fmt.Errorf("unsupported or missing version")
	}
	if r.TenantID == "" {
		return fmt.Errorf("tenant_id is required")
	}
	if r.DetectorVersion == "" {
		return fmt.Errorf("detector_version is required")
	}
	if r.RuleVersion == "" {
		return fmt.Errorf("rule_version is required")
	}
	if r.ModelVersion == "" {
		return fmt.Errorf("model_version is required")
	}
	if !validPurpose(r.Purpose) {
		return fmt.Errorf("purpose is required or invalid")
	}
	if !validDetectorStatus(r.DetectorStatus) {
		return fmt.Errorf("detector_status is required or invalid")
	}
	if !validTransform(r.Transform) {
		return fmt.Errorf("transform is required or invalid")
	}
	if r.Confidence < 0 || r.Confidence > 1 {
		return fmt.Errorf("confidence must be between 0 and 1")
	}
	if r.SourceHash.Algorithm == "" {
		return fmt.Errorf("source_hash.algorithm is required")
	}
	if r.SourceHash.Value == "" {
		return fmt.Errorf("source_hash.value is required")
	}
	for i, count := range r.EntityCounts {
		if !validEntityClass(count.Class) {
			return fmt.Errorf("entity_counts[%d].class is required or invalid", i)
		}
		if count.Count < 0 {
			return fmt.Errorf("entity_counts[%d].count must be non-negative", i)
		}
	}
	if len(r.Destinations) == 0 {
		return fmt.Errorf("at least one destination eligibility is required")
	}
	for i, dest := range r.Destinations {
		if !validDestination(dest.Destination) {
			return fmt.Errorf("destinations[%d].destination is required or invalid", i)
		}
	}
	if err := validateRetention(r.Retention); err != nil {
		return err
	}
	if !validDeletionMode(r.Deletion.Mode) {
		return fmt.Errorf("deletion.mode is required or invalid")
	}
	if err := validateTransformPolicy(r.Transform, r.Retention, r.Deletion); err != nil {
		return err
	}
	return nil
}

func (p *CompiledPolicy) mostRestrictiveRule(purpose Purpose, counts []EntityCount) (TenantRule, bool) {
	var selected TenantRule
	selectedRank := -1
	for _, rule := range p.rules {
		if !containsPurpose(rule.Purposes, purpose) {
			continue
		}
		if !ruleMatchesEntities(rule, counts) {
			continue
		}
		rank := transformRank(rule.Transform)
		if rank > selectedRank {
			selected = rule
			selectedRank = rank
		}
	}
	return selected, selectedRank >= 0
}

func validateRule(rule TenantRule) error {
	if rule.ID == "" {
		return fmt.Errorf("id is required")
	}
	if len(rule.Purposes) == 0 {
		return fmt.Errorf("at least one purpose is required")
	}
	for _, purpose := range rule.Purposes {
		if !validPurpose(purpose) {
			return fmt.Errorf("invalid purpose %q", purpose)
		}
	}
	if len(rule.EntityClasses) == 0 {
		return fmt.Errorf("at least one entity class is required")
	}
	for _, class := range rule.EntityClasses {
		if !validEntityClass(class) {
			return fmt.Errorf("invalid entity class %q", class)
		}
	}
	if !validTransform(rule.Transform) {
		return fmt.Errorf("transform is required or invalid")
	}
	if len(rule.Destinations) == 0 {
		return fmt.Errorf("at least one destination is required")
	}
	for _, destination := range rule.Destinations {
		if !validDestination(destination) {
			return fmt.Errorf("invalid destination %q", destination)
		}
	}
	if err := validateRetention(rule.Retention); err != nil {
		return err
	}
	if !validDeletionMode(rule.Deletion.Mode) {
		return fmt.Errorf("deletion.mode is required or invalid")
	}
	if err := validateRuleAction(rule); err != nil {
		return err
	}
	return nil
}

func validateRuleAction(rule TenantRule) error {
	return validateTransformPolicy(rule.Transform, rule.Retention, rule.Deletion)
}

func validateTransformPolicy(transform Transform, retention RetentionPolicy, deletion DeletionPolicy) error {
	switch transform {
	case TransformDrop:
		if retention.Mode != RetentionNone || deletion.Mode != DeletionImmediate {
			return fmt.Errorf("drop transform requires retention none and immediate deletion")
		}
	case TransformMetadataOnly:
		if retention.Mode != RetentionMetadataOnly && retention.Mode != RetentionNone {
			return fmt.Errorf("metadata_only transform cannot retain content")
		}
	case TransformRestrictedEncryption:
		if retention.Mode != RetentionRestrictedEncrypted {
			return fmt.Errorf("restricted_encryption transform requires restricted encrypted retention")
		}
	case TransformApprovedRetention:
		if retention.Mode != RetentionApproved {
			return fmt.Errorf("approved_retention transform requires approved retention")
		}
	}
	return nil
}

func validateRetention(retention RetentionPolicy) error {
	if !validRetentionMode(retention.Mode) {
		return fmt.Errorf("retention.mode is required or invalid")
	}
	switch retention.Mode {
	case RetentionApproved, RetentionRestrictedEncrypted:
		if retention.DurationDays <= 0 {
			return fmt.Errorf("retention.duration_days must be positive for %s", retention.Mode)
		}
	case RetentionNone, RetentionMetadataOnly:
		if retention.DurationDays < 0 {
			return fmt.Errorf("retention.duration_days must be non-negative")
		}
	}
	return nil
}

func buildDestinationEligibility(requested []Destination, allowed []Destination, eligible bool, reason string) []DestinationEligibility {
	if len(requested) == 0 {
		requested = allowed
	}
	out := make([]DestinationEligibility, 0, len(requested))
	for _, destination := range requested {
		isAllowed := eligible && containsDestination(allowed, destination)
		entry := DestinationEligibility{Destination: destination, Eligible: isAllowed}
		if !isAllowed {
			if reason != "" {
				entry.Reason = reason
			} else {
				entry.Reason = "destination not allowed by privacy rule"
			}
		}
		out = append(out, entry)
	}
	return out
}

func ruleMatchesEntities(rule TenantRule, counts []EntityCount) bool {
	if containsEntityClass(rule.EntityClasses, EntityClassAny) {
		return true
	}
	if len(counts) == 0 {
		return false
	}
	for _, count := range counts {
		if count.Count <= 0 {
			continue
		}
		if containsEntityClass(rule.EntityClasses, count.Class) {
			return true
		}
	}
	return false
}

func transformRank(transform Transform) int {
	switch transform {
	case TransformDrop:
		return 600
	case TransformMetadataOnly:
		return 500
	case TransformRedact:
		return 400
	case TransformPseudonymize:
		return 300
	case TransformRestrictedEncryption:
		return 200
	case TransformApprovedRetention:
		return 100
	default:
		return -1
	}
}

func anyEligible(destinations []DestinationEligibility) bool {
	for _, destination := range destinations {
		if destination.Eligible {
			return true
		}
	}
	return false
}

func cloneRule(rule TenantRule) TenantRule {
	rule.Purposes = append([]Purpose(nil), rule.Purposes...)
	rule.EntityClasses = append([]EntityClass(nil), rule.EntityClasses...)
	rule.Destinations = append([]Destination(nil), rule.Destinations...)
	return rule
}

func cloneEntityCounts(counts []EntityCount) []EntityCount {
	if len(counts) == 0 {
		return nil
	}
	return append([]EntityCount(nil), counts...)
}

func containsPurpose(values []Purpose, target Purpose) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func containsEntityClass(values []EntityClass, target EntityClass) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func containsDestination(values []Destination, target Destination) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func validPurpose(value Purpose) bool {
	switch value {
	case PurposeTrace, PurposeEval, PurposeTraining, PurposeEvidence:
		return true
	default:
		return false
	}
}

func validEntityClass(value EntityClass) bool {
	switch value {
	case EntityClassAny, EntityClassEmail, EntityClassPaymentCard, EntityClassSecret, EntityClassPersonName, EntityClassPhone, EntityClassLocation:
		return true
	default:
		return false
	}
}

func validTransform(value Transform) bool {
	switch value {
	case TransformMetadataOnly, TransformDrop, TransformRedact, TransformPseudonymize, TransformRestrictedEncryption, TransformApprovedRetention:
		return true
	default:
		return false
	}
}

func validDestination(value Destination) bool {
	switch value {
	case DestinationTraceStore, DestinationEvalStore, DestinationTrainingStore, DestinationEvidenceStore, DestinationAuditStore:
		return true
	default:
		return false
	}
}

func validDetectorStatus(value DetectorStatus) bool {
	switch value {
	case DetectorSuccess, DetectorFailure:
		return true
	default:
		return false
	}
}

func validRetentionMode(value RetentionMode) bool {
	switch value {
	case RetentionNone, RetentionMetadataOnly, RetentionRestrictedEncrypted, RetentionApproved:
		return true
	default:
		return false
	}
}

func validDeletionMode(value DeletionMode) bool {
	switch value {
	case DeletionImmediate, DeletionOnSchedule, DeletionOnRequest:
		return true
	default:
		return false
	}
}
