package registry

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"
)

const (
	MaxReviewCandidates = 512

	ReviewSnapshotSchemaVersion = "bifrost.registry.review.v1"
)

type ReviewState string

const (
	ReviewStatePending     ReviewState = "pending"
	ReviewStateApproved    ReviewState = "approved"
	ReviewStateQuarantined ReviewState = "quarantined"
)

type ManifestIdentity struct {
	Repository string `json:"repository"`
	Revision   string `json:"revision"`
	Digest     string `json:"digest"`
}

type ManifestCandidateInput struct {
	Data       []byte
	Source     string
	ObservedAt time.Time
	Err        error
}

type ReviewInput struct {
	Identity  ManifestIdentity
	State     ReviewState
	Reviewer  string
	Reason    string
	DecidedAt time.Time
}

type CandidateRecord struct {
	Identity     ManifestIdentity `json:"identity"`
	Manifest     Manifest         `json:"manifest"`
	State        ReviewState      `json:"state"`
	Source       string           `json:"source,omitempty"`
	SubmittedAt  time.Time        `json:"submitted_at"`
	ReviewedAt   *time.Time       `json:"reviewed_at,omitempty"`
	Reviewer     string           `json:"reviewer,omitempty"`
	ReviewReason string           `json:"review_reason,omitempty"`
}

type ReviewSnapshot struct {
	SchemaVersion string            `json:"schema_version"`
	Records       []CandidateRecord `json:"records"`
	Total         int               `json:"total"`
	Pending       int               `json:"pending"`
	Approved      int               `json:"approved"`
	Quarantined   int               `json:"quarantined"`
}

type ReviewStoreOptions struct {
	MaxCandidates int
	Now           func() time.Time
}

type ReviewStore struct {
	mu              sync.RWMutex
	maxCandidates   int
	now             func() time.Time
	records         map[string]CandidateRecord
	revisionDigests map[string]string
}

func NewReviewStore(options ReviewStoreOptions) *ReviewStore {
	maxCandidates := options.MaxCandidates
	if maxCandidates <= 0 || maxCandidates > MaxReviewCandidates {
		maxCandidates = MaxReviewCandidates
	}
	now := options.Now
	if now == nil {
		now = time.Now
	}
	return &ReviewStore{
		maxCandidates:   maxCandidates,
		now:             now,
		records:         make(map[string]CandidateRecord),
		revisionDigests: make(map[string]string),
	}
}

