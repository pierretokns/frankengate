package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"github.com/bytedance/sonic"
	legacyMCP "github.com/mark3labs/mcp-go/mcp"
	legacyServer "github.com/mark3labs/mcp-go/server"
	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/schemas"
	modernmcp "github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/valyala/fasthttp"
	"github.com/valyala/fasthttp/fasthttpadaptor"
)

const mcpProtocolVersionHeader = "Mcp-Protocol-Version"

// isModernMCPRequest recognizes only the modern wire entry points. Legacy
// initialize traffic continues through mcp-go unchanged. A discovery probe is
// modern even before the client has a negotiated protocol-version header.
func isModernMCPRequest(ctx *fasthttp.RequestCtx) bool {
	if string(ctx.Request.Header.Peek(mcpProtocolVersionHeader)) == "2026-07-28" {
		return true
	}

	var envelope struct {
		Method string `json:"method"`
	}
	if err := sonic.Unmarshal(ctx.PostBody(), &envelope); err != nil {
		return false
	}
	return envelope.Method == "server/discover"
}

// handleModernMCPServer serves one stateless modern MCP request. The official
// SDK owns the 2026-07-28 wire behavior; the existing mcp-go server remains
// the legacy implementation. The server is created per request so no MCP
// session state is required for modern traffic, while Bifrost application
// state remains available through bifrostCtx.
func (h *MCPServerHandler) handleModernMCPServer(
	ctx *fasthttp.RequestCtx,
	bifrostCtx *schemas.BifrostContext,
	legacyServer *legacyServer.MCPServer,
) error {
	requestContext := contextWithMCPFilterHeaders(bifrostCtx, ctx)
	modernServer, err := h.buildModernMCPServer(requestContext, legacyServer)
	if err != nil {
		return err
	}

	modernHandler := modernmcp.NewStreamableHTTPHandler(
		func(*http.Request) *modernmcp.Server { return modernServer },
		&modernmcp.StreamableHTTPOptions{
			Stateless:                    true,
			PropagateRequestCancellation: true,
		},
	)

	// fasthttpadaptor preserves Flush() and therefore keeps modern streaming
	// responses streaming instead of materializing them in the gateway.
	fasthttpHandler := fasthttpadaptor.NewFastHTTPHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		modernHandler.ServeHTTP(w, r.WithContext(requestContext))
	}))
	fasthttpHandler(ctx)
	return nil
}

func contextWithMCPFilterHeaders(ctx context.Context, request *fasthttp.RequestCtx) context.Context {
	if values := splitMCPHeader(request, "x-bf-mcp-include-clients"); len(values) > 0 {
		ctx = context.WithValue(ctx, schemas.MCPContextKeyIncludeClients, values)
	}
	if values := splitMCPHeader(request, "x-bf-mcp-include-tools"); len(values) > 0 {
		ctx = context.WithValue(ctx, schemas.MCPContextKeyIncludeTools, values)
	}
	return ctx
}

func splitMCPHeader(request *fasthttp.RequestCtx, name string) []string {
	value := string(request.Request.Header.Peek(name))
	if value == "" {
		return nil
	}
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		if part = strings.TrimSpace(part); part != "" {
			result = append(result, part)
		}
	}
	return result
}

