package server

import (
	"context"
	"fmt"
	"sync/atomic"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
)

const (
	defaultPrincipalAuthorityBatchSize    = 100
	defaultPrincipalAuthorityPollInterval = time.Second
	// Four seconds leaves one second of scheduling margin inside the accepted
	// five-second revocation SLO for live-session cancellation.
	defaultPrincipalAuthorityMaxStaleness = 4 * time.Second
	principalAuthorityLogInterval         = 5 * time.Second
)

type principalAuthorityEventSource interface {
	ListPrincipalAuthorizationEpochEventsAfter(context.Context, uint64, int) ([]tables.TablePrincipalAuthorizationEpochEvent, error)
	GetPrincipalAuthorizationEpochHighWatermark(context.Context) (uint64, error)
}

type principalAuthorityWakeSource interface {
	PrincipalAuthorizationEpochWakeups(context.Context) <-chan struct{}
}

type principalAuthoritySnapshotSource interface {
	ListPrincipalAuthorizationEpochsAfter(context.Context, string, string, string, int) ([]tables.TablePrincipalAuthorizationEpoch, error)
}

type principalAuthorityPoller struct {
	store                principalAuthorityEventSource
	registry             *authorityepoch.Registry
	batch                int
	cursor               atomic.Uint64
	lastSuccessUnixNano  atomic.Int64
	lastErrorLogUnixNano atomic.Int64
	wake                 <-chan struct{}
	now                  func() time.Time
}

func newPrincipalAuthorityPoller(store principalAuthorityEventSource, registry *authorityepoch.Registry, batch int) *principalAuthorityPoller {
	if batch <= 0 {
		batch = defaultPrincipalAuthorityBatchSize
	}
	return &principalAuthorityPoller{store: store, registry: registry, batch: batch, now: time.Now}
}

func (p *principalAuthorityPoller) clock() time.Time {
	if p != nil && p.now != nil {
		return p.now().UTC()
	}
	return time.Now().UTC()
}

func (p *principalAuthorityPoller) Cursor() uint64 {
	if p == nil {
		return 0
	}
	return p.cursor.Load()
}

func (p *principalAuthorityPoller) pollOnce(ctx context.Context) (bool, error) {
	cursor := p.cursor.Load()
	events, err := p.store.ListPrincipalAuthorizationEpochEventsAfter(ctx, cursor, p.batch)
	if err != nil {
		return false, err
	}
	for _, row := range events {
		if row.ID <= cursor || row.SchemaVersion != tables.PrincipalAuthorizationEpochSchemaVersion {
			return false, fmt.Errorf("invalid principal authority event id=%d schema=%d after cursor=%d", row.ID, row.SchemaVersion, cursor)
		}
		event := authorityepoch.EpochEvent{
			Principal: authorityepoch.Principal{Tenant: row.TenantID, Issuer: row.Issuer, Subject: row.Subject},
			OldEpoch:  row.OldEpoch, NewEpoch: row.NewEpoch, Reason: authorityepoch.Reason(row.Reason), Revision: row.Revision,
		}
		if err := p.registry.Apply(event, row.Active); err != nil {
			return false, fmt.Errorf("apply principal authority event %d: %w", row.ID, err)
		}
		cursor = row.ID
		p.cursor.Store(cursor)
	}
	high, err := p.store.GetPrincipalAuthorizationEpochHighWatermark(ctx)
	if err != nil {
		return false, err
	}
	p.lastSuccessUnixNano.Store(p.clock().UnixNano())
	return cursor < high, nil
}

func (p *principalAuthorityPoller) bootstrap(ctx context.Context, snapshot principalAuthoritySnapshotSource) error {
	if snapshot == nil {
		return fmt.Errorf("principal authority snapshot capability is unavailable")
	}
	fence, err := p.store.GetPrincipalAuthorizationEpochHighWatermark(ctx)
	if err != nil {
		return fmt.Errorf("fence principal authority outbox: %w", err)
	}
	var tenant, issuer, subject string
	for {
		rows, err := snapshot.ListPrincipalAuthorizationEpochsAfter(ctx, tenant, issuer, subject, p.batch)
		if err != nil {
			return fmt.Errorf("load principal authority snapshot: %w", err)
		}
		for i := range rows {
			row := rows[i]
			reason := row.LastReason
			if reason == "" {
				reason = configstore.PrincipalAuthorizationEpochReasonActivated
			}
			if err := p.registry.Apply(authorityepoch.EpochEvent{
				Principal: authorityepoch.Principal{Tenant: row.TenantID, Issuer: row.Issuer, Subject: row.Subject},
				NewEpoch:  row.Epoch, Reason: authorityepoch.Reason(reason), Revision: row.Revision,
			}, row.Active); err != nil {
				return fmt.Errorf("apply principal authority snapshot row: %w", err)
			}
			tenant, issuer, subject = row.TenantID, row.Issuer, row.Subject
		}
		if len(rows) < p.batch {
			break
		}
	}
	p.cursor.Store(fence)
	for {
		more, err := p.pollOnce(ctx)
		if err != nil {
			return err
		}
		if !more {
			return nil
		}
	}
}

