package ingestion

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"sync"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

type Ledger struct {
	mu      sync.RWMutex
	sources map[string]Snapshot
}

func NewLedger() *Ledger {
	return &Ledger{sources: make(map[string]Snapshot)}
}

// Observe records the latest source snapshot and returns a diff against the
// previous observation. The card is copied through JSON so callers cannot
// mutate ledger state after the call returns.
func (l *Ledger) Observe(observation Observation) (Change, error) {
	if l == nil {
		return Change{}, fmt.Errorf("ledger is nil")
	}
	if err := validateObservation(observation); err != nil {
		return Change{}, err
	}
	card, err := cloneCard(observation.Card)
	if err != nil {
		return Change{}, err
	}
	digest, err := digestCard(card)
	if err != nil {
		return Change{}, err
	}
	now := observation.ObservedAt.UTC()
	snapshot := Snapshot{
		SourceID: observation.SourceID, SourceKind: observation.SourceKind,
		ObservedAt: now, ETag: observation.ETag, Digest: digest, Card: card,
	}

	l.mu.Lock()
	defer l.mu.Unlock()
	previous, exists := l.sources[observation.SourceID]
	l.sources[observation.SourceID] = snapshot
	change := Change{SourceID: observation.SourceID, Current: snapshotPtr(snapshot), DetectedAt: now}
	if !exists {
		change.Kind = ChangeAdded
		return change, nil
	}
	change.Previous = snapshotPtr(previous)
	if previous.Digest == snapshot.Digest && previous.ETag == snapshot.ETag {
		change.Kind = ChangeUnchanged
	} else {
		change.Kind = ChangeModified
	}
	return change, nil
}

func (l *Ledger) Snapshot(sourceID string) (Snapshot, bool) {
	if l == nil {
		return Snapshot{}, false
	}
	l.mu.RLock()
	snapshot, ok := l.sources[sourceID]
	l.mu.RUnlock()
	if !ok {
		return Snapshot{}, false
	}
	card, err := cloneCard(snapshot.Card)
	if err != nil {
		return Snapshot{}, false
	}
	snapshot.Card = card
	return snapshot, true
}

func (l *Ledger) Remove(sourceID string) (Change, bool) {
	if l == nil || strings.TrimSpace(sourceID) == "" {
		return Change{}, false
	}
	l.mu.Lock()
	previous, ok := l.sources[sourceID]
	if ok {
		delete(l.sources, sourceID)
	}
	l.mu.Unlock()
	if !ok {
		return Change{}, false
	}
	return Change{Kind: ChangeRemoved, SourceID: sourceID, Previous: snapshotPtr(previous)}, true
}

func (l *Ledger) Snapshots() []Snapshot {
	if l == nil {
		return nil
	}
	l.mu.RLock()
	items := make([]Snapshot, 0, len(l.sources))
	for _, snapshot := range l.sources {
		items = append(items, snapshot)
	}
	l.mu.RUnlock()
	for i := range items {
		items[i].Card, _ = cloneCard(items[i].Card)
	}
	return items
}

func validateObservation(observation Observation) error {
	if strings.TrimSpace(observation.SourceID) == "" {
		return fmt.Errorf("source id is required")
	}
	if len(observation.SourceID) > MaxSourceIDBytes {
		return fmt.Errorf("source id exceeds %d bytes", MaxSourceIDBytes)
	}
	if observation.SourceKind == "" {
		return fmt.Errorf("source kind is required")
	}
	if observation.ObservedAt.IsZero() {
		return fmt.Errorf("observed at is required")
	}
	return observation.Card.Validate()
}

func digestCard(card agentcard.AgentModelCard) (agentcard.Digest, error) {
	data, err := json.Marshal(card)
	if err != nil {
		return agentcard.Digest{}, err
	}
	if len(data) > MaxObservationBytes {
		return agentcard.Digest{}, fmt.Errorf("card exceeds %d bytes", MaxObservationBytes)
	}
	sum := sha256.Sum256(data)
	return agentcard.Digest{Algorithm: "sha256", Value: hex.EncodeToString(sum[:])}, nil
}

func cloneCard(card agentcard.AgentModelCard) (agentcard.AgentModelCard, error) {
	data, err := json.Marshal(card)
	if err != nil {
		return agentcard.AgentModelCard{}, err
	}
	var copy agentcard.AgentModelCard
	if err := json.Unmarshal(data, &copy); err != nil {
		return agentcard.AgentModelCard{}, err
	}
	return copy, nil
}

func snapshotPtr(snapshot Snapshot) *Snapshot {
	copy := snapshot
	copy.Card, _ = cloneCard(snapshot.Card)
	return &copy
}
