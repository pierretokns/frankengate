package provenance

import (
	"strings"
	"testing"
	"time"
)

func TestEventCanonicalizesAndDigestsMetadataOnlyEnvelope(t *testing.T) {
	event := Event{SchemaVersion: SchemaVersion, EventID: "evt-1", TenantID: "tenant-1", TaskID: "task-1", CardDigest: "sha256:card", CardRevision: "rev-1", PolicyEpoch: "epoch-2", CapabilityDecision: "admit", RemoteAgent: "agent.example", Outcome: "completed", ArtifactRef: "artifact://result/1", CostMicros: 42, ObservedAt: time.Date(2026, time.August, 4, 19, 0, 0, 0, time.UTC)}
	payload, err := event.CanonicalJSON()
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(payload), "prompt") || strings.Contains(string(payload), "response") {
		t.Fatalf("metadata envelope contains raw content: %s", payload)
	}
	digest, err := Digest(event)
	if err != nil || !strings.HasPrefix(digest, "sha256:") {
		t.Fatalf("digest = %q, err = %v", digest, err)
	}
}

func TestEventRejectsInvalidAndNegativeCost(t *testing.T) {
	if err := (Event{SchemaVersion: "wrong", EventID: "evt", Outcome: "failed", ObservedAt: time.Now()}).Validate(); err == nil {
		t.Fatal("expected schema rejection")
	}
	if err := (Event{SchemaVersion: SchemaVersion, EventID: "evt", Outcome: "failed", CostMicros: -1, ObservedAt: time.Now()}).Validate(); err == nil {
		t.Fatal("expected negative cost rejection")
	}
}
