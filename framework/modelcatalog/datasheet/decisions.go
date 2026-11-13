package datasheet

import (
	"github.com/maximhq/bifrost/core/schemas"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
)

// calculateOpenAIDecisionsCost uses the dedicated Decisions rates verified on
// 2026-10-08: $0.10/M input, $0.20/M above 272K, 10% regional uplift. There are
// no separate output/cache charges. Generic Luna catalog prices do not apply.
// Existing scoped pricing overrides use gpt-6-luna@decisions with the chat
// pricing mode; this is an accounting key, never a wire/routing model alias.
func (s *Store) calculateOpenAIDecisionsCost(usage *schemas.BifrostLLMUsage, passthrough *schemas.BifrostPassthroughUsage, scopes LookupScopes) float64 {
	if usage == nil {
		return 0
	}
	base := configstoreTables.TableModelPricing{
		Model: "gpt-6-luna@decisions", Provider: string(schemas.OpenAI), Mode: "chat",
		InputCostPerToken:                schemas.Ptr(0.10 / 1_000_000),
		InputCostPerTokenAbove272kTokens: schemas.Ptr(0.20 / 1_000_000),
	}
	if scopes.Provider == "" {
		scopes.Provider = string(schemas.OpenAI)
	}
	pricing, _ := s.applyPricingOverrides(base.Model, schemas.ChatCompletionRequest, base, scopes)
	cost := float64(usage.PromptTokens) * tieredInputRate(&pricing, usage.PromptTokens, serviceTier{})
	if passthrough != nil && passthrough.DecisionsRegional {
		cost *= 1.1
	}
	return cost
}
