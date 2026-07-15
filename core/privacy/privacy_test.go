package privacy

import (
	"reflect"
	"strings"
	"testing"
)

func TestCompilePolicyChoosesMostRestrictiveRuleAndBuildsReceipt(t *testing.T) {
	policy, err := CompilePolicy(TenantPolicy{
		TenantID:    "tenant-a",
		RuleVersion: "rules-2026-07-15",
		Rules: []TenantRule{
			{
				ID:            "default-retain",
				Purposes:      []Purpose{PurposeTrace},
				EntityClasses: []EntityClass{EntityClassAny},
				Transform:     TransformApprovedRetention,
				Destinations:  []Destination{DestinationTraceStore},
				Retention:     RetentionPolicy{Mode: RetentionApproved, DurationDays: 30},
				Deletion:      DeletionPolicy{Mode: DeletionOnSchedule},
			},
			{
				ID:            "payment-redact",
				Purposes:      []Purpose{PurposeTrace},
				EntityClasses: []EntityClass{EntityClassPaymentCard},
				Transform:     TransformRedact,
				Destinations:  []Destination{DestinationTraceStore},
				Retention:     RetentionPolicy{Mode: RetentionMetadataOnly},
				Deletion:      DeletionPolicy{Mode: DeletionOnSchedule},
			},
		},
	})
	if err != nil {
		t.Fatalf("CompilePolicy returned error: %v", err)
	}

	receipt, decision := policy.Evaluate(DetectionResult{
		DetectorVersion: "det-1",
		ModelVersion:    "model-1",
		Status:          DetectorSuccess,
		Confidence:      0.97,
		SourceHash:      SourceHash{Algorithm: "sha256", Value: "0123456789abcdef"},
		EntityCounts: []EntityCount{
			{Class: EntityClassPaymentCard, Count: 1},
			{Class: EntityClassEmail, Count: 2},
		},
	}, EligibilityRequest{
		Purpose:      PurposeTrace,
		Destinations: []Destination{DestinationTraceStore},
	})

	if !decision.Allowed {
		t.Fatalf("expected decision to allow transformed content: %#v", decision)
	}
	if receipt.Version != PrivacyTransformReceiptVersion1 {
		t.Fatalf("version = %q, want %q", receipt.Version, PrivacyTransformReceiptVersion1)
	}
	if receipt.Transform != TransformRedact {
		t.Fatalf("transform = %q, want %q", receipt.Transform, TransformRedact)
	}
	if receipt.RuleVersion != "rules-2026-07-15" {
		t.Fatalf("rule version = %q", receipt.RuleVersion)
	}
	if receipt.DetectorVersion != "det-1" || receipt.ModelVersion != "model-1" {
		t.Fatalf("detector/model versions not preserved: %#v", receipt)
	}
	if receipt.SourceHash.Value != "0123456789abcdef" {
		t.Fatalf("source hash not preserved: %#v", receipt.SourceHash)
	}
	if len(receipt.EntityCounts) != 2 || receipt.EntityCounts[0].Class != EntityClassPaymentCard || receipt.EntityCounts[0].Count != 1 {
		t.Fatalf("entity counts/classes not preserved as counts: %#v", receipt.EntityCounts)
	}
	if len(receipt.Destinations) != 1 || receipt.Destinations[0].Destination != DestinationTraceStore || !receipt.Destinations[0].Eligible {
		t.Fatalf("destination eligibility not recorded: %#v", receipt.Destinations)
	}
	if receipt.Retention.Mode != RetentionMetadataOnly {
		t.Fatalf("retention mode = %q, want %q", receipt.Retention.Mode, RetentionMetadataOnly)
	}
	if err := receipt.Validate(); err != nil {
		t.Fatalf("receipt should validate: %v", err)
	}
}

func TestDetectorFailureFailsClosed(t *testing.T) {
	policy, err := CompilePolicy(TenantPolicy{
		TenantID:    "tenant-a",
		RuleVersion: "rules-1",
		Rules: []TenantRule{{
			ID:            "allow-retention",
			Purposes:      []Purpose{PurposeEval},
			EntityClasses: []EntityClass{EntityClassAny},
			Transform:     TransformApprovedRetention,
			Destinations:  []Destination{DestinationEvalStore},
			Retention:     RetentionPolicy{Mode: RetentionApproved, DurationDays: 7},
			Deletion:      DeletionPolicy{Mode: DeletionOnSchedule},
		}},
	})
	if err != nil {
		t.Fatalf("CompilePolicy returned error: %v", err)
	}

	receipt, decision := policy.Evaluate(DetectionResult{
		DetectorVersion: "det-1",
		ModelVersion:    "model-1",
		Status:          DetectorFailure,
		FailureReason:   "scanner unavailable",
		SourceHash:      SourceHash{Algorithm: "sha256", Value: "hash"},
	}, EligibilityRequest{
		Purpose:      PurposeEval,
		Destinations: []Destination{DestinationEvalStore},
	})

	if decision.Allowed {
		t.Fatalf("detector failure must fail closed: %#v", decision)
	}
	if receipt.Transform != TransformDrop {
		t.Fatalf("detector failure transform = %q, want %q", receipt.Transform, TransformDrop)
	}
	if receipt.Confidence != 0 {
		t.Fatalf("detector failure confidence = %v, want 0", receipt.Confidence)
	}
	if len(receipt.Destinations) != 1 || receipt.Destinations[0].Eligible {
		t.Fatalf("detector failure destination should be ineligible: %#v", receipt.Destinations)
	}
	if err := receipt.Validate(); err != nil {
		t.Fatalf("failure receipt should validate: %v", err)
	}
}

