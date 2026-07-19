package anthropic

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestConvertBifrostReasoning_DefaultsMissingSignature(t *testing.T) {
	text := "reasoning from a provider without signatures"
	typeName := schemas.ResponsesMessageTypeReasoning
	role := schemas.ResponsesInputMessageRoleAssistant
	msg := &schemas.ResponsesMessage{
		Type: &typeName,
		Role: &role,
		Content: &schemas.ResponsesMessageContent{ContentBlocks: []schemas.ResponsesMessageContentBlock{{
			Type: schemas.ResponsesOutputMessageContentTypeReasoning,
			Text: &text,
		}}},
	}

	blocks := convertBifrostReasoningToAnthropicThinking(msg)
	if len(blocks) != 1 {
		t.Fatalf("expected one thinking block, got %d", len(blocks))
	}
	if blocks[0].Signature == nil || *blocks[0].Signature != "" {
		t.Fatalf("expected empty non-nil signature, got %#v", blocks[0].Signature)
	}
}
