package modelcatalog

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog/datasheet"
)

func TestCapabilityAdmissionKeepsProviderAndOperationBoundaries(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pricing.json")
	data := []byte(`{
		"vision": {"provider":"openai", "mode":"chat"},
		"vision-image": {"provider":"openai", "mode":"image_generation"}
	}`)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	ds := datasheet.New(nil, nil, datasheet.Config{URL: "file://" + path})
	if err := ds.LoadFromURLIntoMemory(t.Context()); err != nil {
		t.Fatal(err)
	}
	mc := NewTestCatalogWithDatasheet(ds)

	if !mc.HasProviderModel("vision", schemas.OpenAI) {
		t.Fatal("expected authoritative OpenAI model row")
	}
	if mc.IsRequestTypeSupportedForProvider("vision", schemas.OpenAI, schemas.ImageGenerationRequest) {
		t.Fatal("chat-only model must not admit image generation")
	}
	if !mc.IsRequestTypeSupportedForProvider("vision-image", schemas.OpenAI, schemas.ImageGenerationRequest) {
		t.Fatal("image model must admit image generation")
	}
	if mc.HasProviderModel("vision", schemas.Bedrock) {
		t.Fatal("OpenAI row must not authorize Bedrock")
	}
}

func TestCapabilityAdmissionSupportsBatchOperationFamily(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pricing.json")
	data := []byte(`{
		"batch-model": {"provider":"openai", "mode":"batch_create"}
	}`)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	ds := datasheet.New(nil, nil, datasheet.Config{URL: "file://" + path})
	if err := ds.LoadFromURLIntoMemory(t.Context()); err != nil {
		t.Fatal(err)
	}
	mc := NewTestCatalogWithDatasheet(ds)
	for _, operation := range []schemas.RequestType{
		schemas.BatchCreateRequest,
		schemas.BatchListRequest,
		schemas.BatchRetrieveRequest,
		schemas.BatchCancelRequest,
		schemas.BatchResultsRequest,
		schemas.BatchDeleteRequest,
	} {
		if !mc.IsRequestTypeSupportedForProvider("batch-model", schemas.OpenAI, operation) {
			t.Fatalf("batch operation %q should use the published batch capability", operation)
		}
	}
	if mc.IsRequestTypeSupportedForProvider("batch-model", schemas.OpenAI, schemas.EmbeddingRequest) {
		t.Fatal("batch capability must not authorize embedding")
	}
}

func TestCapabilityAdmissionKeepsRealtimeSeparateFromResponses(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pricing.json")
	data := []byte(`{
		"realtime-model": {"provider":"openai", "mode":"realtime"},
		"responses-model": {"provider":"openai", "mode":"responses"}
	}`)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	ds := datasheet.New(nil, nil, datasheet.Config{URL: "file://" + path})
	if err := ds.LoadFromURLIntoMemory(t.Context()); err != nil {
		t.Fatal(err)
	}
	mc := NewTestCatalogWithDatasheet(ds)
	if !mc.IsRequestTypeSupportedForProvider("realtime-model", schemas.OpenAI, schemas.RealtimeRequest) {
		t.Fatal("realtime catalog row must admit realtime sessions")
	}
	if mc.IsRequestTypeSupportedForProvider("realtime-model", schemas.OpenAI, schemas.ResponsesRequest) {
		t.Fatal("realtime capability must not authorize Responses requests")
	}
	if mc.IsRequestTypeSupportedForProvider("responses-model", schemas.OpenAI, schemas.RealtimeRequest) {
		t.Fatal("Responses capability must not authorize realtime sessions")
	}
}

func TestCapabilityAdmissionKeepsImageVariationSeparateFromGenerationAndEdit(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pricing.json")
	data := []byte(`{
		"variation-model": {"provider":"openai", "mode":"image_variation"},
		"generation-model": {"provider":"openai", "mode":"image_generation"},
		"edit-model": {"provider":"openai", "mode":"image_edit"}
	}`)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	ds := datasheet.New(nil, nil, datasheet.Config{URL: "file://" + path})
	if err := ds.LoadFromURLIntoMemory(t.Context()); err != nil {
		t.Fatal(err)
	}
	mc := NewTestCatalogWithDatasheet(ds)
	if !mc.IsRequestTypeSupportedForProvider("variation-model", schemas.OpenAI, schemas.ImageVariationRequest) {
		t.Fatal("variation capability must admit image variations")
	}
	if mc.IsRequestTypeSupportedForProvider("variation-model", schemas.OpenAI, schemas.ImageGenerationRequest) ||
		mc.IsRequestTypeSupportedForProvider("variation-model", schemas.OpenAI, schemas.ImageEditRequest) {
		t.Fatal("variation capability must not authorize generation or editing")
	}
	if mc.IsRequestTypeSupportedForProvider("generation-model", schemas.OpenAI, schemas.ImageVariationRequest) ||
		mc.IsRequestTypeSupportedForProvider("edit-model", schemas.OpenAI, schemas.ImageVariationRequest) {
		t.Fatal("generation/edit capabilities must not authorize variations")
	}
}

func TestCapabilityAdmissionAudioFamiliesRemainIsolated(t *testing.T) {
	path := filepath.Join(t.TempDir(), "pricing.json")
	data := []byte(`{
		"tts-model": {"provider":"openai", "mode":"speech"},
		"stt-model": {"provider":"openai", "mode":"transcription"},
		"embedding-model": {"provider":"openai", "mode":"embedding"}
	}`)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	ds := datasheet.New(nil, nil, datasheet.Config{URL: "file://" + path})
	if err := ds.LoadFromURLIntoMemory(t.Context()); err != nil {
		t.Fatal(err)
	}
	mc := NewTestCatalogWithDatasheet(ds)
	if !mc.IsRequestTypeSupportedForProvider("tts-model", schemas.OpenAI, schemas.SpeechRequest) ||
		!mc.IsRequestTypeSupportedForProvider("tts-model", schemas.OpenAI, schemas.SpeechStreamRequest) {
		t.Fatal("speech capability must admit unary and streaming speech")
	}
	if mc.IsRequestTypeSupportedForProvider("tts-model", schemas.OpenAI, schemas.TranscriptionRequest) ||
		mc.IsRequestTypeSupportedForProvider("tts-model", schemas.OpenAI, schemas.EmbeddingRequest) {
		t.Fatal("speech capability must not authorize transcription or embedding")
	}
	if !mc.IsRequestTypeSupportedForProvider("stt-model", schemas.OpenAI, schemas.TranscriptionRequest) ||
		!mc.IsRequestTypeSupportedForProvider("stt-model", schemas.OpenAI, schemas.TranscriptionStreamRequest) {
		t.Fatal("transcription capability must admit unary and streaming transcription")
	}
	if mc.IsRequestTypeSupportedForProvider("stt-model", schemas.OpenAI, schemas.SpeechRequest) ||
		mc.IsRequestTypeSupportedForProvider("stt-model", schemas.OpenAI, schemas.EmbeddingRequest) {
		t.Fatal("transcription capability must not authorize speech or embedding")
	}
	if !mc.IsRequestTypeSupportedForProvider("embedding-model", schemas.OpenAI, schemas.EmbeddingRequest) ||
		mc.IsRequestTypeSupportedForProvider("embedding-model", schemas.OpenAI, schemas.SpeechRequest) ||
		mc.IsRequestTypeSupportedForProvider("embedding-model", schemas.OpenAI, schemas.TranscriptionRequest) {
		t.Fatal("embedding capability must remain isolated from audio families")
	}
}
