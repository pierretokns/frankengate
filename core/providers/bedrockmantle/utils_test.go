package bedrockmantle

import (
	"testing"

	"github.com/maximhq/bifrost/core/providers/anthropic"
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