func TestReceiptValidationRejectsRawEntityStorageAndInvalidFields(t *testing.T) {
	valid := PrivacyTransformReceipt{
		Version:         PrivacyTransformReceiptVersion1,
		TenantID:        "tenant-a",
		DetectorVersion: "det-1",
		RuleVersion:     "rules-1",
		ModelVersion:    "model-1",
		Purpose:         PurposeTraining,
		Transform:       TransformPseudonymize,
		Confidence:      0.75,
		SourceHash:      SourceHash{Algorithm: "sha256", Value: "hash"},
		EntityCounts:    []EntityCount{{Class: EntityClassEmail, Count: 1}},
		Destinations:    []DestinationEligibility{{Destination: DestinationTrainingStore, Eligible: true}},
		Retention:       RetentionPolicy{Mode: RetentionMetadataOnly},
		Deletion:        DeletionPolicy{Mode: DeletionOnSchedule},
	}

	tests := []struct {
		name   string
		mutate func(*PrivacyTransformReceipt)
	}{
		{name: "missing version", mutate: func(r *PrivacyTransformReceipt) { r.Version = "" }},
		{name: "missing detector version", mutate: func(r *PrivacyTransformReceipt) { r.DetectorVersion = "" }},
		{name: "missing rule version", mutate: func(r *PrivacyTransformReceipt) { r.RuleVersion = "" }},
		{name: "missing model version", mutate: func(r *PrivacyTransformReceipt) { r.ModelVersion = "" }},
		{name: "missing purpose", mutate: func(r *PrivacyTransformReceipt) { r.Purpose = "" }},
		{name: "missing transform", mutate: func(r *PrivacyTransformReceipt) { r.Transform = "" }},
		{name: "confidence below range", mutate: func(r *PrivacyTransformReceipt) { r.Confidence = -0.01 }},
		{name: "confidence above range", mutate: func(r *PrivacyTransformReceipt) { r.Confidence = 1.01 }},
		{name: "missing source hash algorithm", mutate: func(r *PrivacyTransformReceipt) { r.SourceHash.Algorithm = "" }},
		{name: "missing source hash value", mutate: func(r *PrivacyTransformReceipt) { r.SourceHash.Value = "" }},
		{name: "missing detector status", mutate: func(r *PrivacyTransformReceipt) { r.DetectorStatus = "" }},
		{name: "negative entity count", mutate: func(r *PrivacyTransformReceipt) { r.EntityCounts[0].Count = -1 }},
		{name: "missing destination", mutate: func(r *PrivacyTransformReceipt) { r.Destinations = nil }},
		{name: "missing retention", mutate: func(r *PrivacyTransformReceipt) { r.Retention.Mode = "" }},
		{name: "missing deletion", mutate: func(r *PrivacyTransformReceipt) { r.Deletion.Mode = "" }},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			receipt := valid
			receipt.EntityCounts = append([]EntityCount(nil), valid.EntityCounts...)
			receipt.Destinations = append([]DestinationEligibility(nil), valid.Destinations...)
			tt.mutate(&receipt)
			if err := receipt.Validate(); err == nil {
				t.Fatalf("Validate() succeeded, want error")
			}
		})
	}
}

func TestReceiptValidationRejectsInconsistentTransformPolicy(t *testing.T) {
	receipt := PrivacyTransformReceipt{
		Version:         PrivacyTransformReceiptVersion1,
		TenantID:        "tenant-a",
		DetectorVersion: "det-1",
		RuleVersion:     "rules-1",
		ModelVersion:    "model-1",
		Purpose:         PurposeTrace,
		DetectorStatus:  DetectorSuccess,
		Transform:       TransformApprovedRetention,
		Confidence:      0.75,
		SourceHash:      SourceHash{Algorithm: "sha256", Value: "hash"},
		EntityCounts:    []EntityCount{{Class: EntityClassEmail, Count: 1}},
		Destinations:    []DestinationEligibility{{Destination: DestinationTraceStore, Eligible: true}},
		Retention:       RetentionPolicy{Mode: RetentionMetadataOnly},
		Deletion:        DeletionPolicy{Mode: DeletionOnSchedule},
	}
	if err := receipt.Validate(); err == nil {
		t.Fatalf("Validate() succeeded, want inconsistent transform/retention error")
	}
}

