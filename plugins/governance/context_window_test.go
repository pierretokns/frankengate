package governance

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/stretchr/testify/require"
)

func contextWindowRequest(provider schemas.ModelProvider, model string) *schemas.BifrostRequest {
	return &schemas.BifrostRequest{RequestType: schemas.ChatCompletionRequest, ChatRequest: &schemas.BifrostChatRequest{Provider: provider, Model: model}}
}

func contextWindowContext(value string) *schemas.BifrostContext {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyExtraHeaders, map[string][]string{"Anthropic-Beta": {value}})
	return ctx
}

func TestContextWindowAdmissionAllowsCataloguedProviderModel(t *testing.T) {
	err := validateContextWindowHeaders(contextWindowContext("context-1m-2025-08-07"), schemas.Anthropic, "claude-sonnet-4-5-20250929", schemas.ChatCompletionRequest)
	require.Nil(t, err)
}

func TestContextWindowAdmissionRejectsUnknownModelAndProvider(t *testing.T) {
	for _, tc := range []struct {
		name        string
		provider    schemas.ModelProvider
		model       string
		requestType schemas.RequestType
	}{
		{"opaque alias", schemas.Anthropic, "claude-internal-latest", schemas.ChatCompletionRequest},
		{"unsupported provider", schemas.OpenAI, "claude-sonnet-4-5-20250929", schemas.ChatCompletionRequest},
		{"unsupported operation", schemas.Anthropic, "claude-sonnet-4-5-20250929", schemas.EmbeddingRequest},
	} {
		t.Run(tc.name, func(t *testing.T) {
			err := validateContextWindowHeaders(contextWindowContext("context-1m-2025-08-07"), tc.provider, tc.model, tc.requestType)
			require.NotNil(t, err)
			require.Equal(t, "context_window_unsupported", *err.Type)
			require.False(t, *err.AllowFallbacks)
		})
	}
}

func TestPreLLMHookContextWindowAdmissionHappensBeforeReservation(t *testing.T) {
	p := admissionTestPlugin(t)
	ctx := contextWindowContext("context-1m-2025-08-07")
	_, shortCircuit, err := p.PreLLMHook(ctx, contextWindowRequest(schemas.OpenAI, "gpt-5"))
	require.NoError(t, err)
	require.NotNil(t, shortCircuit)
	require.Equal(t, "context_window_unsupported", *shortCircuit.Error.Type)
}
