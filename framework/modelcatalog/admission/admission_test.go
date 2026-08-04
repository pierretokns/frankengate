package admission

import (
	"testing"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
	"github.com/maximhq/bifrost/framework/modelcatalog/trust"
)

func candidate(id, publisher string, state trust.TrustState, health agentcard.HealthStatus) Candidate {
	return Candidate{
		Card: agentcard.AgentModelCard{
			SchemaVersion: agentcard.SchemaVersion,
			Entity: agentcard.CatalogEntity{
				SchemaVersion: agentcard.SchemaVersion,
				Kind:          agentcard.EntityKindA2AAgent,
				Identity:      agentcard.Identity{ID: id, Name: id},
				Version:       agentcard.VersionInfo{Version: "1"},
				Source:        agentcard.Source{Type: agentcard.SourceA2ACard},
				Publisher:     agentcard.Publisher{Name: publisher, URL: "https://" + publisher + ".example"},
				Capabilities: agentcard.CapabilitySet{
					Modalities: []agentcard.Modality{agentcard.ModalityText},
					Operations: []agentcard.Operation{agentcard.OperationA2ATask},
					Features:   []string{"streaming"},
					Limits:     agentcard.Limits{ContextTokens: 256000},
				},
				Provenance: agentcard.Provenance{Status: agentcard.ProvenanceVerified},
			},
			Health: &agentcard.Health{Status: health, LatencyP95Millis: 100},
		},
		Trust: trust.CardTrustRecord{State: state},
	}
}

func TestRankAppliesCapabilityTrustAndHealthPolicy(t *testing.T) {
	good := candidate("good", "preferred", trust.TrustStateTrusted, agentcard.HealthHealthy)
	good.Card.Entity.Capabilities.Limits.ContextTokens = 256000
	degraded := candidate("degraded", "other", trust.TrustStateTrusted, agentcard.HealthDegraded)
	untrusted := candidate("untrusted", "preferred", trust.TrustStateVerified, agentcard.HealthHealthy)

	accepted, rejected := Rank([]Candidate{degraded, untrusted, good}, Requirement{
		AllowedKinds:        []agentcard.EntityKind{agentcard.EntityKindA2AAgent},
		RequiredOperations:  []agentcard.Operation{agentcard.OperationA2ATask},
		RequiredModalities:  []agentcard.Modality{agentcard.ModalityText},
		RequiredFeatures:    []string{"streaming"},
		MinContextTokens:    200000,
		RequireHealthy:      true,
		RequireTrusted:      true,
		PreferredPublishers: []string{"preferred"},
	})
	if len(accepted) != 1 || accepted[0].Candidate.Card.Entity.Identity.ID != "good" {
		t.Fatalf("unexpected accepted candidates: %#v", accepted)
	}
	if accepted[0].Score != 145 {
		t.Fatalf("unexpected deterministic score: %d", accepted[0].Score)
	}
	if len(rejected) != 2 {
		t.Fatalf("unexpected rejections: %#v", rejected)
	}
	if rejected[0].CandidateID != "degraded" || rejected[0].Reason != ReasonUnhealthy {
		t.Fatalf("rejections should be sorted and explain policy: %#v", rejected)
	}
}

func TestRankTieBreaksByStableCardID(t *testing.T) {
	first := candidate("b", "publisher", trust.TrustStateTrusted, agentcard.HealthHealthy)
	second := candidate("a", "publisher", trust.TrustStateTrusted, agentcard.HealthHealthy)
	accepted, rejected := Rank([]Candidate{first, second}, Requirement{RequireTrusted: true})
	if len(rejected) != 0 || len(accepted) != 2 {
		t.Fatalf("unexpected rank result: %#v %#v", accepted, rejected)
	}
	if accepted[0].Candidate.Card.Entity.Identity.ID != "a" || accepted[1].Candidate.Card.Entity.Identity.ID != "b" {
		t.Fatalf("tie-break was not deterministic: %#v", accepted)
	}
}
