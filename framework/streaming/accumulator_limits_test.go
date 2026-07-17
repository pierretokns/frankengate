package streaming

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"testing"
	"time"

	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/schemas"
)

func testSHA256Hex(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func TestNewAccumulatorUsesProductionRetentionDefaults(t *testing.T) {
	accumulator := NewAccumulator(nil, bifrost.NewDefaultLogger(schemas.LogLevelError))
	t.Cleanup(accumulator.Cleanup)

	limits := accumulator.options.Limits
	checkPositiveInt64 := map[string]int64{
		"ChatMaxRetainedBytes":           limits.ChatMaxRetainedBytes,
		"ResponsesMaxRetainedBytes":      limits.ResponsesMaxRetainedBytes,
		"AudioMaxRetainedBytes":          limits.AudioMaxRetainedBytes,
		"TranscriptionMaxRetainedBytes":  limits.TranscriptionMaxRetainedBytes,
		"ImageMaxRetainedBytes":          limits.ImageMaxRetainedBytes,
		"RawResponseMaxBytes":            limits.RawResponseMaxBytes,
		"PassthroughMaxRetainedBytes":    limits.PassthroughMaxRetainedBytes,
		"PassthroughMaxHeaderTotalBytes": limits.PassthroughMaxHeaderTotalBytes,
	}
	for name, value := range checkPositiveInt64 {
		if value <= 0 {
			t.Fatalf("%s default = %d, want conservative non-zero production limit", name, value)
		}
	}

	checkPositiveDuration := map[string]time.Duration{
		"ChatMaxDuration":          limits.ChatMaxDuration,
		"ResponsesMaxDuration":     limits.ResponsesMaxDuration,
		"AudioMaxDuration":         limits.AudioMaxDuration,
		"TranscriptionMaxDuration": limits.TranscriptionMaxDuration,
		"ImageMaxDuration":         limits.ImageMaxDuration,
		"RawResponseMaxDuration":   limits.RawResponseMaxDuration,
		"PassthroughMaxDuration":   limits.PassthroughMaxDuration,
	}
	for name, value := range checkPositiveDuration {
		if value <= 0 {
			t.Fatalf("%s default = %s, want conservative non-zero production limit", name, value)
		}
	}

	checkPositiveInt := map[string]int{
		"PassthroughMaxHeaderCount":      limits.PassthroughMaxHeaderCount,
		"PassthroughMaxHeaderNameBytes":  limits.PassthroughMaxHeaderNameBytes,
		"PassthroughMaxHeaderValueBytes": limits.PassthroughMaxHeaderValueBytes,
	}
	for name, value := range checkPositiveInt {
		if value <= 0 {
			t.Fatalf("%s default = %d, want conservative non-zero production limit", name, value)
		}
	}
}

func TestAccumulatorDropsRawResponseWhenCaptureDisabled(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{})
	t.Cleanup(accumulator.Cleanup)

	requestID := "raw-capture-disabled"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, false)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

	raw := `{"secret":"provider raw body"}`
	result := &schemas.BifrostResponse{
		ChatResponse: &schemas.BifrostChatResponse{
			ID:     "chatcmpl_raw_disabled",
			Object: "chat.completion.chunk",
			Choices: []schemas.BifrostResponseChoice{
				{
					ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
						Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr("hello")},
					},
					FinishReason: bifrost.Ptr("stop"),
				},
			},
			ExtraFields: schemas.BifrostResponseExtraFields{
				RequestType:            schemas.ChatCompletionStreamRequest,
				Provider:               schemas.OpenAI,
				OriginalModelRequested: "gpt-test",
				ChunkIndex:             0,
				RawResponse:            raw,
			},
		},
	}

	processed, err := accumulator.ProcessStreamingResponse(ctx, result, nil)
	if err != nil {
		t.Fatalf("ProcessStreamingResponse returned error: %v", err)
	}
	if processed == nil || processed.Data == nil {
		t.Fatal("expected final accumulated data")
	}
	if processed.Data.RawResponse != nil {
		t.Fatalf("disabled capture retained raw response: %q", *processed.Data.RawResponse)
	}
	if processed.Data.Capture == nil || processed.Data.Capture.RawResponse.Mode != StreamCaptureModeDrop {
		t.Fatalf("expected explicit raw-response drop metadata, got %#v", processed.Data.Capture)
	}

	stored, ok := accumulator.streamAccumulators.Load(requestID)
	if !ok {
		t.Fatal("expected accumulator to remain until explicit cleanup")
	}
	stream := stored.(*StreamAccumulator)
	stream.mu.Lock()
	defer stream.mu.Unlock()
	if len(stream.ChatStreamChunks) != 1 {
		t.Fatalf("expected one retained chat metadata chunk, got %d", len(stream.ChatStreamChunks))
	}
	if stream.ChatStreamChunks[0].RawResponse != nil {
		t.Fatalf("raw response was copied into retained chunk: %q", *stream.ChatStreamChunks[0].RawResponse)
	}
}

