package bedrockmantle

import "testing"

func TestMantleOpenAIURLUsesOpenAIPrefixForGPT56FrontierModels(t *testing.T) {
	tests := []struct {
		model string
		want  string
	}{
		{"openai.gpt-5.6-sol", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"OpenAI.GPT-5.6-Sol", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"openai.gpt-5.6-terra", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"openai.gpt-5.6-luna", "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"gpt-oss-120b", "https://bedrock-mantle.us-east-1.api.aws/v1/responses"},
	}
	for _, tt := range tests {
		t.Run(tt.model, func(t *testing.T) {
			if got := mantleOpenAIURL("us-east-1", tt.model, "responses"); got != tt.want {
				t.Fatalf("mantleOpenAIURL(%q) = %q, want %q", tt.model, got, tt.want)
			}
		})
	}
}

func TestMantleOpenAIURLHonorsExplicitAliasFamily(t *testing.T) {
	if got := mantleOpenAIURLForFamily("us-east-1", "opaque-soul-deployment", "openai", "responses"); got != "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses" {
		t.Fatalf("explicit OpenAI family must select /openai/v1, got %q", got)
	}
	if got := mantleOpenAIURLForFamily("us-east-1", "Claude-GPT-soul", "openai", "responses"); got != "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses" {
		t.Fatalf("Claude-visible OpenAI alias must select /openai/v1, got %q", got)
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

func TestMantleOpenAIURLPreservesFamilyPrefixAcrossPaths(t *testing.T) {
	for _, path := range []string{"responses", "chat/completions"} {
		t.Run(path, func(t *testing.T) {
			got := mantleOpenAIURLForFamily("us-east-1", "opaque-luna-alias", "openai", path)
			want := "https://bedrock-mantle.us-east-1.api.aws/openai/v1/" + path
			if got != want {
				t.Fatalf("family-qualified Mantle path = %q, want %q", got, want)
			}
		})
	}
}
