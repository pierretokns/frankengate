package server

import (
	"context"
	"errors"
	"fmt"
	"hash/fnv"
	"maps"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/plugins/governance"
	"github.com/maximhq/bifrost/plugins/otel"
	"github.com/maximhq/bifrost/plugins/telemetry"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
)

const (
	defaultVirtualKeyInvalidationBatchSize    = 100
	defaultVirtualKeyInvalidationPollInterval = time.Second
	defaultVirtualKeyAuthorityMaxStaleness    = 5 * time.Second
	virtualKeyInvalidationErrorLogInterval    = 30 * time.Second
)

var mcpRuntimeJitterSalt = uint32(time.Now().UnixNano()) ^ uint32(os.Getpid())

type virtualKeyInvalidationSource interface {
	ListVirtualKeyInvalidationsAfter(ctx context.Context, cursor uint64, limit int) ([]tables.TableVirtualKeyInvalidationEvent, error)
	GetVirtualKeyInvalidationHighWatermark(ctx context.Context) (uint64, error)
}

// virtualKeyInvalidationWakeSource is an optional acceleration capability.
// Implementations may lose or coalesce signals; the durable cursor remains the
// sole authority and periodic polling remains mandatory.
type virtualKeyInvalidationWakeSource interface {
	VirtualKeyInvalidationWakeups(context.Context) <-chan struct{}
}

// governanceSyncMetricSink receives low-cardinality control-plane metrics.
// Implementations must be non-blocking; this is called by the poller, never by
// the inference request path.
type governanceSyncMetricSink interface {
	SetGovernanceSyncMetric(name string, value float64)
}

type virtualKeyInvalidationApply func(context.Context, tables.TableVirtualKeyInvalidationEvent) error

type mcpRuntimeReconcileState struct {
	generation uint64
	operation  sync.Mutex
	ready      chan struct{}
	readyOnce  sync.Once
}

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
	wake         <-chan struct{}

	cursor           atomic.Uint64
	highWatermark    atomic.Uint64
	lastSuccessNano  atomic.Int64
	lastErrorLogNano atomic.Int64
	failureActive    atomic.Bool
	metricSink       governanceSyncMetricSink
	now              func() time.Time
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
		now:          time.Now,
	}
}

func (p *virtualKeyInvalidationPoller) clock() time.Time {
	if p != nil && p.now != nil {
		return p.now().UTC()
	}
	return time.Now().UTC()
}

// StartVirtualKeyInvalidationPoller starts this pod's ordered outbox consumer.
// Mutation handlers append to the same transactionally durable outbox in the
// config store; this consumer is the pod-local hot-reload half of that
// contract. Call during single-threaded server bootstrap so every replica
// starts with a fenced snapshot and then tails subsequent events.
func (s *BifrostHTTPServer) StartVirtualKeyInvalidationPoller(ctx context.Context) error {
	if s == nil || s.VKInvalidationPoller != nil || s.Config == nil || s.Config.ConfigStore == nil {
		return nil
	}
	if !s.Config.IsPluginLoaded(s.getGovernancePluginName()) {
		return nil
	}
	if validator, ok := s.Config.ConfigStore.(interface {
		ValidateVirtualKeyInvalidationNamespace(context.Context) error
	}); ok {
		if err := validator.ValidateVirtualKeyInvalidationNamespace(ctx); err != nil {
			return fmt.Errorf("validate virtual-key invalidation namespace: %w", err)
		}
	}
	s.VKInvalidationPoller = newVirtualKeyInvalidationPoller(
		s.Config.ConfigStore,
		func(ctx context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
			return applyGovernanceInvalidation(
				ctx,
				event,
				s.ReloadVirtualKey,
				s.RemoveVirtualKey,
				s.reloadMCPClientFromAuthority,
				s.removeMCPClientFromAuthority,
			)
		},
		defaultVirtualKeyInvalidationBatchSize,
		defaultVirtualKeyInvalidationPollInterval,
	)
	if err := s.VKInvalidationPoller.bootstrap(ctx, s.rebuildVirtualKeyAuthoritySnapshot); err != nil {
		s.VKInvalidationPoller = nil
		return fmt.Errorf("bootstrap virtual-key authority: %w", err)
	}
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
	if s.MCPServerHandler != nil {
		s.MCPServerHandler.SetAuthorityFreshnessSource(s.VKInvalidationPoller)
	}
	if wakeSource, ok := s.Config.ConfigStore.(virtualKeyInvalidationWakeSource); ok {
		s.VKInvalidationPoller.wake = wakeSource.VirtualKeyInvalidationWakeups(ctx)
	}
	var syncSinks []governanceSyncMetricSink
	if metrics, err := lib.FindPluginAs[*telemetry.PrometheusPlugin](s.Config, telemetry.PluginName); err == nil {
		syncSinks = append(syncSinks, metrics)
	}
	if metrics, err := lib.FindPluginAs[*otel.OtelPlugin](s.Config, otel.PluginName); err == nil {
		syncSinks = append(syncSinks, metrics)
	}
	if len(syncSinks) == 1 {
		s.VKInvalidationPoller.metricSink = syncSinks[0]
	} else if len(syncSinks) > 1 {
		s.VKInvalidationPoller.metricSink = governanceSyncMetricsFanout(syncSinks)
	}
	if setter, ok := s.Config.ConfigStore.(interface {
		SetVirtualKeyInvalidationMetricSink(func(string, float64))
	}); ok && len(syncSinks) > 0 {
		setter.SetVirtualKeyInvalidationMetricSink(func(name string, value float64) {
			for _, sink := range syncSinks {
				if add, ok := sink.(interface{ AddGovernanceSyncMetric(string, float64) }); ok {
					add.AddGovernanceSyncMetric(name, value)
				}
			}
		})
	}
	go s.VKInvalidationPoller.Run(ctx)
	return nil
}

