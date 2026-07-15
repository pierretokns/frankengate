package server

import (
	"context"
	"errors"
	"fmt"
	"path/filepath"
	"reflect"
	"sync"
	"testing"
	"time"

	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
	"gorm.io/gorm"
)

type testVKCache struct {
	mu    sync.Mutex
	byID  map[string]string
	byKey map[string]string
}

func newTestVKCache() *testVKCache {
	return &testVKCache{byID: make(map[string]string), byKey: make(map[string]string)}
}

func (c *testVKCache) reload(vk *tables.TableVirtualKey) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if old := c.byID[vk.ID]; old != "" {
		delete(c.byKey, old)
	}
	value := vk.Value.GetValue()
	c.byID[vk.ID] = value
	c.byKey[value] = vk.ID
}

func (c *testVKCache) remove(id string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if old := c.byID[id]; old != "" {
		delete(c.byKey, old)
	}
	delete(c.byID, id)
}

func (c *testVKCache) contains(value string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	_, ok := c.byKey[value]
	return ok
}

func TestThreePollersShareCreateRotateDeleteThroughDurableStore(t *testing.T) {
	ctx := context.Background()
	store, err := configstore.NewConfigStore(ctx, &configstore.Config{
		Enabled: true,
		Type:    configstore.ConfigStoreTypeSQLite,
		Config:  &configstore.SQLiteConfig{Path: filepath.Join(t.TempDir(), "authority.db")},
	}, bifrost.NewDefaultLogger(schemas.LogLevelError))
	require.NoError(t, err)

	oldValue := "sk-bf-shared-old"
	vk := &tables.TableVirtualKey{ID: "vk-shared", Name: "Shared", Value: *schemas.NewSecretVar(oldValue)}
	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		if err := store.CreateVirtualKey(ctx, vk, tx); err != nil {
			return err
		}
		return store.AppendVirtualKeyInvalidation(ctx, tx, &tables.TableVirtualKeyInvalidationEvent{
			EntityType: tables.VirtualKeyInvalidationEntityType,
			Action:     tables.VirtualKeyInvalidationActionReload,
			EntityID:   vk.ID,
		})
	}))

	caches := []*testVKCache{newTestVKCache(), newTestVKCache(), newTestVKCache()}
	pollers := make([]*virtualKeyInvalidationPoller, 0, len(caches))
	for _, cache := range caches {
		cache := cache
		pollers = append(pollers, newVirtualKeyInvalidationPoller(store, func(ctx context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
			return applyVirtualKeyInvalidation(ctx, event,
				func(ctx context.Context, id string) (*tables.TableVirtualKey, error) {
					loaded, err := store.GetVirtualKey(ctx, id)
					if err == nil {
						cache.reload(loaded)
					}
					return loaded, err
				},
				func(_ context.Context, id string) error { cache.remove(id); return nil },
			)
		}, 100, time.Second))
	}
	pollAll := func() {
		for _, poller := range pollers {
			_, err := poller.pollOnce(ctx)
			require.NoError(t, err)
		}
	}
	pollAll()
	for _, cache := range caches {
		require.True(t, cache.contains(oldValue))
	}

	newValue := "sk-bf-shared-new"
	vk.Value = *schemas.NewSecretVar(newValue)
	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		if err := store.UpdateVirtualKey(ctx, vk, tx); err != nil {
			return err
		}
		return store.AppendVirtualKeyInvalidation(ctx, tx, &tables.TableVirtualKeyInvalidationEvent{
			EntityType: tables.VirtualKeyInvalidationEntityType,
			Action:     tables.VirtualKeyInvalidationActionReload,
			EntityID:   vk.ID,
		})
	}))
	pollAll()
	for _, cache := range caches {
		require.False(t, cache.contains(oldValue))
		require.True(t, cache.contains(newValue))
	}

	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		if err := store.DeleteVirtualKey(ctx, vk.ID, tx); err != nil {
			return err
		}
		return store.AppendVirtualKeyInvalidation(ctx, tx, &tables.TableVirtualKeyInvalidationEvent{
			EntityType: tables.VirtualKeyInvalidationEntityType,
			Action:     tables.VirtualKeyInvalidationActionDelete,
			EntityID:   vk.ID,
		})
	}))
	pollAll()
	for _, cache := range caches {
		require.False(t, cache.contains(oldValue))
		require.False(t, cache.contains(newValue))
	}
}

