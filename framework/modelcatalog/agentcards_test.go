package modelcatalog

import (
	"os"
	"path/filepath"
	"reflect"
	"slices"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog/datasheet"
)

func TestCompileAgentModelCardsDeterministic(t *testing.T) {
	mc := newAgentCardTestCatalog(t)
	generatedAt := time.Date(2026, 8, 4, 18, 30, 0, 0, time.UTC)

	first := mc.CompileAgentModelCardsAt(generatedAt)
	second := mc.CompileAgentModelCardsAt(generatedAt)
	if !reflect.DeepEqual(first, second) {
		t.Fatal("expected deterministic compiled snapshots for the same catalog and generation time")
	}
	if first.SchemaVersion != AgentModelCardSchemaVersion {
		t.Fatalf("schema version = %q, want %q", first.SchemaVersion, AgentModelCardSchemaVersion)
	}
	if first.GenerationID == "" || first.Revision.ID == "" {
		t.Fatalf("expected generation and revision IDs, got generation=%q revision=%q", first.GenerationID, first.Revision.ID)
	}
	if !slices.Equal(first.SourcePrecedence, []AgentModelCardSourceKind{
		AgentModelCardSourceKeyConfig,
		AgentModelCardSourceLiveListModels,
		AgentModelCardSourceDatasheet,
		AgentModelCardSourceModelParameters,
	}) {
		t.Fatalf("unexpected source precedence: %v", first.SourcePrecedence)
	}
	if first.UnknownBehavior.CapabilityState == "" || first.DeprecatedBehavior.Visibility == "" {
		t.Fatal("expected explicit unknown and deprecated behavior metadata")
	}

	models := make([]string, 0, len(first.Cards))
	for _, card := range first.Cards {
		models = append(models, string(card.Provider)+"/"+card.Model)
	}
	wantModels := []string{
		"openai/alias-z",
		"openai/deprecated-a",
		"openai/gpt-z",
		"openai/live-only",
	}
	if !slices.Equal(models, wantModels) {
		t.Fatalf("compiled cards = %v, want %v", models, wantModels)
	}

	aliasCard := findAgentCard(t, first, schemas.OpenAI, "alias-z")
	if aliasCard.ProviderMapping.WireModel != "deployment-z" {
		t.Fatalf("alias wire model = %q, want deployment-z", aliasCard.ProviderMapping.WireModel)
	}
	if len(aliasCard.Aliases) != 1 || aliasCard.Aliases[0].ModelName == nil || *aliasCard.Aliases[0].ModelName != "gpt-z" {
		t.Fatalf("expected alias metadata to preserve canonical model name, got %#v", aliasCard.Aliases)
	}
	if !slices.Contains(aliasCard.Sources, AgentModelCardSourceKeyConfig) {
		t.Fatalf("alias card sources = %v, want key config", aliasCard.Sources)
	}

	gptCard := findAgentCard(t, first, schemas.OpenAI, "gpt-z")
	if gptCard.CapabilityState != AgentModelCapabilityKnown {
		t.Fatalf("gpt-z capability state = %q, want known", gptCard.CapabilityState)
	}
	if gptCard.Pricing == nil || gptCard.Pricing.InputCostPerToken == nil || *gptCard.Pricing.InputCostPerToken != 0.000001 {
		t.Fatalf("expected pricing from datasheet, got %#v", gptCard.Pricing)
	}
	if gptCard.Architecture == nil || !slices.Equal(gptCard.Architecture.InputModalities, []string{"image", "text"}) {
		t.Fatalf("expected copied architecture modalities, got %#v", gptCard.Architecture)
	}
	if !slices.Contains(gptCard.SupportedRequestTypes, schemas.ChatCompletionRequest) ||
		!slices.Contains(gptCard.SupportedRequestTypes, schemas.ChatCompletionStreamRequest) {
		t.Fatalf("expected chat request families, got %v", gptCard.SupportedRequestTypes)
	}
	if !slices.Equal(gptCard.SupportedParameters, []string{"reasoning_with_tool_calls", "stop", "temperature", "tools"}) {
		t.Fatalf("supported parameters = %v", gptCard.SupportedParameters)
	}
	if !slices.Equal(gptCard.LiveKeyIDs, []string{"k1"}) || !slices.Equal(gptCard.UnfilteredLiveKeyIDs, []string{"k1"}) {
		t.Fatalf("expected live key IDs from filtered and unfiltered caches, got filtered=%v unfiltered=%v", gptCard.LiveKeyIDs, gptCard.UnfilteredLiveKeyIDs)
	}

	deprecatedCard := findAgentCard(t, first, schemas.OpenAI, "deprecated-a")
	if !deprecatedCard.IsDeprecated {
		t.Fatal("deprecated datasheet row should compile as visible deprecated metadata")
	}

	liveOnlyCard := findAgentCard(t, first, schemas.OpenAI, "live-only")
	if liveOnlyCard.CapabilityState != AgentModelCapabilityUnknown {
		t.Fatalf("live-only capability state = %q, want unknown", liveOnlyCard.CapabilityState)
	}
	if liveOnlyCard.Pricing != nil {
		t.Fatalf("live-only pricing = %#v, want nil", liveOnlyCard.Pricing)
	}
}

