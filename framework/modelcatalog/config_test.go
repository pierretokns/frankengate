package modelcatalog

import "testing"

func TestEffectiveMCPLibraryURL(t *testing.T) {
	t.Setenv("FRANKENGATE_MCP_LIBRARY_URL", "  https://mirror.example/mcp-library  ")
	if got := EffectiveMCPLibraryURL(); got != "https://mirror.example/mcp-library" {
		t.Fatalf("override was not trimmed/resolved: %q", got)
	}
	t.Setenv("FRANKENGATE_MCP_LIBRARY_URL", "")
	if got := EffectiveMCPLibraryURL(); got != DefaultMCPLibraryURL {
		t.Fatalf("empty override should preserve compatibility default: %q", got)
	}
}