func TestEntityCountsHaveNoRawEntityStorage(t *testing.T) {
	entityCountType := reflect.TypeOf(EntityCount{})
	for i := 0; i < entityCountType.NumField(); i++ {
		field := entityCountType.Field(i)
		name := strings.ToLower(field.Name)
		if strings.Contains(name, "raw") || strings.Contains(name, "value") || strings.Contains(name, "text") || strings.Contains(name, "entity") {
			t.Fatalf("EntityCount field %q looks like raw entity storage", field.Name)
		}
	}
}

func TestCompilePolicyValidationAndRuleActions(t *testing.T) {
	tests := []struct {
		name      string
		transform Transform
		retention RetentionPolicy
		deletion  DeletionPolicy
		wantAllow bool
	}{
		{
			name:      "metadata only",
			transform: TransformMetadataOnly,
			retention: RetentionPolicy{Mode: RetentionMetadataOnly},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
			wantAllow: true,
		},
		{
			name:      "drop",
			transform: TransformDrop,
			retention: RetentionPolicy{Mode: RetentionNone},
			deletion:  DeletionPolicy{Mode: DeletionImmediate},
			wantAllow: false,
		},
		{
			name:      "redact",
			transform: TransformRedact,
			retention: RetentionPolicy{Mode: RetentionMetadataOnly},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
			wantAllow: true,
		},
		{
			name:      "pseudonymize",
			transform: TransformPseudonymize,
			retention: RetentionPolicy{Mode: RetentionMetadataOnly},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
			wantAllow: true,
		},
		{
			name:      "restricted encryption",
			transform: TransformRestrictedEncryption,
			retention: RetentionPolicy{Mode: RetentionRestrictedEncrypted, DurationDays: 7},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
			wantAllow: true,
		},
		{
			name:      "approved retention",
			transform: TransformApprovedRetention,
			retention: RetentionPolicy{Mode: RetentionApproved, DurationDays: 30},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
			wantAllow: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			policy, err := CompilePolicy(TenantPolicy{
				TenantID:    "tenant-a",
				RuleVersion: "rules-1",
				Rules: []TenantRule{{
					ID:            "rule-1",
					Purposes:      []Purpose{PurposeTrace},
					EntityClasses: []EntityClass{EntityClassEmail},
					Transform:     tt.transform,
					Destinations:  []Destination{DestinationTraceStore},
					Retention:     tt.retention,
					Deletion:      tt.deletion,
				}},
			})
			if err != nil {
				t.Fatalf("CompilePolicy returned error: %v", err)
			}
			receipt, decision := policy.Evaluate(DetectionResult{
				DetectorVersion: "det-1",
				ModelVersion:    "model-1",
				Status:          DetectorSuccess,
				Confidence:      0.5,
				SourceHash:      SourceHash{Algorithm: "sha256", Value: "hash"},
				EntityCounts:    []EntityCount{{Class: EntityClassEmail, Count: 1}},
			}, EligibilityRequest{Purpose: PurposeTrace, Destinations: []Destination{DestinationTraceStore}})
			if decision.Allowed != tt.wantAllow {
				t.Fatalf("Allowed = %v, want %v; receipt=%#v decision=%#v", decision.Allowed, tt.wantAllow, receipt, decision)
			}
			if receipt.Transform != tt.transform {
				t.Fatalf("transform = %q, want %q", receipt.Transform, tt.transform)
			}
		})
	}
}

func TestCompilePolicyRejectsInconsistentRuleActions(t *testing.T) {
	tests := []struct {
		name      string
		transform Transform
		retention RetentionPolicy
		deletion  DeletionPolicy
	}{
		{
			name:      "drop must delete immediately with no retention",
			transform: TransformDrop,
			retention: RetentionPolicy{Mode: RetentionApproved, DurationDays: 1},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
		},
		{
			name:      "metadata only must not retain content",
			transform: TransformMetadataOnly,
			retention: RetentionPolicy{Mode: RetentionApproved, DurationDays: 1},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
		},
		{
			name:      "restricted encryption requires restricted encrypted retention",
			transform: TransformRestrictedEncryption,
			retention: RetentionPolicy{Mode: RetentionApproved, DurationDays: 1},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
		},
		{
			name:      "approved retention requires approved retention mode",
			transform: TransformApprovedRetention,
			retention: RetentionPolicy{Mode: RetentionMetadataOnly},
			deletion:  DeletionPolicy{Mode: DeletionOnSchedule},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := CompilePolicy(TenantPolicy{
				TenantID:    "tenant-a",
				RuleVersion: "rules-1",
				Rules: []TenantRule{{
					ID:            "rule-1",
					Purposes:      []Purpose{PurposeTrace},
					EntityClasses: []EntityClass{EntityClassAny},
					Transform:     tt.transform,
					Destinations:  []Destination{DestinationTraceStore},
					Retention:     tt.retention,
					Deletion:      tt.deletion,
				}},
			})
			if err == nil {
				t.Fatalf("CompilePolicy succeeded, want error")
			}
		})
	}
}
