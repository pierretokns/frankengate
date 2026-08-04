package registry

import (
	"errors"
	"strings"
	"testing"
	"time"
)

func TestReviewStoreSubmitsPendingCandidatesWithImmutableIdentity(t *testing.T) {
	now := time.Date(2026, time.August, 4, 12, 0, 0, 0, time.UTC)
	store := NewReviewStore(ReviewStoreOptions{Now: func() time.Time { return now }})
	data := reviewManifest("https://github.com/example/agents", "rev-1", "agent-a", "0")

	record, err := store.SubmitManifest(ManifestCandidateInput{Data: data, Source: "mirror"})
	if err != nil {
		t.Fatal(err)
	}
	if record.State != ReviewStatePending {
		t.Fatalf("new candidate state = %q, want pending", record.State)
	}
	if record.Identity.Repository != "https://github.com/example/agents" || record.Identity.Revision != "rev-1" || !strings.HasPrefix(record.Identity.Digest, "sha256:") {
		t.Fatalf("identity was not pinned to repository/revision/digest: %#v", record.Identity)
	}
	if record.SubmittedAt != now {
		t.Fatalf("submitted_at = %v, want injected time %v", record.SubmittedAt, now)
	}

	again, err := store.SubmitManifest(ManifestCandidateInput{Data: data, Source: "other"})
	if err != nil {
		t.Fatal(err)
	}
	if again.Source != "mirror" {
		t.Fatalf("idempotent submit must not replace immutable record metadata: %#v", again)
	}
}

func TestReviewStoreRejectsMutableRevisionDigest(t *testing.T) {
	store := NewReviewStore(ReviewStoreOptions{})
	first := reviewManifest("repo", "rev-1", "agent-a", "0")
	second := reviewManifest("repo", "rev-1", "agent-b", "1")
	if _, err := store.SubmitManifest(ManifestCandidateInput{Data: first}); err != nil {
		t.Fatal(err)
	}
	if _, err := store.SubmitManifest(ManifestCandidateInput{Data: second}); err == nil || !strings.Contains(err.Error(), "immutable digest") {
		t.Fatalf("expected immutable digest rejection, got %v", err)
	}
	snapshot := store.Snapshot()
	if snapshot.Total != 1 || snapshot.Pending != 1 {
		t.Fatalf("mutable revision attempt changed snapshot: %#v", snapshot)
	}
}

func TestReviewStoreFailsClosedReviewValidation(t *testing.T) {
	store := NewReviewStore(ReviewStoreOptions{})
	record, err := store.SubmitManifest(ManifestCandidateInput{Data: reviewManifest("repo", "rev-1", "agent-a", "0")})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Review(ReviewInput{Identity: record.Identity, State: ReviewStateApproved, Reviewer: "reviewer"}); err == nil || !strings.Contains(err.Error(), "reviewer and reason") {
		t.Fatalf("expected missing reason rejection, got %v", err)
	}
	tampered := record.Identity
	tampered.Digest = "sha256:" + strings.Repeat("f", 64)
	if _, err := store.Review(ReviewInput{Identity: tampered, State: ReviewStateApproved, Reviewer: "reviewer", Reason: "ok"}); err == nil || !strings.Contains(err.Error(), "not pending review") {
		t.Fatalf("expected unknown tampered identity rejection, got %v", err)
	}
	approved, err := store.Review(ReviewInput{Identity: record.Identity, State: ReviewStateApproved, Reviewer: "reviewer", Reason: "pinned source verified"})
	if err != nil {
		t.Fatal(err)
	}
	if approved.State != ReviewStateApproved || approved.Reviewer != "reviewer" || approved.ReviewedAt == nil {
		t.Fatalf("approval did not persist review metadata: %#v", approved)
	}
	if _, err := store.Review(ReviewInput{Identity: record.Identity, State: ReviewStateApproved, Reviewer: "reviewer", Reason: "again"}); err == nil || !strings.Contains(err.Error(), "only pending") {
		t.Fatalf("expected re-approval rejection, got %v", err)
	}
	quarantined, err := store.Review(ReviewInput{Identity: record.Identity, State: ReviewStateQuarantined, Reviewer: "reviewer", Reason: "publisher revoked"})
	if err != nil {
		t.Fatal(err)
	}
	if quarantined.State != ReviewStateQuarantined {
		t.Fatalf("quarantine should be allowed after approval for kill-switch review: %#v", quarantined)
	}
}

