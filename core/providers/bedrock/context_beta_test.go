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