func TestApplyVirtualKeyInvalidationHistoricalReloadOfDeletedRowBecomesDelete(t *testing.T) {
	removed := make([]string, 0, 2)
	reload := func(context.Context, string) (*tables.TableVirtualKey, error) {
		return nil, configstore.ErrNotFound
	}
	remove := func(_ context.Context, id string) error {
		removed = append(removed, id)
		return nil
	}

	reloadEvent := tables.TableVirtualKeyInvalidationEvent{ID: 1, Action: tables.VirtualKeyInvalidationActionReload, EntityID: "vk-deleted"}
	deleteEvent := tables.TableVirtualKeyInvalidationEvent{ID: 2, Action: tables.VirtualKeyInvalidationActionDelete, EntityID: "vk-deleted"}
	require.NoError(t, applyVirtualKeyInvalidation(context.Background(), reloadEvent, reload, remove))
	require.NoError(t, applyVirtualKeyInvalidation(context.Background(), deleteEvent, reload, remove))
	require.Equal(t, []string{"vk-deleted", "vk-deleted"}, removed)
}

type fakeVKInvalidationStore struct {
	mu         sync.Mutex
	events     []tables.TableVirtualKeyInvalidationEvent
	listErr    error
	highWater  uint64
	listCalls  int
	listCalled chan struct{}
}

func (s *fakeVKInvalidationStore) ListVirtualKeyInvalidationsAfter(_ context.Context, cursor uint64, limit int) ([]tables.TableVirtualKeyInvalidationEvent, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.listCalls++
	if s.listCalled != nil {
		select {
		case s.listCalled <- struct{}{}:
		default:
		}
	}
	if s.listErr != nil {
		return nil, s.listErr
	}
	result := make([]tables.TableVirtualKeyInvalidationEvent, 0, limit)
	for _, event := range s.events {
		if event.ID > cursor {
			result = append(result, event)
			if len(result) == limit {
				break
			}
		}
	}
	return result, nil
}

func (s *fakeVKInvalidationStore) GetVirtualKeyInvalidationHighWatermark(context.Context) (uint64, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.highWater, nil
}