func TestReviewStoreSnapshotsAreDeterministicAndCloned(t *testing.T) {
	store := NewReviewStore(ReviewStoreOptions{})
	second, err := store.SubmitManifest(ManifestCandidateInput{Data: reviewManifest("repo-b", "rev-2", "agent-b", "1")})
	if err != nil {
		t.Fatal(err)
	}
	first, err := store.SubmitManifest(ManifestCandidateInput{Data: reviewManifest("repo-a", "rev-1", "agent-a", "0")})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Review(ReviewInput{Identity: first.Identity, State: ReviewStateApproved, Reviewer: "reviewer", Reason: "verified"}); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Review(ReviewInput{Identity: second.Identity, State: ReviewStateQuarantined, Reviewer: "reviewer", Reason: "bad provenance"}); err != nil {
		t.Fatal(err)
	}

	snapshot := store.Snapshot()
	if snapshot.SchemaVersion != ReviewSnapshotSchemaVersion || snapshot.Total != 2 || snapshot.Approved != 1 || snapshot.Quarantined != 1 {
		t.Fatalf("unexpected snapshot counts: %#v", snapshot)
	}
	if snapshot.Records[0].Identity.Repository != "repo-a" || snapshot.Records[1].Identity.Repository != "repo-b" {
		t.Fatalf("snapshot order is not deterministic: %#v", snapshot.Records)
	}
	snapshot.Records[0].Manifest.Entries[0].Transport.Headers["X-Test"] = "mutated"
	again := store.Snapshot()
	if got := again.Records[0].Manifest.Entries[0].Transport.Headers["X-Test"]; got != "0" {
		t.Fatalf("snapshot mutation leaked into store, got header %q", got)
	}
}

func TestReviewStoreBoundsEntriesAndRejectsOutageInputsWithoutMutation(t *testing.T) {
	store := NewReviewStore(ReviewStoreOptions{MaxCandidates: 1})
	if _, err := store.SubmitManifest(ManifestCandidateInput{Data: reviewManifest("repo-a", "rev-1", "agent-a", "0")}); err != nil {
		t.Fatal(err)
	}
	if _, err := store.SubmitManifest(ManifestCandidateInput{Err: errors.New("mirror unavailable")}); err == nil || !strings.Contains(err.Error(), "input unavailable") {
		t.Fatalf("expected injected outage rejection, got %v", err)
	}
	if _, err := store.SubmitManifest(ManifestCandidateInput{Data: reviewManifest("repo-b", "rev-2", "agent-b", "1")}); err == nil || !strings.Contains(err.Error(), "maximum 1 candidates") {
		t.Fatalf("expected bounded store rejection, got %v", err)
	}
	snapshot := store.Snapshot()
	if snapshot.Total != 1 || snapshot.Pending != 1 {
		t.Fatalf("failed input or bounded rejection mutated store: %#v", snapshot)
	}
}

func reviewManifest(repository, revision, id, header string) []byte {
	return []byte(`{"schema_version":"registry.v1","repository":"` + repository + `","revision":"` + revision + `","license":"Apache-2.0","entries":[{"id":"` + id + `","name":"Agent","version":"1.0.0","source":"https://github.com/example/agent","digest":"sha256:0123456789012345678901234567890123456789012345678901234567890123","transport":{"type":"a2a","url":"https://agent.example/a2a","headers":{"X-Test":"` + header + `"}}}]}`)
}