func TestCompileAgentModelCardsSnapshotHasNoCatalogAliasing(t *testing.T) {
	mc := newAgentCardTestCatalog(t)
	generatedAt := time.Date(2026, 8, 4, 18, 45, 0, 0, time.UTC)

	snapshot := mc.CompileAgentModelCardsAt(generatedAt)
	gptCard := findAgentCard(t, snapshot, schemas.OpenAI, "gpt-z")
	*gptCard.Pricing.InputCostPerToken = 99
	*gptCard.Limits.ContextLength = 99
	gptCard.Architecture.InputModalities[0] = "mutated"
	gptCard.SupportedParameters[0] = "mutated"

	aliasCard := findAgentCard(t, snapshot, schemas.OpenAI, "alias-z")
	*aliasCard.Aliases[0].ModelFamily = schemas.ModelFamilyAnthropic
	*aliasCard.Aliases[0].ModelName = "mutated"

	next := mc.CompileAgentModelCardsAt(generatedAt)
	nextGPT := findAgentCard(t, next, schemas.OpenAI, "gpt-z")
	if nextGPT.Pricing == nil || nextGPT.Pricing.InputCostPerToken == nil || *nextGPT.Pricing.InputCostPerToken != 0.000001 {
		t.Fatalf("snapshot pricing mutation leaked into catalog: %#v", nextGPT.Pricing)
	}
	if nextGPT.Limits.ContextLength == nil || *nextGPT.Limits.ContextLength != 128000 {
		t.Fatalf("snapshot limit mutation leaked into catalog: %#v", nextGPT.Limits.ContextLength)
	}
	if !slices.Equal(nextGPT.Architecture.InputModalities, []string{"image", "text"}) {
		t.Fatalf("snapshot architecture mutation leaked into catalog: %#v", nextGPT.Architecture)
	}
	if !slices.Equal(nextGPT.SupportedParameters, []string{"reasoning_with_tool_calls", "stop", "temperature", "tools"}) {
		t.Fatalf("snapshot parameter mutation leaked into catalog: %v", nextGPT.SupportedParameters)
	}

	nextAlias := findAgentCard(t, next, schemas.OpenAI, "alias-z")
	if nextAlias.Aliases[0].ModelFamily == nil || *nextAlias.Aliases[0].ModelFamily != schemas.ModelFamilyOpenAI {
		t.Fatalf("snapshot alias family mutation leaked into catalog: %#v", nextAlias.Aliases[0].ModelFamily)
	}
	if nextAlias.Aliases[0].ModelName == nil || *nextAlias.Aliases[0].ModelName != "gpt-z" {
		t.Fatalf("snapshot alias model-name mutation leaked into catalog: %#v", nextAlias.Aliases[0].ModelName)
	}
}

