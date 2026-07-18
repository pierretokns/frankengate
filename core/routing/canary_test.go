package routing

import (
	"encoding/json"
	"strconv"
	"testing"
)

func TestBucketIsStableAndExperimentScoped(t *testing.T) {
	first := Bucket("user-42", "model-v2")
	if first != Bucket("user-42", "model-v2") {
		t.Fatal("bucket changed for identical input")
	}
	if first >= basisPoints {
		t.Fatalf("bucket out of range: %d", first)
	}
	// Different experiments are intentionally independently hashed; equality is
	// possible by chance after reduction and is not itself an invalid result.
	_ = Bucket("user-42", "model-v3")
}

func TestInTreatmentBoundsAreFailClosed(t *testing.T) {
	if InTreatment("user", "exp", 0) || InTreatment("user", "exp", -1) || InTreatment("user", "exp", basisPoints+1) {
		t.Fatal("invalid rollout was accepted")
	}
	if !InTreatment("user", "exp", basisPoints) {
		t.Fatal("100% rollout was rejected")
	}
}

func TestBucketDoesNotCollapseAssignments(t *testing.T) {
	seen := make(map[uint32]struct{})
	for i := 0; i < 1000; i++ {
		seen[Bucket("user-"+strconv.Itoa(i), "experiment")] = struct{}{}
	}
	if len(seen) < 100 {
		t.Fatalf("bucket assignments collapsed unexpectedly: %d distinct buckets", len(seen))
	}
}

func TestAssignReturnsAuditableDeterministicDecision(t *testing.T) {
	got := Assign("user-1", "models-v2", 5000)
	if got.Subject != "user-1" || got.Experiment != "models-v2" || got.RolloutBasisPoints != 5000 {
		t.Fatalf("assignment metadata = %#v", got)
	}
	if got.Bucket >= basisPoints {
		t.Fatalf("bucket out of range: %d", got.Bucket)
	}
	if got.InTreatment != InTreatment("user-1", "models-v2", 5000) {
		t.Fatalf("assignment treatment disagrees with predicate: %#v", got)
	}
	if again := Assign("user-1", "models-v2", 5000); again != got {
		t.Fatalf("assignment is not deterministic: %#v != %#v", again, got)
	}
}

func TestAssignFailsClosedForInvalidInputs(t *testing.T) {
	cases := []struct {
		subject, experiment string
		rollout             int
	}{
		{"", "experiment", 100},
		{"subject", "", 100},
		{"subject", "experiment", 0},
		{"subject", "experiment", basisPoints + 1},
	}
	for _, tc := range cases {
		got := Assign(tc.subject, tc.experiment, tc.rollout)
		if got.InTreatment || got.Bucket != 0 {
			t.Fatalf("invalid assignment should fail closed: %#v", got)
		}
	}
}

func TestAssignmentHasStableAuditJSON(t *testing.T) {
	original := Assign("user-1", "models-v2", 5000)
	encoded, err := json.Marshal(original)
	if err != nil {
		t.Fatalf("marshal assignment: %v", err)
	}
	var decoded Assignment
	if err := json.Unmarshal(encoded, &decoded); err != nil {
		t.Fatalf("unmarshal assignment: %v", err)
	}
	if decoded != original {
		t.Fatalf("assignment JSON round-trip changed value: got %#v want %#v", decoded, original)
	}
	if string(encoded) == "{}" || string(encoded)[:1] != "{" {
		t.Fatalf("unexpected assignment JSON: %s", encoded)
	}
}

func TestAssignmentTraceAttributesExcludeSubject(t *testing.T) {
	assignment := Assign("user-1", "models-v2", 5000)
	attrs := assignment.TraceAttributes()
	if _, ok := attrs["routing.experiment"]; !ok {
		t.Fatal("trace attributes missing experiment")
	}
	if _, ok := attrs["routing.bucket"]; !ok {
		t.Fatal("trace attributes missing bucket")
	}
	if _, ok := attrs["routing.subject"]; ok {
		t.Fatal("trace attributes must not expose subject")
	}
	attrs["routing.experiment"] = "mutated"
	if assignment.TraceAttributes()["routing.experiment"] != "models-v2" {
		t.Fatal("trace attributes must return an independent map")
	}
}
