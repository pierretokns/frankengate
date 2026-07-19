package governance

import (
	"context"
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
}