// rebuildVirtualKeyAuthoritySnapshot replaces the pod-local VK authority from
// current database rows without replaying the historical outbox. The caller
// fences the outbox before invoking this function; mutations racing this read
// are therefore either represented in the snapshot, replayed after the fence,
// or both (all updates are idempotent).
func (s *BifrostHTTPServer) rebuildVirtualKeyAuthoritySnapshot(ctx context.Context) error {
	plugin, err := s.getGovernancePlugin()
	if err != nil {
		return err
	}
	store := plugin.GetGovernanceStore()
	snapshotStore, ok := store.(interface {
		ReloadAuthorityFromDatabase(context.Context) error
	})
	if !ok {
		return fmt.Errorf("governance store does not support complete authority snapshots")
	}
	oldValues := make(map[string]string)
	if data := store.GetGovernanceData(ctx); data != nil {
		for _, vk := range data.VirtualKeys {
			if vk != nil {
				oldValues[vk.ID] = vk.Value.GetValue()
			}
		}
	}
	if err := snapshotStore.ReloadAuthorityFromDatabase(ctx); err != nil {
		return fmt.Errorf("reload complete governance authority snapshot: %w", err)
	}
	currentValues := make(map[string]string)
	if data := store.GetGovernanceData(ctx); data != nil {
		for _, vk := range data.VirtualKeys {
			if vk != nil {
				currentValues[vk.ID] = vk.Value.GetValue()
			}
		}
	}
	if s.MCPServerHandler != nil {
		for id, oldValue := range oldValues {
			if newValue, ok := currentValues[id]; !ok || newValue != oldValue {
				s.MCPServerHandler.DeleteVKMCPServer(oldValue)
			}
		}
		if err := s.MCPServerHandler.SyncAllMCPServers(ctx); err != nil {
			return fmt.Errorf("resync MCP virtual-key authority caches: %w", err)
		}
	}
	return nil
}

func (s *BifrostHTTPServer) reloadMCPClientFromAuthority(ctx context.Context, id string) error {
	clientConfig, err := s.Config.ConfigStore.GetMCPClientConfigByID(ctx, id)
	if errors.Is(err, configstore.ErrNotFound) {
		return s.removeMCPClientFromAuthority(ctx, id)
	}
	if err != nil {
		return fmt.Errorf("load MCP client %s from authority: %w", id, err)
	}
	s.Config.ApplyMCPClientAuthority(clientConfig)
	state := s.scheduleMCPClientRuntimeReconcile(ctx, id)
	if err := s.quarantineMCPClientRuntime(ctx, id); err != nil {
		return fmt.Errorf("quarantine stale MCP runtime %s: %w", id, err)
	}
	if state != nil {
		// An older runtime update may already be in flight. Quarantine once
		// immediately, then again after that operation exits so it cannot
		// republish stale tools after this authority event is acknowledged.
		state.operation.Lock()
		defer state.operation.Unlock()
		if err := s.quarantineMCPClientRuntime(ctx, id); err != nil {
			return fmt.Errorf("finalize MCP runtime quarantine %s: %w", id, err)
		}
		state.readyOnce.Do(func() { close(state.ready) })
	}
	return nil
}

