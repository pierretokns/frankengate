package identity

import (
	"errors"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
)

func TestSnapshotStoreRejectsDelayedGroupGrantAfterRevocation(t *testing.T) {
	p := authorityepoch.Principal{Tenant: "acme", Issuer: "okta", Subject: "u-1"}
	s := NewSnapshotStore(time.Hour)
	grant := Snapshot{Principal: p, Epoch: 1, Revision: 10, ObservedAt: time.Unix(100, 0), Entitlements: Entitlements{MatchedGroups: []string{"finance"}, Models: []string{"claude-*"}}}
	if err := s.Apply(grant); err != nil {
		t.Fatal(err)
	}
	// Empty grants are an explicit SCIM/Okta revocation, not a partial merge.
	if err := s.Apply(Snapshot{Principal: p, Epoch: 2, Revision: 11, ObservedAt: time.Unix(101, 0)}); err != nil {
		t.Fatal(err)
	}
	if err := s.Apply(grant); !errors.Is(err, ErrSnapshotStale) {
		t.Fatalf("delayed grant err=%v", err)
	}
	got, err := s.Get(p, time.Unix(102, 0))
	if err != nil {
		t.Fatal(err)
	}
	if len(got.Entitlements.Models) != 0 || len(got.Entitlements.MatchedGroups) != 0 {
		t.Fatalf("revocation was merged with old grant: %+v", got)
	}
}

func TestSnapshotStoreSamePositionConflictFailsClosedAndReadsAreCopies(t *testing.T) {
	p := authorityepoch.Principal{Tenant: "acme", Issuer: "okta", Subject: "u-2"}
	s := NewSnapshotStore(time.Hour)
	in := Snapshot{Principal: p, Epoch: 4, Revision: 9, ObservedAt: time.Unix(100, 0), Entitlements: Entitlements{Models: []string{"gpt"}}}
	if err := s.Apply(in); err != nil {
		t.Fatal(err)
	}
	conflict := in
	conflict.Entitlements.Models = []string{"claude"}
	if err := s.Apply(conflict); !errors.Is(err, ErrSnapshotStale) {
		t.Fatalf("conflict err=%v", err)
	}
	got, err := s.Get(p, time.Unix(101, 0))
	if err != nil {
		t.Fatal(err)
	}
	got.Entitlements.Models[0] = "mutated"
	again, err := s.Get(p, time.Unix(101, 0))
	if err != nil {
		t.Fatal(err)
	}
	if again.Entitlements.Models[0] != "gpt" {
		t.Fatalf("snapshot leaked mutable backing array: %+v", again)
	}
}

func TestSnapshotStoreStaleReadFailsClosed(t *testing.T) {
	p := authorityepoch.Principal{Tenant: "acme", Issuer: "okta", Subject: "u-3"}
	s := NewSnapshotStore(time.Minute)
	if err := s.Apply(Snapshot{Principal: p, Epoch: 1, Revision: 1, ObservedAt: time.Unix(100, 0)}); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Get(p, time.Unix(161, 0)); !errors.Is(err, ErrSnapshotStale) {
		t.Fatalf("err=%v", err)
	}
}
