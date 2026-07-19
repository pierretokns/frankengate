package mcp_test

import (
	"context"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/mcp"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/tracing"
)

func TestRunWithPluginPipelineCreatesMCPToolSpan(t *testing.T) {
	tracer := tracing.NewTracer(tracing.NewTraceStore(time.Minute, nil), nil, nil)
	traceID := tracer.CreateTrace("", "mcp-request")
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyTracer, tracer)
	ctx.SetValue(schemas.BifrostContextKeyTraceID, traceID)
	toolName := "warehouse.query"
	toolCallID := "call-1"

	manager := &mcp.MCPManager{}
	_, err := manager.RunWithPluginPipeline(ctx, &schemas.BifrostMCPRequest{
		RequestType: schemas.MCPRequestTypeExecuteTool,
		ClientName:  "warehouse",
		ChatAssistantMessageToolCall: &schemas.ChatAssistantMessageToolCall{
			ID:       &toolCallID,
			Function: schemas.ChatAssistantMessageToolCallFunction{Name: &toolName, Arguments: `{"sql":"select 1"}`},
		},
	}, func(*schemas.BifrostMCPRequest) (*schemas.BifrostMCPResponse, error) {
		return &schemas.BifrostMCPResponse{}, nil
	})
	if err != nil {
		t.Fatalf("RunWithPluginPipeline returned error: %v", err)
	}
	trace := tracer.EndTrace(traceID)
	if trace == nil {
		t.Fatal("expected completed trace")
	}
	for _, span := range trace.Spans {
		if span != nil && span.Kind == schemas.SpanKindMCPTool {
			if span.Name != "mcp.execute_tool.warehouse" {
				t.Fatalf("unexpected tool span name %q", span.Name)
			}
			if span.Attributes[schemas.AttrToolName] != toolName || span.Attributes[schemas.AttrToolCallID] != toolCallID {
				t.Fatalf("tool attributes missing: %#v", span.Attributes)
			}
			if span.Attributes[schemas.AttrToolCallArguments] != `{"sql":"select 1"}` {
				t.Fatalf("tool arguments not preserved: %#v", span.Attributes[schemas.AttrToolCallArguments])
			}
			return
		}
	}
	t.Fatal("expected MCP tool span")
}