func TestRawResponseCaptureUsesExactBytesForCommonTypes(t *testing.T) {
	tests := []struct {
		name string
		raw  interface{}
		want []byte
	}{
		{name: "string", raw: "raw-string", want: []byte("raw-string")},
		{name: "bytes", raw: []byte("raw-bytes"), want: []byte("raw-bytes")},
		{name: "raw-message", raw: json.RawMessage(`{"a":1}`), want: []byte(`{"a":1}`)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
				Limits: AccumulatorLimits{RawResponseMaxBytes: 1024},
			})
			t.Cleanup(accumulator.Cleanup)

			requestID := "raw-exact-" + tt.name
			ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
			ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
			ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, true)
			ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

			processed, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
				ChatResponse: &schemas.BifrostChatResponse{
					ID:     "chatcmpl_raw_exact",
					Object: "chat.completion.chunk",
					Choices: []schemas.BifrostResponseChoice{
						{
							ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
								Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr("ok")},
							},
							FinishReason: bifrost.Ptr("stop"),
						},
					},
					ExtraFields: schemas.BifrostResponseExtraFields{
						RequestType:            schemas.ChatCompletionStreamRequest,
						Provider:               schemas.OpenAI,
						OriginalModelRequested: "gpt-test",
						ChunkIndex:             0,
						RawResponse:            tt.raw,
					},
				},
			}, nil)
			if err != nil {
				t.Fatalf("ProcessStreamingResponse returned error: %v", err)
			}
			if processed.Data == nil || processed.Data.RawResponse == nil {
				t.Fatal("expected retained raw response")
			}
			if got := *processed.Data.RawResponse; got != string(tt.want) {
				t.Fatalf("raw response = %q, want exact bytes %q", got, string(tt.want))
			}
			meta := processed.Data.Capture.RawResponse
			if meta.RetainedBytes != int64(len(tt.want)) {
				t.Fatalf("retained bytes = %d, want %d", meta.RetainedBytes, len(tt.want))
			}
			if meta.DigestSHA256 != testSHA256Hex(tt.want) {
				t.Fatalf("digest = %s, want exact-byte digest %s", meta.DigestSHA256, testSHA256Hex(tt.want))
			}
		})
	}
}

func TestOversizedRawResponseUsesExactBytesForDigestAndAccounting(t *testing.T) {
	tests := []struct {
		name string
		raw  interface{}
		want []byte
	}{
		{name: "bytes", raw: []byte("0123456789"), want: []byte("0123456789")},
		{name: "raw-message", raw: json.RawMessage(`{"too":"large"}`), want: []byte(`{"too":"large"}`)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
				Limits: AccumulatorLimits{RawResponseMaxBytes: 4},
			})
			t.Cleanup(accumulator.Cleanup)

			requestID := "raw-oversized-" + tt.name
			ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
			ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
			ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, true)
			ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

			processed, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
				ChatResponse: &schemas.BifrostChatResponse{
					ID:     "chatcmpl_raw_oversized",
					Object: "chat.completion.chunk",
					Choices: []schemas.BifrostResponseChoice{
						{
							ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
								Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr("ok")},
							},
							FinishReason: bifrost.Ptr("stop"),
						},
					},
					ExtraFields: schemas.BifrostResponseExtraFields{
						RequestType:            schemas.ChatCompletionStreamRequest,
						Provider:               schemas.OpenAI,
						OriginalModelRequested: "gpt-test",
						ChunkIndex:             0,
						RawResponse:            tt.raw,
					},
				},
			}, nil)
			if err != nil {
				t.Fatalf("ProcessStreamingResponse returned error: %v", err)
			}
			if processed.Data.RawResponse != nil {
				t.Fatalf("oversized raw response was retained: %q", *processed.Data.RawResponse)
			}
			meta := processed.Data.Capture.RawResponse
			if meta.Mode != StreamCaptureModeMetadataOnly {
				t.Fatalf("raw capture mode = %q, want metadata_only", meta.Mode)
			}
			if meta.DroppedBytes != int64(len(tt.want)) {
				t.Fatalf("dropped bytes = %d, want exact length %d", meta.DroppedBytes, len(tt.want))
			}
			if meta.DigestSHA256 != testSHA256Hex(tt.want) {
				t.Fatalf("digest = %s, want exact-byte digest %s", meta.DigestSHA256, testSHA256Hex(tt.want))
			}
		})
	}
}

func TestChatStreamDowngradesToMetadataOnlyWhenOutputLimitExceeded(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{
			ChatMaxRetainedBytes: 64,
		},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "chat-output-byte-limit"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, false)

	var final *ProcessedStreamResponse
	for i := 0; i < 100; i++ {
		isFinal := i == 99
		ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, isFinal)

		response := &schemas.BifrostResponse{
			ChatResponse: &schemas.BifrostChatResponse{
				ID:     "chatcmpl_limit",
				Object: "chat.completion.chunk",
				Choices: []schemas.BifrostResponseChoice{
					{
						ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
							Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr(strings.Repeat("x", 20))},
						},
					},
				},
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.ChatCompletionStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "gpt-test",
					ChunkIndex:             i,
				},
			},
		}
		if isFinal {
			response.ChatResponse.Choices[0].FinishReason = bifrost.Ptr("stop")
			response.ChatResponse.Usage = &schemas.BifrostLLMUsage{
				PromptTokens:     5,
				CompletionTokens: 10,
				TotalTokens:      15,
			}
		}

		processed, err := accumulator.ProcessStreamingResponse(ctx, response, nil)
		if err != nil {
			t.Fatalf("chunk %d failed: %v", i, err)
		}
		if isFinal {
			final = processed
		}
	}

	if final == nil || final.Data == nil {
		t.Fatal("expected final accumulated data")
	}
	if final.Data.Capture == nil || final.Data.Capture.Output.Mode != StreamCaptureModeMetadataOnly {
		t.Fatalf("expected metadata-only output capture, got %#v", final.Data.Capture)
	}
	if final.Data.Capture.Output.DigestSHA256 == "" {
		t.Fatal("expected bounded rolling digest metadata")
	}
	if final.Data.TokenUsage == nil || final.Data.TokenUsage.TotalTokens != 15 {
		t.Fatalf("expected final token usage to survive downgrade, got %#v", final.Data.TokenUsage)
	}
	if final.Data.FinishReason == nil || *final.Data.FinishReason != "stop" {
		t.Fatalf("expected final finish reason to survive downgrade, got %#v", final.Data.FinishReason)
	}

	stored, ok := accumulator.streamAccumulators.Load(requestID)
	if !ok {
		t.Fatal("expected accumulator to remain until explicit cleanup")
	}
	stream := stored.(*StreamAccumulator)
	stream.mu.Lock()
	defer stream.mu.Unlock()
	if len(stream.ChatStreamChunks) > 4 {
		t.Fatalf("expected bounded retained chunks, got %d", len(stream.ChatStreamChunks))
	}
	if len(stream.ChatChunksSeen) > metadataDedupeMaxEntries {
		t.Fatalf("expected bounded de-dup map, got %d", len(stream.ChatChunksSeen))
	}
}