func TestVirtualKeyInvalidationPollerAppliesOrderedBatchAndPublishesFreshness(t *testing.T) {
	store := &fakeVKInvalidationStore{
		highWater: 3,
		events: []tables.TableVirtualKeyInvalidationEvent{
			{ID: 1, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-a", Action: tables.VirtualKeyInvalidationActionReload, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion},
			{ID: 2, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-b", Action: tables.VirtualKeyInvalidationActionDelete, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion},
			{ID: 3, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-c", Action: tables.VirtualKeyInvalidationActionReload, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion},
		},
	}
	var applied []string
	poller := newVirtualKeyInvalidationPoller(store, func(_ context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
		applied = append(applied, event.Action+":"+event.EntityID)
		return nil
	}, 10, time.Second)

	more, err := poller.pollOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if more {
		t.Fatal("short batch unexpectedly reported more work")
	}
	want := []string{"reload:vk-a", "delete:vk-b", "reload:vk-c"}
	if len(applied) != len(want) {
		t.Fatalf("applied = %v, want %v", applied, want)
	}
	for i := range want {
		if applied[i] != want[i] {
			t.Fatalf("applied = %v, want %v", applied, want)
		}
	}
	state := poller.Freshness(time.Now(), time.Minute)
	if state.Cursor != 3 || state.HighWatermark != 3 || state.Lag != 0 || !state.Fresh || state.LastSuccess.IsZero() {
		t.Fatalf("unexpected freshness state: %+v", state)
	}
}

func TestVirtualKeyInvalidationBootstrapSkipsBoundedHistoricalOutbox(t *testing.T) {
	const history = 100_000
	store := &fakeVKInvalidationStore{highWater: history}
	for id := uint64(1); id <= history; id++ {
		store.events = append(store.events, tables.TableVirtualKeyInvalidationEvent{
			ID: id, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "deleted-vk", Action: tables.VirtualKeyInvalidationActionReload, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion,
		})
	}
	applied := 0
	snapshots := 0
	poller := newVirtualKeyInvalidationPoller(store, func(context.Context, tables.TableVirtualKeyInvalidationEvent) error {
		applied++
		return nil
	}, 100, time.Second)
	require.NoError(t, poller.bootstrap(context.Background(), func(context.Context) error {
		snapshots++
		return nil
	}))
	require.Equal(t, 1, snapshots)
	require.Equal(t, 0, applied)
	require.Equal(t, uint64(history), poller.Cursor())
	require.Equal(t, 1, store.listCalls, "bootstrap must not page through historical events")
}

func TestVirtualKeyInvalidationBootstrapAppliesMutationAfterFence(t *testing.T) {
	store := &fakeVKInvalidationStore{highWater: 7}
	var applied []uint64
	poller := newVirtualKeyInvalidationPoller(store, func(_ context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
		applied = append(applied, event.ID)
		return nil
	}, 100, time.Second)
	require.NoError(t, poller.bootstrap(context.Background(), func(context.Context) error {
		store.mu.Lock()
		defer store.mu.Unlock()
		store.events = append(store.events, tables.TableVirtualKeyInvalidationEvent{
			ID: 8, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-after-fence", Action: tables.VirtualKeyInvalidationActionReload, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion,
		})
		store.highWater = 8
		return nil
	}))
	require.Equal(t, []uint64{8}, applied)
	require.Equal(t, uint64(8), poller.Cursor())
}

func TestVirtualKeyInvalidationBootstrapFailsClosedWhenSnapshotUnavailable(t *testing.T) {
	store := &fakeVKInvalidationStore{highWater: 50_000}
	poller := newVirtualKeyInvalidationPoller(store, func(context.Context, tables.TableVirtualKeyInvalidationEvent) error {
		t.Fatal("historical replay must not be used as a snapshot fallback")
		return nil
	}, 100, time.Second)
	err := poller.bootstrap(context.Background(), func(context.Context) error {
		return errors.New("snapshot unavailable")
	})
	require.ErrorContains(t, err, "snapshot unavailable")
	require.Equal(t, uint64(0), poller.Cursor())
	require.Equal(t, 0, store.listCalls)
}

func TestApplyGovernanceInvalidationDispatchesMCPClientEvents(t *testing.T) {
	var calls []string
	reloadVK := func(context.Context, string) (*tables.TableVirtualKey, error) {
		return nil, errors.New("unexpected VK reload")
	}
	removeVK := func(context.Context, string) error { return errors.New("unexpected VK delete") }
	reloadMCP := func(_ context.Context, id string) error {
		calls = append(calls, "reload:"+id)
		return nil
	}
	removeMCP := func(_ context.Context, id string) error {
		calls = append(calls, "delete:"+id)
		return nil
	}
	for _, event := range []tables.TableVirtualKeyInvalidationEvent{
		{EntityType: tables.VirtualKeyInvalidationEntityType, Action: tables.VirtualKeyInvalidationActionReload, EntityID: tables.MCPClientInvalidationEntityID("mcp-a")},
		{EntityType: tables.VirtualKeyInvalidationEntityType, Action: tables.VirtualKeyInvalidationActionDelete, EntityID: tables.MCPClientInvalidationEntityID("mcp-b")},
	} {
		if err := applyGovernanceInvalidation(context.Background(), event, reloadVK, removeVK, reloadMCP, removeMCP); err != nil {
			t.Fatal(err)
		}
	}
	if want := []string{"reload:mcp-a", "delete:mcp-b"}; !reflect.DeepEqual(calls, want) {
		t.Fatalf("calls = %v, want %v", calls, want)
	}
}

func TestMCPControlRecordIsSafeForPreMCPConsumer(t *testing.T) {
	entityID := tables.MCPClientInvalidationEntityID("mcp-a")
	var removed string
	err := applyVirtualKeyInvalidation(
		context.Background(),
		tables.TableVirtualKeyInvalidationEvent{
			EntityType: tables.VirtualKeyInvalidationEntityType,
			Action:     tables.VirtualKeyInvalidationActionReload,
			EntityID:   entityID,
		},
		func(context.Context, string) (*tables.TableVirtualKey, error) { return nil, configstore.ErrNotFound },
		func(_ context.Context, id string) error { removed = id; return nil },
	)
	if err != nil {
		t.Fatal(err)
	}
	if removed != entityID {
		t.Fatalf("legacy consumer removed %q, want reserved control id %q", removed, entityID)
	}
}

func TestLegacyConsumerAdvancesPastMCPControlRecordInMigratedStore(t *testing.T) {
	ctx := context.Background()
	store, err := configstore.NewConfigStore(ctx, &configstore.Config{
		Enabled: true,
		Type:    configstore.ConfigStoreTypeSQLite,
		Config:  &configstore.SQLiteConfig{Path: filepath.Join(t.TempDir(), "legacy.db")},
	}, bifrost.NewDefaultLogger(schemas.LogLevelError))
	require.NoError(t, err)
	event := &tables.TableVirtualKeyInvalidationEvent{
		EntityType: tables.VirtualKeyInvalidationEntityType,
		Action:     tables.VirtualKeyInvalidationActionReload,
		EntityID:   tables.MCPClientInvalidationEntityID("mcp-rolling-upgrade"),
	}
	require.NoError(t, store.ExecuteTransaction(ctx, func(tx *gorm.DB) error {
		return store.AppendVirtualKeyInvalidation(ctx, tx, event)
	}))

	// This callback is the complete pre-MCP consumer behavior: it knows only
	// reload/delete VK records and resolves against the real migrated store.
	legacyPoller := newVirtualKeyInvalidationPoller(store, func(ctx context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
		return applyVirtualKeyInvalidation(ctx, event, store.GetVirtualKey, func(context.Context, string) error { return nil })
	}, 100, time.Second)
	more, err := legacyPoller.pollOnce(ctx)
	require.NoError(t, err)
	require.False(t, more)
	require.Equal(t, event.ID, legacyPoller.Cursor())
	require.True(t, legacyPoller.Freshness(time.Now(), time.Minute).Fresh)
}

func TestMCPRuntimeReconcileNewerGenerationCannotBeLost(t *testing.T) {
	server := &BifrostHTTPServer{mcpReconcileWorkers: make(map[string]*mcpRuntimeReconcileState)}
	state := &mcpRuntimeReconcileState{generation: 1}
	server.mcpReconcileWorkers["mcp-a"] = state

	// A newer event arrives while the generation-1 attempt is in flight.
	state.generation = 2
	done, changed := server.completeMCPRuntimeReconcileAttempt("mcp-a", state, 1, nil)
	if done || !changed {
		t.Fatalf("older success done=%v changed=%v, want retained dirty generation", done, changed)
	}
	if server.mcpReconcileWorkers["mcp-a"] != state {
		t.Fatal("older success deleted the worker for a newer generation")
	}

	done, changed = server.completeMCPRuntimeReconcileAttempt("mcp-a", state, 2, nil)
	if !done || changed {
		t.Fatalf("latest success done=%v changed=%v, want completion", done, changed)
	}
	if _, exists := server.mcpReconcileWorkers["mcp-a"]; exists {
		t.Fatal("latest successful generation left a retry worker behind")
	}
}

func TestNewMCPEventQuarantinesAfterBlockedOlderRuntimeAttempt(t *testing.T) {
	server := &BifrostHTTPServer{mcpReconcileWorkers: make(map[string]*mcpRuntimeReconcileState)}
	state := &mcpRuntimeReconcileState{generation: 1, ready: make(chan struct{})}
	server.mcpReconcileWorkers["mcp-a"] = state
	oldStarted := make(chan struct{})
	releaseOld := make(chan struct{})
	order := make(chan string, 2)
	go func() {
		state.operation.Lock()
		close(oldStarted)
		<-releaseOld
		order <- "old-runtime-write"
		state.operation.Unlock()
	}()
	<-oldStarted

	server.mcpReconcileMu.Lock()
	state.generation++
	server.mcpReconcileMu.Unlock()
	newQuarantined := make(chan struct{})
	go func() {
		state.operation.Lock()
		order <- "new-quarantine"
		state.operation.Unlock()
		close(newQuarantined)
	}()
	close(releaseOld)
	<-newQuarantined
	if first, second := <-order, <-order; first != "old-runtime-write" || second != "new-quarantine" {
		t.Fatalf("operation order = %q then %q, want old write then final quarantine", first, second)
	}
	done, changed := server.completeMCPRuntimeReconcileAttempt("mcp-a", state, 1, nil)
	if done || !changed {
		t.Fatalf("older attempt done=%v changed=%v, want retry of latest generation", done, changed)
	}
}

func TestOnlyPerUserAuthUsesPersistedMCPToolSnapshot(t *testing.T) {
	for _, tt := range []struct {
		name string
		auth schemas.MCPAuthType
		want bool
	}{
		{name: "none", auth: schemas.MCPAuthTypeNone, want: false},
		{name: "static headers", auth: schemas.MCPAuthTypeHeaders, want: false},
		{name: "server oauth", auth: schemas.MCPAuthTypeOauth, want: false},
		{name: "per-user oauth", auth: schemas.MCPAuthTypePerUserOauth, want: true},
		{name: "per-user headers", auth: schemas.MCPAuthTypePerUserHeaders, want: true},
	} {
		t.Run(tt.name, func(t *testing.T) {
			if got := usesPersistedMCPToolSnapshot(&schemas.MCPClientConfig{AuthType: tt.auth}); got != tt.want {
				t.Fatalf("usesPersistedMCPToolSnapshot(%q) = %v, want %v", tt.auth, got, tt.want)
			}
		})
	}
	if usesPersistedMCPToolSnapshot(&schemas.MCPClientConfig{AuthType: schemas.MCPAuthTypePerUserOauth, Disabled: true}) {
		t.Fatal("disabled per-user client attempted to restore persisted tools")
	}
}

func TestVirtualKeyInvalidationPollerRetriesFailedEventWithoutSkippingIt(t *testing.T) {
	store := &fakeVKInvalidationStore{
		highWater: 2,
		events: []tables.TableVirtualKeyInvalidationEvent{
			{ID: 1, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-a", Action: tables.VirtualKeyInvalidationActionReload, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion},
			{ID: 2, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-b", Action: tables.VirtualKeyInvalidationActionDelete, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion},
		},
	}
	attempts := map[uint64]int{}
	poller := newVirtualKeyInvalidationPoller(store, func(_ context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
		attempts[event.ID]++
		if event.ID == 2 && attempts[event.ID] == 1 {
			return errors.New("temporary reload failure")
		}
		return nil
	}, 10, time.Second)

	if _, err := poller.pollOnce(context.Background()); err == nil {
		t.Fatal("first poll unexpectedly succeeded")
	}
	if got := poller.Cursor(); got != 1 {
		t.Fatalf("cursor after partial failure = %d, want 1", got)
	}
	if _, err := poller.pollOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	if got := poller.Cursor(); got != 2 {
		t.Fatalf("cursor after retry = %d, want 2", got)
	}
	if attempts[1] != 1 || attempts[2] != 2 {
		t.Fatalf("attempts = %v, want event 1 once and event 2 twice", attempts)
	}
}

func TestVirtualKeyInvalidationPollerRejectsOutOfOrderBatchWithoutAdvancingPastIt(t *testing.T) {
	store := &fakeVKInvalidationStore{
		highWater: 3,
		events: []tables.TableVirtualKeyInvalidationEvent{
			{ID: 2, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-a", Action: tables.VirtualKeyInvalidationActionReload, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion},
			{ID: 1, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-b", Action: tables.VirtualKeyInvalidationActionReload, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion},
		},
	}
	var applied []uint64
	poller := newVirtualKeyInvalidationPoller(store, func(_ context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
		applied = append(applied, event.ID)
		return nil
	}, 10, time.Second)

	if _, err := poller.pollOnce(context.Background()); err == nil {
		t.Fatal("out-of-order batch unexpectedly succeeded")
	}
	if got := poller.Cursor(); got != 0 {
		t.Fatalf("cursor = %d, want no progress for malformed batch", got)
	}
	if len(applied) != 0 {
		t.Fatalf("applied = %v, want no side effects", applied)
	}
}

func TestVirtualKeyInvalidationPollerLeavesFreshnessStaleAfterStoreFailure(t *testing.T) {
	store := &fakeVKInvalidationStore{highWater: 7, listErr: errors.New("database unavailable")}
	poller := newVirtualKeyInvalidationPoller(store, func(context.Context, tables.TableVirtualKeyInvalidationEvent) error { return nil }, 10, time.Second)

	if _, err := poller.pollOnce(context.Background()); err == nil {
		t.Fatal("failed list unexpectedly succeeded")
	}
	state := poller.Freshness(time.Now(), time.Minute)
	if state.HighWatermark != 7 || state.Lag != 7 || state.Fresh || !state.LastSuccess.IsZero() {
		t.Fatalf("unexpected freshness after failure: %+v", state)
	}
}

func TestVirtualKeyInvalidationPollerStopsOnContextCancellation(t *testing.T) {
	store := &fakeVKInvalidationStore{}
	poller := newVirtualKeyInvalidationPoller(store, func(context.Context, tables.TableVirtualKeyInvalidationEvent) error { return nil }, 10, time.Hour)
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		poller.Run(ctx)
		close(done)
	}()
	cancel()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("poller did not stop after context cancellation")
	}
}

func TestVirtualKeyInvalidationWakeInterruptsLongPollAndDrainsAllBatches(t *testing.T) {
	store := &fakeVKInvalidationStore{listCalled: make(chan struct{}, 1)}
	wake := make(chan struct{}, 1)
	applied := make(chan uint64, 5)
	poller := newVirtualKeyInvalidationPoller(store, func(_ context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
		applied <- event.ID
		return nil
	}, 2, time.Hour)
	poller.wake = wake

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		poller.Run(ctx)
		close(done)
	}()
	defer func() {
		cancel()
		<-done
	}()

	select {
	case <-store.listCalled:
	case <-time.After(time.Second):
		t.Fatal("initial durable poll did not run")
	}

	store.mu.Lock()
	store.highWater = 5
	for id := uint64(1); id <= 5; id++ {
		store.events = append(store.events, tables.TableVirtualKeyInvalidationEvent{
			ID: id, EntityType: tables.VirtualKeyInvalidationEntityType,
			EntityID: fmt.Sprintf("vk-%d", id), Action: tables.VirtualKeyInvalidationActionReload,
			SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion,
		})
	}
	store.mu.Unlock()

	// A storm coalesces into one buffered hint. The poller still drains every
	// durable batch immediately and in cursor order.
	for i := 0; i < 100; i++ {
		select {
		case wake <- struct{}{}:
		default:
		}
	}
	for want := uint64(1); want <= 5; want++ {
		select {
		case got := <-applied:
			if got != want {
				t.Fatalf("applied event %d, want %d", got, want)
			}
		case <-time.After(time.Second):
			t.Fatalf("notification wake did not drain event %d", want)
		}
	}
	if poller.Cursor() != 5 {
		t.Fatalf("cursor = %d, want 5", poller.Cursor())
	}
}

func TestVirtualKeyInvalidationClosedWakeFallsBackWithoutSpin(t *testing.T) {
	store := &fakeVKInvalidationStore{listCalled: make(chan struct{}, 2)}
	wake := make(chan struct{})
	poller := newVirtualKeyInvalidationPoller(store, func(context.Context, tables.TableVirtualKeyInvalidationEvent) error { return nil }, 10, time.Hour)
	poller.wake = wake
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() { poller.Run(ctx); close(done) }()
	<-store.listCalled
	close(wake)
	<-store.listCalled // one final immediate durable check after closure
	time.Sleep(25 * time.Millisecond)
	store.mu.Lock()
	calls := store.listCalls
	store.mu.Unlock()
	cancel()
	<-done
	if calls != 2 {
		t.Fatalf("closed wake caused %d durable polls, want exactly 2", calls)
	}
}

func TestVirtualKeyInvalidationLostWakeFallsBackToPeriodicPoll(t *testing.T) {
	store := &fakeVKInvalidationStore{listCalled: make(chan struct{}, 1)}
	applied := make(chan uint64, 1)
	poller := newVirtualKeyInvalidationPoller(store, func(_ context.Context, event tables.TableVirtualKeyInvalidationEvent) error {
		applied <- event.ID
		return nil
	}, 10, 20*time.Millisecond)
	poller.wake = make(chan struct{}, 1) // deliberately never signaled
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() { poller.Run(ctx); close(done) }()
	defer func() { cancel(); <-done }()
	<-store.listCalled

	store.mu.Lock()
	store.highWater = 1
	store.events = []tables.TableVirtualKeyInvalidationEvent{{
		ID: 1, EntityType: tables.VirtualKeyInvalidationEntityType, EntityID: "vk-lost-wake",
		Action: tables.VirtualKeyInvalidationActionDelete, SchemaVersion: tables.VirtualKeyInvalidationSchemaVersion,
	}}
	store.mu.Unlock()
	select {
	case got := <-applied:
		if got != 1 {
			t.Fatalf("applied event %d, want 1", got)
		}
	case <-time.After(time.Second):
		t.Fatal("periodic durable poll did not repair a lost notification")
	}
}

func TestVirtualKeyInvalidationWakeStormCannotBypassFailureBackoff(t *testing.T) {
	store := &fakeVKInvalidationStore{listErr: errors.New("database unavailable")}
	wake := make(chan struct{}, 1)
	poller := newVirtualKeyInvalidationPoller(store, func(context.Context, tables.TableVirtualKeyInvalidationEvent) error {
		return nil
	}, 10, 30*time.Millisecond)
	poller.wake = wake

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() { poller.Run(ctx); close(done) }()
	stormDone := make(chan struct{})
	go func() {
		defer close(stormDone)
		for ctx.Err() == nil {
			select {
			case wake <- struct{}{}:
			default:
			}
			time.Sleep(time.Millisecond)
		}
	}()

	time.Sleep(140 * time.Millisecond)
	cancel()
	<-done
	<-stormDone
	store.mu.Lock()
	calls := store.listCalls
	store.mu.Unlock()
	if calls < 3 || calls > 6 {
		t.Fatalf("database failure made %d polls during 140ms with 30ms backoff; want 3..6", calls)
	}
}
