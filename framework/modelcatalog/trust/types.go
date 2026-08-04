// Package trust verifies signed Agent Model Card envelopes and records the
// resulting evidence for a separate admission policy to evaluate.
package trust

import (
	"crypto/ed25519"
	"fmt"
	"strings"
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

const (
	EnvelopeType               = "bifrost-agent-card+jws"
	AlgorithmEdDSA             = "EdDSA"
	DigestSHA256               = "sha256"
	CanonicalizationSubsetV1   = "bifrost-agent-card-jcs-subset-v1"
	DefaultMaxSignatureAge     = 30 * 24 * time.Hour
	DefaultClockSkew           = 5 * time.Minute
	MaxProtectedBytes          = 2 * 1024
	MaxPayloadBytes            = agentcard.MaxAgentModelCardJSONBytes
	MaxSignatureBytes          = ed25519.SignatureSize
	MaxKeyIDBytes              = 128
	MaxPublisherNameBytes      = 256
	MaxPublisherDomainBytes    = 253
	MaxCompactEnvelopeSegments = 3
)

type RejectReason string

const (
	ReasonMalformedEnvelope    RejectReason = "malformed_envelope"
	ReasonMalformedProtected   RejectReason = "malformed_protected"
	ReasonMalformedPayload     RejectReason = "malformed_payload"
	ReasonMalformedSignature   RejectReason = "malformed_signature"
	ReasonOversizedProtected   RejectReason = "oversized_protected"
	ReasonOversizedPayload     RejectReason = "oversized_payload"
	ReasonUnsupportedAlgorithm RejectReason = "unsupported_algorithm"
	ReasonAlgorithmConfusion   RejectReason = "algorithm_confusion"
	ReasonUnknownKey           RejectReason = "unknown_key"
	ReasonRevokedKey           RejectReason = "revoked_key"
	ReasonStaleSignature       RejectReason = "stale_signature"
	ReasonPublisherMismatch    RejectReason = "publisher_mismatch"
	ReasonDigestMismatch       RejectReason = "digest_mismatch"
	ReasonCardVersionMismatch  RejectReason = "card_version_mismatch"
	ReasonInvalidSignature     RejectReason = "invalid_signature"
	ReasonInvalidTrustState    RejectReason = "invalid_trust_state"
)

type VerificationError struct {
	Reason RejectReason
	Err    error
}

func (e *VerificationError) Error() string {
	if e == nil {
		return ""
	}
	if e.Err == nil {
		return string(e.Reason)
	}
	return string(e.Reason) + ": " + e.Err.Error()
}

func (e *VerificationError) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Err
}

func reject(reason RejectReason, format string, args ...any) *VerificationError {
	if format == "" {
		return &VerificationError{Reason: reason}
	}
	return &VerificationError{Reason: reason, Err: fmt.Errorf(format, args...)}
}

type SignedAgentCardEnvelope struct {
	Protected string `json:"protected"`
	Payload   string `json:"payload"`
	Signature string `json:"signature"`
}

type ProtectedHeader struct {
	Type             string           `json:"typ"`
	Algorithm        string           `json:"alg"`
	KeyID            string           `json:"kid"`
	Canonicalization string           `json:"canon"`
	PayloadDigest    agentcard.Digest `json:"payload_digest"`
	Publisher        string           `json:"publisher"`
	Domain           string           `json:"domain"`
	CardVersion      string           `json:"card_version"`
	EvidenceOnly     bool             `json:"evidence_only"`
	SignedAt         string           `json:"signed_at"`
	NotBefore        string           `json:"not_before,omitempty"`
	ExpiresAt        string           `json:"expires_at"`
}

type KeyRecord struct {
	KeyID         string
	Algorithm     string
	PublicKey     ed25519.PublicKey
	PublisherName string
	Domain        string
	ValidFrom     time.Time
	ValidUntil    time.Time
	RevokedAt     time.Time
}

type KeyStore interface {
	LookupKey(keyID string) (KeyRecord, bool)
}

