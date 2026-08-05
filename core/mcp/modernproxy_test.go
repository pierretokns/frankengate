package mcp

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	legacyMCP "github.com/mark3labs/mcp-go/mcp"
	legacyServer "github.com/mark3labs/mcp-go/server"
	"github.com/maximhq/bifrost/core/schemas"
	modernmcp "github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/stretchr/testify/require"
)

func TestModernToolToLegacy(t *testing.T) {
	tool, err := modernToolToLegacy(&modernmcp.Tool{
		Name:        "search",
		Description: "Search the catalog",
		InputSchema: map[string]any{"type": "object", "properties": map[string]any{"q": map[string]any{"type": "string"}}},
		Annotations: &modernmcp.ToolAnnotations{Title: "Catalog search", ReadOnlyHint: true},
	})
	require.NoError(t, err)
	require.Equal(t, "search", tool.Name)
	require.Equal(t, "Catalog search", tool.Title)
	require.True(t, tool.Annotations.ReadOnlyHint != nil && *tool.Annotations.ReadOnlyHint)

	var schema map[string]any
	require.NoError(t, json.Unmarshal(tool.RawInputSchema, &schema))
	require.Equal(t, "object", schema["type"])
}

func TestModernToolToLegacyRejectsNonObjectSchema(t *testing.T) {
	_, err := modernToolToLegacy(&modernmcp.Tool{Name: "invalid", InputSchema: map[string]any{"type": "string"}})
	require.EqualError(t, err, `tool "invalid" input schema must have type object`)
}

func TestModernResultToLegacy(t *testing.T) {
	result := modernResultToLegacy(&modernmcp.CallToolResult{
		Content: []modernmcp.Content{
			&modernmcp.TextContent{Text: "first"},
			&modernmcp.TextContent{Text: "second"},
		},
	})
	require.False(t, result.IsError)
	require.Len(t, result.Content, 1)
	require.Equal(t, "first\nsecond", result.Content[0].(legacyMCP.TextContent).Text)

	errResult := modernResultToLegacy(&modernmcp.CallToolResult{
		Content: []modernmcp.Content{&modernmcp.TextContent{Text: "failed"}},
		IsError: true,
	})
	require.True(t, errResult.IsError)
}

func TestMCPHeaderRoundTripper(t *testing.T) {
	var got *http.Request
	roundTripper := &mcpHeaderRoundTripper{
		base: roundTripperFunc(func(req *http.Request) (*http.Response, error) {
			got = req
			return &http.Response{StatusCode: http.StatusOK, Body: io.NopCloser(nil), Header: make(http.Header)}, nil
		}),
		headers: map[string]string{"Authorization": "Bearer test"},
		extras: func(context.Context) map[string]string {
			return map[string]string{"X-BF-Request": "request-value"}
		},
	}
	req, err := http.NewRequestWithContext(context.Background(), http.MethodPost, "https://example.test/mcp", nil)
	require.NoError(t, err)
	_, err = roundTripper.RoundTrip(req)
	require.NoError(t, err)
	require.Equal(t, "Bearer test", got.Header.Get("Authorization"))
	require.Equal(t, "request-value", got.Header.Get("X-BF-Request"))
}

func TestMCPProtocolModeConfig(t *testing.T) {
	var config schemas.MCPClientConfig
	require.NoError(t, json.Unmarshal([]byte(`{"name":"catalog","connection_type":"http","protocol_mode":"auto"}`), &config))
	require.Equal(t, schemas.MCPProtocolModeAuto, config.MCPProtocolMode)
}

