package integrations

import (
	"context"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestIsClaudeModelUsesResolvedAliasFamilyBeforeCosmeticName(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), time.Time{})
	openAI := schemas.ModelFamilyOpenAI
	ctx.SetValue(schemas.BifrostContextKeyResolvedAlias, &schemas.ResolvedAlias{
		Key: "Claude-Soul",
		Config: &schemas.AliasConfig{
			ModelID:     "opaque-soul-deployment",
			ModelFamily: &openAI,
		},
	})
	if isClaudeModel(ctx, "Claude-Soul", "Claude-Soul", string(schemas.BedrockMantle)) {
		t.Fatal("Claude-visible OpenAI alias must not use Anthropic response conversion")
	}

	anthropic := schemas.ModelFamilyAnthropic
	ctx.SetValue(schemas.BifrostContextKeyResolvedAlias, &schemas.ResolvedAlias{
		Key: "Claude-Sonnet",
		Config: &schemas.AliasConfig{
			ModelID:     "opaque-sonnet-deployment",
			ModelFamily: &anthropic,
		},
	})
	if !isClaudeModel(ctx, "Claude-Sonnet", "Claude-Sonnet", string(schemas.BedrockMantle)) {
		t.Fatal("Anthropic-family alias must use Anthropic response conversion")
	}
}
