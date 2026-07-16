package server

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

type principalAuthorityTestSource struct {
	events     []tables.TablePrincipalAuthorizationEpochEvent
	rows       []tables.TablePrincipalAuthorizationEpoch
	err        error
	onSnapshot func()
}

func (s *principalAuthorityTestSource) ListPrincipalAuthorizationEpochsAfter(_ context.Context, tenant, issuer, subject string, limit int) ([]tables.TablePrincipalAuthorizationEpoch, error) {
	if s.onSnapshot != nil {
		s.onSnapshot()
		s.onSnapshot = nil
	}
	out := make([]tables.TablePrincipalAuthorizationEpoch, 0, limit)
	for _, row := range s.rows {
		if row.TenantID > tenant || (row.TenantID == tenant && row.Issuer > issuer) || (row.TenantID == tenant && row.Issuer == issuer && row.Subject > subject) {
			out = append(out, row)
			if len(out) == limit {
				break
			}
		}
	}
	return out, nil
}

func (s *principalAuthorityTestSource) ListPrincipalAuthorizationEpochEventsAfter(_ context.Context, cursor uint64, limit int) ([]tables.TablePrincipalAuthorizationEpochEvent, error) {
	if s.err != nil {
		return nil, s.err
	}
	out := make([]tables.TablePrincipalAuthorizationEpochEvent, 0, limit)
	for _, event := range s.events {
		if event.ID > cursor && len(out) < limit {
			out = append(out, event)
		}
	}
	return out, nil
}

func TestPrincipalAuthorityPollerFreshnessExpiresAfterFailedReads(t *testing.T) {
	if defaultPrincipalAuthorityMaxStaleness > 4*time.Second {
		t.Fatalf("principal authority lease %s leaves insufficient margin inside the 5s cancellation SLO", defaultPrincipalAuthorityMaxStaleness)
	}
	source := &principalAuthorityTestSource{}
	poller := newPrincipalAuthorityPoller(source, authorityepoch.NewRegistry(), 100)
	if _, err := poller.pollOnce(context.Background()); err != nil {
		t.Fatalf("initial poll: %v", err)
	}
	if !poller.IsPrincipalAuthorityFresh() {
		t.Fatal("successful poll did not establish freshness")
	}
	poller.lastSuccessUnixNano.Store(time.Now().Add(-defaultPrincipalAuthorityMaxStaleness - time.Millisecond).UnixNano())
	source.err = errors.New("database unavailable")
	if _, err := poller.pollOnce(context.Background()); err == nil {
		t.Fatal("failed poll unexpectedly succeeded")
	}
	if poller.IsPrincipalAuthorityFresh() {
		t.Fatal("failed reads extended an expired principal authority lease")
	}
}

func TestPrincipalAuthorityPollerFailsClosedWhenClockMovesBackward(t *testing.T) {
	now := time.Date(2026, 7, 16, 12, 0, 0, 0, time.UTC)
	poller := newPrincipalAuthorityPoller(&principalAuthorityTestSource{}, authorityepoch.NewRegistry(), 100)
	poller.now = func() time.Time { return now }
	poller.lastSuccessUnixNano.Store(now.UnixNano())
	require.True(t, poller.IsPrincipalAuthorityFresh())
	now = now.Add(-time.Second)
	require.False(t, poller.IsPrincipalAuthorityFresh(), "backward clock movement must fail closed")
}

func (s *principalAuthorityTestSource) GetPrincipalAuthorizationEpochHighWatermark(context.Context) (uint64, error) {
	if len(s.events) == 0 {
		return 0, nil
	}
	return s.events[len(s.events)-1].ID, nil
}

func TestPrincipalAuthorityPollerReplaysAndCancelsLiveMCPReference(t *testing.T) {
	principal := authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer-a", Subject: "user-a"}
	source := &principalAuthorityTestSource{events: []tables.TablePrincipalAuthorizationEpochEvent{{
		ID: 1, TenantID: principal.Tenant, Issuer: principal.Issuer, Subject: principal.Subject,
		NewEpoch: 1, Active: true, Reason: "activated", Revision: 1, SchemaVersion: 1,
	}}}
	registry := authorityepoch.NewRegistry()
	poller := newPrincipalAuthorityPoller(source, registry, 100)
	more, err := poller.pollOnce(context.Background())
	if err != nil || more {
		t.Fatalf("activation poll: more=%v err=%v", more, err)
	}
	ref, err := registry.Mint(principal, authorityepoch.ArtifactMCPLiveConnection, "mcp-live-1")
	if err != nil {
		t.Fatalf("mint: %v", err)
	}
	cancelled, unsubscribe, err := registry.Subscribe(ref)
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	defer unsubscribe()
	source.events = append(source.events, tables.TablePrincipalAuthorizationEpochEvent{
		ID: 2, TenantID: principal.Tenant, Issuer: principal.Issuer, Subject: principal.Subject,
		OldEpoch: 1, NewEpoch: 2, Active: false, Reason: string(authorityepoch.ReasonDeactivated), Revision: 2, SchemaVersion: 1,
	})
	if _, err := poller.pollOnce(context.Background()); err != nil {
		t.Fatalf("deactivation poll: %v", err)
	}
	select {
	case <-cancelled:
	default:
		t.Fatal("peer deactivation did not cancel live MCP reference")
	}
	if got := poller.Cursor(); got != 2 {
		t.Fatalf("cursor=%d want 2", got)
	}
}

func TestPrincipalAuthorityBootstrapSkipsHistoryAndAppliesPostFenceMutation(t *testing.T) {
	principal := authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer-a", Subject: "user-a"}
	source := &principalAuthorityTestSource{
		rows: []tables.TablePrincipalAuthorizationEpoch{{
			TenantID: principal.Tenant, Issuer: principal.Issuer, Subject: principal.Subject,
			Epoch: 9, Active: true, LastReason: "activated", Revision: 9,
		}},
		events: make([]tables.TablePrincipalAuthorizationEpochEvent, 10_000),
	}
	for i := range source.events {
		source.events[i] = tables.TablePrincipalAuthorizationEpochEvent{ID: uint64(i + 1)}
	}
	source.onSnapshot = func() {
		source.events = append(source.events, tables.TablePrincipalAuthorizationEpochEvent{
			ID: 10_001, TenantID: principal.Tenant, Issuer: principal.Issuer, Subject: principal.Subject,
			OldEpoch: 9, NewEpoch: 10, Active: false, Reason: string(authorityepoch.ReasonDeactivated), Revision: 10, SchemaVersion: 1,
		})
	}
	registry := authorityepoch.NewRegistry()
	poller := newPrincipalAuthorityPoller(source, registry, 100)
	require.NoError(t, poller.bootstrap(context.Background(), source))
	require.Equal(t, uint64(10_001), poller.Cursor())
	_, err := registry.Mint(principal, authorityepoch.ArtifactMCPGrant, "grant-after-bootstrap")
	require.ErrorIs(t, err, authorityepoch.ErrInactivePrincipal)
}