func TestMetadataOnlyModeDedupesDuplicateDeliveriesForOutputAndRaw(t *testing.T) {
	tests := []struct {
		name      string
		requestID string
		result    *schemas.BifrostResponse
	}{
		{
			name:      "chat",
			requestID: "metadata-dedupe-chat",
			result: &schemas.BifrostResponse{ChatResponse: &schemas.BifrostChatResponse{
				ID:     "chatcmpl_metadata_dedupe",
				Object: "chat.completion.chunk",
				Choices: []schemas.BifrostResponseChoice{
					{ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr(strings.Repeat("c", 64))}}},
				},
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.ChatCompletionStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "gpt-test",
					ChunkIndex:             7,
					RawResponse:            []byte("same-chat-raw"),
				},
			}},
		},
		{
			name:      "responses",
			requestID: "metadata-dedupe-responses",
			result: &schemas.BifrostResponse{ResponsesStreamResponse: &schemas.BifrostResponsesStreamResponse{
				Type:  schemas.ResponsesStreamResponseTypeOutputTextDelta,
				Delta: bifrost.Ptr(strings.Repeat("r", 64)),
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.ResponsesStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "gpt-test",
					ChunkIndex:             7,
					RawResponse:            []byte("same-responses-raw"),
				},
			}},
		},
		{
			name:      "audio",
			requestID: "metadata-dedupe-audio",
			result: &schemas.BifrostResponse{SpeechStreamResponse: &schemas.BifrostSpeechStreamResponse{
				Type:  schemas.SpeechStreamResponseTypeDelta,
				Audio: []byte(strings.Repeat("a", 64)),
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.SpeechStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "tts-test",
					ChunkIndex:             7,
					RawResponse:            []byte("same-audio-raw"),
				},
			}},
		},
		{
			name:      "transcription",
			requestID: "metadata-dedupe-transcription",
			result: &schemas.BifrostResponse{TranscriptionStreamResponse: &schemas.BifrostTranscriptionStreamResponse{
				Type:  schemas.TranscriptionStreamResponseTypeDelta,
				Delta: bifrost.Ptr(strings.Repeat("t", 64)),
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.TranscriptionStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "whisper-test",
					ChunkIndex:             7,
					RawResponse:            []byte("same-transcription-raw"),
				},
			}},
		},
		{
			name:      "image",
			requestID: "metadata-dedupe-image",
			result: &schemas.BifrostResponse{ImageGenerationStreamResponse: &schemas.BifrostImageGenerationStreamResponse{
				Type:       schemas.ImageGenerationEventTypePartial,
				B64JSON:    strings.Repeat("i", 64),
				Index:      0,
				ChunkIndex: 7,
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.ImageGenerationStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "image-test",
					ChunkIndex:             7,
					RawResponse:            []byte("same-image-raw"),
				},
			}},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
				Limits: AccumulatorLimits{
					ChatMaxRetainedBytes:          1,
					ResponsesMaxRetainedBytes:     1,
					AudioMaxRetainedBytes:         1,
					TranscriptionMaxRetainedBytes: 1,
					ImageMaxRetainedBytes:         1,
					RawResponseMaxBytes:           1024,
				},
			})
			t.Cleanup(accumulator.Cleanup)

			ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
			ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, tt.requestID)
			ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, true)
			ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, false)

			for i := 0; i < 2; i++ {
				if _, err := accumulator.ProcessStreamingResponse(ctx, tt.result, nil); err != nil {
					t.Fatalf("duplicate delivery %d failed: %v", i, err)
				}
			}

			stored, ok := accumulator.streamAccumulators.Load(tt.requestID)
			if !ok {
				t.Fatal("expected accumulator")
			}
			stream := stored.(*StreamAccumulator)
			stream.mu.Lock()
			defer stream.mu.Unlock()
			if stream.capture.Output.ChunksSeen != 1 {
				t.Fatalf("duplicate metadata output was counted: %#v", stream.capture.Output)
			}
			if stream.capture.RawResponse.ChunksSeen != 1 {
				t.Fatalf("duplicate metadata raw response was counted: %#v", stream.capture.RawResponse)
			}
		})
	}
}

