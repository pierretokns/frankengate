package bedrock

import (
	"context"
	"testing"

	schemas "github.com/maximhq/bifrost/core/schemas"
)

func TestMantleSigningExtraHeadersIncludesRequestScopedAmzHeaders(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyExtraHeaders, map[string][]string{
		"X-Amz-Trace-Id": {"trace-123"},
		"X-Request-Id":   {"request-123"},
	})
	got := mantleSigningExtraHeaders(ctx, map[string]string{"x-amz-source": "gateway"})
	if got["X-Amz-Trace-Id"] != "trace-123" || got["x-amz-source"] != "gateway" {
		t.Fatalf("signed headers missing request/provider values: %#v", got)
	}
	if _, ok := got["X-Request-Id"]; ok {
		t.Fatalf("non-amz request header must not be included in signing set: %#v", got)
	}
}

func TestIsMantleModel(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	cases := []struct {
		model string
		want  bool
	}{
		// gpt-oss family → mantle
		{"gpt-oss-120b", true},
		{"openai.gpt-oss-20b", true},
		{"gpt-oss-safeguard-120b", true},
		{"us.openai.gpt-oss-120b", true},
		// closed gpt-5.x → mantle
		{"gpt-5.5", true},
		{"openai.gpt-5.4", true},
		// Gemma 4 → mantle (mantle-only, no Converse endpoint)
		{"gemma-4-31b", true},
		{"google.gemma-4-e2b", true},
		{"gemma-4-26b-a4b", true},
		// Gemma 3 → NOT mantle: it has a Converse fallback that serves both APIs,
		// while mantle only supports Chat (so Responses would break there).
		{"gemma-3-12b-it", false},
		{"google.gemma-3-27b-it", false},
		{"gemma-3-4b-it", false},
		// Anthropic (Claude) models stay on the Converse path.
		{"claude-opus-4-8", false},
		{"anthropic.claude-3-5-sonnet-20240620-v1:0", false},
		// other families stay on the Converse path
		{"amazon.titan-text-express-v1", false},
	}
	for _, tc := range cases {
		if got := isMantleModel(ctx, tc.model); got != tc.want {
			t.Errorf("isMantleModel(%q) = %v, want %v", tc.model, got, tc.want)
		}
	}
}

func TestMantleOpenAIURL(t *testing.T) {
	cases := []struct {
		name   string
		region string
		model  string
		path   string
		want   string
	}{
		{"gpt-oss uses bare v1", "us-east-1", "openai.gpt-oss-120b", "chat/completions",
			"https://bedrock-mantle.us-east-1.api.aws/v1/chat/completions"},
		{"gpt-oss-safeguard uses bare v1", "us-west-2", "openai.gpt-oss-safeguard-120b", "chat/completions",
			"https://bedrock-mantle.us-west-2.api.aws/v1/chat/completions"},
		{"gpt-5.x uses openai/v1", "us-east-2", "openai.gpt-5.5", "responses",
			"https://bedrock-mantle.us-east-2.api.aws/openai/v1/responses"},
		{"undocumented gpt-5 name stays on generic v1", "us-east-2", "openai.gpt-5.3", "responses",
			"https://bedrock-mantle.us-east-2.api.aws/v1/responses"},
		{"gemma-4 uses openai/v1", "us-east-1", "google.gemma-4-31b", "responses",
			"https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses"},
		{"gemma-3 uses bare v1", "us-east-1", "google.gemma-3-12b-it", "chat/completions",
			"https://bedrock-mantle.us-east-1.api.aws/v1/chat/completions"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := mantleOpenAIURL(tc.region, tc.model, tc.path); got != tc.want {
				t.Errorf("mantleOpenAIURL(%q, %q, %q) = %q, want %q", tc.region, tc.model, tc.path, got, tc.want)
			}
		})
	}

	if got := mantleOpenAIURL("us-east-1", "OpenAI.GPT-5.6-SOL", "responses"); got != "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses" {
		t.Fatalf("case-insensitive frontier model routing = %q", got)
	}
	if got := mantleOpenAIURL("us-east-1", "GEMMA-4-27B", "responses"); got != "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses" {
		t.Fatalf("case-insensitive Gemma routing = %q", got)
	}
}

func TestMantleOpenAIURLDoesNotUseConversionFamilyAsPathAuthority(t *testing.T) {
	got := mantleOpenAIURLForFamily("us-east-1", "claude-gpt-soul", schemas.ModelFamilyOpenAI, "responses")
	want := "https://bedrock-mantle.us-east-1.api.aws/v1/responses"
	if got != want {
		t.Fatalf("conversion family must not select an exceptional AWS path: got %q, want %q", got, want)
	}
}

func TestMantleOpenAIURLGPTOSSOverridesExplicitOpenAIFamily(t *testing.T) {
	got := mantleOpenAIURLForFamily("us-east-1", "gpt-oss-120b", schemas.ModelFamilyOpenAI, "responses")
	want := "https://bedrock-mantle.us-east-1.api.aws/v1/responses"
	if got != want {
		t.Fatalf("gpt-oss must use bare Mantle surface even with OpenAI family metadata: got %q, want %q", got, want)
	}
}