func TestCompileAgentModelCardsDoesNotChangeExistingCatalogBehavior(t *testing.T) {
	mc := newAgentCardTestCatalog(t)
	generatedAt := time.Date(2026, 8, 4, 19, 0, 0, 0, time.UTC)

	beforeModels := mc.GetModelsForProvider(schemas.OpenAI)
	beforeProviders := mc.GetProvidersForModel("gpt-z")
	beforeKeys := mc.KeysAllowingModel(schemas.OpenAI, "gpt-z")
	beforePricing := mc.GetPricingEntryForModel("gpt-z", schemas.OpenAI)
	beforeSupportsChat := mc.IsRequestTypeSupportedForProvider("gpt-z", schemas.OpenAI, schemas.ChatCompletionRequest)

	_ = mc.CompileAgentModelCardsAt(generatedAt)

	afterModels := mc.GetModelsForProvider(schemas.OpenAI)
	afterProviders := mc.GetProvidersForModel("gpt-z")
	afterKeys := mc.KeysAllowingModel(schemas.OpenAI, "gpt-z")
	afterPricing := mc.GetPricingEntryForModel("gpt-z", schemas.OpenAI)
	afterSupportsChat := mc.IsRequestTypeSupportedForProvider("gpt-z", schemas.OpenAI, schemas.ChatCompletionRequest)

	if !slices.Equal(beforeModels, afterModels) {
		t.Fatalf("GetModelsForProvider changed: before=%v after=%v", beforeModels, afterModels)
	}
	if !slices.Equal(beforeProviders, afterProviders) {
		t.Fatalf("GetProvidersForModel changed: before=%v after=%v", beforeProviders, afterProviders)
	}
	if !slices.Equal(beforeKeys, afterKeys) {
		t.Fatalf("KeysAllowingModel changed: before=%v after=%v", beforeKeys, afterKeys)
	}
	if beforeSupportsChat != afterSupportsChat {
		t.Fatalf("capability lookup changed: before=%v after=%v", beforeSupportsChat, afterSupportsChat)
	}
	if beforePricing == nil || afterPricing == nil ||
		beforePricing.InputCostPerToken == nil || afterPricing.InputCostPerToken == nil ||
		*beforePricing.InputCostPerToken != *afterPricing.InputCostPerToken {
		t.Fatalf("pricing lookup changed: before=%#v after=%#v", beforePricing, afterPricing)
	}
}

func newAgentCardTestCatalog(t *testing.T) *ModelCatalog {
	t.Helper()

	dir := t.TempDir()
	pricingPath := filepath.Join(dir, "pricing.json")
	pricingJSON := []byte(`{
		"gpt-z": {
			"provider": "openai",
			"mode": "chat",
			"base_model": "gpt-z",
			"context_length": 128000,
			"max_input_tokens": 64000,
			"max_output_tokens": 16000,
			"input_cost_per_token": 0.000001,
			"output_cost_per_token": 0.000002,
			"architecture": {
				"modality": "text",
				"input_modalities": ["text", "image"],
				"output_modalities": ["text"]
			}
		},
		"deprecated-a": {
			"provider": "openai",
			"mode": "chat",
			"base_model": "deprecated-a",
			"is_deprecated": true
		}
	}`)
	if err := os.WriteFile(pricingPath, pricingJSON, 0o600); err != nil {
		t.Fatalf("write pricing fixture: %v", err)
	}

	paramsPath := filepath.Join(dir, "model-parameters.json")
	paramsJSON := []byte(`{
		"gpt-z": {
			"provider": "openai",
			"supported_endpoints": ["/v1/chat/completions"],
			"model_parameters": [{"id": "temperature"}, {"id": "stop_sequences"}],
			"supports_function_calling": true
		}
	}`)
	if err := os.WriteFile(paramsPath, paramsJSON, 0o600); err != nil {
		t.Fatalf("write model parameters fixture: %v", err)
	}

	ds := datasheet.New(nil, nil, datasheet.Config{
		URL:                "file://" + pricingPath,
		ModelParametersURL: "file://" + paramsPath,
	})
	if err := ds.LoadFromURLIntoMemory(t.Context()); err != nil {
		t.Fatalf("load pricing fixture: %v", err)
	}
	if err := ds.LoadModelParamsFromURLIntoMemory(t.Context()); err != nil {
		t.Fatalf("load model parameters fixture: %v", err)
	}
	ds.MarkSynced(time.Date(2026, 8, 4, 18, 0, 0, 0, time.UTC))

	mc := NewTestCatalogWithDatasheet(ds)
	mc.UpsertLive(schemas.OpenAI, "k1", false, []string{"gpt-z", "live-only"})
	mc.UpsertLive(schemas.OpenAI, "k1", true, []string{"gpt-z", "unfiltered-only"})
	modelFamily := schemas.ModelFamilyOpenAI
	modelName := "gpt-z"
	mc.SetKeyConfigForProvider(schemas.OpenAI, []schemas.Key{
		{
			ID:                "k1",
			Models:            schemas.WhiteList{"*"},
			BlacklistedModels: schemas.BlackList{},
			Aliases: schemas.KeyAliases{
				"alias-z": {
					ModelID:     "deployment-z",
					ModelName:   &modelName,
					ModelFamily: &modelFamily,
					Description: "test deployment alias",
				},
			},
		},
	})
	return mc
}

func findAgentCard(t *testing.T, snapshot AgentModelCardSnapshot, provider schemas.ModelProvider, model string) AgentModelCard {
	t.Helper()
	for _, card := range snapshot.Cards {
		if card.Provider == provider && card.Model == model {
			return card
		}
	}
	t.Fatalf("card %s/%s not found in %#v", provider, model, snapshot.Cards)
	return AgentModelCard{}
}