func TestAccumulatorBoundedSoakDoesNotGrowRetainedChatState(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{ChatMaxRetainedBytes: 128},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "chat-bounded-soak"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, false)

	const chunks = 5000
	for i := 0; i < chunks; i++ {
		ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, i == chunks-1)
		_, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
			ChatResponse: &schemas.BifrostChatResponse{
				ID:     "chatcmpl_bounded_soak",
				Object: "chat.completion.chunk",
				Choices: []schemas.BifrostResponseChoice{
					{
						ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
							Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr(strings.Repeat("s", 64))},
						},
					},
				},
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.ChatCompletionStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "gpt-test",
					ChunkIndex:             i,
				},
			},
		}, nil)
		if err != nil {
			t.Fatalf("chunk %d failed: %v", i, err)
		}
	}

	stored, ok := accumulator.streamAccumulators.Load(requestID)
	if !ok {
		t.Fatal("expected accumulator to remain until explicit cleanup")
	}
	stream := stored.(*StreamAccumulator)
	stream.mu.Lock()
	defer stream.mu.Unlock()
	if stream.capture.Output.Mode != StreamCaptureModeMetadataOnly {
		t.Fatalf("expected metadata-only output mode after soak, got %#v", stream.capture.Output)
	}
	if stream.capture.Output.RetainedBytes != 0 {
		t.Fatalf("expected retained bytes to stay dropped after soak, got %d", stream.capture.Output.RetainedBytes)
	}
	if len(stream.ChatStreamChunks) != 0 {
		t.Fatalf("retained chunks grew during soak: %d", len(stream.ChatStreamChunks))
	}
	if len(stream.ChatChunksSeen) > metadataDedupeMaxEntries {
		t.Fatalf("dedupe map grew beyond bounded metadata cap: %d", len(stream.ChatChunksSeen))
	}
	if stream.capture.Output.ChunksSeen != chunks {
		t.Fatalf("digest metadata did not observe every chunk: got %d want %d", stream.capture.Output.ChunksSeen, chunks)
	}
	if stream.capture.Output.DigestSHA256 == "" {
		t.Fatal("expected rolling digest after soak")
	}
}

func TestChatStreamDowngradesToMetadataOnlyWhenTimeLimitExceeded(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{
			ChatMaxDuration: time.Millisecond,
		},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "chat-output-time-limit"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, false)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

	accumulator.CreateStreamAccumulator(requestID, time.Now().Add(-time.Second))
	processed, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
		ChatResponse: &schemas.BifrostChatResponse{
			ID:     "chatcmpl_time_limit",
			Object: "chat.completion.chunk",
			Choices: []schemas.BifrostResponseChoice{
				{
					ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
						Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr("late chunk")},
					},
					FinishReason: bifrost.Ptr("stop"),
				},
			},
			ExtraFields: schemas.BifrostResponseExtraFields{
				RequestType:            schemas.ChatCompletionStreamRequest,
				Provider:               schemas.OpenAI,
				OriginalModelRequested: "gpt-test",
				ChunkIndex:             0,
			},
		},
	}, nil)
	if err != nil {
		t.Fatalf("ProcessStreamingResponse returned error: %v", err)
	}
	if processed.Data.Capture == nil || processed.Data.Capture.Output.Mode != StreamCaptureModeMetadataOnly {
		t.Fatalf("expected metadata-only output capture, got %#v", processed.Data.Capture)
	}
	if processed.Data.Capture.Output.Reason != StreamCaptureReasonTimeLimit {
		t.Fatalf("expected time-limit reason, got %q", processed.Data.Capture.Output.Reason)
	}

	stored, ok := accumulator.streamAccumulators.Load(requestID)
	if !ok {
		t.Fatal("expected accumulator to remain until explicit cleanup")
	}
	stream := stored.(*StreamAccumulator)
	stream.mu.Lock()
	defer stream.mu.Unlock()
	if len(stream.ChatStreamChunks) != 0 {
		t.Fatalf("expected no retained chat chunks after time downgrade, got %d", len(stream.ChatStreamChunks))
	}
}

