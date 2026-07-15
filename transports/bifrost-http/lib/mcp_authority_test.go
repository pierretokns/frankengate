package lib

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestMCPAuthoritySnapshotConvergesWithoutRuntimeClient(t *testing.T) {
	config := &Config{MCPConfig: &schemas.MCPConfig{}}
	client := &schemas.MCPClientConfig{ID: "mcp-a", Name: "tools", AllowOnAllVirtualKeys: true}
	config.ApplyMCPClientAuthority(client)
	if got := config.GetAllowOnAllVirtualKeysClients()[client.ID]; got != client.Name {
		t.Fatalf("allow-all snapshot = %q, want %q", got, client.Name)
	}

	disabled := *client
	disabled.Disabled = true
	config.ApplyMCPClientAuthority(&disabled)
	if got := config.GetAllowOnAllVirtualKeysClients(); len(got) != 0 {
		t.Fatalf("disabled MCP remained in allow-all authority: %v", got)
	}

	config.RemoveMCPClientAuthority(client.ID)
	if len(config.MCPConfig.ClientConfigs) != 0 {
		t.Fatalf("authority removal left clients: %v", config.MCPConfig.ClientConfigs)
	}
}
