package bedrock

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/maximhq/bifrost/core/providers/anthropic"
	"github.com/maximhq/bifrost/core/schemas"
)

func TestInjectConverseAnthropicBetaTunnelsContext1M(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyExtraHeaders, map[string][]string{
		anthropic.AnthropicBetaHeader: {anthropic.AnthropicContext1MBetaHeader},
	})
	provider := &BedrockProvider{}
	body := []byte(`{"messages":[],"additionalModelRequestFields":{"anthropic_beta":["computer-use-2025-01-24"]}}`)
	got := provider.injectConverseAnthropicBeta(ctx, body, "converse", "anthropic.claude-sonnet-4-6")
	var decoded struct {
		Additional map[string][]string `json:"additionalModelRequestFields"`
	}
	if err := json.Unmarshal(got, &decoded); err != nil {
		t.Fatal(err)
	}
	values := decoded.Additional["anthropic_beta"]
	seen := make(map[string]bool, len(values))
	for _, value := range values {
		seen[value] = true
	}
	if len(values) != 2 || !seen[anthropic.AnthropicContext1MBetaHeader] || !seen["computer-use-2025-01-24"] {
		t.Fatalf("unexpected tunneled beta values: %#v", values)
	}
}

func TestInjectConverseAnthropicBetaDoesNotTouchInvokeOrNonAnthropic(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyExtraHeaders, map[string][]string{
		anthropic.AnthropicBetaHeader: {anthropic.AnthropicContext1MBetaHeader},
	})
	provider := &BedrockProvider{}
	body := []byte(`{"messages":[]}`)
	for _, tc := range []struct {
		path, model string
	}{
		{path: "invoke", model: "anthropic.claude-sonnet-4-6"},
		{path: "converse", model: "meta.llama3-3-70b-instruct-v1:0"},
	} {
		got := provider.injectConverseAnthropicBeta(ctx, body, tc.path, tc.model)
		if string(got) != string(body) {
			t.Errorf("request changed for %s/%s: %s", tc.path, tc.model, got)
		}
	}
}

func TestInjectInvokeAnthropicBetaTunnelsContext1MAndPreservesExisting(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyExtraHeaders, map[string][]string{
		anthropic.AnthropicBetaHeader: {anthropic.AnthropicContext1MBetaHeader},
	})
	provider := &BedrockProvider{}
	body := []byte(`{"anthropic_version":"bedrock-2023-05-31","anthropic_beta":["computer-use-2025-01-24"]}`)
	for _, path := range []string{"invoke", "invoke-with-response-stream"} {
		got := provider.injectInvokeAnthropicBeta(ctx, body, path, "anthropic.claude-sonnet-4-6")
		var decoded struct{ Beta []string `json:"anthropic_beta"` }
		if err := json.Unmarshal(got, &decoded); err != nil {
			t.Fatal(err)
		}
		if len(decoded.Beta) != 2 || decoded.Beta[0] != anthropic.AnthropicContext1MBetaHeader || decoded.Beta[1] != "computer-use-2025-01-24" {
			t.Fatalf("%s: unexpected beta values: %#v", path, decoded.Beta)
		}
	}
}

func TestInjectInvokeAnthropicBetaFailClosedForUnsupportedModel(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyExtraHeaders, map[string][]string{
		anthropic.AnthropicBetaHeader: {anthropic.AnthropicContext1MBetaHeader},
	})
	provider := &BedrockProvider{}
	body := []byte(`{"messages":[]}`)
	got := provider.injectInvokeAnthropicBeta(ctx, body, "invoke", "anthropic.claude-sonnet-9-9")
	if string(got) != string(body) {
		t.Fatalf("unsupported model received beta: %s", got)
	}
}
