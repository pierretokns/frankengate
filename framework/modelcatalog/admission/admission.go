// Package admission evaluates model and agent cards for a routing request.
// Discovery and signature verification provide facts; this package applies
// the explicit capability, health, and trust policy required before routing.
package admission

import (
	"fmt"
	"slices"
	"strings"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
	"github.com/maximhq/bifrost/framework/modelcatalog/trust"
)

type Requirement struct {
	AllowedKinds        []agentcard.EntityKind
	RequiredOperations  []agentcard.Operation
	RequiredModalities  []agentcard.Modality
	RequiredFeatures    []string
	MinContextTokens    int64
	MaxLatencyMillis    int64
	RequireHealthy      bool
	RequireTrusted      bool
	PreferredPublishers []string
}

type Candidate struct {
	Card  agentcard.AgentModelCard
	Trust trust.CardTrustRecord
}

type RejectionReason string

const (
	ReasonInvalidCard       RejectionReason = "invalid_card"
	ReasonKindMismatch      RejectionReason = "kind_mismatch"
	ReasonOperationMissing  RejectionReason = "operation_missing"
	ReasonModalityMissing   RejectionReason = "modality_missing"
	ReasonFeatureMissing    RejectionReason = "feature_missing"
	ReasonContextTooSmall   RejectionReason = "context_too_small"
	ReasonLatencyTooHigh    RejectionReason = "latency_too_high"
	ReasonUnhealthy         RejectionReason = "unhealthy"
	ReasonNotTrusted        RejectionReason = "not_trusted"
	ReasonPublisherMismatch RejectionReason = "publisher_not_preferred"
)

type Rejection struct {
	CandidateID string
	Reason      RejectionReason
	Detail      string
}

type Result struct {
	Candidate  Candidate
	Score      int
	Rejections []Rejection
}

// Rank returns candidates in deterministic preference order. It never mutates
// the input slice and reports every rejected candidate for audit diagnostics.
func Rank(candidates []Candidate, requirement Requirement) ([]Result, []Rejection) {
	accepted := make([]Result, 0, len(candidates))
	rejected := make([]Rejection, 0)
	for _, candidate := range candidates {
		id := candidate.Card.Entity.Identity.ID
		if err := candidate.Card.Validate(); err != nil {
			rejected = append(rejected, Rejection{CandidateID: id, Reason: ReasonInvalidCard, Detail: err.Error()})
			continue
		}
		if reason, detail := evaluate(candidate, requirement); reason != "" {
			rejected = append(rejected, Rejection{CandidateID: id, Reason: reason, Detail: detail})
			continue
		}
		score := scoreCandidate(candidate, requirement)
		accepted = append(accepted, Result{Candidate: candidate, Score: score})
	}
	slices.SortStableFunc(accepted, func(a, b Result) int {
		if a.Score != b.Score {
			if a.Score > b.Score {
				return -1
			}
			return 1
		}
		return strings.Compare(a.Candidate.Card.Entity.Identity.ID, b.Candidate.Card.Entity.Identity.ID)
	})
	slices.SortStableFunc(rejected, func(a, b Rejection) int {
		if a.CandidateID != b.CandidateID {
			return strings.Compare(a.CandidateID, b.CandidateID)
		}
		return strings.Compare(string(a.Reason), string(b.Reason))
	})
	return accepted, rejected
}

func evaluate(candidate Candidate, requirement Requirement) (RejectionReason, string) {
	card := candidate.Card
	if !containsKind(requirement.AllowedKinds, card.Entity.Kind) {
		return ReasonKindMismatch, fmt.Sprintf("card kind %q is not allowed", card.Entity.Kind)
	}
	for _, operation := range requirement.RequiredOperations {
		if !slices.Contains(card.Entity.Capabilities.Operations, operation) {
			return ReasonOperationMissing, fmt.Sprintf("required operation %q is absent", operation)
		}
	}
	for _, modality := range requirement.RequiredModalities {
		if !slices.Contains(card.Entity.Capabilities.Modalities, modality) {
			return ReasonModalityMissing, fmt.Sprintf("required modality %q is absent", modality)
		}
	}
	for _, feature := range requirement.RequiredFeatures {
		if !slices.Contains(card.Entity.Capabilities.Features, feature) {
			return ReasonFeatureMissing, fmt.Sprintf("required feature %q is absent", feature)
		}
	}
	if requirement.MinContextTokens > 0 && card.Entity.Capabilities.Limits.ContextTokens < requirement.MinContextTokens {
		return ReasonContextTooSmall, fmt.Sprintf("context capacity %d is below %d", card.Entity.Capabilities.Limits.ContextTokens, requirement.MinContextTokens)
	}
	if requirement.MaxLatencyMillis > 0 && card.Health != nil && card.Health.LatencyP95Millis > requirement.MaxLatencyMillis {
		return ReasonLatencyTooHigh, fmt.Sprintf("p95 latency %d exceeds %d ms", card.Health.LatencyP95Millis, requirement.MaxLatencyMillis)
	}
	if requirement.RequireHealthy && (card.Health == nil || card.Health.Status != agentcard.HealthHealthy) {
		return ReasonUnhealthy, "candidate health is not healthy"
	}
	if requirement.RequireTrusted && candidate.Trust.State != trust.TrustStateTrusted {
		return ReasonNotTrusted, fmt.Sprintf("trust state is %q", candidate.Trust.State)
	}
	if len(requirement.PreferredPublishers) > 0 && !slices.Contains(requirement.PreferredPublishers, card.Entity.Publisher.Name) {
		return ReasonPublisherMismatch, fmt.Sprintf("publisher %q is not preferred", card.Entity.Publisher.Name)
	}
	return "", ""
}

func scoreCandidate(candidate Candidate, requirement Requirement) int {
	score := 0
	if candidate.Trust.State == trust.TrustStateTrusted {
		score += 100
	}
	if candidate.Card.Health != nil {
		switch candidate.Card.Health.Status {
		case agentcard.HealthHealthy:
			score += 20
		case agentcard.HealthDegraded:
			score += 5
		}
	}
	if len(requirement.PreferredPublishers) > 0 && slices.Contains(requirement.PreferredPublishers, candidate.Card.Entity.Publisher.Name) {
		score += 25
	}
	return score
}

func containsKind(kinds []agentcard.EntityKind, kind agentcard.EntityKind) bool {
	return len(kinds) == 0 || slices.Contains(kinds, kind)
}
