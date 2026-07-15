package server

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"time"

	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/plugins/governance"
)

const (
	defaultVirtualKeyInvalidationBatchSize    = 100
	defaultVirtualKeyInvalidationPollInterval = time.Second
	defaultVirtualKeyAuthorityMaxStaleness    = 5 * time.Second
	virtualKeyInvalidationErrorLogInterval    = 30 * time.Second
)

type virtualKeyInvalidationSource interface {
	ListVirtualKeyInvalidationsAfter(ctx context.Context, cursor uint64, limit int) ([]tables.TableVirtualKeyInvalidationEvent, error)
	GetVirtualKeyInvalidationHighWatermark(ctx context.Context) (uint64, error)
}

type virtualKeyInvalidationApply func(context.Context, tables.TableVirtualKeyInvalidationEvent) error

// VirtualKeyInvalidationFreshness is an immutable snapshot of one pod's
// progress through the durable virtual-key invalidation outbox.
type VirtualKeyInvalidationFreshness struct {
	Cursor        uint64
	HighWatermark uint64
	Lag           uint64
	LastSuccess   time.Time
	Fresh         bool
}

// virtualKeyInvalidationPoller consumes the durable outbox in ID order. Cursor
// progress is deliberately process-local: replay from an older cursor is safe
// because reload and delete operations are idempotent.
type virtualKeyInvalidationPoller struct {
	store        virtualKeyInvalidationSource
	apply        virtualKeyInvalidationApply
	batchSize    int
	pollInterval time.Duration

	cursor           atomic.Uint64
	highWatermark    atomic.Uint64
	lastSuccessNano  atomic.Int64
	lastErrorLogNano atomic.Int64
	failureActive    atomic.Bool
}

func newVirtualKeyInvalidationPoller(store virtualKeyInvalidationSource, apply virtualKeyInvalidationApply, batchSize int, pollInterval time.Duration) *virtualKeyInvalidationPoller {
	if batchSize <= 0 {
		batchSize = defaultVirtualKeyInvalidationBatchSize
	}
	if pollInterval <= 0 {
		pollInterval = defaultVirtualKeyInvalidationPollInterval
	}
	return &virtualKeyInvalidationPoller{
		store:        store,
		apply:        apply,
		batchSize:    batchSize,
		pollInterval: pollInterval,
	}
}

// StartVirtualKeyInvalidationPoller starts this pod's ordered outbox consumer.
// It intentionally does not wire mutation handlers; producers may be enabled
// separately once their transaction contract is ready. Call during
// single-threaded server bootstrap.
func (s *BifrostHTTPServer) StartVirtualKeyInvalidationPoller(ctx context.Context) error {
	if s == nil || s.VKInvalidationPoller != nil || s.Config == nil || s.Config.ConfigStore == nil {
		return nil
	}
	if !s.Config.IsPluginLoaded(s.getGovernancePluginName()) {
		return nil
	}
	s.VKInvalidationPoller = newVirtualKeyInvalidationPoller(
		s.Config.ConfigStore,
		func(ctx context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
			return applyVirtualKeyInvalidation(ctx, event, s.ReloadVirtualKey, s.RemoveVirtualKey)
		},
		defaultVirtualKeyInvalidationBatchSize,
		defaultVirtualKeyInvalidationPollInterval,
	)
	plugin, err := s.getGovernancePlugin()
	if err != nil {
		s.VKInvalidationPoller = nil
		return fmt.Errorf("wire virtual-key authority freshness: %w", err)
	}
	setter, ok := plugin.(interface {
		SetAuthorityFreshnessSource(governance.AuthorityFreshnessSource)
	})
	if !ok {
		s.VKInvalidationPoller = nil
		return fmt.Errorf("governance plugin %q does not support virtual-key authority freshness", s.getGovernancePluginName())
	}
	setter.SetAuthorityFreshnessSource(s.VKInvalidationPoller)
	go s.VKInvalidationPoller.Run(ctx)
	return nil
}

func applyVirtualKeyInvalidation(
	ctx context.Context,
	event tables.TableVirtualKeyInvalidationEvent,
	reload func(context.Context, string) (*tables.TableVirtualKey, error),
	remove func(context.Context, string) error,
) error {
	switch event.Action {
	case tables.VirtualKeyInvalidationActionReload:
		_, err := reload(ctx, event.EntityID)
		if errors.Is(err, configstore.ErrNotFound) {
			// A restarted/lagging pod can replay an old reload after the row has
			// already been deleted. Apply the current authority (absence) and keep
			// advancing toward the later tombstone instead of wedging forever.
			return remove(ctx, event.EntityID)
		}
		return err
	case tables.VirtualKeyInvalidationActionDelete:
		return remove(ctx, event.EntityID)
	default:
		return fmt.Errorf("unsupported virtual-key invalidation action %q", event.Action)
	}
}

// IsAuthorityFresh implements governance.AuthorityFreshnessSource. A pod is
// authorized to accept virtual keys only while it is caught up and has
// successfully contacted the durable authority within the bounded lease.
func (p *virtualKeyInvalidationPoller) IsAuthorityFresh() bool {
	return p.Freshness(time.Now(), defaultVirtualKeyAuthorityMaxStaleness).Fresh
}

