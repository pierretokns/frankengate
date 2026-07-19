package governance

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/identity"
	"github.com/maximhq/bifrost/core/schemas"
)

func TestPreLLMHookEnforcesIdentityEntitlementsBeforeProviderEffects(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	if err := schemas.SetIdentityEntitlements(ctx, identity.Entitlements{
		Models: []string{"claude-*"}, Providers: []string{"bedrock"}, ToolGroups: []string{"sql-*"},
	}); err != nil {
		t.Fatal(err)
	}
	plugin := &GovernancePlugin{}
	req := &schemas.BifrostRequest{RequestType: schemas.ChatCompletionRequest, ChatRequest: &schemas.BifrostChatRequest{
		Provider: schemas.OpenAI, Model: "gpt-4",
	}}
	_, shortCircuit, err := plugin.PreLLMHook(ctx, req)
	if err != nil {
		t.Fatal(err)
	}
	if shortCircuit == nil || shortCircuit.Error == nil || shortCircuit.Error.Type == nil || *shortCircuit.Error.Type != "identity_entitlement_denied" {
		t.Fatalf("short circuit = %#v, want identity entitlement denial", shortCircuit)
	}
	decision, ok := schemas.IdentityEntitlementDecisionFromContext(ctx)
	if !ok || decision.Allowed || decision.Capability != "provider_model" || decision.Reason != "provider_not_granted" {
		t.Fatalf("decision=%+v present=%v, want sanitized provider denial", decision, ok)
	}

	// A denied decision must not expose group claims or grant lists.
	if got := shortCircuit.Error.Error.Message; got == "" || strings.Contains(got, "bedrock") {
		t.Fatalf("denial leaked sensitive entitlement detail: %q", got)
	}
}

func TestPreLLMHookRecordsGrantedEntitlementDecision(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	recordIdentityEntitlementDecision(ctx, true, "provider_model", "granted")
	decision, ok := schemas.IdentityEntitlementDecisionFromContext(ctx)
	if !ok || !decision.Allowed || decision.Capability != "provider_model" || decision.Reason != "granted" {
		t.Fatalf("decision=%+v present=%v, want granted provider/model decision", decision, ok)
	}
}

func TestPreMCPHookEnforcesIdentityEntitlementsBeforeCodemodeOrWireEffects(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	if err := schemas.SetIdentityEntitlements(ctx, identity.Entitlements{
		ToolGroups: []string{"sql-*"},
	}); err != nil {
		t.Fatal(err)
	}
	plugin := &GovernancePlugin{}
	tool := "shell.exec"
	req := &schemas.BifrostMCPRequest{
		RequestType:          schemas.MCPRequestTypeExecuteTool,
		ClientName:           "internal-tools",
		ResponsesToolMessage: &schemas.ResponsesToolMessage{Name: &tool},
	}
	_, shortCircuit, err := plugin.PreMCPHook(ctx, req)
	if err != nil {
		t.Fatal(err)
	}
	if shortCircuit == nil || shortCircuit.Error == nil || shortCircuit.Error.Type == nil || *shortCircuit.Error.Type != "identity_entitlement_denied" {
		t.Fatalf("short circuit = %#v, want identity entitlement denial", shortCircuit)
	}
	if rejected, _ := ctx.Value(governanceRejectedContextKey).(bool); !rejected {
		t.Fatal("expected governance rejection marker")
	}
	decision, ok := schemas.IdentityEntitlementDecisionFromContext(ctx)
	if !ok || decision.Allowed || decision.Capability != "mcp_tool" || decision.Reason != "tool_not_granted" {
		t.Fatalf("decision=%+v present=%v, want sanitized MCP denial", decision, ok)
	}
}
