package governance

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestDeriveModelFamilyIsStableForAliases(t *testing.T) {
	tests := map[string]string{
		"claude-gpt-soul":     "claude",
		"bedrock/nova-pro":    "nova",
		"Qwen2.5-72B":         "qwen",
		"vendor/custom-model": "unknown",
	}
	for model, want := range tests {
		require.Equal(t, want, deriveModelFamily(model), model)
	}
}

func TestRoutingEnvironmentSupportsModelFamily(t *testing.T) {
	env, err := createCELEnvironment()
	require.NoError(t, err)
	ast, issues := env.Compile(`model_family == "claude" && model.startsWith("claude-")`)
	require.False(t, issues.Err() != nil, "%v", issues.Err())
	program, err := env.Program(ast)
	require.NoError(t, err)
	out, _, err := program.Eval(map[string]any{
		"model": "claude-gpt-soul", "model_family": "claude", "provider": "bedrock",
		"request_type": "chat_completion", "headers": map[string]string{}, "params": map[string]string{},
		"virtual_key_id": "", "virtual_key_name": "", "team_id": "", "team_name": "",
		"customer_id": "", "customer_name": "", "tokens_used": 0.0, "request": 0.0,
		"budget_used": 0.0, "complexity_tier": "",
	})
	require.NoError(t, err)
	require.Equal(t, true, out.Value())
}
