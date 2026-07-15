package vkcrypto

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"testing"
)

type pepperKey struct {
	tenantID string
	purpose  PepperPurpose
	version  string
}

type testPepperResolver struct {
	activeVersion map[string]string
	peppers       map[pepperKey]Pepper
	err           error
}

func newTestPepperResolver() *testPepperResolver {
	return &testPepperResolver{
		activeVersion: make(map[string]string),
		peppers:       make(map[pepperKey]Pepper),
	}
}

func (r *testPepperResolver) add(tenantID string, purpose PepperPurpose, version string, material string, active bool) {
	r.peppers[pepperKey{tenantID: tenantID, purpose: purpose, version: version}] = Pepper{
		Version:  version,
		Material: []byte(material),
	}
	if active {
		r.activeVersion[r.activeKey(tenantID, purpose)] = version
	}
}

func (r *testPepperResolver) ActivePepper(_ context.Context, tenantID string, purpose PepperPurpose) (Pepper, error) {
	if r.err != nil {
		return Pepper{}, r.err
	}
	version := r.activeVersion[r.activeKey(tenantID, purpose)]
	return r.Pepper(context.Background(), tenantID, purpose, version)
}

func (r *testPepperResolver) Pepper(_ context.Context, tenantID string, purpose PepperPurpose, version string) (Pepper, error) {
	if r.err != nil {
		return Pepper{}, r.err
	}
	pepper, ok := r.peppers[pepperKey{tenantID: tenantID, purpose: purpose, version: version}]
	if !ok {
		return Pepper{}, fmt.Errorf("missing pepper %s/%s/%s", tenantID, purpose, version)
	}
	return pepper, nil
}

func (r *testPepperResolver) activeKey(tenantID string, purpose PepperPurpose) string {
	return tenantID + "\x00" + string(purpose)
}

func resolverWithTenant(tenantID string) *testPepperResolver {
	resolver := newTestPepperResolver()
	resolver.add(tenantID, PepperPurposeFingerprint, "fp-v1", strongMaterial("fingerprint-pepper-"+tenantID), true)
	resolver.add(tenantID, PepperPurposeVerification, "verify-v1", strongMaterial("verification-pepper-"+tenantID), true)
	return resolver
}

func strongMaterial(label string) string {
	return label + ":" + strings.Repeat("x", 64)
}

func TestCreateRecordUsesTenantScopedIndexedFingerprintAndSeparateVerificationDigest(t *testing.T) {
	ctx := context.Background()
	rawKey := []byte("vk_live_secret")
	resolver := resolverWithTenant("tenant-a")
	resolver.add("tenant-b", PepperPurposeFingerprint, "fp-v1", strongMaterial("fingerprint-pepper-tenant-a"), true)
	resolver.add("tenant-b", PepperPurposeVerification, "verify-v1", strongMaterial("verification-pepper-tenant-a"), true)
	manager := NewManager(resolver)

	record, err := manager.CreateRecord(ctx, "tenant-a", rawKey)
	if err != nil {
		t.Fatalf("CreateRecord returned error: %v", err)
	}
	if err := record.Validate(); err != nil {
		t.Fatalf("record should validate: %v", err)
	}
	if record.TenantID != "tenant-a" {
		t.Fatalf("tenant id = %q, want tenant-a", record.TenantID)
	}
	if record.Algorithm != AlgorithmHMACSHA256 {
		t.Fatalf("algorithm = %q, want %q", record.Algorithm, AlgorithmHMACSHA256)
	}
	if record.FingerprintPepperVersion != "fp-v1" || record.VerificationPepperVersion != "verify-v1" {
		t.Fatalf("pepper versions not recorded: %#v", record)
	}
	if record.Fingerprint == "" || record.VerificationDigest == "" {
		t.Fatalf("fingerprint and verification digest must be populated: %#v", record)
	}
	if record.Fingerprint == record.VerificationDigest {
		t.Fatalf("indexed fingerprint and verification digest must use separate domains")
	}
	if strings.Contains(fmt.Sprintf("%+v", record), string(rawKey)) {
		t.Fatalf("record must not store raw virtual key material: %#v", record)
	}

	tenantBRecord, err := manager.CreateRecord(ctx, "tenant-b", rawKey)
	if err != nil {
		t.Fatalf("CreateRecord tenant-b returned error: %v", err)
	}
	if tenantBRecord.Fingerprint == record.Fingerprint {
		t.Fatalf("same key must not have same indexed fingerprint across tenants")
	}
	if tenantBRecord.VerificationDigest == record.VerificationDigest {
		t.Fatalf("same key must not have same verification digest across tenants")
	}
}