func TestNonChatStreamsDowngradeToMetadataOnlyWhenOutputLimitExceeded(t *testing.T) {
	tests := []struct {
		name       string
		limits     AccumulatorLimits
		requestID  string
		makeResult func(chunkIndex int, final bool) *schemas.BifrostResponse
		assert     func(t *testing.T, data *AccumulatedData)
	}{
		{
			name: "responses",
			limits: AccumulatorLimits{
				ResponsesMaxRetainedBytes: 32,
			},
			requestID: "responses-output-byte-limit",
			makeResult: func(chunkIndex int, final bool) *schemas.BifrostResponse {
				resp := &schemas.BifrostResponsesStreamResponse{
					Type:  schemas.ResponsesStreamResponseTypeOutputTextDelta,
					Delta: bifrost.Ptr(strings.Repeat("r", 64)),
					ExtraFields: schemas.BifrostResponseExtraFields{
						RequestType:            schemas.ResponsesStreamRequest,
						Provider:               schemas.OpenAI,
						OriginalModelRequested: "gpt-test",
						ChunkIndex:             chunkIndex,
					},
				}
				if final {
					resp.Type = schemas.ResponsesStreamResponseTypeCompleted
					resp.Response = &schemas.BifrostResponsesResponse{
						Usage: &schemas.ResponsesResponseUsage{InputTokens: 1, OutputTokens: 2, TotalTokens: 3},
					}
				}
				return &schemas.BifrostResponse{ResponsesStreamResponse: resp}
			},
			assert: func(t *testing.T, data *AccumulatedData) {
				t.Helper()
				if data.TokenUsage == nil || data.TokenUsage.TotalTokens != 3 {
					t.Fatalf("responses token usage did not survive downgrade: %#v", data.TokenUsage)
				}
			},
		},
		{
			name: "audio",
			limits: AccumulatorLimits{
				AudioMaxRetainedBytes: 32,
			},
			requestID: "audio-output-byte-limit",
			makeResult: func(chunkIndex int, final bool) *schemas.BifrostResponse {
				resp := &schemas.BifrostSpeechStreamResponse{
					Type:  schemas.SpeechStreamResponseTypeDelta,
					Audio: []byte(strings.Repeat("a", 64)),
					ExtraFields: schemas.BifrostResponseExtraFields{
						RequestType:            schemas.SpeechStreamRequest,
						Provider:               schemas.OpenAI,
						OriginalModelRequested: "tts-test",
						ChunkIndex:             chunkIndex,
					},
				}
				if final {
					resp.Type = schemas.SpeechStreamResponseTypeDone
					resp.Usage = &schemas.SpeechUsage{InputTokens: 1, OutputTokens: 2, TotalTokens: 3}
				}
				return &schemas.BifrostResponse{SpeechStreamResponse: resp}
			},
			assert: func(t *testing.T, data *AccumulatedData) {
				t.Helper()
				if data.TokenUsage == nil || data.TokenUsage.TotalTokens != 3 {
					t.Fatalf("audio token usage did not survive downgrade: %#v", data.TokenUsage)
				}
			},
		},
		{
			name: "transcription",
			limits: AccumulatorLimits{
				TranscriptionMaxRetainedBytes: 32,
			},
			requestID: "transcription-output-byte-limit",
			makeResult: func(chunkIndex int, final bool) *schemas.BifrostResponse {
				inputTokens, outputTokens, totalTokens := 1, 2, 3
				resp := &schemas.BifrostTranscriptionStreamResponse{
					Type:  schemas.TranscriptionStreamResponseTypeDelta,
					Delta: bifrost.Ptr(strings.Repeat("t", 64)),
					ExtraFields: schemas.BifrostResponseExtraFields{
						RequestType:            schemas.TranscriptionStreamRequest,
						Provider:               schemas.OpenAI,
						OriginalModelRequested: "whisper-test",
						ChunkIndex:             chunkIndex,
					},
				}
				if final {
					resp.Type = schemas.TranscriptionStreamResponseTypeDone
					resp.Usage = &schemas.TranscriptionUsage{InputTokens: &inputTokens, OutputTokens: &outputTokens, TotalTokens: &totalTokens}
				}
				return &schemas.BifrostResponse{TranscriptionStreamResponse: resp}
			},
			assert: func(t *testing.T, data *AccumulatedData) {
				t.Helper()
				if data.TokenUsage == nil || data.TokenUsage.TotalTokens != 3 {
					t.Fatalf("transcription token usage did not survive downgrade: %#v", data.TokenUsage)
				}
			},
		},
		{
			name: "image",
			limits: AccumulatorLimits{
				ImageMaxRetainedBytes: 32,
			},
			requestID: "image-output-byte-limit",
			makeResult: func(chunkIndex int, final bool) *schemas.BifrostResponse {
				resp := &schemas.BifrostImageGenerationStreamResponse{
					Type:       schemas.ImageGenerationEventTypePartial,
					B64JSON:    strings.Repeat("i", 64),
					ChunkIndex: chunkIndex,
					Index:      0,
					ExtraFields: schemas.BifrostResponseExtraFields{
						RequestType:            schemas.ImageGenerationStreamRequest,
						Provider:               schemas.OpenAI,
						OriginalModelRequested: "image-test",
						ChunkIndex:             chunkIndex,
					},
				}
				if final {
					resp.Type = schemas.ImageGenerationEventTypeCompleted
					resp.Usage = &schemas.ImageUsage{InputTokens: 1, OutputTokens: 2, TotalTokens: 3}
				}
				return &schemas.BifrostResponse{ImageGenerationStreamResponse: resp}
			},
			assert: func(t *testing.T, data *AccumulatedData) {
				t.Helper()
				if data.TokenUsage == nil || data.TokenUsage.TotalTokens != 3 {
					t.Fatalf("image token usage did not survive downgrade: %#v", data.TokenUsage)
				}
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{Limits: tt.limits})
			t.Cleanup(accumulator.Cleanup)

			ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
			ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, tt.requestID)

			var final *ProcessedStreamResponse
			for i := 0; i < 2; i++ {
				isFinal := i == 1
				ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, isFinal)
				processed, err := accumulator.ProcessStreamingResponse(ctx, tt.makeResult(i, isFinal), nil)
				if err != nil {
					t.Fatalf("chunk %d failed: %v", i, err)
				}
				if isFinal {
					final = processed
				}
			}

			if final == nil || final.Data == nil {
				t.Fatal("expected final accumulated data")
			}
			if final.Data.Capture == nil || final.Data.Capture.Output.Mode != StreamCaptureModeMetadataOnly {
				t.Fatalf("expected metadata-only output capture, got %#v", final.Data.Capture)
			}
			if final.Data.Capture.Output.DigestSHA256 == "" {
				t.Fatal("expected bounded output digest metadata")
			}
			if final.Data.Capture.Output.RetainedBytes != 0 {
				t.Fatalf("expected no retained output bytes after downgrade, got %d", final.Data.Capture.Output.RetainedBytes)
			}
			tt.assert(t, final.Data)
		})
	}
}

