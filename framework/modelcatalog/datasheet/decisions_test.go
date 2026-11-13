package datasheet

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

func TestDecisionsInputOnlyPricing(t *testing.T) {
	s := newTestStore()
	for _, tc := range []struct {
		tokens   int
		regional bool
		want     float64
	}{{1000000, false, 0.20}, {272000, false, 0.0272}, {272001, false, 0.0544002}, {100, true, 0.000011}} {
		u := &schemas.BifrostLLMUsage{PromptTokens: tc.tokens, CompletionTokens: 9999, TotalTokens: tc.tokens + 9999, PromptTokensDetails: &schemas.ChatPromptTokensDetails{CachedReadTokens: 50, CachedWriteTokens: 25}, OpenAIDecisions: true, DecisionsRegional: tc.regional}
		resp := &schemas.BifrostResponse{PassthroughResponse: &schemas.BifrostPassthroughResponse{PassthroughUsage: &schemas.BifrostPassthroughUsage{LLMUsage: u, DecisionsRegional: tc.regional}, ExtraFields: schemas.BifrostResponseExtraFields{RequestType: schemas.PassthroughRequest, PassthroughPath: "/v1/decisions", RoutingInfo: routingInfoFor(schemas.OpenAI, "gpt-6-luna")}}}
		require.InDelta(t, tc.want, s.CalculateCost(resp, nil), 1e-12)
		require.InDelta(t, tc.want, s.CalculateCostForUsage(u, schemas.OpenAI, "gpt-6-luna", schemas.PassthroughRequest, nil), 1e-12, "failed validation must use identical billing")
	}
	provider := "openai"
	require.NoError(t, s.SetOverrides([]configstoreTables.TablePricingOverride{{ID: "decisions", ScopeKind: string(ScopeKindProvider), ProviderID: &provider, MatchType: string(MatchTypeExact), Pattern: "gpt-6-luna@decisions", RequestTypes: []schemas.RequestType{schemas.ChatCompletionRequest}, PricingPatchJSON: `{"input_cost_per_token":0.000003}`}}))
	require.InDelta(t, 0.0003, s.calculateOpenAIDecisionsCost(&schemas.BifrostLLMUsage{PromptTokens: 100, CompletionTokens: 99999}, nil, LookupScopes{}), 1e-12)
}