func TestModernHTTPProxyClientNegotiatesModernUpstream(t *testing.T) {
	upstream := modernmcp.NewServer(&modernmcp.Implementation{Name: "modern-upstream", Version: "1.0.0"}, nil)
	modernmcp.AddTool(upstream, &modernmcp.Tool{
		Name:        "echo",
		InputSchema: map[string]any{"type": "object", "properties": map[string]any{}},
	}, func(_ context.Context, _ *modernmcp.CallToolRequest, _ map[string]any) (*modernmcp.CallToolResult, any, error) {
		return &modernmcp.CallToolResult{Content: []modernmcp.Content{&modernmcp.TextContent{Text: "modern"}}}, nil, nil
	})
	handler := modernmcp.NewStreamableHTTPHandler(
		func(*http.Request) *modernmcp.Server { return upstream },
		&modernmcp.StreamableHTTPOptions{Stateless: true},
	)
	httpServer := httptest.NewServer(handler)
	defer httpServer.Close()

	config := &schemas.MCPClientConfig{
		Name:            "modern-upstream",
		ConnectionType:  schemas.MCPConnectionTypeHTTP,
		MCPProtocolMode: schemas.MCPProtocolModeModern,
	}
	compat, err := newModernHTTPProxyClient(context.Background(), httpServer.URL, nil, nil, config)
	require.NoError(t, err)
	require.NoError(t, compat.Start(context.Background()))
	defer compat.Close()
	_, err = compat.Initialize(context.Background(), legacyMCP.InitializeRequest{
		Params: legacyMCP.InitializeParams{
			ProtocolVersion: legacyMCP.LATEST_PROTOCOL_VERSION,
			ClientInfo:      legacyMCP.Implementation{Name: "facade", Version: "1.0.0"},
		},
	})
	require.NoError(t, err)

	tools, err := compat.ListTools(context.Background(), legacyMCP.ListToolsRequest{})
	require.NoError(t, err)
	require.Len(t, tools.Tools, 1)
	require.Equal(t, "echo", tools.Tools[0].Name)

	result, err := compat.CallTool(context.Background(), legacyMCP.CallToolRequest{Params: legacyMCP.CallToolParams{Name: "echo", Arguments: map[string]any{}}})
	require.NoError(t, err)
	require.Equal(t, "modern", result.Content[0].(legacyMCP.TextContent).Text)
}

func TestModernHTTPProxyClientFallsBackToLegacyUpstream(t *testing.T) {
	upstream := legacyServer.NewMCPServer("legacy-upstream", "1.0.0", legacyServer.WithToolCapabilities(true))
	upstream.AddTool(legacyMCP.NewTool("echo"), func(_ context.Context, _ legacyMCP.CallToolRequest) (*legacyMCP.CallToolResult, error) {
		return legacyMCP.NewToolResultText("legacy"), nil
	})
	httpServer := httptest.NewServer(legacyServer.NewStreamableHTTPServer(upstream, legacyServer.WithStateLess(true)))
	defer httpServer.Close()

	config := &schemas.MCPClientConfig{
		Name:            "legacy-upstream",
		ConnectionType:  schemas.MCPConnectionTypeHTTP,
		MCPProtocolMode: schemas.MCPProtocolModeAuto,
	}
	compat, err := newModernHTTPProxyClient(context.Background(), httpServer.URL, nil, nil, config)
	require.NoError(t, err)
	require.NoError(t, compat.Start(context.Background()))
	defer compat.Close()
	_, err = compat.Initialize(context.Background(), legacyMCP.InitializeRequest{
		Params: legacyMCP.InitializeParams{
			ProtocolVersion: legacyMCP.LATEST_PROTOCOL_VERSION,
			ClientInfo:      legacyMCP.Implementation{Name: "facade", Version: "1.0.0"},
		},
	})
	require.NoError(t, err)

	result, err := compat.CallTool(context.Background(), legacyMCP.CallToolRequest{Params: legacyMCP.CallToolParams{Name: "echo", Arguments: map[string]any{}}})
	require.NoError(t, err)
	require.Equal(t, "legacy", result.Content[0].(legacyMCP.TextContent).Text)
}

type roundTripperFunc func(*http.Request) (*http.Response, error)

func (f roundTripperFunc) RoundTrip(req *http.Request) (*http.Response, error) { return f(req) }