func (s *BifrostHTTPServer) removeMCPClientFromAuthority(ctx context.Context, id string) error {
	s.Config.RemoveMCPClientAuthority(id)
	state := s.scheduleMCPClientRuntimeReconcile(ctx, id)
	if err := s.quarantineMCPClientRuntime(ctx, id); err != nil {
		return fmt.Errorf("quarantine deleted MCP runtime %s: %w", id, err)
	}
	if state != nil {
		state.operation.Lock()
		defer state.operation.Unlock()
		if err := s.quarantineMCPClientRuntime(ctx, id); err != nil {
			return fmt.Errorf("finalize deleted MCP runtime quarantine %s: %w", id, err)
		}
		state.readyOnce.Do(func() { close(state.ready) })
	}
	return nil
}

func (s *BifrostHTTPServer) quarantineMCPClientRuntime(ctx context.Context, id string) error {
	// Clearing tools is local and does not dial the remote endpoint. Do it before
	// attempting any reconnect so revoked/disabled/changed credentials cannot
	// remain exposed through the global or lazily cached per-VK MCP servers.
	s.Client.SetClientTools(id, map[string]schemas.ChatTool{}, map[string]string{})
	if s.MCPServerHandler != nil {
		return s.MCPServerHandler.SyncAllMCPServers(ctx)
	}
	return nil
}

func (s *BifrostHTTPServer) reconcileMCPClientRuntimeOnce(ctx context.Context, id string) error {
	clientConfig, err := s.Config.ConfigStore.GetMCPClientConfigByID(ctx, id)
	if errors.Is(err, configstore.ErrNotFound) {
		if err := s.Client.RemoveMCPClient(id); err != nil && !strings.Contains(strings.ToLower(err.Error()), "not found") {
			return err
		}
		return nil
	}
	if err != nil {
		return err
	}
	clients, err := s.Client.GetMCPClients()
	if err != nil {
		return err
	}
	registered := false
	for _, client := range clients {
		if client.Config.ID == id {
			registered = true
			break
		}
	}
	if registered {
		// Replace rather than edit in place: UpdateMCPClient intentionally does
		// not reconnect credentials or drive disabled/enabled lifecycle. A full
		// remove/add applies the complete authority row and stops old workers and
		// transports. AddMCPClient creates a disabled placeholder without dialing
		// when the authority row is disabled.
		if err := s.Client.RemoveMCPClient(id); err != nil {
			return err
		}
	}
	if err := s.Client.AddMCPClient(ctx, clientConfig); err != nil {
		return err
	}
	if usesPersistedMCPToolSnapshot(clientConfig) {
		// Per-user auth clients discover tools during verified user flows and
		// persist that snapshot; they have no shared connection from which Add can
		// rediscover. Publish the durable snapshot exactly. Persistent clients keep
		// the fresh tools AddMCPClient just discovered from their live endpoint.
		s.Client.SetClientTools(
			id,
			maps.Clone(clientConfig.DiscoveredTools),
			maps.Clone(clientConfig.DiscoveredToolNameMapping),
		)
	}
	if s.MCPServerHandler != nil {
		if err := s.MCPServerHandler.SyncAllMCPServers(ctx); err != nil {
			return err
		}
	}
	return nil
}

func usesPersistedMCPToolSnapshot(config *schemas.MCPClientConfig) bool {
	return config != nil && !config.Disabled &&
		(config.AuthType == schemas.MCPAuthTypePerUserOauth || config.AuthType == schemas.MCPAuthTypePerUserHeaders)
}

