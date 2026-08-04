package trust

import (
	"bytes"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

var protectedHeaderFields = map[string]struct{}{
	"typ":            {},
	"alg":            {},
	"kid":            {},
	"canon":          {},
	"payload_digest": {},
	"publisher":      {},
	"domain":         {},
	"card_version":   {},
	"evidence_only":  {},
	"signed_at":      {},
	"not_before":     {},
	"expires_at":     {},
}

func ParseCompactEnvelope(compact string) (SignedAgentCardEnvelope, error) {
	parts := strings.Split(compact, ".")
	if len(parts) != MaxCompactEnvelopeSegments {
		return SignedAgentCardEnvelope{}, reject(ReasonMalformedEnvelope, "compact envelope must contain protected, payload, and signature segments")
	}
	return SignedAgentCardEnvelope{
		Protected: parts[0],
		Payload:   parts[1],
		Signature: parts[2],
	}, nil
}

func (e SignedAgentCardEnvelope) Compact() string {
	return e.Protected + "." + e.Payload + "." + e.Signature
}

func (v *Verifier) VerifyCompact(compact string) (VerificationResult, error) {
	envelope, err := ParseCompactEnvelope(compact)
	if err != nil {
		return VerificationResult{}, err
	}
	return v.VerifyEnvelope(envelope)
}

func (v *Verifier) VerifyEnvelope(envelope SignedAgentCardEnvelope) (VerificationResult, error) {
	if v == nil || v.keys == nil {
		return VerificationResult{}, reject(ReasonUnknownKey, "key store is required")
	}
	opts := v.opts.withDefaults()

	protected, err := decodeEnvelopePart("protected", envelope.Protected, MaxProtectedBytes)
	if err != nil {
		return VerificationResult{}, err
	}
	payload, err := decodeEnvelopePart("payload", envelope.Payload, MaxPayloadBytes)
	if err != nil {
		return VerificationResult{}, err
	}
	signature, err := decodeEnvelopePart("signature", envelope.Signature, MaxSignatureBytes)
	if err != nil {
		return VerificationResult{}, err
	}
	if len(signature) != ed25519.SignatureSize {
		return VerificationResult{}, reject(ReasonMalformedSignature, "Ed25519 signature must be %d bytes", ed25519.SignatureSize)
	}

	header, signedAt, expiresAt, err := decodeProtectedHeader(protected)
	if err != nil {
		return VerificationResult{}, err
	}
	key, ok := v.keys.LookupKey(header.KeyID)
	if !ok {
		return VerificationResult{}, reject(ReasonUnknownKey, "key %q is not trusted", header.KeyID)
	}
	if err := validateHeaderAndKey(header, key); err != nil {
		return VerificationResult{}, err
	}
	if err := validateSignatureFreshness(header, key, opts, signedAt, expiresAt); err != nil {
		return VerificationResult{}, err
	}

	signingInput := envelope.Protected + "." + envelope.Payload
	if !ed25519.Verify(key.PublicKey, []byte(signingInput), signature) {
		return VerificationResult{}, reject(ReasonInvalidSignature, "signature does not verify")
	}

	card, canonicalPayload, err := decodeCanonicalCardPayload(payload)
	if err != nil {
		return VerificationResult{}, reject(ReasonMalformedPayload, "%w", err)
	}
	digest := sha256Digest(canonicalPayload)
	if header.PayloadDigest.Algorithm != DigestSHA256 || header.PayloadDigest.Value != digest {
		return VerificationResult{}, reject(ReasonDigestMismatch, "payload digest does not match protected header")
	}
	if header.CardVersion != card.Entity.Version.Version {
		return VerificationResult{}, reject(ReasonCardVersionMismatch, "protected card_version %q does not match payload version %q", header.CardVersion, card.Entity.Version.Version)
	}
	if err := validatePublisherBinding(header, key, card, opts); err != nil {
		return VerificationResult{}, err
	}

	evidence := VerificationEvidence{
		VerifiedAt:       opts.now(),
		KeyID:            header.KeyID,
		Algorithm:        header.Algorithm,
		Canonicalization: header.Canonicalization,
		PublisherName:    header.Publisher,
		Domain:           header.Domain,
		CardDigest: agentcard.Digest{
			Algorithm: DigestSHA256,
			Value:     digest,
		},
		CardVersion:       header.CardVersion,
		SignedAt:          signedAt,
		ExpiresAt:         expiresAt,
		EvidenceOnly:      true,
		RoutingAuthorized: false,
		PolicyAdmitted:    false,
	}
	return VerificationResult{Card: card, Evidence: evidence}, nil
}

func decodeEnvelopePart(name, value string, maxDecoded int) ([]byte, error) {
	if value == "" {
		return nil, reject(reasonForMalformedPart(name), "%s segment is required", name)
	}
	maxEncoded := base64.RawURLEncoding.EncodedLen(maxDecoded)
	if len(value) > maxEncoded {
		return nil, reject(reasonForOversizedPart(name), "%s segment exceeds encoded limit for %d decoded bytes", name, maxDecoded)
	}
	decoded, err := base64.RawURLEncoding.DecodeString(value)
	if err != nil {
		return nil, reject(reasonForMalformedPart(name), "%s segment is not unpadded base64url: %w", name, err)
	}
	if len(decoded) > maxDecoded {
		return nil, reject(reasonForOversizedPart(name), "%s segment exceeds %d decoded bytes", name, maxDecoded)
	}
	return decoded, nil
}

func reasonForMalformedPart(name string) RejectReason {
	switch name {
	case "protected":
		return ReasonMalformedProtected
	case "payload":
		return ReasonMalformedPayload
	case "signature":
		return ReasonMalformedSignature
	default:
		return ReasonMalformedEnvelope
	}
}

func reasonForOversizedPart(name string) RejectReason {
	switch name {
	case "protected":
		return ReasonOversizedProtected
	case "payload":
		return ReasonOversizedPayload
	default:
		return ReasonMalformedEnvelope
	}
}

func decodeProtectedHeader(protected []byte) (ProtectedHeader, time.Time, time.Time, error) {
	canonical, err := canonicalizeJSON(protected)
	if err != nil {
		return ProtectedHeader{}, time.Time{}, time.Time{}, reject(ReasonMalformedProtected, "%w", err)
	}
	if !bytes.Equal(canonical, protected) {
		return ProtectedHeader{}, time.Time{}, time.Time{}, reject(ReasonMalformedProtected, "protected header is not %s canonical JSON", CanonicalizationSubsetV1)
	}

	var raw map[string]json.RawMessage
	if err := json.Unmarshal(protected, &raw); err != nil {
		return ProtectedHeader{}, time.Time{}, time.Time{}, reject(ReasonMalformedProtected, "%w", err)
	}
	for key := range raw {
		if _, ok := protectedHeaderFields[key]; !ok {
			return ProtectedHeader{}, time.Time{}, time.Time{}, reject(ReasonMalformedProtected, "unknown protected header field %q", key)
		}
	}

	var header ProtectedHeader
	if err := json.Unmarshal(protected, &header); err != nil {
		return ProtectedHeader{}, time.Time{}, time.Time{}, reject(ReasonMalformedProtected, "%w", err)
	}
	signedAt, err := parseRequiredTime("signed_at", header.SignedAt)
	if err != nil {
		return ProtectedHeader{}, time.Time{}, time.Time{}, reject(ReasonStaleSignature, "%w", err)
	}
	expiresAt, err := parseRequiredTime("expires_at", header.ExpiresAt)
	if err != nil {
		return ProtectedHeader{}, time.Time{}, time.Time{}, reject(ReasonStaleSignature, "%w", err)
	}
	return header, signedAt, expiresAt, nil
}

func validateHeaderAndKey(header ProtectedHeader, key KeyRecord) error {
	if header.Type != EnvelopeType {
		return reject(ReasonMalformedProtected, "typ must be %q", EnvelopeType)
	}
	if header.Algorithm == "" {
		return reject(ReasonUnsupportedAlgorithm, "alg is required")
	}
	if header.Algorithm != AlgorithmEdDSA {
		return reject(ReasonUnsupportedAlgorithm, "alg %q is not supported", header.Algorithm)
	}
	if key.Algorithm != AlgorithmEdDSA {
		return reject(ReasonAlgorithmConfusion, "key %q is %q but protected alg is %q", key.KeyID, key.Algorithm, header.Algorithm)
	}
	if header.KeyID == "" {
		return reject(ReasonMalformedProtected, "kid is required")
	}
	if len(header.KeyID) > MaxKeyIDBytes {
		return reject(ReasonMalformedProtected, "kid exceeds %d bytes", MaxKeyIDBytes)
	}
	if header.Canonicalization != CanonicalizationSubsetV1 {
		return reject(ReasonMalformedProtected, "canon must be %q", CanonicalizationSubsetV1)
	}
	if header.PayloadDigest.Algorithm != DigestSHA256 {
		return reject(ReasonDigestMismatch, "payload_digest.algorithm must be %q", DigestSHA256)
	}
	if header.PayloadDigest.Value == "" {
		return reject(ReasonDigestMismatch, "payload_digest.value is required")
	}
	if header.CardVersion == "" {
		return reject(ReasonCardVersionMismatch, "card_version is required")
	}
	if !header.EvidenceOnly {
		return reject(ReasonMalformedProtected, "evidence_only must be true")
	}
	if !key.RevokedAt.IsZero() {
		return reject(ReasonRevokedKey, "key %q was revoked at %s", key.KeyID, key.RevokedAt.UTC().Format(time.RFC3339))
	}
	return nil
}

func validateSignatureFreshness(header ProtectedHeader, key KeyRecord, opts VerificationOptions, signedAt, expiresAt time.Time) error {
	now := opts.now()
	skew := opts.ClockSkew
	if signedAt.After(now.Add(skew)) {
		return reject(ReasonStaleSignature, "signed_at is in the future")
	}
	if !header.NotBeforeIsZero() {
		notBefore, err := time.Parse(time.RFC3339, header.NotBefore)
		if err != nil {
			return reject(ReasonStaleSignature, "not_before must be RFC3339: %w", err)
		}
		if now.Add(skew).Before(notBefore) {
			return reject(ReasonStaleSignature, "signature is not valid before %s", notBefore.UTC().Format(time.RFC3339))
		}
	}
	if !expiresAt.After(signedAt) {
		return reject(ReasonStaleSignature, "expires_at must be after signed_at")
	}
	if now.After(expiresAt.Add(skew)) {
		return reject(ReasonStaleSignature, "signature expired at %s", expiresAt.UTC().Format(time.RFC3339))
	}
	if opts.MaxSignatureAge > 0 {
		if now.Sub(signedAt) > opts.MaxSignatureAge+skew {
			return reject(ReasonStaleSignature, "signature age exceeds %s", opts.MaxSignatureAge)
		}
		if expiresAt.Sub(signedAt) > opts.MaxSignatureAge+skew {
			return reject(ReasonStaleSignature, "signature validity exceeds %s", opts.MaxSignatureAge)
		}
	}
	if !key.ValidFrom.IsZero() && signedAt.Add(skew).Before(key.ValidFrom) {
		return reject(ReasonStaleSignature, "signature predates key validity")
	}
	if !key.ValidUntil.IsZero() && signedAt.After(key.ValidUntil.Add(skew)) {
		return reject(ReasonStaleSignature, "signature postdates key validity")
	}
	return nil
}

func (h ProtectedHeader) NotBeforeIsZero() bool {
	return h.NotBefore == ""
}

func validatePublisherBinding(header ProtectedHeader, key KeyRecord, card agentcard.AgentModelCard, opts VerificationOptions) error {
	if err := validatePublisherName(header.Publisher); err != nil {
		return reject(ReasonPublisherMismatch, "%w", err)
	}
	if header.Publisher != key.PublisherName {
		return reject(ReasonPublisherMismatch, "protected publisher %q does not match key publisher %q", header.Publisher, key.PublisherName)
	}
	if header.Publisher != card.Entity.Publisher.Name {
		return reject(ReasonPublisherMismatch, "protected publisher %q does not match card publisher %q", header.Publisher, card.Entity.Publisher.Name)
	}

	headerDomain, err := normalizeDomain(header.Domain)
	if err != nil {
		return reject(ReasonPublisherMismatch, "protected domain: %w", err)
	}
	keyDomain, err := normalizeDomain(key.Domain)
	if err != nil {
		return reject(ReasonPublisherMismatch, "key domain: %w", err)
	}
	if headerDomain != keyDomain {
		return reject(ReasonPublisherMismatch, "protected domain %q does not match key domain %q", headerDomain, keyDomain)
	}
	cardDomain, err := publisherURLDomain(card.Entity.Publisher.URL)
	if err != nil {
		return reject(ReasonPublisherMismatch, "card publisher url: %w", err)
	}
	if headerDomain != cardDomain {
		return reject(ReasonPublisherMismatch, "protected domain %q does not match card publisher domain %q", headerDomain, cardDomain)
	}
	if opts.ExpectedPublisher != "" && opts.ExpectedPublisher != header.Publisher {
		return reject(ReasonPublisherMismatch, "expected publisher %q, got %q", opts.ExpectedPublisher, header.Publisher)
	}
	if opts.ExpectedDomain != "" {
		expectedDomain, err := normalizeDomain(opts.ExpectedDomain)
		if err != nil {
			return reject(ReasonPublisherMismatch, "expected domain: %w", err)
		}
		if expectedDomain != headerDomain {
			return reject(ReasonPublisherMismatch, "expected domain %q, got %q", expectedDomain, headerDomain)
		}
	}
	return nil
}

func parseRequiredTime(name, value string) (time.Time, error) {
	if value == "" {
		return time.Time{}, fmt.Errorf("%s is required", name)
	}
	parsed, err := time.Parse(time.RFC3339, value)
	if err != nil {
		return time.Time{}, fmt.Errorf("%s must be RFC3339: %w", name, err)
	}
	return parsed.UTC(), nil
}

func sha256Digest(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func publisherURLDomain(rawURL string) (string, error) {
	if rawURL == "" {
		return "", fmt.Errorf("publisher url is required for signed envelopes")
	}
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return "", err
	}
	if parsed.Scheme != "https" {
		return "", fmt.Errorf("publisher url must use https")
	}
	if parsed.User != nil {
		return "", fmt.Errorf("publisher url must not contain userinfo")
	}
	if parsed.Host == "" {
		return "", fmt.Errorf("publisher url host is required")
	}
	return normalizeDomain(parsed.Hostname())
}

func normalizeDomain(value string) (string, error) {
	domain := strings.TrimSuffix(strings.ToLower(strings.TrimSpace(value)), ".")
	if domain == "" {
		return "", fmt.Errorf("domain is required")
	}
	if len(domain) > MaxPublisherDomainBytes {
		return "", fmt.Errorf("domain exceeds %d bytes", MaxPublisherDomainBytes)
	}
	labels := strings.Split(domain, ".")
	for _, label := range labels {
		if label == "" {
			return "", fmt.Errorf("domain contains an empty label")
		}
		if len(label) > 63 {
			return "", fmt.Errorf("domain label %q exceeds 63 bytes", label)
		}
		if strings.HasPrefix(label, "-") || strings.HasSuffix(label, "-") {
			return "", fmt.Errorf("domain label %q must not start or end with hyphen", label)
		}
		for _, r := range label {
			if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' {
				continue
			}
			return "", fmt.Errorf("domain label %q contains unsupported character %q", label, r)
		}
	}
	return domain, nil
}
