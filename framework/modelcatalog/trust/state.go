package trust

import (
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

type TrustState string

const (
	TrustStateUnverified     TrustState = "unverified"
	TrustStateVerified       TrustState = "verified"
	TrustStateTrusted        TrustState = "trusted"
	TrustStateQuarantined    TrustState = "quarantined"
	TrustStateReviewRequired TrustState = "review_required"
	TrustStateKilled         TrustState = "killed"
)

type CardTrustRecord struct {
	State          TrustState
	CardDigest     agentcard.Digest
	CardVersion    string
	PublisherName  string
	Domain         string
	Evidence       VerificationEvidence
	PolicyAdmitted bool
	Reason         string
	UpdatedAt      time.Time
}

func NewCardTrustRecord(now time.Time) CardTrustRecord {
	return CardTrustRecord{State: TrustStateUnverified, UpdatedAt: now.UTC()}
}

func RecordVerification(record CardTrustRecord, evidence VerificationEvidence, now time.Time) (CardTrustRecord, error) {
	if record.State == "" {
		record.State = TrustStateUnverified
	}
	if record.State == TrustStateKilled {
		return record, reject(ReasonInvalidTrustState, "killed cards cannot accept new verification evidence")
	}
	if err := validateEvidence(evidence); err != nil {
		return record, err
	}
	if record.CardDigest.Value != "" && (record.CardDigest != evidence.CardDigest || record.CardVersion != evidence.CardVersion) {
		record.State = TrustStateReviewRequired
		record.PolicyAdmitted = false
		record.Reason = "verified evidence changed immutable card digest or version"
		record.UpdatedAt = now.UTC()
		return record, reject(ReasonInvalidTrustState, "new evidence must be reviewed before replacing immutable card digest/version")
	}
	record.State = TrustStateVerified
	record.CardDigest = evidence.CardDigest
	record.CardVersion = evidence.CardVersion
	record.PublisherName = evidence.PublisherName
	record.Domain = evidence.Domain
	record.Evidence = evidence
	record.PolicyAdmitted = false
	record.Reason = ""
	record.UpdatedAt = now.UTC()
	return record, nil
}

func AdmitByPolicy(record CardTrustRecord, digest agentcard.Digest, version string, now time.Time) (CardTrustRecord, error) {
	if record.State != TrustStateVerified {
		return record, reject(ReasonInvalidTrustState, "policy can admit only verified cards")
	}
	if record.CardDigest != digest || record.CardVersion != version {
		record.State = TrustStateReviewRequired
		record.PolicyAdmitted = false
		record.Reason = "policy admission target did not match verified digest/version"
		record.UpdatedAt = now.UTC()
		return record, reject(ReasonInvalidTrustState, "policy admission must bind to verified digest/version")
	}
	record.State = TrustStateTrusted
	record.PolicyAdmitted = true
	record.Evidence.PolicyAdmitted = true
	record.Evidence.RoutingAuthorized = false
	record.Reason = ""
	record.UpdatedAt = now.UTC()
	return record, nil
}

func Quarantine(record CardTrustRecord, reason string, now time.Time) (CardTrustRecord, error) {
	if record.State == TrustStateKilled {
		return record, reject(ReasonInvalidTrustState, "killed cards cannot leave killed state")
	}
	if reason == "" {
		return record, reject(ReasonInvalidTrustState, "quarantine reason is required")
	}
	record.State = TrustStateQuarantined
	record.PolicyAdmitted = false
	record.Evidence.PolicyAdmitted = false
	record.Evidence.RoutingAuthorized = false
	record.Reason = reason
	record.UpdatedAt = now.UTC()
	return record, nil
}

func RequireReview(record CardTrustRecord, reason string, now time.Time) (CardTrustRecord, error) {
	if record.State == TrustStateKilled {
		return record, reject(ReasonInvalidTrustState, "killed cards cannot leave killed state")
	}
	if reason == "" {
		return record, reject(ReasonInvalidTrustState, "review reason is required")
	}
	record.State = TrustStateReviewRequired
	record.PolicyAdmitted = false
	record.Evidence.PolicyAdmitted = false
	record.Evidence.RoutingAuthorized = false
	record.Reason = reason
	record.UpdatedAt = now.UTC()
	return record, nil
}

func Kill(record CardTrustRecord, reason string, now time.Time) (CardTrustRecord, error) {
	if reason == "" {
		return record, reject(ReasonInvalidTrustState, "kill reason is required")
	}
	record.State = TrustStateKilled
	record.PolicyAdmitted = false
	record.Evidence.PolicyAdmitted = false
	record.Evidence.RoutingAuthorized = false
	record.Reason = reason
	record.UpdatedAt = now.UTC()
	return record, nil
}

func validateEvidence(evidence VerificationEvidence) error {
	if evidence.CardDigest.Algorithm != DigestSHA256 || evidence.CardDigest.Value == "" {
		return reject(ReasonDigestMismatch, "verification evidence must include a sha256 card digest")
	}
	if evidence.CardVersion == "" {
		return reject(ReasonCardVersionMismatch, "verification evidence must include card version")
	}
	if evidence.KeyID == "" || evidence.PublisherName == "" || evidence.Domain == "" {
		return reject(ReasonPublisherMismatch, "verification evidence is missing key, publisher, or domain binding")
	}
	if evidence.RoutingAuthorized {
		return reject(ReasonInvalidTrustState, "verification evidence must not authorize routing")
	}
	if evidence.PolicyAdmitted {
		return reject(ReasonInvalidTrustState, "verification evidence must not include policy admission")
	}
	if !evidence.EvidenceOnly {
		return reject(ReasonInvalidTrustState, "verification evidence must be evidence-only")
	}
	if evidence.SignedAt.IsZero() || evidence.ExpiresAt.IsZero() || !evidence.ExpiresAt.After(evidence.SignedAt) {
		return reject(ReasonStaleSignature, "verification evidence has invalid signature timestamps")
	}
	if evidence.Canonicalization != CanonicalizationSubsetV1 {
		return reject(ReasonMalformedPayload, "verification evidence must use %s", CanonicalizationSubsetV1)
	}
	return nil
}
