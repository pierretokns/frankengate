package handlers

import (
	"context"
	"testing"

	legacyMCP "github.com/mark3labs/mcp-go/mcp"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/stretchr/testify/require"
	"github.com/valyala/fasthttp"
)

func TestIsModernMCPRequest(t *testing.T) {
	tests := []struct {
		name       string
		version    string
		body       string
		wantModern bool
	}{
		{name: "modern protocol header", version: "2026-07-28", wantModern: true},
		{name: "modern discovery probe", body: `{"jsonrpc":"2.0","id":1,"method":"server/discover"}`, wantModern: true},
		{name: "legacy initialize", body: `{"jsonrpc":"2.0","id":1,"method":"initialize"}`, wantModern: false},
		{name: "unsupported protocol header", version: "2025-06-18", wantModern: false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ctx := &fasthttp.RequestCtx{}
			if tt.version != "" {
				ctx.Request.Header.Set(mcpProtocolVersionHeader, tt.version)
			}
			if tt.body != "" {
				ctx.Request.SetBodyString(tt.body)
			}
			require.Equal(t, tt.wantModern, isModernMCPRequest(ctx))
		})
	}
}

func TestContextWithMCPFilterHeaders(t *testing.T) {
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.Set("x-bf-mcp-include-clients", "alpha, beta,, gamma")
	ctx.Request.Header.Set("x-bf-mcp-include-tools", "alpha-search, beta-* ")

	filtered := contextWithMCPFilterHeaders(context.Background(), ctx)
	require.Equal(t, []string{"alpha", "beta", "gamma"}, filtered.Value(schemas.MCPContextKeyIncludeClients))
	require.Equal(t, []string{"alpha-search", "beta-*"}, filtered.Value(schemas.MCPContextKeyIncludeTools))
}

func TestModernToolInputSchema(t *testing.T) {
	t.Run("normalizes empty schema fields", func(t *testing.T) {
		schema, err := modernToolInputSchema(legacyMCP.ToolInputSchema{})
		require.NoError(t, err)
		require.Equal(t, "object", schema.(map[string]any)["type"])
		require.Equal(t, map[string]any{}, schema.(map[string]any)["properties"])
	})

	t.Run("preserves json schema fields", func(t *testing.T) {
		schema, err := modernToolInputSchema(legacyMCP.ToolInputSchema{
			Type:       "object",
			Properties: map[string]any{"query": map[string]any{"type": "string"}},
			Required:   []string{"query"},
		})
		require.NoError(t, err)
		got := schema.(map[string]any)
		require.Equal(t, map[string]any{"query": map[string]any{"type": "string"}}, got["properties"])
		require.Equal(t, []any{"query"}, got["required"])
	})

	t.Run("rejects non object schemas", func(t *testing.T) {
		_, err := modernToolInputSchema(legacyMCP.ToolInputSchema{Type: "string"})
		require.EqualError(t, err, "input schema type must be object, got string")
	})
}

func TestModernToolAnnotations(t *testing.T) {
	readOnly := true
	destructive := false
	idempotent := true
	openWorld := false

	got := modernToolAnnotations(legacyMCP.ToolAnnotation{
		Title:           "Search",
		ReadOnlyHint:    &readOnly,
		DestructiveHint: &destructive,
		IdempotentHint:  &idempotent,
		OpenWorldHint:   &openWorld,
	})
	require.Equal(t, "Search", got.Title)
	require.True(t, got.ReadOnlyHint)
	require.NotNil(t, got.DestructiveHint)
	require.False(t, *got.DestructiveHint)
	require.True(t, got.IdempotentHint)
	require.NotNil(t, got.OpenWorldHint)
	require.False(t, *got.OpenWorldHint)
}