func TestRawResponseDowngradesToMetadataOnlyWhenByteLimitExceeded(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{
			RawResponseMaxBytes: 16,
		},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "raw-response-byte-limit"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, true)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

	result := &schemas.BifrostResponse{
		ChatResponse: &schemas.BifrostChatResponse{
			ID:     "chatcmpl_raw_limit",
			Object: "chat.completion.chunk",
			Choices: []schemas.BifrostResponseChoice{
				{
					ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
						Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr("ok")},
					},
					FinishReason: bifrost.Ptr("stop"),
				},
			},
			ExtraFields: schemas.BifrostResponseExtraFields{
				RequestType:            schemas.ChatCompletionStreamRequest,
				Provider:               schemas.OpenAI,
				OriginalModelRequested: "gpt-test",
				ChunkIndex:             0,
				RawResponse:            strings.Repeat("r", 128),
			},
		},
	}

	processed, err := accumulator.ProcessStreamingResponse(ctx, result, nil)
	if err != nil {
		t.Fatalf("ProcessStreamingResponse returned error: %v", err)
	}
	if processed.Data.RawResponse != nil {
		t.Fatalf("oversized raw response retained raw body: %q", *processed.Data.RawResponse)
	}
	if processed.Data.Capture == nil || processed.Data.Capture.RawResponse.Mode != StreamCaptureModeMetadataOnly {
		t.Fatalf("expected metadata-only raw response capture, got %#v", processed.Data.Capture)
	}
	if processed.Data.Capture.RawResponse.Reason != StreamCaptureReasonByteLimit {
		t.Fatalf("expected byte-limit reason, got %q", processed.Data.Capture.RawResponse.Reason)
	}
	if processed.Data.Capture.RawResponse.DigestSHA256 == "" {
		t.Fatal("expected bounded raw-response digest metadata")
	}
}

func TestChatOutputAccountingIncludesNonContentPayloadFields(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{ChatMaxRetainedBytes: 32},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "chat-non-content-accounting"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

	url := "https://example.test/citation"
	text := strings.Repeat("cited text ", 8)
	reasoningText := strings.Repeat("reasoning detail ", 8)
	signature := strings.Repeat("tool-extra", 8)
	result := &schemas.BifrostResponse{
		ChatResponse: &schemas.BifrostChatResponse{
			ID:     "chatcmpl_non_content",
			Object: "chat.completion.chunk",
			Choices: []schemas.BifrostResponseChoice{
				{
					ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
						Delta: &schemas.ChatStreamResponseChoiceDelta{
							Audio: &schemas.ChatAudioMessageAudio{
								ID:         "audio-1",
								Data:       strings.Repeat("audio", 16),
								Transcript: strings.Repeat("transcript", 8),
							},
							ReasoningDetails: []schemas.ChatReasoningDetails{
								{Index: 0, Type: schemas.BifrostReasoningDetailsTypeText, Text: &reasoningText},
							},
							Annotations: []schemas.ChatAssistantMessageAnnotation{
								{
									Type: "url_citation",
									URLCitation: schemas.ChatAssistantMessageAnnotationCitation{
										URL:  &url,
										Text: &text,
									},
								},
							},
							ToolCalls: []schemas.ChatAssistantMessageToolCall{
								{
									Index:        0,
									ID:           bifrost.Ptr("call_1"),
									Type:         bifrost.Ptr("function"),
									Function:     schemas.ChatAssistantMessageToolCallFunction{Name: bifrost.Ptr("lookup")},
									ExtraContent: []byte(`{"signature":"` + signature + `"}`),
								},
							},
							ExtraContent: []byte(`{"provider_blob":"` + strings.Repeat("blob", 16) + `"}`),
						},
					},
					FinishReason: bifrost.Ptr("stop"),
				},
			},
			ExtraFields: schemas.BifrostResponseExtraFields{
				RequestType:            schemas.ChatCompletionStreamRequest,
				Provider:               schemas.OpenAI,
				OriginalModelRequested: "gpt-test",
				ChunkIndex:             0,
			},
		},
	}

	processed, err := accumulator.ProcessStreamingResponse(ctx, result, nil)
	if err != nil {
		t.Fatalf("ProcessStreamingResponse returned error: %v", err)
	}
	if processed.Data.Capture == nil || processed.Data.Capture.Output.Mode != StreamCaptureModeMetadataOnly {
		t.Fatalf("non-content payload fields were not counted toward output limit: %#v", processed.Data.Capture)
	}
	if processed.Data.Capture.Output.DigestSHA256 == "" {
		t.Fatal("expected digest to include non-content payload fields")
	}
}

func TestRawResponseAccountingRunsAfterChunkDeduplication(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{RawResponseMaxBytes: 1024},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "raw-dedupe-accounting"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, true)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, false)

	raw := strings.Repeat("same-raw", 8)
	for i := 0; i < 2; i++ {
		_, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
			ChatResponse: &schemas.BifrostChatResponse{
				ID:     "chatcmpl_raw_dedupe",
				Object: "chat.completion.chunk",
				Choices: []schemas.BifrostResponseChoice{
					{
						ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
							Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr("duplicate")},
						},
					},
				},
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.ChatCompletionStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "gpt-test",
					ChunkIndex:             7,
					RawResponse:            raw,
				},
			},
		}, nil)
		if err != nil {
			t.Fatalf("duplicate chunk %d failed: %v", i, err)
		}
	}

	stored, ok := accumulator.streamAccumulators.Load(requestID)
	if !ok {
		t.Fatal("expected accumulator")
	}
	stream := stored.(*StreamAccumulator)
	stream.mu.Lock()
	defer stream.mu.Unlock()
	if stream.capture.RawResponse.ChunksSeen != 1 {
		t.Fatalf("raw response was counted before de-duplication: %#v", stream.capture.RawResponse)
	}
	if stream.capture.RawResponse.RetainedBytes != int64(len(raw)) {
		t.Fatalf("raw retained bytes = %d, want %d", stream.capture.RawResponse.RetainedBytes, len(raw))
	}
}

