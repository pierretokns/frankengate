package vkcrypto

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
)

const (
	AlgorithmHMACSHA256 Algorithm = "hmac-sha256.v1"

	PepperPurposeFingerprint  PepperPurpose = "fingerprint"
	PepperPurposeVerification PepperPurpose = "verification"
)

const hmacDomain = "bifrost.virtual_key.v1"
const minimumPepperBytes = 32

type Algorithm string

type PepperPurpose string

type Pepper struct {
	Version  string
	Material []byte
}

type PepperResolver interface {
	ActivePepper(ctx context.Context, tenantID string, purpose PepperPurpose) (Pepper, error)
	Pepper(ctx context.Context, tenantID string, purpose PepperPurpose, version string) (Pepper, error)
}

type KMSDegradedError struct {
	Op  string
	Err error
}

func (e *KMSDegradedError) Error() string {
	if e == nil {
		return "kms degraded"
	}
	if e.Err == nil {
		return "kms degraded during " + e.Op
	}
	return "kms degraded during " + e.Op + ": " + e.Err.Error()
}

func (e *KMSDegradedError) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Err
}

type Record struct {
	TenantID                  string    `json:"tenant_id"`
	Algorithm                 Algorithm `json:"algorithm"`
	Fingerprint               string    `json:"fingerprint"`
	FingerprintPepperVersion  string    `json:"fingerprint_pepper_version"`
	VerificationDigest        string    `json:"verification_digest"`
	VerificationPepperVersion string    `json:"verification_pepper_version"`
}

type FingerprintCandidate struct {
	Fingerprint   string `json:"fingerprint"`
	PepperVersion string `json:"pepper_version"`
	Active        bool   `json:"active"`
}

type VerificationResult struct {
	Match         bool
	NeedsRotation bool
	Rotated       *Record
}

type Manager struct {
	resolver  PepperResolver
	algorithm Algorithm
}

func NewManager(resolver PepperResolver) *Manager {
	return &Manager{
		resolver:  resolver,
		algorithm: AlgorithmHMACSHA256,
	}
}

func (m *Manager) CreateRecord(ctx context.Context, tenantID string, rawKey []byte) (Record, error) {
	if err := validateInputs(tenantID, rawKey); err != nil {
		return Record{}, err
	}
	fingerprintPepper, err := m.activePepper(ctx, tenantID, PepperPurposeFingerprint)
	if err != nil {
		return Record{}, err
	}
	verificationPepper, err := m.activePepper(ctx, tenantID, PepperPurposeVerification)
	if err != nil {
		return Record{}, err
	}
	return m.recordForPeppers(tenantID, rawKey, fingerprintPepper, verificationPepper)
}

func (m *Manager) RestoreRecord(ctx context.Context, tenantID string, rawKey []byte, fingerprintPepperVersion string, verificationPepperVersion string) (Record, error) {
	if err := validateInputs(tenantID, rawKey); err != nil {
		return Record{}, err
	}
	if fingerprintPepperVersion == "" {
		return Record{}, errors.New("fingerprint pepper version is required")
	}
	if verificationPepperVersion == "" {
		return Record{}, errors.New("verification pepper version is required")
	}
	fingerprintPepper, err := m.pepper(ctx, tenantID, PepperPurposeFingerprint, fingerprintPepperVersion)
	if err != nil {
		return Record{}, err
	}
	verificationPepper, err := m.pepper(ctx, tenantID, PepperPurposeVerification, verificationPepperVersion)
	if err != nil {
		return Record{}, err
	}
	return m.recordForPeppers(tenantID, rawKey, fingerprintPepper, verificationPepper)
}

