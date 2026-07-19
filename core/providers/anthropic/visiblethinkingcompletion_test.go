package anthropic

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestToBifrostResponsesStream_VisibleThinkingCarriesCompletedText(t *testing.T) {
	thinkingType := AnthropicContentBlockTypeThinking
	stop := AnthropicStopReasonEndTurn
	events := []*AnthropicStreamEvent{{
		Type:    AnthropicStreamEventTypeMessageStart,
		Message: &AnthropicMessageResponse{ID: "msg_visible", Model: "claude-sonnet-4-5"},
	}, {
		Type: AnthropicStreamEventTypeContentBlockStart, Index: schemas.Ptr(0),
		ContentBlock: &AnthropicContentBlock{Type: thinkingType},
	}, {
		Type: AnthropicStreamEventTypeContentBlockDelta, Index: schemas.Ptr(0),
		Delta: &AnthropicStreamDelta{Type: AnthropicStreamDeltaTypeThinking, Thinking: schemas.Ptr("first ")},
	}, {
		Type: AnthropicStreamEventTypeContentBlockDelta, Index: schemas.Ptr(0),
		Delta: &AnthropicStreamDelta{Type: AnthropicStreamDeltaTypeThinking, Thinking: schemas.Ptr("second")},
	}, {
		Type: AnthropicStreamEventTypeContentBlockDelta, Index: schemas.Ptr(0),
		Delta: &AnthropicStreamDelta{Type: AnthropicStreamDeltaTypeSignature, Signature: schemas.Ptr("sig")},
	}, {
		Type: AnthropicStreamEventTypeContentBlockStop, Index: schemas.Ptr(0),
	}, {
		Type:  AnthropicStreamEventTypeMessageDelta,
		Delta: &AnthropicStreamDelta{StopReason: &stop},
	}, {Type: AnthropicStreamEventTypeMessageStop}}

	responses := driveResponsesStream(t, events)
	var done *schemas.BifrostResponsesStreamResponse
	var part *schemas.BifrostResponsesStreamResponse
	for _, response := range responses {
		switch response.Type {
		case schemas.ResponsesStreamResponseTypeReasoningSummaryTextDone:
			done = response
		case schemas.ResponsesStreamResponseTypeContentPartDone:
			part = response
		}
	}
	if done == nil || done.Text == nil || *done.Text != "first second" {
		t.Fatalf("reasoning summary completion = %#v, want accumulated text", done)
	}
	if part == nil || part.Part == nil || part.Part.Text == nil || *part.Part.Text != "first second" {
		t.Fatalf("reasoning content part completion = %#v, want accumulated text", part)
	}
	if part.Part.Signature == nil || *part.Part.Signature != "sig" {
		t.Fatalf("reasoning content part signature = %v, want sig", part.Part.Signature)
	}
}
