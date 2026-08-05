package mcp

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/stretchr/testify/require"
)

func TestCreateSTDIOConnectionAllowsInlineEnvAssignments(t *testing.T) {
	t.Parallel()

	config := &schemas.MCPClientConfig{
		Name:           "test-stdio-client",
		ConnectionType: schemas.MCPConnectionTypeSTDIO,
		StdioConfig: &schemas.MCPStdioConfig{
			Command: "echo",
			Envs:    []string{"TEST_STDIO_ENV_ASSIGNMENT=inline-value"},
		},
	}

	_, _, err := (&MCPManager{}).createSTDIOConnection(context.Background(), config, nil)
	require.NoError(t, err)
}

func TestMCPProtocolTransportSelection(t *testing.T) {
	modern := &schemas.MCPClientConfig{MCPProtocolMode: schemas.MCPProtocolModeModern}
	require.True(t, usesModernMCPTransport(modern))

	pinnedModern := &schemas.MCPClientConfig{MCPProtocolMode: schemas.MCPProtocolModePin, MCPProtocolVersion: "2026-07-28"}
	require.True(t, usesModernMCPTransport(pinnedModern))

	pinnedLegacy := &schemas.MCPClientConfig{MCPProtocolMode: schemas.MCPProtocolModePin, MCPProtocolVersion: "2025-06-18"}
	require.False(t, usesModernMCPTransport(pinnedLegacy))
	require.Equal(t, "2025-06-18", mcpProtocolVersion(pinnedLegacy))
	require.Error(t, validateMCPProtocolConfig(&schemas.MCPClientConfig{MCPProtocolMode: schemas.MCPProtocolModePin}))
}

func TestSetClientToolsReplacesSnapshotAndClearsRemovedTools(t *testing.T) {
	manager := &MCPManager{
		logger: &MockLogger{},
		clientMap: map[string]*schemas.MCPClientState{
			"client-a": {
				Name: "client-a",
				ToolMap: map[string]schemas.ChatTool{
					"old": {Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{Name: "old"}},
				},
				ToolNameMapping: map[string]string{"old": "old"},
			},
		},
	}
	manager.SetClientTools("client-a", map[string]schemas.ChatTool{
		"new": {Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{Name: "new"}},
	}, map[string]string{"new": "new"})
	state := manager.clientMap["client-a"]
	require.NotContains(t, state.ToolMap, "old")
	require.Contains(t, state.ToolMap, "new")
	require.Equal(t, map[string]string{"new": "new"}, state.ToolNameMapping)

	manager.SetClientTools("client-a", nil, nil)
	require.Empty(t, state.ToolMap)
	require.Empty(t, state.ToolNameMapping)
}

func TestCreateSTDIOConnectionAllowsSetReferencedEnvVars(t *testing.T) {
	t.Setenv("TEST_STDIO_ENV_REFERENCE_SET", "set-value")

	config := &schemas.MCPClientConfig{
		Name:           "test-stdio-client",
		ConnectionType: schemas.MCPConnectionTypeSTDIO,
		StdioConfig: &schemas.MCPStdioConfig{
			Command: "echo",
			Envs:    []string{"TEST_STDIO_ENV_REFERENCE_SET"},
		},
	}

	_, _, err := (&MCPManager{}).createSTDIOConnection(context.Background(), config, nil)
	require.NoError(t, err)
}

func TestCreateSTDIOConnectionRequiresReferencedEnvVars(t *testing.T) {
	t.Setenv("TEST_STDIO_ENV_REFERENCE_MISSING", "")

	config := &schemas.MCPClientConfig{
		Name:           "test-stdio-client",
		ConnectionType: schemas.MCPConnectionTypeSTDIO,
		StdioConfig: &schemas.MCPStdioConfig{
			Command: "echo",
			Envs:    []string{"TEST_STDIO_ENV_REFERENCE_MISSING"},
		},
	}

	_, _, err := (&MCPManager{}).createSTDIOConnection(context.Background(), config, nil)
	require.Error(t, err)
	require.Contains(t, err.Error(), "environment variable TEST_STDIO_ENV_REFERENCE_MISSING is not set")
}

func TestCreateSTDIOConnectionRejectsEmptyEnvAssignmentName(t *testing.T) {
	t.Parallel()

	config := &schemas.MCPClientConfig{
		Name:           "test-stdio-client",
		ConnectionType: schemas.MCPConnectionTypeSTDIO,
		StdioConfig: &schemas.MCPStdioConfig{
			Command: "echo",
			Envs:    []string{"=inline-value"},
		},
	}

	_, _, err := (&MCPManager{}).createSTDIOConnection(context.Background(), config, nil)
	require.Error(t, err)
	require.Contains(t, err.Error(), "environment variable name is empty")
}