func (s *BifrostHTTPServer) scheduleMCPClientRuntimeReconcile(ctx context.Context, id string) *mcpRuntimeReconcileState {
	s.mcpReconcileMu.Lock()
	if s.mcpReconcileStopping {
		s.mcpReconcileMu.Unlock()
		return nil
	}
	if s.mcpReconcileWorkers == nil {
		s.mcpReconcileWorkers = make(map[string]*mcpRuntimeReconcileState)
	}
	if state, ok := s.mcpReconcileWorkers[id]; ok {
		state.generation++
		s.mcpReconcileMu.Unlock()
		return state
	}
	state := &mcpRuntimeReconcileState{generation: 1, ready: make(chan struct{})}
	s.mcpReconcileWorkers[id] = state
	s.mcpReconcileWG.Add(1)
	s.mcpReconcileMu.Unlock()

	go func() {
		defer s.mcpReconcileWG.Done()
		select {
		case <-ctx.Done():
			s.mcpReconcileMu.Lock()
			delete(s.mcpReconcileWorkers, id)
			s.mcpReconcileMu.Unlock()
			return
		case <-state.ready:
		}
		attempt := 0
		for {
			s.mcpReconcileMu.Lock()
			targetGeneration := state.generation
			s.mcpReconcileMu.Unlock()

			delay := mcpRuntimeReconcileBackoff(id, attempt)
			timer := time.NewTimer(delay)
			select {
			case <-ctx.Done():
				if !timer.Stop() {
					<-timer.C
				}
				s.mcpReconcileMu.Lock()
				delete(s.mcpReconcileWorkers, id)
				s.mcpReconcileMu.Unlock()
				return
			case <-timer.C:
			}

			state.operation.Lock()
			err := s.reconcileMCPClientRuntimeOnce(ctx, id)
			state.operation.Unlock()
			done, generationChanged := s.completeMCPRuntimeReconcileAttempt(id, state, targetGeneration, err)
			if done {
				return
			}
			if generationChanged {
				attempt = 0
				continue
			}
			attempt++
			if logger != nil && (attempt == 1 || attempt&(attempt-1) == 0) {
				logger.Warn("MCP runtime reconciliation for %s still failing after %d attempts: %v", id, attempt, err)
			}
		}
	}()
	return state
}

func (s *BifrostHTTPServer) stopMCPRuntimeReconcilers() {
	s.mcpReconcileMu.Lock()
	s.mcpReconcileStopping = true
	s.mcpReconcileMu.Unlock()
}

func (s *BifrostHTTPServer) completeMCPRuntimeReconcileAttempt(
	id string,
	state *mcpRuntimeReconcileState,
	targetGeneration uint64,
	err error,
) (done bool, generationChanged bool) {
	s.mcpReconcileMu.Lock()
	defer s.mcpReconcileMu.Unlock()
	generationChanged = state.generation != targetGeneration
	if err == nil && !generationChanged {
		delete(s.mcpReconcileWorkers, id)
		return true, false
	}
	return false, generationChanged
}

func mcpRuntimeReconcileBackoff(id string, attempt int) time.Duration {
	if attempt > 6 {
		attempt = 6
	}
	base := time.Second * time.Duration(1<<attempt)
	h := fnv.New32a()
	_, _ = fmt.Fprintf(h, "%s:%d", id, mcpRuntimeJitterSalt)
	jitter := time.Duration(h.Sum32()%500) * time.Millisecond
	return base + jitter
}

func applyGovernanceInvalidation(
	ctx context.Context,
	event tables.TableVirtualKeyInvalidationEvent,
	reloadVirtualKey func(context.Context, string) (*tables.TableVirtualKey, error),
	removeVirtualKey func(context.Context, string) error,
	reloadMCPClient func(context.Context, string) error,
	removeMCPClient func(context.Context, string) error,
) error {
	if event.EntityType != tables.VirtualKeyInvalidationEntityType {
		return fmt.Errorf("unsupported governance invalidation entity type %q", event.EntityType)
	}
	if mcpClientID, ok := tables.ParseMCPClientInvalidationEntityID(event.EntityID); ok {
		switch event.Action {
		case tables.VirtualKeyInvalidationActionReload:
			if reloadMCPClient == nil {
				return errors.New("MCP client reload handler is not configured")
			}
			return reloadMCPClient(ctx, mcpClientID)
		case tables.VirtualKeyInvalidationActionDelete:
			if removeMCPClient == nil {
				return errors.New("MCP client removal handler is not configured")
			}
			return removeMCPClient(ctx, mcpClientID)
		default:
			return fmt.Errorf("unsupported MCP client invalidation action %q", event.Action)
		}
	}
	return applyVirtualKeyInvalidation(ctx, event, reloadVirtualKey, removeVirtualKey)
}

