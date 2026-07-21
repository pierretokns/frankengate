package bedrockmantle

import (
	"context"
	"testing"

	schemas "github.com/maximhq/bifrost/core/schemas"
)

func TestMantleOpenAIURLUsesOpenAIPrefixForGPT56FrontierModels(t *testing.T) {
	// AWS's generic Mantle guide documents https://bedrock-mantle.<region>.api.aws/v1,
	// while the GPT-5.4 and GPT-5.5 model cards explicitly document the exceptional
	// /openai/v1/responses path. GPT-5.6 aliases are pinned by the deployment contract.
	// Sources checked 2026-07-21:
	// https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html
	// https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-54.html
	// https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-55.html
	tests := []struct {
		model string
		want  string
	}{
		{"openai.gpt-5.4", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"openai.gpt-5.5", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"openai.gpt-5.6-sol", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"OpenAI.GPT-5.6-Sol", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"openai.gpt-5.6-terra", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"openai.gpt-5.6-luna", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"gpt-oss-120b", "https://bedrock-mantle.us-east-1.api.aws/v1/responses"},
		// An undocumented name must not inherit the exceptional route merely
		// because it contains "gpt-5". Explicit alias family metadata is tested below.
		{"openai.gpt-5.3", "https://bedrock-mantle.us-east-1.api.aws/v1/responses"},
		{"openai.gpt-5.50", "https://bedrock-mantle.us-east-1.api.aws/v1/responses"},
		{"google.gemma-4-e2b", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
	}
	for _, tt := range tests {
		t.Run(tt.model, func(t *testing.T) {
			if got := mantleOpenAIURL("us-east-1", tt.model, "responses"); got != tt.want {
				t.Fatalf("mantleOpenAIURL(%q) = %q, want %q", tt.model, got, tt.want)
			}
		})
	}
}

func TestMantleOpenAIURLDoesNotUseExplicitAliasFamilyAsPathAuthority(t *testing.T) {
	want := "https://bedrock-mantle.us-east-1.api.aws/v1/responses"
	if got := mantleOpenAIURLForFamily("us-east-1", "opaque-soul-deployment", "openai", "responses"); got != want {
		t.Fatalf("explicit OpenAI conversion family must not select an exceptional path: got %q, want %q", got, want)
	}
	if got := mantleOpenAIURLForFamily("us-east-1", "Claude-GPT-soul", "openai", "responses"); got != want {
		t.Fatalf("alias spelling/family must not select an exceptional path: got %q, want %q", got, want)
	}
}

func TestMantleProductionResolutionRequiresCanonicalModelForExceptionalPath(t *testing.T) {
	openaiFamily := schemas.ModelFamilyOpenAI
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	unknownModel := "openai.gpt-5.3"
	unknownCanonical := schemas.ResolveCanonicalModel(ctx, unknownModel)
	unknownFamily := schemas.ResolveFamily(ctx, unknownModel)
	if unknownFamily != schemas.ModelFamilyOpenAI {
		t.Fatalf("production fallback family resolution = %q, want openai", unknownFamily)
	}
	wantBare := "https://bedrock-mantle.us-east-1.api.aws/v1/responses"
	if got := mantleOpenAIURLForFamily("us-east-1", unknownCanonical, unknownFamily, "responses"); got != wantBare {
		t.Fatalf("unknown OpenAI-family model selected exceptional path: got %q, want %q", got, wantBare)
	}

	ctx.SetValue(schemas.BifrostContextKeyResolvedAlias, &schemas.ResolvedAlias{
		Key: "customer-frontier-alias",
		Config: &schemas.AliasConfig{
			ModelID:     "opaque-deployment-id",
			ModelFamily: &openaiFamily,
		},
	})

	canonical := schemas.ResolveCanonicalModel(ctx, "customer-frontier-alias")
	family := schemas.ResolveFamily(ctx, "customer-frontier-alias")
	if family != schemas.ModelFamilyOpenAI {
		t.Fatalf("production family resolution = %q, want openai", family)
	}
	if got := mantleOpenAIURLForFamily("us-east-1", canonical, family, "responses"); got != wantBare {
		t.Fatalf("opaque alias family selected exceptional path: got %q, want %q", got, wantBare)
	}

	ctx.SetValue(schemas.BifrostContextKeyResolvedAlias, &schemas.ResolvedAlias{
		Key: "customer-frontier-alias",
		Config: &schemas.AliasConfig{
			ModelID:     "opaque-deployment-id",
			ModelName:   schemas.Ptr("openai.gpt-5.5"),
			ModelFamily: &openaiFamily,
		},
	})
	canonical = schemas.ResolveCanonicalModel(ctx, "customer-frontier-alias")
	family = schemas.ResolveFamily(ctx, "customer-frontier-alias")
	wantPrefixed := "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"
	if got := mantleOpenAIURLForFamily("us-east-1", canonical, family, "responses"); got != wantPrefixed {
		t.Fatalf("pinned canonical model did not select exceptional path: got %q, want %q", got, wantPrefixed)
	}
}

func TestGPT54And55RejectChatCompletions(t *testing.T) {
	provider := &BedrockMantleProvider{}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	for _, model := range []string{"openai.gpt-5.4", "openai.gpt-5.5"} {
		t.Run(model, func(t *testing.T) {
			_, err := provider.ChatCompletion(ctx, schemas.Key{}, &schemas.BifrostChatRequest{Model: model})
			if err == nil || err.Error == nil || err.Error.Message != "model "+model+" supports Responses API only on Bedrock Mantle" {
				t.Fatalf("ChatCompletion error = %#v", err)
			}
			_, err = provider.ChatCompletionStream(ctx, nil, nil, schemas.Key{}, &schemas.BifrostChatRequest{Model: model})
			if err == nil || err.Error == nil || err.Error.Message != "model "+model+" supports Responses API only on Bedrock Mantle" {
				t.Fatalf("ChatCompletionStream error = %#v", err)
			}
		})
	}
}

func TestMantleOpenAIURLKeepsGPTOSSOnBareSurfaceWithOpenAIFamily(t *testing.T) {
	// ResolveFamily classifies gpt-oss as OpenAI because its wire format is
	// OpenAI-compatible. Mantle nevertheless serves it at /v1, not /openai/v1.
	want := "https://bedrock-mantle.us-east-1.api.aws/v1/responses"
	if got := mantleOpenAIURLForFamily("us-east-1", "gpt-oss-120b", "openai", "responses"); got != want {
		t.Fatalf("gpt-oss must use bare Mantle surface, got %q, want %q", got, want)
	}
}

func TestMantleOpenAIURLPreservesCanonicalModelPrefixAcrossPaths(t *testing.T) {
	for _, path := range []string{"responses", "chat/completions"} {
		t.Run(path, func(t *testing.T) {
			got := mantleOpenAIURLForFamily("us-east-1", "openai.gpt-5.6-luna", "openai", path)
			want := "https://bedrock-mantle.us-east-1.api.aws/openai/v1/" + path
			if got != want {
				t.Fatalf("family-qualified Mantle path = %q, want %q", got, want)
			}
		})
	}
}

func TestParseBedrockRegionAndModel(t *testing.T) {
	tests := []struct {
		input, region, model string
	}{
		{input: "us-east-1/gpt-oss-120b", region: "us-east-1", model: "gpt-oss-120b"},
		{input: "eu-central-1/openai.gpt-5.6-sol", region: "eu-central-1", model: "openai.gpt-5.6-sol"},
		{input: "gpt-oss-120b", model: "gpt-oss-120b"},
		{input: "not-a-region/gpt-oss-120b", model: "not-a-region/gpt-oss-120b"},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			region, model := parseBedrockRegionAndModel(tt.input)
			if region != tt.region || model != tt.model {
				t.Fatalf("parseBedrockRegionAndModel(%q) = (%q, %q), want (%q, %q)", tt.input, region, model, tt.region, tt.model)
			}
		})
	}
}
