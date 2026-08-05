package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"

	legacyClient "github.com/mark3labs/mcp-go/client"
	legacyTransport "github.com/mark3labs/mcp-go/client/transport"
	legacyMCP "github.com/mark3labs/mcp-go/mcp"
	legacyServer "github.com/mark3labs/mcp-go/server"
	"github.com/maximhq/bifrost/core/mcp/protocol"
	"github.com/maximhq/bifrost/core/mcp/utils"
	"github.com/maximhq/bifrost/core/schemas"
	modernmcp "github.com/modelcontextprotocol/go-sdk/mcp"
)

// newModernHTTPProxyClient connects to an HTTP MCP server with the official
// SDK, which probes server/discover and falls back to legacy initialize when
// the peer does not implement the modern stateless protocol. The returned
// mcp-go client is an in-process compatibility facade so the rest of Bifrost
// can retain its existing client/state abstractions while the upstream wire
// leg negotiates independently.
func newModernHTTPProxyClient(
	ctx context.Context,
	url string,
	headers map[string]string,
	httpClient *http.Client,
	config *schemas.MCPClientConfig,
) (*legacyClient.Client, error) {
	if httpClient == nil {
		httpClient = &http.Client{}
	} else {
		clone := *httpClient
		httpClient = &clone
	}
	baseTransport := httpClient.Transport
	if baseTransport == nil {
		baseTransport = http.DefaultTransport
	}
	httpClient.Transport = &mcpHeaderRoundTripper{
		base:    baseTransport,
		headers: cloneHeaderMap(headers),
		extras: func(reqCtx context.Context) map[string]string {
			if config == nil {
				return nil
			}
			return utils.FlattenHeaders(utils.ExtractFilteredExtras(reqCtx, config))
		},
	}

	client := modernmcp.NewClient(
		&modernmcp.Implementation{Name: BifrostMCPClientName, Version: BifrostMCPVersion},
		nil,
	)
	transport := &modernmcp.StreamableClientTransport{
		Endpoint:             url,
		HTTPClient:           httpClient,
		DisableStandaloneSSE: true,
		MaxRetries:           2,
	}
	session, err := client.Connect(ctx, transport, nil)
	if err != nil {
		return nil, fmt.Errorf("MCP upstream negotiation failed: %w", err)
	}
	if config != nil && config.MCPProtocolMode == schemas.MCPProtocolModeModern {
		result := session.InitializeResult()
		if result == nil || result.ProtocolVersion != protocol.Version2026_07_28 {
			_ = session.Close()
			return nil, fmt.Errorf("MCP upstream negotiated %q, modern mode requires %q", protocolVersion(result), protocol.Version2026_07_28)
		}
	}

	tools, err := session.ListTools(ctx, nil)
	if err != nil {
		_ = session.Close()
		return nil, fmt.Errorf("MCP upstream tools/list failed: %w", err)
	}

	proxyServer := legacyServer.NewMCPServer(
		"FrankenGate upstream compatibility proxy",
		BifrostMCPVersion,
		legacyServer.WithToolCapabilities(true),
	)
	for _, tool := range tools.Tools {
		if tool == nil || tool.Name == "" {
			continue
		}
		legacyTool, err := modernToolToLegacy(tool)
		if err != nil {
			_ = session.Close()
			return nil, err
		}
		toolName := tool.Name
		proxyServer.AddTool(legacyTool, func(toolCtx context.Context, request legacyMCP.CallToolRequest) (*legacyMCP.CallToolResult, error) {
			result, callErr := session.CallTool(toolCtx, &modernmcp.CallToolParams{
				Name:      toolName,
				Arguments: request.GetArguments(),
			})
			if callErr != nil {
				return legacyMCP.NewToolResultError(callErr.Error()), nil
			}
			return modernResultToLegacy(result), nil
		})
	}

	inProcess := legacyTransport.NewInProcessTransport(proxyServer)
	compatTransport := &modernProxyTransport{
		InProcessTransport: inProcess,
		closeUpstream:      session.Close,
	}
	return legacyClient.NewClient(compatTransport), nil
}