func (m *Manager) FingerprintsForLookup(ctx context.Context, tenantID string, rawKey []byte, legacyPepperVersions []string) ([]FingerprintCandidate, error) {
	if err := validateInputs(tenantID, rawKey); err != nil {
		return nil, err
	}
	activePepper, err := m.activePepper(ctx, tenantID, PepperPurposeFingerprint)
	if err != nil {
		return nil, err
	}
	candidates := []FingerprintCandidate{{
		Fingerprint:   fingerprint(tenantID, rawKey, activePepper),
		PepperVersion: activePepper.Version,
		Active:        true,
	}}
	seen := map[string]struct{}{activePepper.Version: {}}
	for _, version := range legacyPepperVersions {
		if version == "" {
			continue
		}
		if _, ok := seen[version]; ok {
			continue
		}
		pepper, err := m.pepper(ctx, tenantID, PepperPurposeFingerprint, version)
		if err != nil {
			return nil, err
		}
		candidates = append(candidates, FingerprintCandidate{
			Fingerprint:   fingerprint(tenantID, rawKey, pepper),
			PepperVersion: pepper.Version,
			Active:        false,
		})
		seen[version] = struct{}{}
	}
	return candidates, nil
}

func (m *Manager) Verify(ctx context.Context, record Record, rawKey []byte) (VerificationResult, error) {
	if err := validateInputs(record.TenantID, rawKey); err != nil {
		return VerificationResult{}, err
	}
	if err := record.Validate(); err != nil {
		return VerificationResult{}, err
	}
	fingerprintPepper, err := m.pepper(ctx, record.TenantID, PepperPurposeFingerprint, record.FingerprintPepperVersion)
	if err != nil {
		return VerificationResult{}, err
	}
	verificationPepper, err := m.pepper(ctx, record.TenantID, PepperPurposeVerification, record.VerificationPepperVersion)
	if err != nil {
		return VerificationResult{}, err
	}
	expectedFingerprint, err := decodeDigest(record.Fingerprint, "fingerprint")
	if err != nil {
		return VerificationResult{}, err
	}
	expectedDigest, err := decodeDigest(record.VerificationDigest, "verification digest")
	if err != nil {
		return VerificationResult{}, err
	}
	actualFingerprint := digestBytes(record.TenantID, rawKey, PepperPurposeFingerprint, fingerprintPepper)
	actualDigest := digestBytes(record.TenantID, rawKey, PepperPurposeVerification, verificationPepper)
	if !hmac.Equal(actualFingerprint, expectedFingerprint) || !hmac.Equal(actualDigest, expectedDigest) {
		return VerificationResult{Match: false}, nil
	}

	activeFingerprintPepper, err := m.activePepper(ctx, record.TenantID, PepperPurposeFingerprint)
	if err != nil {
		return VerificationResult{}, err
	}
	activeVerificationPepper, err := m.activePepper(ctx, record.TenantID, PepperPurposeVerification)
	if err != nil {
		return VerificationResult{}, err
	}
	if activeFingerprintPepper.Version == record.FingerprintPepperVersion && activeVerificationPepper.Version == record.VerificationPepperVersion {
		return VerificationResult{Match: true}, nil
	}
	rotated, err := m.recordForPeppers(record.TenantID, rawKey, activeFingerprintPepper, activeVerificationPepper)
	if err != nil {
		return VerificationResult{}, err
	}
	return VerificationResult{
		Match:         true,
		NeedsRotation: true,
		Rotated:       &rotated,
	}, nil
}

func (r Record) Validate() error {
	if r.TenantID == "" {
		return errors.New("tenant_id is required")
	}
	if r.Algorithm != AlgorithmHMACSHA256 {
		return fmt.Errorf("unsupported algorithm %q", r.Algorithm)
	}
	if r.FingerprintPepperVersion == "" {
		return errors.New("fingerprint pepper version is required")
	}
	if r.VerificationPepperVersion == "" {
		return errors.New("verification pepper version is required")
	}
	if _, err := decodeDigest(r.Fingerprint, "fingerprint"); err != nil {
		return err
	}
	if _, err := decodeDigest(r.VerificationDigest, "verification digest"); err != nil {
		return err
	}
	if r.Fingerprint == r.VerificationDigest {
		return errors.New("fingerprint and verification digest must be separate values")
	}
	return nil
}

