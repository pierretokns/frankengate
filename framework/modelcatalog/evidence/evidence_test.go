package evidence

import (
	"reflect"
	"testing"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

func TestEvidenceRoundTripPreservesAttributionAndMissingness(t *testing.T) {
	score, confidence, reproducible := 0.81, 0.72, true
	original := Record{
		Name: "tool-use", Metric: "accuracy", Score: &score, Status: agentcard.ProvenanceVerified,
		DatasetURI: "https://example.test/data", DatasetRevision: "rev-3", ReportURI: "https://example.test/report",
		Methodology: "held-out tasks", SourceURI: "https://example.test/run", Verifier: "eval-ci",
		Confidence: &confidence, RunRevision: "run-7", Reproducible: &reproducible,
		Slice: map[string]string{"locale": "en-US"}, ObservedAt: "2026-08-04T12:00:00Z", Stale: false,
	}
	decoded, err := RoundTripJSON(original)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(decoded, original) {
		t.Fatalf("round trip changed evidence: %#v", decoded)
	}
	cardEvidence, err := original.ToCardEvidence()
	if err != nil {
		t.Fatal(err)
	}
	if cardEvidence.DatasetRef == nil || cardEvidence.Source == nil || cardEvidence.Confidence == nil {
		t.Fatalf("attribution was not preserved: %#v", cardEvidence)
	}
	cardEvidence.Slice["locale"] = "fr-FR"
	if original.Slice["locale"] != "en-US" {
		t.Fatal("card conversion leaked mutable slice")
	}
}

func TestEvidenceRejectsUnsupportedScoresAndBoundsSlices(t *testing.T) {
	score := 1.1
	if _, err := (Record{Name: "bad", Status: agentcard.ProvenanceVerified, Score: &score}).ToCardEvidence(); err == nil {
		t.Fatal("expected score validation failure")
	}
	slice := make(map[string]string, 33)
	for i := 0; i < 33; i++ {
		slice[string(rune('a'+i))] = "x"
	}
	if _, err := RoundTripJSON(Record{Name: "too-many-slices", Status: agentcard.ProvenanceVerified, Slice: slice}); err == nil {
		t.Fatal("expected slice bound failure")
	}
}

func TestSortIsDeterministic(t *testing.T) {
	records := []Record{{Name: "z", RunRevision: "1"}, {Name: "a", RunRevision: "2"}, {Name: "a", RunRevision: "1"}}
	sorted := Sort(records)
	if sorted[0].Name != "a" || sorted[0].RunRevision != "1" || sorted[2].Name != "z" {
		t.Fatalf("unexpected sort: %#v", sorted)
	}
}
