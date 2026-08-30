package mcp

import (
	"context"
	"sync"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

const (
	// Tool sync configuration
	DefaultToolSyncInterval = 10 * time.Minute // Default interval for syncing tools from MCP servers
	ToolSyncTimeout         = 10 * time.Second // Timeout for each sync operation
)

// ClientToolSyncer periodically syncs tools from an MCP server
type ClientToolSyncer struct {
	manager    *MCPManager
	clientID   string
	clientName string
	interval   time.Duration
	timeout    time.Duration
	logger     schemas.Logger
	mu         sync.Mutex
	ctx        context.Context
	cancel     context.CancelFunc
	intervalCh chan time.Duration
	isSyncing  bool
	usesGlobal bool
}

// NewClientToolSyncer creates a new tool syncer for an MCP client
func NewClientToolSyncer(
	manager *MCPManager,
	clientID string,
	clientName string,
	interval time.Duration,
	logger schemas.Logger,
) *ClientToolSyncer {
	if interval <= 0 {
		interval = DefaultToolSyncInterval
	}

	if logger == nil {
		logger = defaultLogger
	}

	return &ClientToolSyncer{
		manager:    manager,
		clientID:   clientID,
		clientName: clientName,
		interval:   interval,
		timeout:    ToolSyncTimeout,
		logger:     logger,
		isSyncing:  false,
	}
}

// Start begins syncing tools in a background goroutine
func (cts *ClientToolSyncer) Start() {
	cts.mu.Lock()
	defer cts.mu.Unlock()

	if cts.isSyncing {
		return // Already syncing
	}

	cts.isSyncing = true
	cts.ctx, cts.cancel = context.WithCancel(context.Background())
	cts.intervalCh = make(chan time.Duration, 1)
	ctx := cts.ctx
	intervalCh := cts.intervalCh
	interval := cts.interval

	go cts.syncLoop(ctx, intervalCh, interval)
	cts.logger.Debug("%s Tool syncer started for client %s (interval: %v)", MCPLogPrefix, cts.clientID, cts.interval)
}

// Stop stops syncing tools
func (cts *ClientToolSyncer) Stop() {
	cts.mu.Lock()
	defer cts.mu.Unlock()

	if !cts.isSyncing {
		return // Not syncing
	}

	cts.isSyncing = false
	if cts.cancel != nil {
		cts.cancel()
	}
	cts.intervalCh = nil
	cts.logger.Debug("%s Tool syncer stopped for client %s", MCPLogPrefix, cts.clientID)
}

// SetInterval updates the sync interval. A running syncer is retimed immediately.
func (cts *ClientToolSyncer) SetInterval(interval time.Duration) {
	if interval <= 0 {
		interval = DefaultToolSyncInterval
	}

	cts.mu.Lock()
	cts.interval = interval
	if cts.isSyncing && cts.intervalCh != nil {
		// Keep only the newest interval update. The sync loop owns the timer.
		select {
		case <-cts.intervalCh:
		default:
		}
		select {
		case cts.intervalCh <- interval:
		default:
		}
	}
	cts.mu.Unlock()
}

// syncLoop runs the tool sync loop

func (cts *ClientToolSyncer) syncLoop(ctx context.Context, intervalCh <-chan time.Duration, interval time.Duration) {
	timer := time.NewTimer(interval)
	defer timer.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case interval = <-intervalCh:
			if interval <= 0 {
				interval = DefaultToolSyncInterval
			}
			if !timer.Stop() {
				select {
				case <-timer.C:
				default:
				}
			}
			timer.Reset(interval)
		case <-timer.C:
			cts.performSync()
			timer.Reset(interval)
		}
	}
}

// performSync performs a tool sync for the client
func (cts *ClientToolSyncer) performSync() {
	// Get the client connection (read lock)
	cts.manager.mu.RLock()
	clientState, exists := cts.manager.clientMap[cts.clientID]
	if !exists {
		cts.manager.mu.RUnlock()
		cts.Stop()
		return
	}

	if clientState.Conn == nil {
		cts.manager.mu.RUnlock()
		cts.logger.Debug("%s Skipping tool sync for %s: client not connected", MCPLogPrefix, cts.clientID)
		return
	}

	// Get the connection reference while holding the lock
	conn := clientState.Conn
	clientName := clientState.ExecutionConfig.Name
	cts.manager.mu.RUnlock()

	// Perform tool sync with timeout (outside of lock)
	ctx, cancel := context.WithTimeout(context.Background(), cts.timeout)
	defer cancel()

	newTools, newMapping, err := cts.manager.runListToolsWithHooks(ctx, conn, clientName)
	if err != nil {
		// On failure, keep existing tools intact
		cts.logger.Warn("%s Tool sync failed for %s, keeping existing tools: %v", MCPLogPrefix, cts.clientID, err)
		return
	}

	// Update tools atomically (write lock)
	cts.manager.mu.Lock()
	clientState, exists = cts.manager.clientMap[cts.clientID]
	if !exists {
		cts.manager.mu.Unlock()
		return
	}
	// A reconnect replaces Conn while an older list_tools request may still be
	// in flight. Never let that stale response overwrite the new connection's
	// tools or a deliberately disabled client.
	if clientState.Conn != conn || clientState.State == schemas.MCPConnectionStateDisabled {
		cts.manager.mu.Unlock()
		return
	}

	// Check if tools have changed
	oldToolCount := len(clientState.ToolMap)
	newToolCount := len(newTools)

	clientState.ToolMap = newTools
	clientState.ToolNameMapping = newMapping
	cts.manager.mu.Unlock()

	if oldToolCount != newToolCount {
		cts.logger.Info("%s Tool sync completed for %s: %d -> %d tools", MCPLogPrefix, cts.clientID, oldToolCount, newToolCount)
	} else {
		cts.logger.Debug("%s Tool sync completed for %s: %d tools (no change)", MCPLogPrefix, cts.clientID, newToolCount)
	}
}