func TestVerifyUsesStoredPepperAndReturnsActiveRotation(t *testing.T) {
	ctx := context.Background()
	rawKey := []byte("vk_live_rotating")
	resolver := newTestPepperResolver()
	resolver.add("tenant-a", PepperPurposeFingerprint, "fp-v1", strongMaterial("old-fingerprint-pepper"), false)
	resolver.add("tenant-a", PepperPurposeVerification, "verify-v1", strongMaterial("old-verification-pepper"), false)
	resolver.add("tenant-a", PepperPurposeFingerprint, "fp-v2", strongMaterial("new-fingerprint-pepper"), true)
	resolver.add("tenant-a", PepperPurposeVerification, "verify-v2", strongMaterial("new-verification-pepper"), true)
	manager := NewManager(resolver)

	oldRecord, err := manager.RestoreRecord(ctx, "tenant-a", rawKey, "fp-v1", "verify-v1")
	if err != nil {
		t.Fatalf("RestoreRecord returned error: %v", err)
	}

	result, err := manager.Verify(ctx, oldRecord, rawKey)
	if err != nil {
		t.Fatalf("Verify returned error: %v", err)
	}
	if !result.Match {
		t.Fatalf("stored old verification pepper should still verify")
	}
	if !result.NeedsRotation || result.Rotated == nil {
		t.Fatalf("old record should return a rotated single-write replacement: %#v", result)
	}
	if result.Rotated.FingerprintPepperVersion != "fp-v2" || result.Rotated.VerificationPepperVersion != "verify-v2" {
		t.Fatalf("rotated record should use active pepper versions: %#v", result.Rotated)
	}
	if oldRecord.FingerprintPepperVersion != "fp-v1" || oldRecord.VerificationPepperVersion != "verify-v1" {
		t.Fatalf("Verify must not mutate the stored old record: %#v", oldRecord)
	}

	activeResult, err := manager.Verify(ctx, *result.Rotated, rawKey)
	if err != nil {
		t.Fatalf("Verify rotated returned error: %v", err)
	}
	if !activeResult.Match || activeResult.NeedsRotation || activeResult.Rotated != nil {
		t.Fatalf("active record should verify without rotation: %#v", activeResult)
	}
}

func TestFingerprintsForLookupSupportsDualReadWhileCreateSingleWritesActive(t *testing.T) {
	ctx := context.Background()
	rawKey := []byte("vk_live_lookup")
	resolver := newTestPepperResolver()
	resolver.add("tenant-a", PepperPurposeFingerprint, "fp-v1", strongMaterial("old-fingerprint-pepper"), false)
	resolver.add("tenant-a", PepperPurposeVerification, "verify-v1", strongMaterial("old-verification-pepper"), false)
	resolver.add("tenant-a", PepperPurposeFingerprint, "fp-v2", strongMaterial("new-fingerprint-pepper"), true)
	resolver.add("tenant-a", PepperPurposeVerification, "verify-v2", strongMaterial("new-verification-pepper"), true)
	manager := NewManager(resolver)

	candidates, err := manager.FingerprintsForLookup(ctx, "tenant-a", rawKey, []string{"fp-v1", "fp-v2", "fp-v1"})
	if err != nil {
		t.Fatalf("FingerprintsForLookup returned error: %v", err)
	}
	if len(candidates) != 2 {
		t.Fatalf("expected active plus one legacy candidate, got %#v", candidates)
	}
	if !candidates[0].Active || candidates[0].PepperVersion != "fp-v2" {
		t.Fatalf("active fingerprint must be first: %#v", candidates)
	}
	if candidates[1].Active || candidates[1].PepperVersion != "fp-v1" {
		t.Fatalf("legacy fingerprint candidate not preserved: %#v", candidates)
	}
	if candidates[0].Fingerprint == candidates[1].Fingerprint {
		t.Fatalf("old and new pepper versions must not produce same lookup fingerprint")
	}

	record, err := manager.CreateRecord(ctx, "tenant-a", rawKey)
	if err != nil {
		t.Fatalf("CreateRecord returned error: %v", err)
	}
	if record.FingerprintPepperVersion != "fp-v2" || record.VerificationPepperVersion != "verify-v2" {
		t.Fatalf("writes must use only active pepper versions: %#v", record)
	}
}