func (h *MCPServerHandler) buildModernMCPServer(ctx context.Context, legacy *legacyServer.MCPServer) (*modernmcp.Server, error) {
	modern := modernmcp.NewServer(
		&modernmcp.Implementation{Name: "FrankenGate", Version: version},
		nil,
	)

	legacyTools := legacy.ListTools()
	tools := make([]legacyMCP.Tool, 0, len(legacyTools))
	for _, registered := range legacyTools {
		if registered != nil {
			tools = append(tools, registered.Tool)
		}
	}
	tools = h.makeIncludeClientsFilter()(ctx, tools)

	for _, tool := range tools {
		if tool.Name == "" {
			continue
		}
		inputSchema, err := modernToolInputSchema(tool.InputSchema)
		if err != nil {
			return nil, fmt.Errorf("tool %q has invalid input schema: %w", tool.Name, err)
		}
		toolName := tool.Name
		modernTool := &modernmcp.Tool{
			Name:        toolName,
			Description: tool.Description,
			InputSchema: inputSchema,
			Annotations: modernToolAnnotations(tool.Annotations),
		}
		if len(tool.RawOutputSchema) > 0 {
			var outputSchema any
			if err := json.Unmarshal(tool.RawOutputSchema, &outputSchema); err != nil {
				return nil, fmt.Errorf("tool %q has invalid output schema: %w", toolName, err)
			}
			modernTool.OutputSchema = outputSchema
		}
		modern.AddTool(modernTool, func(toolCtx context.Context, request *modernmcp.CallToolRequest) (*modernmcp.CallToolResult, error) {
			toolCallType := "function"
			toolCallID := fmt.Sprintf("mcp-%s", toolName)
			argsJSON, marshalErr := sonic.Marshal(request.Params.Arguments)
			if marshalErr != nil {
				return modernToolError(fmt.Sprintf("Failed to marshal tool arguments: %v", marshalErr)), nil
			}
			toolCall := schemas.ChatAssistantMessageToolCall{
				ID:   &toolCallID,
				Type: &toolCallType,
				Function: schemas.ChatAssistantMessageToolCallFunction{
					Name:      &toolName,
					Arguments: string(argsJSON),
				},
			}
			toolMessage, bifrostErr := h.toolManager.ExecuteChatMCPTool(toolCtx, &toolCall)
			if bifrostErr != nil {
				return modernToolError(fmt.Sprintf("Tool execution failed: %v", bifrost.GetErrorMessage(bifrostErr))), nil
			}
			return modernToolTextResult(mcpToolMessageText(toolMessage)), nil
		})
	}
	return modern, nil
}

func modernToolInputSchema(input legacyMCP.ToolInputSchema) (any, error) {
	raw, err := json.Marshal(input)
	if err != nil {
		return nil, err
	}
	var schema map[string]any
	if err := json.Unmarshal(raw, &schema); err != nil {
		return nil, err
	}
	if schema["type"] == nil || schema["type"] == "" {
		schema["type"] = "object"
	} else if schemaType, ok := schema["type"].(string); !ok || schemaType != "object" {
		return nil, fmt.Errorf("input schema type must be object, got %v", schema["type"])
	}
	if _, ok := schema["properties"]; !ok {
		schema["properties"] = map[string]any{}
	}
	return schema, nil
}

func modernToolAnnotations(annotation legacyMCP.ToolAnnotation) *modernmcp.ToolAnnotations {
	return &modernmcp.ToolAnnotations{
		Title:           annotation.Title,
		ReadOnlyHint:    boolValue(annotation.ReadOnlyHint),
		DestructiveHint: annotation.DestructiveHint,
		IdempotentHint:  boolValue(annotation.IdempotentHint),
		OpenWorldHint:   annotation.OpenWorldHint,
	}
}

func boolValue(value *bool) bool {
	return value != nil && *value
}

func modernToolTextResult(text string) *modernmcp.CallToolResult {
	return &modernmcp.CallToolResult{Content: []modernmcp.Content{&modernmcp.TextContent{Text: text}}}
}

func modernToolError(text string) *modernmcp.CallToolResult {
	return &modernmcp.CallToolResult{
		Content: []modernmcp.Content{&modernmcp.TextContent{Text: text}},
		IsError: true,
	}
}

func mcpToolMessageText(toolMessage *schemas.ChatMessage) string {
	if toolMessage == nil || toolMessage.Content == nil {
		return ""
	}
	if toolMessage.Content.ContentStr != nil {
		return *toolMessage.Content.ContentStr
	}
	var result string
	for _, block := range toolMessage.Content.ContentBlocks {
		if block.Type == schemas.ChatContentBlockTypeText && block.Text != nil {
			result += *block.Text
		}
	}
	return result
}