func (m *Manager) recordForPeppers(tenantID string, rawKey []byte, fingerprintPepper Pepper, verificationPepper Pepper) (Record, error) {
	if err := validatePepper(fingerprintPepper, "fingerprint"); err != nil {
		return Record{}, err
	}
	if err := validatePepper(verificationPepper, "verification"); err != nil {
		return Record{}, err
	}
	record := Record{
		TenantID:                  tenantID,
		Algorithm:                 m.algorithm,
		Fingerprint:               fingerprint(tenantID, rawKey, fingerprintPepper),
		FingerprintPepperVersion:  fingerprintPepper.Version,
		VerificationDigest:        verificationDigest(tenantID, rawKey, verificationPepper),
		VerificationPepperVersion: verificationPepper.Version,
	}
	if err := record.Validate(); err != nil {
		return Record{}, err
	}
	return record, nil
}

func (m *Manager) activePepper(ctx context.Context, tenantID string, purpose PepperPurpose) (Pepper, error) {
	if m == nil || m.resolver == nil {
		return Pepper{}, errors.New("pepper resolver is required")
	}
	pepper, err := m.resolver.ActivePepper(ctx, tenantID, purpose)
	if err != nil {
		return Pepper{}, kmsDegraded("active pepper "+string(purpose), err)
	}
	if err := validatePepper(pepper, string(purpose)); err != nil {
		return Pepper{}, err
	}
	return pepper, nil
}

func (m *Manager) pepper(ctx context.Context, tenantID string, purpose PepperPurpose, version string) (Pepper, error) {
	if m == nil || m.resolver == nil {
		return Pepper{}, errors.New("pepper resolver is required")
	}
	pepper, err := m.resolver.Pepper(ctx, tenantID, purpose, version)
	if err != nil {
		return Pepper{}, kmsDegraded("pepper "+string(purpose)+" "+version, err)
	}
	if pepper.Version != version {
		return Pepper{}, fmt.Errorf("%s pepper resolver returned version %q for requested version %q", purpose, pepper.Version, version)
	}
	if err := validatePepper(pepper, string(purpose)); err != nil {
		return Pepper{}, err
	}
	return pepper, nil
}

func fingerprint(tenantID string, rawKey []byte, pepper Pepper) string {
	return hex.EncodeToString(digestBytes(tenantID, rawKey, PepperPurposeFingerprint, pepper))
}

func verificationDigest(tenantID string, rawKey []byte, pepper Pepper) string {
	return hex.EncodeToString(digestBytes(tenantID, rawKey, PepperPurposeVerification, pepper))
}

func digestBytes(tenantID string, rawKey []byte, purpose PepperPurpose, pepper Pepper) []byte {
	mac := hmac.New(sha256.New, pepper.Material)
	writeHMACField(mac, []byte(hmacDomain))
	writeHMACField(mac, []byte(tenantID))
	writeHMACField(mac, []byte(purpose))
	writeHMACField(mac, rawKey)
	return mac.Sum(nil)
}

type hmacWriter interface {
	Write([]byte) (int, error)
}

func writeHMACField(mac hmacWriter, value []byte) {
	var length [8]byte
	binary.BigEndian.PutUint64(length[:], uint64(len(value)))
	_, _ = mac.Write(length[:])
	_, _ = mac.Write(value)
}

func validateInputs(tenantID string, rawKey []byte) error {
	if tenantID == "" {
		return errors.New("tenant_id is required")
	}
	if len(rawKey) == 0 {
		return errors.New("raw virtual key is required")
	}
	return nil
}

func validatePepper(pepper Pepper, name string) error {
	if pepper.Version == "" {
		return fmt.Errorf("%s pepper version is required", name)
	}
	if len(pepper.Material) < minimumPepperBytes {
		return fmt.Errorf("%s pepper material must be at least %d bytes", name, minimumPepperBytes)
	}
	return nil
}

func decodeDigest(value string, name string) ([]byte, error) {
	if value == "" {
		return nil, fmt.Errorf("%s is required", name)
	}
	decoded, err := hex.DecodeString(value)
	if err != nil {
		return nil, fmt.Errorf("%s must be hex-encoded hmac-sha256: %w", name, err)
	}
	if len(decoded) != sha256.Size {
		return nil, fmt.Errorf("%s must be %d bytes", name, sha256.Size)
	}
	return decoded, nil
}

func kmsDegraded(op string, err error) error {
	var degraded *KMSDegradedError
	if errors.As(err, &degraded) {
		return err
	}
	return &KMSDegradedError{Op: op, Err: err}
}