func (p *principalAuthorityPoller) IsPrincipalAuthorityFresh() bool {
	if p == nil {
		return false
	}
	lastSuccess := p.lastSuccessUnixNano.Load()
	if lastSuccess == 0 {
		return false
	}
	age := p.clock().Sub(time.Unix(0, lastSuccess))
	return age >= 0 && age <= defaultPrincipalAuthorityMaxStaleness
}

func (p *principalAuthorityPoller) PrincipalAuthorityFreshUntil() time.Time {
	if p == nil {
		return time.Time{}
	}
	lastSuccess := p.lastSuccessUnixNano.Load()
	if lastSuccess == 0 {
		return time.Time{}
	}
	return time.Unix(0, lastSuccess).Add(defaultPrincipalAuthorityMaxStaleness)
}

func (p *principalAuthorityPoller) shouldLogError(now time.Time) bool {
	for {
		last := p.lastErrorLogUnixNano.Load()
		if last != 0 && now.Sub(time.Unix(0, last)) < principalAuthorityLogInterval {
			return false
		}
		if p.lastErrorLogUnixNano.CompareAndSwap(last, now.UnixNano()) {
			return true
		}
	}
}

func (p *principalAuthorityPoller) Run(ctx context.Context) {
	for {
		more, err := p.pollOnce(ctx)
		if err == nil && more {
			continue
		}
		if err != nil && ctx.Err() == nil && logger != nil && p.shouldLogError(p.clock()) {
			logger.Error("principal authority polling failed; live principal revocation may be delayed: %v", err)
		}
		timer := time.NewTimer(defaultPrincipalAuthorityPollInterval)
		select {
		case <-ctx.Done():
			if !timer.Stop() {
				<-timer.C
			}
			return
		case <-timer.C:
		case <-p.wake:
			if !timer.Stop() {
				select {
				case <-timer.C:
				default:
				}
			}
		}
	}
}

func (s *BifrostHTTPServer) StartPrincipalAuthorityPoller(ctx context.Context) error {
	if s == nil || s.PrincipalAuthorityPoller != nil || s.Config == nil || s.Config.ConfigStore == nil {
		return nil
	}
	store, ok := s.Config.ConfigStore.(configstore.PrincipalAuthorizationEpochStore)
	if !ok {
		return nil
	}
	registry := authorityepoch.NewRegistry()
	poller := newPrincipalAuthorityPoller(store, registry, defaultPrincipalAuthorityBatchSize)
	snapshot, ok := s.Config.ConfigStore.(principalAuthoritySnapshotSource)
	if !ok {
		return fmt.Errorf("bootstrap principal authority: snapshot capability is unavailable")
	}
	if wakeSource, ok := s.Config.ConfigStore.(principalAuthorityWakeSource); ok {
		poller.wake = wakeSource.PrincipalAuthorizationEpochWakeups(ctx)
	}
	// Fence and snapshot synchronously so restart cost is proportional to current
	// principals, never retained event history.
	if err := poller.bootstrap(ctx, snapshot); err != nil {
		return fmt.Errorf("bootstrap principal authority: %w", err)
	}
	s.PrincipalAuthorityRegistry = registry
	s.PrincipalAuthorityPoller = poller
	if governancePlugin, err := s.getGovernancePlugin(); err == nil {
		governancePlugin.SetPrincipalAuthorityRegistry(registry)
	}
	if s.MCPServerHandler != nil {
		s.MCPServerHandler.SetAuthorityRegistry(registry)
		s.MCPServerHandler.SetPrincipalAuthorityFreshnessSource(poller)
	}
	go poller.Run(ctx)
	return nil
}
