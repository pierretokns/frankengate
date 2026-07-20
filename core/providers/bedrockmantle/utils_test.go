package bedrockmantle

import (
	"context"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/providers/anthropic"
	"github.com/maximhq/bifrost/core/schemas"
)

func TestAddAnthropicHeadersPreservesContext1MBeta(t *testing.T) {
	base := map[string]string{
		"anthropic-beta": anthropic.AnthropicContext1MBetaHeader,
		"x-custom":       "keep",
	}
	got := addAnthropicHeaders(base)
	if got["anthropic-beta"] != anthropic.AnthropicContext1MBetaHeader {
		t.Fatalf("context-1m beta header was not preserved: %#v", got)
	}
	if got["anthropic-version"] != mantleAnthropicVersion {
		t.Fatalf("missing Mantle Anthropic version header: %#v", got)
	}
	if _, ok := base["anthropic-version"]; ok {
		t.Fatal("addAnthropicHeaders mutated shared input")
	}
}

func TestUsesAnthropicSurfaceDoesNotMisclassifyCodexGPTAlias(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	for _, model := range []string{"Claude-GPT-soul", "Claude-GPT-luna", "Claude-GPT-terra", "Claude-GPT-sol"} {
		if usesAnthropicSurface(ctx, model) {
			t.Fatalf("Codex GPT alias %q incorrectly selected native Anthropic surface", model)
		}
	}
	if !usesAnthropicSurface(ctx, "claude-sonnet-4-6") {
		t.Fatal("ordinary Claude model should select native Anthropic surface")
	}
}