func TestRetentionHookMayReenterAccumulatorWithoutDeadlock(t *testing.T) {
	var accumulator *Accumulator
	hookCalled := make(chan struct{}, 1)
	accumulator = NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{ChatMaxRetainedBytes: 1},
		Hooks: AccumulatorHooks{
			OnRetainedBytes: func(event StreamRetentionEvent) {
				if event.Mode == StreamCaptureModeMetadataOnly {
					_ = accumulator.IsStreamPaused(event.RequestID)
					hookCalled <- struct{}{}
				}
			},
		},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "retention-hook-reenter"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

	done := make(chan error, 1)
	go func() {
		_, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
			ChatResponse: &schemas.BifrostChatResponse{
				ID:     "chatcmpl_hook_reenter",
				Object: "chat.completion.chunk",
				Choices: []schemas.BifrostResponseChoice{
					{
						ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
							Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr(strings.Repeat("x", 64))},
						},
					},
				},
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.ChatCompletionStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "gpt-test",
					ChunkIndex:             0,
				},
			},
		}, nil)
		done <- err
	}()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("ProcessStreamingResponse returned error: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("retention hook deadlocked while reentering accumulator")
	}
	select {
	case <-hookCalled:
	default:
		t.Fatal("expected metadata-only retention hook")
	}
}

func TestPassthroughStreamDowngradesToMetadataOnlyWhenBodyLimitExceeded(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{
			PassthroughMaxRetainedBytes: 64,
		},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "passthrough-body-byte-limit"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)

	var final *ProcessedStreamResponse
	for i := 0; i < 50; i++ {
		isFinal := i == 49
		ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, isFinal)
		processed, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
			PassthroughResponse: &schemas.BifrostPassthroughResponse{
				StatusCode: 200,
				Headers:    map[string]string{"content-type": "application/json"},
				Body:       []byte(strings.Repeat("p", 32)),
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.PassthroughStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "passthrough-test",
					ChunkIndex:             i,
				},
			},
		}, nil)
		if err != nil {
			t.Fatalf("chunk %d failed: %v", i, err)
		}
		if isFinal {
			final = processed
		}
	}

	if final == nil || final.Data == nil || final.Data.PassthroughOutput == nil {
		t.Fatal("expected final passthrough output")
	}
	if len(final.Data.PassthroughOutput.Body) != 0 {
		t.Fatalf("oversized passthrough stream retained %d body bytes", len(final.Data.PassthroughOutput.Body))
	}
	if final.Data.Capture == nil || final.Data.Capture.PassthroughBody.Mode != StreamCaptureModeMetadataOnly {
		t.Fatalf("expected metadata-only passthrough capture, got %#v", final.Data.Capture)
	}
	if final.Data.Capture.PassthroughBody.DigestSHA256 == "" {
		t.Fatal("expected bounded passthrough digest metadata")
	}

	stored, ok := accumulator.streamAccumulators.Load(requestID)
	if !ok {
		t.Fatal("expected accumulator to remain until explicit cleanup")
	}
	stream := stored.(*StreamAccumulator)
	stream.mu.Lock()
	defer stream.mu.Unlock()
	if len(stream.PassthroughBody) != 0 {
		t.Fatalf("expected retained passthrough body to be dropped, got %d bytes", len(stream.PassthroughBody))
	}
}

func TestPassthroughHeadersAreBounded(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{
			PassthroughMaxHeaderCount:      2,
			PassthroughMaxHeaderNameBytes:  8,
			PassthroughMaxHeaderValueBytes: 8,
			PassthroughMaxHeaderTotalBytes: 24,
		},
	})
	t.Cleanup(accumulator.Cleanup)

	headers := make(map[string]string)
	for i := 0; i < 10; i++ {
		headers[fmt.Sprintf("h%d", i)] = strings.Repeat("v", 8)
	}
	headers["name-too-long"] = "v"
	headers["h-long-value"] = strings.Repeat("x", 64)

	requestID := "passthrough-header-caps"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

	processed, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
		PassthroughResponse: &schemas.BifrostPassthroughResponse{
			StatusCode: 200,
			Headers:    headers,
			ExtraFields: schemas.BifrostResponseExtraFields{
				RequestType:            schemas.PassthroughStreamRequest,
				Provider:               schemas.OpenAI,
				OriginalModelRequested: "passthrough-test",
			},
		},
	}, nil)
	if err != nil {
		t.Fatalf("ProcessStreamingResponse returned error: %v", err)
	}
	if processed.Data == nil || processed.Data.PassthroughOutput == nil {
		t.Fatal("expected passthrough output")
	}
	gotHeaders := processed.Data.PassthroughOutput.Headers
	if len(gotHeaders) > 2 {
		t.Fatalf("retained %d headers, want at most 2", len(gotHeaders))
	}
	var total int
	for name, value := range gotHeaders {
		if len(name) > 8 {
			t.Fatalf("retained oversized header name %q", name)
		}
		if len(value) > 8 {
			t.Fatalf("retained oversized header value for %q", name)
		}
		total += len(name) + len(value)
	}
	if total > 24 {
		t.Fatalf("retained header bytes = %d, want <= 24", total)
	}
	if processed.Data.Capture == nil || processed.Data.Capture.PassthroughHeaders.Mode != StreamCaptureModeMetadataOnly {
		t.Fatalf("expected metadata-only header capture after drops, got %#v", processed.Data.Capture)
	}
}