// ToolSyncManager manages all client tool syncers
type ToolSyncManager struct {
	syncers        map[string]*ClientToolSyncer
	globalInterval time.Duration
	mu             sync.RWMutex
}

// NewToolSyncManager creates a new tool sync manager
func NewToolSyncManager(globalInterval time.Duration) *ToolSyncManager {
	if globalInterval <= 0 {
		globalInterval = DefaultToolSyncInterval
	}

	return &ToolSyncManager{
		syncers:        make(map[string]*ClientToolSyncer),
		globalInterval: globalInterval,
	}
}

// GetGlobalInterval returns the global tool sync interval
func (tsm *ToolSyncManager) GetGlobalInterval() time.Duration {
	tsm.mu.RLock()
	defer tsm.mu.RUnlock()
	return tsm.globalInterval
}

// SetGlobalInterval updates the global interval and immediately retimes all
// currently running syncers that use the global setting. Per-client overrides
// are intentionally not changed.
func (tsm *ToolSyncManager) SetGlobalInterval(interval time.Duration) {
	if interval <= 0 {
		interval = DefaultToolSyncInterval
	}

	tsm.mu.Lock()
	tsm.globalInterval = interval
	for _, syncer := range tsm.syncers {
		if syncer.usesGlobal {
			syncer.SetInterval(interval)
		}
	}
	tsm.mu.Unlock()
}

// SetClientInterval retimes an existing client syncer. A non-positive value
// stops and removes the syncer; a positive value starts it when absent.
func (tsm *ToolSyncManager) SetClientInterval(clientID string, interval time.Duration, create func() *ClientToolSyncer) {
	tsm.mu.Lock()
	defer tsm.mu.Unlock()

	if interval <= 0 {
		if syncer, ok := tsm.syncers[clientID]; ok {
			syncer.Stop()
			delete(tsm.syncers, clientID)
		}
		return
	}
	if syncer, ok := tsm.syncers[clientID]; ok {
		syncer.SetInterval(interval)
		return
	}
	if create == nil {
		return
	}
	syncer := create()
	tsm.syncers[clientID] = syncer
	syncer.Start()
}

// StartSyncing starts syncing for a specific client
func (tsm *ToolSyncManager) StartSyncing(syncer *ClientToolSyncer, usesGlobal ...bool) {
	tsm.mu.Lock()
	defer tsm.mu.Unlock()
	if len(usesGlobal) > 0 {
		syncer.usesGlobal = usesGlobal[0]
	}

	// Stop any existing syncer for this client
	if existing, ok := tsm.syncers[syncer.clientID]; ok {
		existing.Stop()
	}

	tsm.syncers[syncer.clientID] = syncer
	syncer.Start()
}

// StopSyncing stops syncing for a specific client
func (tsm *ToolSyncManager) StopSyncing(clientID string) {
	tsm.mu.Lock()
	defer tsm.mu.Unlock()

	if syncer, ok := tsm.syncers[clientID]; ok {
		syncer.Stop()
		delete(tsm.syncers, clientID)
	}
}

// StopAll stops all syncing
func (tsm *ToolSyncManager) StopAll() {
	tsm.mu.Lock()
	defer tsm.mu.Unlock()

	for _, syncer := range tsm.syncers {
		syncer.Stop()
	}
	tsm.syncers = make(map[string]*ClientToolSyncer)
}

// ResolveToolSyncInterval determines the effective tool sync interval for a client.
// Priority: per-client override > global setting > default
//
// Per-client semantics:
//   - Negative value: disabled for this client
//   - Zero: use global setting
//   - Positive value: use this interval
//
// Returns 0 if sync is disabled for this client.
func ResolveToolSyncInterval(clientConfig *schemas.MCPClientConfig, globalInterval time.Duration) time.Duration {
	// Per-client explicitly disabled (negative value)
	if clientConfig.ToolSyncInterval < 0 {
		return 0 // Disabled for this client
	}

	// Per-client override (positive value)
	if clientConfig.ToolSyncInterval > 0 {
		return clientConfig.ToolSyncInterval
	}

	// Use global interval (or default if global is 0)
	if globalInterval > 0 {
		return globalInterval
	}

	return DefaultToolSyncInterval
}
