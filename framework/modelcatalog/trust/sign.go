package trust

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

type SigningKey struct {
	KeyID         string
	PublisherName string
	Domain        string
	PrivateKey    ed25519.PrivateKey
}

type SigningOptions struct {
	SignedAt  time.Time
	NotBefore time.Time
	ExpiresAt time.Time
}

func SignAgentCard(card agentcard.AgentModelCard, key SigningKey, opts SigningOptions) (SignedAgentCardEnvelope, error) {
	if key.KeyID == "" {
		return SignedAgentCardEnvelope{}, fmt.Errorf("key id is required")
	}
	if len(key.PrivateKey) != ed25519.PrivateKeySize {
		return SignedAgentCardEnvelope{}, fmt.Errorf("Ed25519 private key must be %d bytes", ed25519.PrivateKeySize)
	}
	if err := validatePublisherName(key.PublisherName); err != nil {
		return SignedAgentCardEnvelope{}, err
	}
	domain, err := normalizeDomain(key.Domain)
	if err != nil {
		return SignedAgentCardEnvelope{}, err
	}
	signedAt := opts.SignedAt.UTC()
	if signedAt.IsZero() {
		signedAt = time.Now().UTC()
	}
	expiresAt := opts.ExpiresAt.UTC()
	if expiresAt.IsZero() {
		expiresAt = signedAt.Add(DefaultMaxSignatureAge)
	}

	payload, err := canonicalCardPayload(card)
	if err != nil {
		return SignedAgentCardEnvelope{}, err
	}
	digest := sha256Digest(payload)
	header := ProtectedHeader{
		Type:             EnvelopeType,
		Algorithm:        AlgorithmEdDSA,
		KeyID:            key.KeyID,
		Canonicalization: CanonicalizationSubsetV1,
		PayloadDigest: agentcard.Digest{
			Algorithm: DigestSHA256,
			Value:     digest,
		},
		Publisher:    key.PublisherName,
		Domain:       domain,
		CardVersion:  card.Entity.Version.Version,
		EvidenceOnly: true,
		SignedAt:     signedAt.Format(time.RFC3339),
		ExpiresAt:    expiresAt.Format(time.RFC3339),
	}
	if !opts.NotBefore.IsZero() {
		header.NotBefore = opts.NotBefore.UTC().Format(time.RFC3339)
	}
	protected, err := canonicalProtectedHeader(header)
	if err != nil {
		return SignedAgentCardEnvelope{}, err
	}

	envelope := SignedAgentCardEnvelope{
		Protected: base64.RawURLEncoding.EncodeToString(protected),
		Payload:   base64.RawURLEncoding.EncodeToString(payload),
	}
	signingInput := envelope.Protected + "." + envelope.Payload
	envelope.Signature = base64.RawURLEncoding.EncodeToString(ed25519.Sign(key.PrivateKey, []byte(signingInput)))
	return envelope, nil
}

func canonicalProtectedHeader(header ProtectedHeader) ([]byte, error) {
	data, err := json.Marshal(header)
	if err != nil {
		return nil, err
	}
	if len(data) > MaxProtectedBytes {
		return nil, fmt.Errorf("protected header exceeds %d bytes", MaxProtectedBytes)
	}
	return canonicalizeJSON(data)
}
