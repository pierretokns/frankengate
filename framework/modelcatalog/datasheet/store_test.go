package datasheet

import (
	"slices"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
)

func TestDeprecatedDatasheetModelsForProviderUsesRebuiltIndex(t *testing.T) {
	s := NewTestStore(nil)
	s.mu.Lock()
	s.pricingData[makeKey("deprecated-b", "openai", "chat")] = configstoreTables.TableModelPricing{
		Model:        "deprecated-b",
		Provider:     "openai",
		Mode:         "chat",
		IsDeprecated: true,
	}
	s.pricingData[makeKey("deprecated-a", "openai", "chat")] = configstoreTables.TableModelPricing{
		Model:        "deprecated-a",
		Provider:     "openai",
		Mode:         "chat",
		IsDeprecated: true,
	}
	s.pricingData[makeKey("deprecated-a", "openai", "responses")] = configstoreTables.TableModelPricing{
		Model:        "deprecated-a",
		Provider:     "openai",
		Mode:         "responses",
		IsDeprecated: true,
	}
	s.pricingData[makeKey("active", "openai", "chat")] = configstoreTables.TableModelPricing{
		Model:    "active",
		Provider: "openai",
		Mode:     "chat",
	}
	s.pricingData[makeKey("deprecated-vertex", "vertex_ai", "chat")] = configstoreTables.TableModelPricing{
		Model:        "deprecated-vertex",
		Provider:     "vertex_ai",
		Mode:         "chat",
		IsDeprecated: true,
	}
	s.rebuildDatasheetViewUnsafe()
	s.mu.Unlock()

	got := s.DeprecatedDatasheetModelsForProvider(schemas.OpenAI)
	want := []string{"deprecated-a", "deprecated-b"}
	if !slices.Equal(got, want) {
		t.Fatalf("expected deprecated OpenAI models %v, got %v", want, got)
	}

	got[0] = "mutated"
	got = s.DeprecatedDatasheetModelsForProvider(schemas.OpenAI)
	if !slices.Equal(got, want) {
		t.Fatalf("expected defensive copy from index %v, got %v", want, got)
	}

	got = s.DeprecatedDatasheetModelsForProvider(schemas.Vertex)
	want = []string{"deprecated-vertex"}
	if !slices.Equal(got, want) {
		t.Fatalf("expected deprecated Vertex models %v, got %v", want, got)
	}
}

func TestIsRequestTypeSupportedForProviderNormalizesDatabaseProviderAliases(t *testing.T) {
	s := NewTestStore(nil)
	s.mu.Lock()
	s.pricingData[makeKey("text-embedding-alias", "vertex_ai", "embedding")] = configstoreTables.TableModelPricing{
		Model: "text-embedding-alias", Provider: "vertex_ai", Mode: "embedding",
	}
	s.mu.Unlock()

	if !s.IsRequestTypeSupportedForProvider("text-embedding-alias", schemas.Vertex, schemas.EmbeddingRequest) {
		t.Fatal("embedding capability should survive a database provider alias")
	}
	if !s.HasProviderModel("text-embedding-alias", schemas.Vertex) {
		t.Fatal("provider/model lookup should survive a database provider alias")
	}
}

func TestGetCapabilityEntryNormalizesDatabaseProviderAliases(t *testing.T) {
	s := NewTestStore(nil)
	s.mu.Lock()
	s.pricingData[makeKey("text-embedding-alias", "vertex_ai", "embedding")] = configstoreTables.TableModelPricing{
		Model: "text-embedding-alias", Provider: "vertex_ai", Mode: "embedding",
	}
	s.mu.Unlock()

	entry := s.GetCapabilityEntry("text-embedding-alias", schemas.Vertex)
	if entry == nil {
		t.Fatal("capability lookup should survive a database provider alias")
	}
}

func TestCapabilityAdmissionKeepsBedrockMantleTransportBoundary(t *testing.T) {
	s := NewTestStore(nil)
	s.mu.Lock()
	s.pricingData[makeKey("mantle-model", string(schemas.BedrockMantle), "chat")] = configstoreTables.TableModelPricing{
		Model: "mantle-model", Provider: string(schemas.BedrockMantle), Mode: "chat",
	}
	s.pricingData[makeKey("bedrock-model", string(schemas.Bedrock), "chat")] = configstoreTables.TableModelPricing{
		Model: "bedrock-model", Provider: string(schemas.Bedrock), Mode: "chat",
	}
	s.mu.Unlock()

	if !s.IsRequestTypeSupportedForProvider("mantle-model", schemas.BedrockMantle, schemas.ChatCompletionRequest) {
		t.Fatal("Mantle row should admit Mantle requests")
	}
	if s.IsRequestTypeSupportedForProvider("mantle-model", schemas.Bedrock, schemas.ChatCompletionRequest) {
		t.Fatal("Mantle capability must not authorize legacy Bedrock requests")
	}
	if !s.IsRequestTypeSupportedForProvider("bedrock-model", schemas.Bedrock, schemas.ChatCompletionRequest) {
		t.Fatal("Bedrock row should admit Bedrock requests")
	}
	if s.IsRequestTypeSupportedForProvider("bedrock-model", schemas.BedrockMantle, schemas.ChatCompletionRequest) {
		t.Fatal("Bedrock capability must not authorize Mantle requests")
	}
}