func TestPassthroughFinalRawCaptureAppearsInCaptureSnapshot(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{RawResponseMaxBytes: 4},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "passthrough-final-raw-snapshot"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, true)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, true)

	processed, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
		PassthroughResponse: &schemas.BifrostPassthroughResponse{
			StatusCode: 200,
			Body:       []byte("ok"),
			ExtraFields: schemas.BifrostResponseExtraFields{
				RequestType:            schemas.PassthroughStreamRequest,
				Provider:               schemas.OpenAI,
				OriginalModelRequested: "passthrough-test",
				RawResponse:            []byte("0123456789"),
			},
		},
	}, nil)
	if err != nil {
		t.Fatalf("ProcessStreamingResponse returned error: %v", err)
	}
	if processed.Data == nil || processed.Data.Capture == nil {
		t.Fatal("expected capture snapshot")
	}
	if processed.Data.RawResponse != nil {
		t.Fatalf("oversized final raw response retained: %q", *processed.Data.RawResponse)
	}
	if processed.Data.Capture.RawResponse.Mode != StreamCaptureModeMetadataOnly {
		t.Fatalf("final raw capture missing from snapshot: %#v", processed.Data.Capture.RawResponse)
	}
	if processed.Data.Capture.RawResponse.DigestSHA256 != testSHA256Hex([]byte("0123456789")) {
		t.Fatalf("final raw digest = %s", processed.Data.Capture.RawResponse.DigestSHA256)
	}
}

func TestRejectedChatChunkIsReturnedToPoolOnDowngrade(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{ChatMaxRetainedBytes: 1},
	})
	t.Cleanup(accumulator.Cleanup)

	chunk := accumulator.getChatStreamChunk()
	chunk.Timestamp = time.Now()
	chunk.ChunkIndex = 0
	chunk.Delta = &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr(strings.Repeat("x", 64))}
	chunk.rawResponseCandidate = []byte("raw")
	chunk.captureRawResponse = true

	if err := accumulator.addChatStreamChunk("pooled-rejected-chat", StreamTypeChat, chunk, false); err != nil {
		t.Fatalf("addChatStreamChunk returned error: %v", err)
	}
	if chunk.Delta != nil || chunk.rawResponseCandidate != nil || chunk.captureRawResponse || chunk.RawResponse != nil {
		t.Fatalf("rejected chunk was not reset before returning to pool: %#v", chunk)
	}
}

func TestAccumulatorEmitsRetainedByteHookOnDowngrade(t *testing.T) {
	var events []StreamRetentionEvent
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{
		Limits: AccumulatorLimits{
			ChatMaxRetainedBytes: 16,
		},
		Hooks: AccumulatorHooks{
			OnRetainedBytes: func(event StreamRetentionEvent) {
				events = append(events, event)
			},
		},
	})
	t.Cleanup(accumulator.Cleanup)

	requestID := "retained-byte-hook"
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyCaptureRawResponse, false)

	for i := 0; i < 2; i++ {
		ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, i == 1)
		_, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
			ChatResponse: &schemas.BifrostChatResponse{
				ID:     "chatcmpl_hook",
				Object: "chat.completion.chunk",
				Choices: []schemas.BifrostResponseChoice{
					{
						ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
							Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr(strings.Repeat("h", 20))},
						},
					},
				},
				ExtraFields: schemas.BifrostResponseExtraFields{
					RequestType:            schemas.ChatCompletionStreamRequest,
					Provider:               schemas.OpenAI,
					OriginalModelRequested: "gpt-test",
					ChunkIndex:             i,
				},
			},
		}, nil)
		if err != nil {
			t.Fatalf("chunk %d failed: %v", i, err)
		}
	}

	var sawDowngrade bool
	for _, event := range events {
		if event.RequestID == requestID && event.Purpose == StreamCapturePurposeOutput && event.Mode == StreamCaptureModeMetadataOnly {
			sawDowngrade = true
			if event.RetainedBytes != 0 {
				t.Fatalf("downgrade hook reported retained bytes: %#v", event)
			}
			if event.DroppedBytes == 0 {
				t.Fatalf("downgrade hook did not report dropped bytes: %#v", event)
			}
		}
	}
	if !sawDowngrade {
		t.Fatalf("expected metadata-only output event, got %#v", events)
	}
}

func TestProcessStreamingResponseCleansAccumulatorWhenContextCancelled(t *testing.T) {
	accumulator := NewAccumulatorWithOptions(nil, bifrost.NewDefaultLogger(schemas.LogLevelError), AccumulatorOptions{})
	t.Cleanup(accumulator.Cleanup)

	requestID := "cancelled-stream-cleanup"
	parent, cancel := context.WithCancel(context.Background())
	ctx := schemas.NewBifrostContext(parent, time.Time{})
	ctx.SetValue(schemas.BifrostContextKeyAccumulatorID, requestID)
	ctx.SetValue(schemas.BifrostContextKeyStreamEndIndicator, false)

	accumulator.CreateStreamAccumulator(requestID, time.Now())
	if _, ok := accumulator.streamAccumulators.Load(requestID); !ok {
		t.Fatal("expected accumulator to exist before cancellation")
	}

	cancel()
	select {
	case <-ctx.Done():
	case <-time.After(2 * time.Second):
		t.Fatal("bifrost context did not observe parent cancellation")
	}

	_, err := accumulator.ProcessStreamingResponse(ctx, &schemas.BifrostResponse{
		ChatResponse: &schemas.BifrostChatResponse{
			ID:     "chatcmpl_cancelled",
			Object: "chat.completion.chunk",
			Choices: []schemas.BifrostResponseChoice{
				{
					ChatStreamResponseChoice: &schemas.ChatStreamResponseChoice{
						Delta: &schemas.ChatStreamResponseChoiceDelta{Content: bifrost.Ptr("late")},
					},
				},
			},
			ExtraFields: schemas.BifrostResponseExtraFields{
				RequestType:            schemas.ChatCompletionStreamRequest,
				Provider:               schemas.OpenAI,
				OriginalModelRequested: "gpt-test",
				ChunkIndex:             0,
			},
		},
	}, nil)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
	if _, ok := accumulator.streamAccumulators.Load(requestID); ok {
		t.Fatal("cancelled stream accumulator was not cleaned up")
	}
}