// VirtualKeyInvalidationFreshness returns this pod's current outbox progress.
func (s *BifrostHTTPServer) VirtualKeyInvalidationFreshness(now time.Time, maxAge time.Duration) VirtualKeyInvalidationFreshness {
	if s == nil || s.VKInvalidationPoller == nil {
		return VirtualKeyInvalidationFreshness{}
	}
	return s.VKInvalidationPoller.Freshness(now, maxAge)
}

func (p *virtualKeyInvalidationPoller) Cursor() uint64 {
	if p == nil {
		return 0
	}
	return p.cursor.Load()
}

func (p *virtualKeyInvalidationPoller) Freshness(now time.Time, maxAge time.Duration) VirtualKeyInvalidationFreshness {
	if p == nil {
		return VirtualKeyInvalidationFreshness{}
	}
	cursor := p.cursor.Load()
	highWatermark := p.highWatermark.Load()
	var lag uint64
	if highWatermark > cursor {
		lag = highWatermark - cursor
	}
	lastNano := p.lastSuccessNano.Load()
	var lastSuccess time.Time
	if lastNano > 0 {
		lastSuccess = time.Unix(0, lastNano)
	}
	fresh := !lastSuccess.IsZero() && lag == 0 && maxAge >= 0 && now.Sub(lastSuccess) <= maxAge
	return VirtualKeyInvalidationFreshness{
		Cursor:        cursor,
		HighWatermark: highWatermark,
		Lag:           lag,
		LastSuccess:   lastSuccess,
		Fresh:         fresh,
	}
}

// Run polls immediately, drains full batches without sleeping, and waits only
// when caught up or after a failure. Context cancellation interrupts both DB
// calls (through ctx) and the wait between attempts.
func (p *virtualKeyInvalidationPoller) Run(ctx context.Context) {
	if p == nil || p.store == nil || p.apply == nil {
		return
	}
	for {
		more, err := p.pollOnce(ctx)
		if err == nil && more {
			continue
		}
		if err != nil && ctx.Err() == nil {
			p.failureActive.Store(true)
			now := time.Now()
			lastLog := time.Unix(0, p.lastErrorLogNano.Load())
			if logger != nil && (lastLog.IsZero() || now.Sub(lastLog) >= virtualKeyInvalidationErrorLogInterval) {
				p.lastErrorLogNano.Store(now.UnixNano())
				logger.Error("virtual-key invalidation poll failed; VK authority will fail closed after the freshness lease: %v", err)
			}
		} else if err == nil && p.failureActive.Swap(false) && logger != nil {
			logger.Info("virtual-key invalidation polling recovered; VK authority freshness restored")
		}
		timer := time.NewTimer(p.pollInterval)
		select {
		case <-ctx.Done():
			if !timer.Stop() {
				<-timer.C
			}
			return
		case <-timer.C:
		}
	}
}

func (p *virtualKeyInvalidationPoller) pollOnce(ctx context.Context) (bool, error) {
	if p == nil || p.store == nil || p.apply == nil {
		return false, errors.New("virtual-key invalidation poller is not configured")
	}
	if err := ctx.Err(); err != nil {
		return false, err
	}
	highWatermark, err := p.store.GetVirtualKeyInvalidationHighWatermark(ctx)
	if err != nil {
		return false, fmt.Errorf("get virtual-key invalidation high watermark: %w", err)
	}
	p.highWatermark.Store(highWatermark)

	cursor := p.cursor.Load()
	events, err := p.store.ListVirtualKeyInvalidationsAfter(ctx, cursor, p.batchSize)
	if err != nil {
		return false, fmt.Errorf("list virtual-key invalidations after %d: %w", cursor, err)
	}
	previous := cursor
	for _, event := range events {
		if event.ID <= previous {
			return false, fmt.Errorf("virtual-key invalidation events are not strictly ordered: id %d after %d", event.ID, previous)
		}
		if event.EntityType != tables.VirtualKeyInvalidationEntityType || event.EntityID == "" || event.SchemaVersion != tables.VirtualKeyInvalidationSchemaVersion {
			return false, fmt.Errorf("invalid virtual-key invalidation event %d", event.ID)
		}
		if event.Action != tables.VirtualKeyInvalidationActionReload && event.Action != tables.VirtualKeyInvalidationActionDelete {
			return false, fmt.Errorf("unsupported virtual-key invalidation action %q at event %d", event.Action, event.ID)
		}
		previous = event.ID
	}

	for _, event := range events {
		if err := p.apply(ctx, event); err != nil {
			return false, fmt.Errorf("apply virtual-key invalidation event %d: %w", event.ID, err)
		}
		// Publish progress only after the event has been applied successfully. A
		// later failure therefore retries that event without replaying predecessors.
		p.cursor.Store(event.ID)
	}
	// The watermark and list reads are separate database statements. An event
	// may commit between them, so never publish a watermark behind an event this
	// pod has already observed and applied.
	if previous > highWatermark {
		p.highWatermark.Store(previous)
	}
	p.lastSuccessNano.Store(time.Now().UnixNano())
	return len(events) == p.batchSize, nil
}