func (s *ReviewStore) SubmitManifest(input ManifestCandidateInput) (CandidateRecord, error) {
	if s == nil {
		return CandidateRecord{}, errors.New("registry review store is nil")
	}
	if input.Err != nil {
		return CandidateRecord{}, fmt.Errorf("registry manifest input unavailable: %w", input.Err)
	}
	manifest, err := Parse(input.Data)
	if err != nil {
		return CandidateRecord{}, err
	}
	identity := ManifestIdentityFor(manifest, input.Data)
	if err := validateManifestIdentity(identity); err != nil {
		return CandidateRecord{}, err
	}
	recordKey := identityKey(identity)
	revisionKey := manifestRevisionKey(identity)
	observedAt := input.ObservedAt
	if observedAt.IsZero() {
		observedAt = s.now()
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	if existingDigest, ok := s.revisionDigests[revisionKey]; ok && existingDigest != identity.Digest {
		return CandidateRecord{}, fmt.Errorf("registry manifest revision %q for repository %q already has immutable digest %q", identity.Revision, identity.Repository, existingDigest)
	}
	if existing, ok := s.records[recordKey]; ok {
		return cloneCandidateRecord(existing), nil
	}
	if len(s.records) >= s.maxCandidates {
		return CandidateRecord{}, fmt.Errorf("registry review store contains the maximum %d candidates", s.maxCandidates)
	}
	record := CandidateRecord{
		Identity:    identity,
		Manifest:    normalizeManifest(manifest),
		State:       ReviewStatePending,
		Source:      strings.TrimSpace(input.Source),
		SubmittedAt: observedAt.UTC(),
	}
	s.records[recordKey] = record
	s.revisionDigests[revisionKey] = identity.Digest
	return cloneCandidateRecord(record), nil
}

func (s *ReviewStore) Review(input ReviewInput) (CandidateRecord, error) {
	if s == nil {
		return CandidateRecord{}, errors.New("registry review store is nil")
	}
	if err := validateReviewInput(input); err != nil {
		return CandidateRecord{}, err
	}
	decidedAt := input.DecidedAt
	if decidedAt.IsZero() {
		decidedAt = s.now()
	}
	decidedAt = decidedAt.UTC()

	s.mu.Lock()
	defer s.mu.Unlock()
	record, ok := s.records[identityKey(input.Identity)]
	if !ok {
		return CandidateRecord{}, fmt.Errorf("registry candidate %s is not pending review", identityKey(input.Identity))
	}
	if record.Identity != input.Identity {
		return CandidateRecord{}, errors.New("registry review identity does not match candidate")
	}
	if input.State == ReviewStateApproved && record.State != ReviewStatePending {
		return CandidateRecord{}, fmt.Errorf("only pending registry candidates can be approved, got %q", record.State)
	}
	reviewed := decidedAt
	record.State = input.State
	record.Reviewer = strings.TrimSpace(input.Reviewer)
	record.ReviewReason = strings.TrimSpace(input.Reason)
	record.ReviewedAt = &reviewed
	s.records[identityKey(record.Identity)] = record
	return cloneCandidateRecord(record), nil
}

func (s *ReviewStore) Snapshot() ReviewSnapshot {
	if s == nil {
		return ReviewSnapshot{SchemaVersion: ReviewSnapshotSchemaVersion}
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	records := make([]CandidateRecord, 0, len(s.records))
	for _, record := range s.records {
		records = append(records, cloneCandidateRecord(record))
	}
	sort.Slice(records, func(i, j int) bool {
		return identityKey(records[i].Identity) < identityKey(records[j].Identity)
	})
	snapshot := ReviewSnapshot{SchemaVersion: ReviewSnapshotSchemaVersion, Records: records, Total: len(records)}
	for _, record := range records {
		switch record.State {
		case ReviewStatePending:
			snapshot.Pending++
		case ReviewStateApproved:
			snapshot.Approved++
		case ReviewStateQuarantined:
			snapshot.Quarantined++
		}
	}
	return snapshot
}

func ManifestIdentityFor(manifest Manifest, data []byte) ManifestIdentity {
	sum := sha256.Sum256(data)
	return ManifestIdentity{
		Repository: strings.TrimSpace(manifest.Repository),
		Revision:   strings.TrimSpace(manifest.Revision),
		Digest:     "sha256:" + hex.EncodeToString(sum[:]),
	}
}

func validateReviewInput(input ReviewInput) error {
	if err := validateManifestIdentity(input.Identity); err != nil {
		return err
	}
	if input.State != ReviewStateApproved && input.State != ReviewStateQuarantined {
		return fmt.Errorf("registry review decision must be approved or quarantined, got %q", input.State)
	}
	if strings.TrimSpace(input.Reviewer) == "" || strings.TrimSpace(input.Reason) == "" {
		return errors.New("registry review requires reviewer and reason")
	}
	return nil
}

func validateManifestIdentity(identity ManifestIdentity) error {
	if strings.TrimSpace(identity.Repository) == "" || strings.TrimSpace(identity.Revision) == "" {
		return errors.New("registry manifest identity requires repository and revision")
	}
	if !strings.HasPrefix(identity.Digest, "sha256:") || len(identity.Digest) != len("sha256:")+64 {
		return errors.New("registry manifest identity requires sha256 digest")
	}
	return nil
}

func identityKey(identity ManifestIdentity) string {
	return identity.Repository + "\x00" + identity.Revision + "\x00" + identity.Digest
}

func manifestRevisionKey(identity ManifestIdentity) string {
	return identity.Repository + "\x00" + identity.Revision
}

func normalizeManifest(manifest Manifest) Manifest {
	manifest.SchemaVersion = strings.TrimSpace(manifest.SchemaVersion)
	manifest.Repository = strings.TrimSpace(manifest.Repository)
	manifest.Revision = strings.TrimSpace(manifest.Revision)
	manifest.License = strings.TrimSpace(manifest.License)
	manifest.Entries = cloneEntries(manifest.Entries)
	return manifest
}

func cloneCandidateRecord(record CandidateRecord) CandidateRecord {
	record.Manifest = normalizeManifest(record.Manifest)
	if record.ReviewedAt != nil {
		reviewedAt := *record.ReviewedAt
		record.ReviewedAt = &reviewedAt
	}
	return record
}

func cloneEntries(entries []Entry) []Entry {
	if entries == nil {
		return nil
	}
	out := make([]Entry, len(entries))
	for i, entry := range entries {
		out[i] = entry
		if entry.Transport != nil {
			transport := *entry.Transport
			if entry.Transport.Headers != nil {
				transport.Headers = make(map[string]string, len(entry.Transport.Headers))
				for key, value := range entry.Transport.Headers {
					transport.Headers[key] = value
				}
			}
			out[i].Transport = &transport
		}
	}
	return out
}
