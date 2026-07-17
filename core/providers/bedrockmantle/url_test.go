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