func TestWrongPepperOrWrongKeyDoesNotVerify(t *testing.T) {
	ctx := context.Background()
	rawKey := []byte("vk_live_secret")
	record, err := NewManager(resolverWithTenant("tenant-a")).CreateRecord(ctx, "tenant-a", rawKey)
	if err != nil {
		t.Fatalf("CreateRecord returned error: %v", err)
	}

	wrongPepperResolver := newTestPepperResolver()
	wrongPepperResolver.add("tenant-a", PepperPurposeFingerprint, "fp-v1", strongMaterial("fingerprint-pepper-tenant-a"), true)
	wrongPepperResolver.add("tenant-a", PepperPurposeVerification, "verify-v1", strongMaterial("wrong-verification-pepper"), true)
	wrongPepperResult, err := NewManager(wrongPepperResolver).Verify(ctx, record, rawKey)
	if err != nil {
		t.Fatalf("Verify with wrong pepper returned error: %v", err)
	}
	if wrongPepperResult.Match {
		t.Fatalf("record verified with wrong verification pepper")
	}

	wrongKeyResult, err := NewManager(resolverWithTenant("tenant-a")).Verify(ctx, record, []byte("vk_live_other"))
	if err != nil {
		t.Fatalf("Verify with wrong key returned error: %v", err)
	}
	if wrongKeyResult.Match {
		t.Fatalf("record verified with wrong virtual key")
	}
}

func TestVerifyRejectsTamperedFingerprint(t *testing.T) {
	ctx := context.Background()
	rawKey := []byte("vk_live_secret")
	manager := NewManager(resolverWithTenant("tenant-a"))
	record, err := manager.CreateRecord(ctx, "tenant-a", rawKey)
	if err != nil {
		t.Fatalf("CreateRecord returned error: %v", err)
	}
	record.Fingerprint = strings.Repeat("c", 64)

	result, err := manager.Verify(ctx, record, rawKey)
	if err != nil {
		t.Fatalf("Verify returned error: %v", err)
	}
	if result.Match {
		t.Fatalf("tampered indexed fingerprint authenticated")
	}
}

func TestResolverVersionConfusionFailsClosed(t *testing.T) {
	ctx := context.Background()
	rawKey := []byte("vk_live_secret")
	record, err := NewManager(resolverWithTenant("tenant-a")).CreateRecord(ctx, "tenant-a", rawKey)
	if err != nil {
		t.Fatalf("CreateRecord returned error: %v", err)
	}

	confusedResolver := resolverWithTenant("tenant-a")
	confusedResolver.peppers[pepperKey{tenantID: "tenant-a", purpose: PepperPurposeVerification, version: "verify-v1"}] = Pepper{
		Version:  "verify-v2",
		Material: []byte(strongMaterial("verification-pepper-tenant-a")),
	}

	result, err := NewManager(confusedResolver).Verify(ctx, record, rawKey)
	if err == nil {
		t.Fatalf("Verify succeeded with resolver-returned version mismatch: %#v", result)
	}
	if strings.Contains(err.Error(), string(rawKey)) {
		t.Fatalf("error leaked raw virtual key: %v", err)
	}
}