func applyVirtualKeyInvalidation(
	ctx context.Context,
	event tables.TableVirtualKeyInvalidationEvent,
	reload func(context.Context, string) (*tables.TableVirtualKey, error),
	remove func(context.Context, string) error,
) error {
	switch event.Action {
	case tables.VirtualKeyInvalidationActionReload:
		if reload == nil {
			return errors.New("virtual-key reload handler is not configured")
		}
		_, err := reload(ctx, event.EntityID)
		if errors.Is(err, configstore.ErrNotFound) {
			// A restarted/lagging pod can replay an old reload after the row has
			// already been deleted. Apply the current authority (absence) and keep
			// advancing toward the later tombstone instead of wedging forever.
			return remove(ctx, event.EntityID)
		}
		return err
	case tables.VirtualKeyInvalidationActionDelete:
		if remove == nil {
			return errors.New("virtual-key removal handler is not configured")
		}
		return remove(ctx, event.EntityID)
	default:
		return fmt.Errorf("unsupported virtual-key invalidation action %q", event.Action)
	}
}

// IsAuthorityFresh implements governance.AuthorityFreshnessSource. A pod is
// authorized to accept virtual keys only while it is caught up and has
// successfully contacted the durable authority within the bounded lease.
func (p *virtualKeyInvalidationPoller) IsAuthorityFresh() bool {
	return p.Freshness(p.clock(), defaultVirtualKeyAuthorityMaxStaleness).Fresh
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
	// A backwards wall-clock jump must fail closed. Otherwise a pod can appear
	// fresh indefinitely after its last successful authority read.
	age := now.Sub(lastSuccess)
	fresh := !lastSuccess.IsZero() && lag == 0 && maxAge >= 0 && age >= 0 && age <= maxAge
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
	wake := p.wake
	for {
		more, err := p.pollOnce(ctx)
		if err == nil && more {
			continue
		}
		if err != nil && ctx.Err() == nil {
			if add, ok := p.metricSink.(interface{ AddGovernanceSyncMetric(string, float64) }); ok {
				add.AddGovernanceSyncMetric("poll_errors", 1)
			}
			p.failureActive.Store(true)
			// Readiness is a live control-plane signal, not a boot-only fact. A
			// failed durable poll must close the exported gauge immediately so
			// scrapers and alerting do not continue to treat this pod as synced
			// while the freshness lease is counting down.
			if p.metricSink != nil {
				p.metricSink.SetGovernanceSyncMetric("ready", 0)
			}
			now := p.clock()
			lastLog := time.Unix(0, p.lastErrorLogNano.Load())
			if logger != nil && (lastLog.IsZero() || now.Sub(lastLog) >= virtualKeyInvalidationErrorLogInterval) {
				p.lastErrorLogNano.Store(now.UnixNano())
				logger.Error("virtual-key invalidation poll failed; VK authority will fail closed after the freshness lease: %v", err)
			}
		} else if err == nil && p.failureActive.Swap(false) && logger != nil {
			logger.Info("virtual-key invalidation polling recovered; VK authority freshness restored")
		}
		waitWake := wake
		if err != nil {
			// Notification hints must never bypass the database failure backoff.
			// Drain a coalesced hint and disable wake acceleration for this wait;
			// the next retry remains timer-bounded even during a NOTIFY storm.
			select {
			case <-wake:
			default:
			}
			waitWake = nil
		}
		timer := time.NewTimer(p.pollInterval)
		select {
		case <-ctx.Done():
			if !timer.Stop() {
				<-timer.C
			}
			return
		case _, ok := <-waitWake:
			if !timer.Stop() {
				select {
				case <-timer.C:
				default:
				}
			}
			if !ok {
				// A wake source ending is not an authority failure. Disable it and
				// retain the periodic durable poll without spinning on a closed channel.
				wake = nil
			}
		case <-timer.C:
		}
	}
}

