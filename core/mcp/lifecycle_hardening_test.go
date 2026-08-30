package mcp

import (
	"context"
	"testing"
	"time"

	"github.com/mark3labs/mcp-go/client"
	"github.com/maximhq/bifrost/core/schemas"
)

func TestToolSyncManagerGlobalIntervalDoesNotOverridePerClientInterval(t *testing.T) {
	tsm := NewToolSyncManager(time.Hour)
	globalSyncer := &ClientToolSyncer{clientID: "global", interval: time.Hour, logger: defaultLogger}
	overrideSyncer := &ClientToolSyncer{clientID: "override", interval: 2 * time.Hour, logger: defaultLogger}
	tsm.StartSyncing(globalSyncer, true)
	tsm.StartSyncing(overrideSyncer, false)
	defer tsm.StopAll()

	tsm.SetGlobalInterval(5 * time.Minute)

	globalSyncer.mu.Lock()
	globalInterval := globalSyncer.interval
	globalSyncer.mu.Unlock()
	overrideSyncer.mu.Lock()
	overrideInterval := overrideSyncer.interval
	overrideSyncer.mu.Unlock()

	if globalInterval != 5*time.Minute {
		t.Fatalf("global syncer interval = %v, want 5m", globalInterval)
	}
	if overrideInterval != 2*time.Hour {
		t.Fatalf("per-client override interval = %v, want 2h", overrideInterval)
	}
}

func TestHealthMonitorIgnoresStaleConnectionStateUpdate(t *testing.T) {
	manager := &MCPManager{
		ctx:       context.Background(),
		clientMap: make(map[string]*schemas.MCPClientState),
	}
	conn1 := client.NewClient(nil)
	conn2 := client.NewClient(nil)
	manager.clientMap["client-1"] = &schemas.MCPClientState{
		Name:            "client-1",
		Conn:            conn2,
		State:           schemas.MCPConnectionStateDisconnected,
		ExecutionConfig: &schemas.MCPClientConfig{Name: "client-1"},
	}
	monitor := NewClientHealthMonitor(manager, "client-1", time.Hour, true, nil)

	monitor.updateClientState(conn1, schemas.MCPConnectionStateConnected)

	if got := manager.clientMap["client-1"].State; got != schemas.MCPConnectionStateDisconnected {
		t.Fatalf("stale connection changed state to %q", got)
	}
}

func TestClientToolSyncerSetClientIntervalStopsDisabledSync(t *testing.T) {
	tsm := NewToolSyncManager(time.Hour)
	syncer := &ClientToolSyncer{clientID: "client-1", interval: time.Hour, logger: defaultLogger}
	tsm.StartSyncing(syncer, true)

	tsm.SetClientInterval("client-1", 0, nil)

	tsm.mu.RLock()
	_, exists := tsm.syncers["client-1"]
	tsm.mu.RUnlock()
	if exists {
		t.Fatal("disabled client still has a tool syncer")
	}
}

func TestIsEnableableAllowsRetryAfterPartialEnable(t *testing.T) {
	if !isEnableable(&schemas.MCPClientState{
		State:           schemas.MCPConnectionStateDisabled,
		ExecutionConfig: &schemas.MCPClientConfig{Disabled: false},
	}) {
		t.Fatal("disabled state should be enableable")
	}
	if !isEnableable(&schemas.MCPClientState{
		State:           schemas.MCPConnectionStateConnected,
		ExecutionConfig: &schemas.MCPClientConfig{Disabled: true},
	}) {
		t.Fatal("partially-applied disabled config should be enableable")
	}
	if isEnableable(&schemas.MCPClientState{
		State:           schemas.MCPConnectionStateDisconnected,
		ExecutionConfig: &schemas.MCPClientConfig{Disabled: false},
	}) {
		t.Fatal("already-enabled disconnected client should not match the enable guard")
	}
}
