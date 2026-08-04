package ingestion

import (
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

func testCard() agentcard.AgentModelCard {
	return agentcard.AgentModelCard{
		SchemaVersion: agentcard.SchemaVersion,
		Entity: agentcard.CatalogEntity{
			SchemaVersion: agentcard.SchemaVersion,
			Kind:          agentcard.EntityKindA2AAgent,
			Identity:      agentcard.Identity{ID: "agent-1", Name: "Agent One"},
			Version:       agentcard.VersionInfo{Version: "1.0.0"},
			Source:        agentcard.Source{Type: agentcard.SourceA2ACard},
			Publisher:     agentcard.Publisher{Name: "Example", URL: "https://example.com"},
			Provenance:    agentcard.Provenance{Status: agentcard.ProvenanceSelfReported},
		},
	}
}

func TestLedgerObserveDiffsAndCopiesCards(t *testing.T) {
	ledger := NewLedger()
	now := time.Date(2026, time.January, 2, 3, 4, 5, 0, time.UTC)
	observation := Observation{SourceID: "https://example.com/.well-known/agent-card.json", SourceKind: SourceA2A, ObservedAt: now, ETag: "v1", Card: testCard()}

	change, err := ledger.Observe(observation)
	if err != nil {
		t.Fatal(err)
	}
	if change.Kind != ChangeAdded || !change.IsAdmissionRequired() {
		t.Fatalf("unexpected first change: %#v", change)
	}

	observation.Card.Narrative.Summary = "mutated after observe"
	snapshot, ok := ledger.Snapshot(observation.SourceID)
	if !ok || snapshot.Card.Narrative.Summary != "" {
		t.Fatalf("ledger retained caller mutation: %#v", snapshot.Card.Narrative.Summary)
	}

	unchanged, err := ledger.Observe(Observation{SourceID: observation.SourceID, SourceKind: SourceA2A, ObservedAt: now.Add(time.Minute), ETag: "v1", Card: testCard()})
	if err != nil {
		t.Fatal(err)
	}
	if unchanged.Kind != ChangeUnchanged {
		t.Fatalf("expected unchanged diff, got %s", unchanged.Kind)
	}

	updated := testCard()
	updated.Entity.Version.Version = "2.0.0"
	modified, err := ledger.Observe(Observation{SourceID: observation.SourceID, SourceKind: SourceA2A, ObservedAt: now.Add(2 * time.Minute), ETag: "v2", Card: updated})
	if err != nil {
		t.Fatal(err)
	}
	if modified.Kind != ChangeModified || modified.Previous == nil || modified.Current == nil {
		t.Fatalf("unexpected modified diff: %#v", modified)
	}
}

func TestLedgerRejectsUnboundedOrInvalidObservations(t *testing.T) {
	ledger := NewLedger()
	_, err := ledger.Observe(Observation{SourceID: "", SourceKind: SourceA2A, Card: testCard()})
	if err == nil {
		t.Fatal("expected missing source id error")
	}
	_, err = ledger.Observe(Observation{SourceID: "source", SourceKind: SourceA2A, ObservedAt: time.Now(), Card: agentcard.AgentModelCard{}})
	if err == nil {
		t.Fatal("expected invalid card error")
	}
}

func TestLedgerRemove(t *testing.T) {
	ledger := NewLedger()
	now := time.Now().UTC()
	_, err := ledger.Observe(Observation{SourceID: "source", SourceKind: SourceImport, ObservedAt: now, Card: testCard()})
	if err != nil {
		t.Fatal(err)
	}
	change, ok := ledger.Remove("source")
	if !ok || change.Kind != ChangeRemoved || change.Previous == nil {
		t.Fatalf("unexpected remove: %#v, %v", change, ok)
	}
	if _, ok := ledger.Snapshot("source"); ok {
		t.Fatal("removed snapshot still present")
	}
}
