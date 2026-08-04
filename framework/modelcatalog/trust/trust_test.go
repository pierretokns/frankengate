package trust

import (
	"bytes"
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

var fixedNow = time.Date(2026, 8, 4, 12, 0, 0, 0, time.UTC)

func TestVerifySignedAgentCardEvidenceAndPolicyAdmission(t *testing.T) {
	key := testSigningKey("publisher-key", 1, "Example Publisher", "publisher.example")
	verifier := testVerifier(t, []KeyRecord{testKeyRecord(key, nil)}, fixedNow)
	envelope := signTestCard(t, testAgentCard(), key, fixedNow.Add(-time.Hour), fixedNow.Add(time.Hour))

	result, err := verifier.VerifyEnvelope(envelope)
	if err != nil {
		t.Fatalf("verify envelope: %v", err)
	}
	if result.Evidence.CardDigest.Algorithm != DigestSHA256 || result.Evidence.CardDigest.Value == "" {
		t.Fatalf("verification did not bind sha256 card digest: %+v", result.Evidence.CardDigest)
	}
	if result.Evidence.CardVersion != "2026.08.04" {
		t.Fatalf("verification did not bind card version: %q", result.Evidence.CardVersion)
	}
	if !result.Evidence.EvidenceOnly || result.Evidence.RoutingAuthorized || result.Evidence.PolicyAdmitted {
		t.Fatalf("signature evidence must not authorize routing or policy admission: %+v", result.Evidence)
	}

	record, err := RecordVerification(NewCardTrustRecord(fixedNow), result.Evidence, fixedNow)
	if err != nil {
		t.Fatalf("record verification: %v", err)
	}
	if record.State != TrustStateVerified || record.PolicyAdmitted {
		t.Fatalf("verification should produce verified, not trusted: %+v", record)
	}
	record, err = AdmitByPolicy(record, result.Evidence.CardDigest, result.Evidence.CardVersion, fixedNow)
	if err != nil {
		t.Fatalf("policy admit: %v", err)
	}
	if record.State != TrustStateTrusted || !record.PolicyAdmitted || record.Evidence.RoutingAuthorized {
		t.Fatalf("policy admission should trust without claiming signature routing authorization: %+v", record)
	}
}

func TestRejectsTamperAndMalformedSignature(t *testing.T) {
	key := testSigningKey("publisher-key", 2, "Example Publisher", "publisher.example")
	verifier := testVerifier(t, []KeyRecord{testKeyRecord(key, nil)}, fixedNow)
	envelope := signTestCard(t, testAgentCard(), key, fixedNow.Add(-time.Hour), fixedNow.Add(time.Hour))

	payload := mustDecodeSegment(t, envelope.Payload)
	payload = bytes.Replace(payload, []byte("Test card"), []byte("Best card"), 1)
	envelope.Payload = base64.RawURLEncoding.EncodeToString(payload)
	assertVerifyReason(t, verifier, envelope, ReasonInvalidSignature)

	envelope = signTestCard(t, testAgentCard(), key, fixedNow.Add(-time.Hour), fixedNow.Add(time.Hour))
	envelope.Signature = "not-base64$$"
	assertVerifyReason(t, verifier, envelope, ReasonMalformedSignature)
}

func TestKeyRolloverUnknownAndRevokedKeys(t *testing.T) {
	oldKey := testSigningKey("old-key", 3, "Example Publisher", "publisher.example")
	newKey := testSigningKey("new-key", 4, "Example Publisher", "publisher.example")
	oldRecord := testKeyRecord(oldKey, func(record *KeyRecord) {
		record.ValidUntil = fixedNow.Add(-10 * time.Minute)
	})
	newRecord := testKeyRecord(newKey, func(record *KeyRecord) {
		record.ValidFrom = fixedNow.Add(-10 * time.Minute)
	})
	verifier := testVerifier(t, []KeyRecord{oldRecord, newRecord}, fixedNow)

	newEnvelope := signTestCard(t, testAgentCard(), newKey, fixedNow.Add(-time.Minute), fixedNow.Add(time.Hour))
	if _, err := verifier.VerifyEnvelope(newEnvelope); err != nil {
		t.Fatalf("new rollover key should verify: %v", err)
	}

	oldEnvelope := signTestCard(t, testAgentCard(), oldKey, fixedNow.Add(-time.Minute), fixedNow.Add(time.Hour))
	assertVerifyReason(t, verifier, oldEnvelope, ReasonStaleSignature)

	unknownEnvelope := signTestCard(t, testAgentCard(), testSigningKey("unknown-key", 5, "Example Publisher", "publisher.example"), fixedNow.Add(-time.Minute), fixedNow.Add(time.Hour))
	assertVerifyReason(t, verifier, unknownEnvelope, ReasonUnknownKey)

	revokedRecord := testKeyRecord(newKey, func(record *KeyRecord) {
		record.RevokedAt = fixedNow.Add(-time.Minute)
	})
	revokedVerifier := testVerifier(t, []KeyRecord{revokedRecord}, fixedNow)
	assertVerifyReason(t, revokedVerifier, newEnvelope, ReasonRevokedKey)
}

func TestRejectsPublisherTakeoverAndStaleCard(t *testing.T) {
	key := testSigningKey("publisher-key", 6, "Example Publisher", "publisher.example")
	verifier := testVerifier(t, []KeyRecord{testKeyRecord(key, nil)}, fixedNow)

	takeover := testAgentCard()
	takeover.Entity.Publisher.URL = "https://evil.example"
	takeoverEnvelope := signTestCard(t, takeover, key, fixedNow.Add(-time.Hour), fixedNow.Add(time.Hour))
	assertVerifyReason(t, verifier, takeoverEnvelope, ReasonPublisherMismatch)

	staleEnvelope := signTestCard(t, testAgentCard(), key, fixedNow.Add(-48*time.Hour), fixedNow.Add(-47*time.Hour))
	assertVerifyReason(t, verifier, staleEnvelope, ReasonStaleSignature)
}

func TestRejectsUnsupportedAlgorithmAndOversizedEnvelopeFields(t *testing.T) {
	key := testSigningKey("publisher-key", 7, "Example Publisher", "publisher.example")
	verifier := testVerifier(t, []KeyRecord{testKeyRecord(key, nil)}, fixedNow)
	envelope := signTestCard(t, testAgentCard(), key, fixedNow.Add(-time.Hour), fixedNow.Add(time.Hour))

	var header ProtectedHeader
	if err := json.Unmarshal(mustDecodeSegment(t, envelope.Protected), &header); err != nil {
		t.Fatalf("decode protected header: %v", err)
	}
	header.Algorithm = "none"
	protected, err := canonicalProtectedHeader(header)
	if err != nil {
		t.Fatalf("canonical protected header: %v", err)
	}
	envelope.Protected = base64.RawURLEncoding.EncodeToString(protected)
	assertVerifyReason(t, verifier, envelope, ReasonUnsupportedAlgorithm)

	emptyStore, err := NewStaticKeyStore(nil)
	if err != nil {
		t.Fatalf("empty key store: %v", err)
	}
	emptyVerifier := NewVerifier(emptyStore, VerificationOptions{Now: func() time.Time { return fixedNow }})
	signature := base64.RawURLEncoding.EncodeToString(bytes.Repeat([]byte{0}, ed25519.SignatureSize))
	assertVerifyReason(t, emptyVerifier, SignedAgentCardEnvelope{
		Protected: base64.RawURLEncoding.EncodeToString(bytes.Repeat([]byte{'x'}, MaxProtectedBytes+1)),
		Payload:   "e30",
		Signature: signature,
	}, ReasonOversizedProtected)
	assertVerifyReason(t, emptyVerifier, SignedAgentCardEnvelope{
		Protected: "e30",
		Payload:   base64.RawURLEncoding.EncodeToString(bytes.Repeat([]byte{'x'}, MaxPayloadBytes+1)),
		Signature: signature,
	}, ReasonOversizedPayload)
}

func TestTrustStateQuarantineKillAndReviewTransitions(t *testing.T) {
	key := testSigningKey("publisher-key", 8, "Example Publisher", "publisher.example")
	verifier := testVerifier(t, []KeyRecord{testKeyRecord(key, nil)}, fixedNow)
	result, err := verifier.VerifyEnvelope(signTestCard(t, testAgentCard(), key, fixedNow.Add(-time.Hour), fixedNow.Add(time.Hour)))
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	record, err := RecordVerification(NewCardTrustRecord(fixedNow), result.Evidence, fixedNow)
	if err != nil {
		t.Fatalf("record verification: %v", err)
	}

	quarantined, err := Quarantine(record, "operator kill switch pending review", fixedNow)
	if err != nil {
		t.Fatalf("quarantine: %v", err)
	}
	if quarantined.State != TrustStateQuarantined || quarantined.PolicyAdmitted {
		t.Fatalf("quarantine must remove policy admission: %+v", quarantined)
	}
	_, err = AdmitByPolicy(quarantined, result.Evidence.CardDigest, result.Evidence.CardVersion, fixedNow)
	assertReason(t, err, ReasonInvalidTrustState)

	review, err := RequireReview(record, "publisher rotation requires manual review", fixedNow)
	if err != nil {
		t.Fatalf("require review: %v", err)
	}
	if review.State != TrustStateReviewRequired || review.PolicyAdmitted {
		t.Fatalf("review must be non-admitted: %+v", review)
	}

	killed, err := Kill(record, "publisher key compromised", fixedNow)
	if err != nil {
		t.Fatalf("kill: %v", err)
	}
	if killed.State != TrustStateKilled || killed.PolicyAdmitted {
		t.Fatalf("kill must be terminal and non-admitted: %+v", killed)
	}
	_, err = Quarantine(killed, "cannot revive killed card", fixedNow)
	assertReason(t, err, ReasonInvalidTrustState)
	_, err = RecordVerification(killed, result.Evidence, fixedNow)
	assertReason(t, err, ReasonInvalidTrustState)
}

func testAgentCard() agentcard.AgentModelCard {
	return agentcard.AgentModelCard{
		SchemaVersion: agentcard.SchemaVersion,
		Entity: agentcard.CatalogEntity{
			SchemaVersion: agentcard.SchemaVersion,
			Kind:          agentcard.EntityKindA2AAgent,
			Identity: agentcard.Identity{
				ID:        "agent.example.publisher",
				Namespace: "a2a/example",
				Name:      "example publisher agent",
				Provider:  "example",
			},
			Version: agentcard.VersionInfo{Version: "2026.08.04"},
			Source: agentcard.Source{
				Type: agentcard.SourceA2ACard,
				URI:  "https://publisher.example/.well-known/agent-card.json",
			},
			Publisher: agentcard.Publisher{
				Name: "Example Publisher",
				URL:  "https://publisher.example",
			},
			Capabilities: agentcard.CapabilitySet{
				Modalities: []agentcard.Modality{agentcard.ModalityText},
				Operations: []agentcard.Operation{agentcard.OperationA2AMessage},
			},
			Provenance: agentcard.Provenance{Status: agentcard.ProvenanceSelfReported},
		},
		Narrative: agentcard.Narrative{DisplayName: "Test card"},
		Interfaces: []agentcard.Interface{{
			Type:            agentcard.InterfaceA2A,
			URL:             "https://publisher.example/a2a",
			ProtocolVersion: "1.0.1",
			Operations:      []agentcard.Operation{agentcard.OperationA2AMessage},
		}},
		Skills: []agentcard.Skill{{
			ID:               "answer",
			Name:             "Answer",
			InputModalities:  []agentcard.Modality{agentcard.ModalityText},
			OutputModalities: []agentcard.Modality{agentcard.ModalityText},
			Operations:       []agentcard.Operation{agentcard.OperationA2AMessage},
		}},
	}
}

func testSigningKey(keyID string, seedByte byte, publisher, domain string) SigningKey {
	seed := bytes.Repeat([]byte{seedByte}, ed25519.SeedSize)
	privateKey := ed25519.NewKeyFromSeed(seed)
	return SigningKey{KeyID: keyID, PublisherName: publisher, Domain: domain, PrivateKey: privateKey}
}

func testKeyRecord(key SigningKey, mutate func(*KeyRecord)) KeyRecord {
	record := KeyRecord{
		KeyID: key.KeyID, Algorithm: AlgorithmEdDSA, PublicKey: key.PrivateKey.Public().(ed25519.PublicKey),
		PublisherName: key.PublisherName, Domain: key.Domain,
		ValidFrom: fixedNow.Add(-24 * time.Hour), ValidUntil: fixedNow.Add(24 * time.Hour),
	}
	if mutate != nil {
		mutate(&record)
	}
	return record
}

func testVerifier(t *testing.T, records []KeyRecord, now time.Time) *Verifier {
	t.Helper()
	store, err := NewStaticKeyStore(records)
	if err != nil {
		t.Fatalf("new key store: %v", err)
	}
	return NewVerifier(store, VerificationOptions{Now: func() time.Time { return now }, MaxSignatureAge: 24 * time.Hour, ClockSkew: time.Minute})
}

func signTestCard(t *testing.T, card agentcard.AgentModelCard, key SigningKey, signedAt, expiresAt time.Time) SignedAgentCardEnvelope {
	t.Helper()
	envelope, err := SignAgentCard(card, key, SigningOptions{SignedAt: signedAt, ExpiresAt: expiresAt})
	if err != nil {
		t.Fatalf("sign card: %v", err)
	}
	return envelope
}

func mustDecodeSegment(t *testing.T, segment string) []byte {
	t.Helper()
	data, err := base64.RawURLEncoding.DecodeString(segment)
	if err != nil {
		t.Fatalf("decode segment: %v", err)
	}
	return data
}

func assertVerifyReason(t *testing.T, verifier *Verifier, envelope SignedAgentCardEnvelope, reason RejectReason) {
	t.Helper()
	_, err := verifier.VerifyEnvelope(envelope)
	assertReason(t, err, reason)
}

func assertReason(t *testing.T, err error, reason RejectReason) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected %s error", reason)
	}
	var verifyErr *VerificationError
	if !errors.As(err, &verifyErr) {
		t.Fatalf("expected VerificationError, got %T: %v", err, err)
	}
	if verifyErr.Reason != reason {
		t.Fatalf("expected reason %s, got %s: %v", reason, verifyErr.Reason, err)
	}
}
