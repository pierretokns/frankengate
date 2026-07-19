package schemas

import "testing"

func TestStreamChunkFallbackRoutingInfo(t *testing.T) {
	primaryProvider := ModelProvider("openai")
	chunk := &BifrostStreamChunk{BifrostChatResponse: &BifrostChatResponse{
		Model: "fallback-model",
	}}
	chunk.SetFallbackRoutingInfo(primaryProvider, "primary-model")
	info := chunk.BifrostChatResponse.ExtraFields.RoutingInfo
	if !info.IsFallback || info.PrimaryProvider == nil || *info.PrimaryProvider != primaryProvider || info.PrimaryModel == nil || *info.PrimaryModel != "primary-model" {
		t.Fatalf("fallback routing metadata not propagated: %+v", info)
	}
	if got := chunk.BifrostChatResponse.ExtraFields.OriginalModelRequested; got != "primary-model" {
		t.Fatalf("deprecated original model not synchronized: %q", got)
	}
}

func TestStreamChunkFallbackErrorRoutingInfo(t *testing.T) {
	chunk := &BifrostStreamChunk{BifrostError: &BifrostError{}}
	chunk.SetFallbackRoutingInfo(ModelProvider("bedrock"), "primary")
	if !chunk.BifrostError.ExtraFields.RoutingInfo.IsFallback {
		t.Fatal("error chunk was not marked as fallback")
	}
}