// bootstrap fences the historical outbox before rebuilding current authority,
// then consumes only mutations that committed after the fence. Snapshot failure
// is fatal: falling back to cursor zero would make startup latency proportional
// to retained history and can violate revocation SLOs.
func (p *virtualKeyInvalidationPoller) bootstrap(ctx context.Context, snapshot func(context.Context) error) error {
	if p == nil || p.store == nil || snapshot == nil {
		return errors.New("virtual-key snapshot bootstrap is not configured")
	}
	fence, err := p.store.GetVirtualKeyInvalidationHighWatermark(ctx)
	if err != nil {
		return fmt.Errorf("fence virtual-key invalidation outbox: %w", err)
	}
	if err := snapshot(ctx); err != nil {
		return err
	}
	p.cursor.Store(fence)
	p.highWatermark.Store(fence)
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
	// A failover or a read from an eventually-consistent replica can briefly
	// return a watermark older than one this consumer has already observed.
	// Never move the local fence backwards: doing so would publish a false
	// zero-lag/readiness signal and could hide committed events until a later
	// notification happens to wake the poller.
	if observed := p.highWatermark.Load(); observed > highWatermark {
		highWatermark = observed
	}
	p.highWatermark.Store(highWatermark)

	cursor := p.cursor.Load()
	events, err := p.store.ListVirtualKeyInvalidationsAfter(ctx, cursor, p.batchSize)
	if err != nil {
		return false, fmt.Errorf("list virtual-key invalidations after %d: %w", cursor, err)
	}
	previous := cursor
	for i := range events {
		event := &events[i]
		if event.ID <= previous {
			return false, fmt.Errorf("virtual-key invalidation events are not strictly ordered: id %d after %d", event.ID, previous)
		}
		// Older outbox rows may have been written before the write-boundary
		// canonicalization was added. Normalize the ID while validating so one
		// harmlessly padded legacy row cannot permanently wedge the ordered
		// consumer and hold readiness closed. The normalized copy is applied
		// below; durable cursor advancement remains tied to the original row ID.
		event.EntityID = strings.TrimSpace(event.EntityID)
		// Rows written before schema_version was added (or decoded from an
		// older replica that omitted the column) arrive with the Go zero value.
		// AppendVirtualKeyInvalidation treats zero as the v1 default, so the
		// consumer must apply the same compatibility rule. Rejecting zero here
		// would permanently wedge the ordered cursor on the first legacy row and
		// keep every replica's readiness gate closed until manual repair.
		if event.SchemaVersion == 0 {
			event.SchemaVersion = tables.VirtualKeyInvalidationSchemaVersion
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
		// Do not continue mutating the pod-local authority after shutdown or a
		// cancelled bootstrap/poll.  Besides wasting work, advancing the cursor
		// for events applied after cancellation can make the next lifecycle start
		// appear caught up even though its predecessor never completed.  The
		// event remains durable and will be retried from the last published
		// cursor on the next poll.
		if err := ctx.Err(); err != nil {
			return false, err
		}
		started := time.Now()
		if err := p.apply(ctx, event); err != nil {
			return false, fmt.Errorf("apply virtual-key invalidation event %d: %w", event.ID, err)
		}
		if p.metricSink != nil {
			p.metricSink.SetGovernanceSyncMetric("reload_latency_seconds", time.Since(started).Seconds())
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
	p.lastSuccessNano.Store(p.clock().UnixNano())
	if p.metricSink != nil {
		lag := uint64(0)
		if highWatermark > previous {
			lag = highWatermark - previous
		}
		p.metricSink.SetGovernanceSyncMetric("consumer_lag", float64(lag))
		p.metricSink.SetGovernanceSyncMetric("outbox_depth", float64(lag))
		// Match the readiness contract: a successful database read is not
		// sufficient while the durable cursor is still behind the watermark.
		// Keep the exported signal false during catch-up so alerts do not claim
		// a pod is synchronized before all committed authority mutations apply.
		ready := 0.0
		if lag == 0 {
			ready = 1
		}
		p.metricSink.SetGovernanceSyncMetric("ready", ready)
	}
	return len(events) == p.batchSize, nil
}