func protocolVersion(result *modernmcp.InitializeResult) string {
	if result == nil {
		return ""
	}
	return result.ProtocolVersion
}

type mcpHeaderRoundTripper struct {
	base    http.RoundTripper
	headers map[string]string
	extras  func(context.Context) map[string]string
}

func (t *mcpHeaderRoundTripper) RoundTrip(req *http.Request) (*http.Response, error) {
	clone := req.Clone(req.Context())
	for key, value := range t.headers {
		clone.Header.Set(key, value)
	}
	if t.extras != nil {
		for key, value := range t.extras(req.Context()) {
			clone.Header.Set(key, value)
		}
	}
	return t.base.RoundTrip(clone)
}

type modernProxyTransport struct {
	*legacyTransport.InProcessTransport
	closeUpstream func() error
	closeOnce     sync.Once
	closeErr      error
}

func (t *modernProxyTransport) Close() error {
	t.closeOnce.Do(func() {
		if t.InProcessTransport != nil {
			t.closeErr = t.InProcessTransport.Close()
		}
		if t.closeUpstream != nil {
			if err := t.closeUpstream(); t.closeErr == nil {
				t.closeErr = err
			}
		}
	})
	return t.closeErr
}

func cloneHeaderMap(headers map[string]string) map[string]string {
	if len(headers) == 0 {
		return nil
	}
	clone := make(map[string]string, len(headers))
	for key, value := range headers {
		clone[key] = value
	}
	return clone
}

func modernToolToLegacy(tool *modernmcp.Tool) (legacyMCP.Tool, error) {
	rawSchema, err := json.Marshal(tool.InputSchema)
	if err != nil {
		return legacyMCP.Tool{}, fmt.Errorf("tool %q has invalid input schema: %w", tool.Name, err)
	}
	var schema map[string]any
	if err := json.Unmarshal(rawSchema, &schema); err != nil {
		return legacyMCP.Tool{}, fmt.Errorf("tool %q has invalid input schema: %w", tool.Name, err)
	}
	if schema["type"] != "object" {
		return legacyMCP.Tool{}, fmt.Errorf("tool %q input schema must have type object", tool.Name)
	}

	legacyTool := legacyMCP.NewToolWithRawSchema(tool.Name, tool.Description, rawSchema)
	legacyTool.Title = tool.Title
	legacyTool.Annotations = modernAnnotationsToLegacy(tool.Annotations)
	if legacyTool.Title == "" {
		legacyTool.Title = legacyTool.Annotations.Title
	}
	return legacyTool, nil
}

func modernAnnotationsToLegacy(annotation *modernmcp.ToolAnnotations) legacyMCP.ToolAnnotation {
	if annotation == nil {
		return legacyMCP.ToolAnnotation{}
	}
	return legacyMCP.ToolAnnotation{
		Title:           annotation.Title,
		ReadOnlyHint:    boolPtr(annotation.ReadOnlyHint),
		DestructiveHint: annotation.DestructiveHint,
		IdempotentHint:  boolPtr(annotation.IdempotentHint),
		OpenWorldHint:   annotation.OpenWorldHint,
	}
}

func boolPtr(value bool) *bool {
	return &value
}

func modernResultToLegacy(result *modernmcp.CallToolResult) *legacyMCP.CallToolResult {
	if result == nil {
		return legacyMCP.NewToolResultText("")
	}
	texts := make([]string, 0, len(result.Content))
	for _, content := range result.Content {
		switch item := content.(type) {
		case *modernmcp.TextContent:
			texts = append(texts, item.Text)
		default:
			if raw, err := json.Marshal(item); err == nil {
				texts = append(texts, string(raw))
			}
		}
	}
	if len(texts) == 0 && result.StructuredContent != nil {
		if raw, err := json.Marshal(result.StructuredContent); err == nil {
			texts = append(texts, string(raw))
		}
	}
	var text string
	for i, item := range texts {
		if i > 0 {
			text += "\n"
		}
		text += item
	}
	if result.IsError {
		return legacyMCP.NewToolResultError(text)
	}
	return legacyMCP.NewToolResultText(text)
}
