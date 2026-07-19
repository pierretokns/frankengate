package identity

import (
	"errors"
	"sync"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
)

var (
	ErrSnapshotStale   = errors.New("identity: entitlement snapshot is stale")
	ErrSnapshotMissing = errors.New("identity: entitlement snapshot is unavailable")
)

// Snapshot is the immutable result of an Okta/SCIM group evaluation. Epoch is
// the durable authorization epoch for the principal; Revision is the source
// cursor used to order refreshes. A newer empty Entitlements value is an
// explicit revocation and must never be merged with the previous grant.
type Snapshot struct {
	Principal    authorityepoch.Principal
	Epoch        uint64
	Revision     uint64
	Entitlements Entitlements
	ObservedAt   time.Time
}

// SnapshotStore keeps the latest snapshot per principal. Updates are
// monotonic by (epoch, revision), so delayed Okta/SCIM jobs cannot resurrect a
// revoked group. Reads are fail-closed when no snapshot or a stale snapshot is
// available.
type SnapshotStore struct {
	mu     sync.RWMutex
	items  map[authorityepoch.Principal]Snapshot
	maxAge time.Duration
}

func NewSnapshotStore(maxAge time.Duration) *SnapshotStore {
	return &SnapshotStore{items: make(map[authorityepoch.Principal]Snapshot), maxAge: maxAge}
}

// Apply accepts a snapshot only when it advances the durable authority
// position. Same-position retries are idempotent; conflicting same-position
// data is rejected rather than nondeterministically merged.
func (s *SnapshotStore) Apply(in Snapshot) error {
	if s == nil {
		return ErrSnapshotMissing
	}
	if err := authorityepoch.ValidatePrincipal(in.Principal); err != nil || in.Epoch == 0 || in.Revision == 0 {
		return ErrSnapshotStale
	}
	if in.ObservedAt.IsZero() {
		in.ObservedAt = time.Now().UTC()
	}
	in.Entitlements = cloneEntitlements(in.Entitlements)
	s.mu.Lock()
	defer s.mu.Unlock()
	old, ok := s.items[in.Principal]
	if ok {
		if in.Epoch < old.Epoch || (in.Epoch == old.Epoch && in.Revision < old.Revision) {
			return ErrSnapshotStale
		}
		if in.Epoch == old.Epoch && in.Revision == old.Revision {
			if !sameEntitlements(old.Entitlements, in.Entitlements) {
				return ErrSnapshotStale
			}
			return nil
		}
	}
	s.items[in.Principal] = in
	return nil
}

// Get returns a copy only while the snapshot is fresh. Revocations are
// represented by an empty, newer snapshot and therefore remain authoritative.
func (s *SnapshotStore) Get(principal authorityepoch.Principal, now time.Time) (Snapshot, error) {
	if s == nil {
		return Snapshot{}, ErrSnapshotMissing
	}
	s.mu.RLock()
	in, ok := s.items[principal]
	s.mu.RUnlock()
	if !ok {
		return Snapshot{}, ErrSnapshotMissing
	}
	if s.maxAge > 0 && now.Sub(in.ObservedAt) > s.maxAge {
		return Snapshot{}, ErrSnapshotStale
	}
	in.Entitlements = cloneEntitlements(in.Entitlements)
	return in, nil
}

func cloneEntitlements(in Entitlements) Entitlements {
	in.MatchedGroups = append([]string(nil), in.MatchedGroups...)
	in.Models = append([]string(nil), in.Models...)
	in.Providers = append([]string(nil), in.Providers...)
	in.ToolGroups = append([]string(nil), in.ToolGroups...)
	return in
}

func sameEntitlements(a, b Entitlements) bool {
	return equalStrings(a.MatchedGroups, b.MatchedGroups) && equalStrings(a.Models, b.Models) && equalStrings(a.Providers, b.Providers) && equalStrings(a.ToolGroups, b.ToolGroups)
}

func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
