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

	manager := &mcp.MCPManager{}
	_, err := manager.RunWithPluginPipeline(ctx, &schemas.BifrostMCPRequest{
		RequestType: schemas.MCPRequestTypeExecuteTool,
		ClientName:  "warehouse",
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
			return
		}
	}
	t.Fatal("expected MCP tool span")
}
