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