type StaticKeyStore struct {
	keys map[string]KeyRecord
}

func NewStaticKeyStore(records []KeyRecord) (*StaticKeyStore, error) {
	store := &StaticKeyStore{keys: make(map[string]KeyRecord, len(records))}
	for _, record := range records {
		if record.KeyID == "" {
			return nil, fmt.Errorf("key id is required")
		}
		if len(record.KeyID) > MaxKeyIDBytes {
			return nil, fmt.Errorf("key id %q exceeds %d bytes", record.KeyID, MaxKeyIDBytes)
		}
		if _, exists := store.keys[record.KeyID]; exists {
			return nil, fmt.Errorf("duplicate key id %q", record.KeyID)
		}
		if record.Algorithm == "" {
			record.Algorithm = AlgorithmEdDSA
		}
		if record.Algorithm != AlgorithmEdDSA {
			return nil, fmt.Errorf("key %q uses unsupported algorithm %q", record.KeyID, record.Algorithm)
		}
		if len(record.PublicKey) != ed25519.PublicKeySize {
			return nil, fmt.Errorf("key %q has invalid Ed25519 public key length", record.KeyID)
		}
		if err := validatePublisherName(record.PublisherName); err != nil {
			return nil, fmt.Errorf("key %q publisher: %w", record.KeyID, err)
		}
		domain, err := normalizeDomain(record.Domain)
		if err != nil {
			return nil, fmt.Errorf("key %q domain: %w", record.KeyID, err)
		}
		record.Domain = domain
		store.keys[record.KeyID] = record
	}
	return store, nil
}

func (s *StaticKeyStore) LookupKey(keyID string) (KeyRecord, bool) {
	if s == nil {
		return KeyRecord{}, false
	}
	record, ok := s.keys[keyID]
	return record, ok
}

type VerificationOptions struct {
	Now               func() time.Time
	MaxSignatureAge   time.Duration
	ClockSkew         time.Duration
	ExpectedPublisher string
	ExpectedDomain    string
}

type Verifier struct {
	keys KeyStore
	opts VerificationOptions
}

func NewVerifier(keys KeyStore, opts VerificationOptions) *Verifier {
	return &Verifier{keys: keys, opts: opts.withDefaults()}
}

func (o VerificationOptions) withDefaults() VerificationOptions {
	if o.Now == nil {
		o.Now = time.Now
	}
	if o.MaxSignatureAge == 0 {
		o.MaxSignatureAge = DefaultMaxSignatureAge
	}
	if o.ClockSkew == 0 {
		o.ClockSkew = DefaultClockSkew
	}
	return o
}

func (o VerificationOptions) now() time.Time {
	return o.Now().UTC()
}

type VerificationResult struct {
	Card     agentcard.AgentModelCard
	Evidence VerificationEvidence
}

type VerificationEvidence struct {
	VerifiedAt        time.Time        `json:"verified_at"`
	KeyID             string           `json:"key_id"`
	Algorithm         string           `json:"algorithm"`
	Canonicalization  string           `json:"canonicalization"`
	PublisherName     string           `json:"publisher_name"`
	Domain            string           `json:"domain"`
	CardDigest        agentcard.Digest `json:"card_digest"`
	CardVersion       string           `json:"card_version"`
	SignedAt          time.Time        `json:"signed_at"`
	ExpiresAt         time.Time        `json:"expires_at"`
	EvidenceOnly      bool             `json:"evidence_only"`
	RoutingAuthorized bool             `json:"routing_authorized"`
	PolicyAdmitted    bool             `json:"policy_admitted"`
}

func validatePublisherName(value string) error {
	if value == "" {
		return fmt.Errorf("publisher name is required")
	}
	if len(value) > MaxPublisherNameBytes {
		return fmt.Errorf("publisher name exceeds %d bytes", MaxPublisherNameBytes)
	}
	if strings.TrimSpace(value) != value {
		return fmt.Errorf("publisher name must not have leading or trailing whitespace")
	}
	return nil
}