func TestWeakPepperMaterialRejected(t *testing.T) {
	ctx := context.Background()
	rawKey := []byte("vk_live_secret")
	resolver := newTestPepperResolver()
	resolver.add("tenant-a", PepperPurposeFingerprint, "fp-v1", "short", true)
	resolver.add("tenant-a", PepperPurposeVerification, "verify-v1", strongMaterial("verification-pepper-tenant-a"), true)

	record, err := NewManager(resolver).CreateRecord(ctx, "tenant-a", rawKey)
	if err == nil {
		t.Fatalf("CreateRecord accepted weak pepper material: %#v", record)
	}
	if strings.Contains(err.Error(), string(rawKey)) {
		t.Fatalf("error leaked raw virtual key: %v", err)
	}
	if strings.Contains(fmt.Sprintf("%+v", record), string(rawKey)) {
		t.Fatalf("record leaked raw virtual key: %#v", record)
	}
}

func TestKMSDegradedFailsClosedWithoutLookupFallback(t *testing.T) {
	ctx := context.Background()
	resolver := resolverWithTenant("tenant-a")
	resolver.err = errors.New("kms unavailable")
	manager := NewManager(resolver)

	record, err := manager.CreateRecord(ctx, "tenant-a", []byte("vk_live_secret"))
	if err == nil {
		t.Fatalf("CreateRecord succeeded during KMS degradation")
	}
	var degraded *KMSDegradedError
	if !errors.As(err, &degraded) {
		t.Fatalf("CreateRecord error = %T, want KMSDegradedError", err)
	}
	if record != (Record{}) {
		t.Fatalf("degraded create must not return a partial record: %#v", record)
	}

	candidates, err := manager.FingerprintsForLookup(ctx, "tenant-a", []byte("vk_live_secret"), []string{"fp-v1"})
	if err == nil || !errors.As(err, &degraded) {
		t.Fatalf("lookup should fail closed with KMSDegradedError, got %T %v", err, err)
	}
	if len(candidates) != 0 {
		t.Fatalf("degraded lookup must not return fallback hashes: %#v", candidates)
	}

	_, err = manager.Verify(ctx, Record{
		TenantID:                  "tenant-a",
		Algorithm:                 AlgorithmHMACSHA256,
		Fingerprint:               strings.Repeat("a", 64),
		FingerprintPepperVersion:  "fp-v1",
		VerificationDigest:        strings.Repeat("b", 64),
		VerificationPepperVersion: "verify-v1",
	}, []byte("vk_live_secret"))
	if err == nil || !errors.As(err, &degraded) {
		t.Fatalf("verify should fail closed with KMSDegradedError, got %T %v", err, err)
	}
}

func TestMalformedRecordsRejected(t *testing.T) {
	valid := Record{
		TenantID:                  "tenant-a",
		Algorithm:                 AlgorithmHMACSHA256,
		Fingerprint:               strings.Repeat("a", 64),
		FingerprintPepperVersion:  "fp-v1",
		VerificationDigest:        strings.Repeat("b", 64),
		VerificationPepperVersion: "verify-v1",
	}
	tests := []struct {
		name   string
		mutate func(*Record)
	}{
		{name: "missing tenant", mutate: func(r *Record) { r.TenantID = "" }},
		{name: "unsupported algorithm", mutate: func(r *Record) { r.Algorithm = "sha256" }},
		{name: "missing fingerprint", mutate: func(r *Record) { r.Fingerprint = "" }},
		{name: "missing fingerprint pepper version", mutate: func(r *Record) { r.FingerprintPepperVersion = "" }},
		{name: "missing verification digest", mutate: func(r *Record) { r.VerificationDigest = "" }},
		{name: "missing verification pepper version", mutate: func(r *Record) { r.VerificationPepperVersion = "" }},
		{name: "malformed fingerprint", mutate: func(r *Record) { r.Fingerprint = "not-hex" }},
		{name: "short fingerprint", mutate: func(r *Record) { r.Fingerprint = "abcd" }},
		{name: "malformed verification digest", mutate: func(r *Record) { r.VerificationDigest = "not-hex" }},
		{name: "short verification digest", mutate: func(r *Record) { r.VerificationDigest = "abcd" }},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			record := valid
			tt.mutate(&record)
			if err := record.Validate(); err == nil {
				t.Fatalf("Validate() succeeded, want error")
			}
			_, err := NewManager(resolverWithTenant("tenant-a")).Verify(context.Background(), record, []byte("vk_live_secret"))
			if err == nil {
				t.Fatalf("Verify() succeeded for malformed record")
			}
		})
	}
}
