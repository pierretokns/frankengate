package governance

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/maximhq/bifrost/core/reservations"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	tables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/framework/modelcatalog"
	"github.com/maximhq/bifrost/framework/modelcatalog/datasheet"
	"github.com/stretchr/testify/require"
)

func TestDecisionsGovernanceDenials(t *testing.T) {
	// A generic Luna Responses row must neither deny the verified Decisions
	// capability nor cause generic passthrough admission to become permissive.
	pricingFile := filepath.Join(t.TempDir(), "pricing.json")
	require.NoError(t, os.WriteFile(pricingFile, []byte(`{"gpt-6-luna":{"provider":"openai","mode":"responses","input_cost_per_token":0.0009}}`), 0600))
	ds := datasheet.New(nil, NewMockLogger(), datasheet.Config{URL: "file://" + pricingFile})
	require.NoError(t, ds.LoadFromURLIntoMemory(context.Background()))
	catalog := modelcatalog.NewTestCatalogWithDatasheet(ds)
	require.True(t, catalog.HasProviderModel("gpt-6-luna", schemas.OpenAI))
	const body = `{"model":"gpt-6-luna","input":"local fixture","questions":[{"type":"predicate","instructions":"check"}]}`
	for _, name := range []string{"allow", "invalid key", "model", "provider", "budget", "rate limit"} {
		t.Run(name, func(t *testing.T) {
			vk := buildVirtualKeyWithProviders("decision-vk", "test-vk", "local", []tables.TableVirtualKeyProviderConfig{buildProviderConfig("openai", []string{"gpt-6-luna"})})
			cfg := &configstore.GovernanceConfig{VirtualKeys: []tables.TableVirtualKey{*vk}}
			switch name {
			case "model":
				cfg.VirtualKeys[0].ProviderConfigs = []tables.TableVirtualKeyProviderConfig{buildProviderConfig("openai", []string{"gpt-6-sol"})}
			case "provider":
				cfg.VirtualKeys[0].ProviderConfigs = []tables.TableVirtualKeyProviderConfig{buildProviderConfig("anthropic", []string{"*"})}
			case "budget":
				b := buildBudgetWithUsage("decision-budget", 1, 1, "1d")
				cfg.VirtualKeys[0] = *buildVirtualKeyWithBudget("decision-vk", "test-vk", "local", b)
				cfg.Budgets = []tables.TableBudget{*b}
			case "rate limit":
				r := buildRateLimitWithUsage("decision-rl", 1000, 0, 1, 1)
				cfg.VirtualKeys[0] = *buildVirtualKeyWithRateLimit("decision-vk", "test-vk", "local", r)
				cfg.RateLimits = []tables.TableRateLimit{*r}
			}
			p, err := Init(context.Background(), &Config{IsVkMandatory: schemas.Ptr(true)}, NewMockLogger(), nil, cfg, catalog, nil, nil)
			require.NoError(t, err)
			defer p.Cleanup()
			ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
			key := "test-vk"
			if name == "invalid key" {
				key = "unknown"
			}
			ctx.SetValue(schemas.BifrostContextKeyVirtualKey, key)
			req := &schemas.BifrostRequest{RequestType: schemas.PassthroughRequest, PassthroughRequest: &schemas.BifrostPassthroughRequest{Provider: schemas.OpenAI, Model: "gpt-6-luna", Method: "POST", Path: "/v1/decisions", Body: []byte(body)}}
			_, sc, err := p.PreLLMHook(ctx, req)
			require.NoError(t, err)
			if name == "allow" {
				require.Nil(t, sc)
				require.NotNil(t, p.validateCatalogCapabilityFor(schemas.OpenAI, "gpt-6-luna", schemas.PassthroughRequest))
				req.PassthroughRequest.Model = "different"
				require.NotNil(t, p.validateRequestCapability(req, schemas.OpenAI, "different"))
			} else {
				require.NotNil(t, sc)
				require.NotNil(t, sc.Error)
			}
		})
	}
}

func TestDecisionsDurableAccounting(t *testing.T) {
	for _, tc := range []struct {
		name             string
		input, output    int
		regional, failed bool
		status           int
		override         bool
		wantMicros       int64
	}{
		{name: "success", input: 100, output: 5, wantMicros: 10},
		{name: "malformed billed success", input: 100, output: 5, failed: true, wantMicros: 10},
		{name: "regional billed error", input: 100, output: 5, regional: true, failed: true, wantMicros: 11},
		{name: "fractional micro", input: 1, wantMicros: 1},
		{name: "exact micro binary rounding", input: 10150, wantMicros: 1015},
		{name: "regional exact micro binary rounding", input: 2300, regional: true, wantMicros: 253},
		{name: "reported zero usage"},
		{name: "upstream unauthenticated", status: 401},
		{name: "upstream rate limit", status: 429},
		{name: "upstream failure", status: 503},
		{name: "scoped price override", input: 100, output: 5, override: true, wantMicros: 300},
	} {
		t.Run(tc.name, func(t *testing.T) {
			p := admissionTestPlugin(t)
			defer p.Cleanup()
			ds := datasheet.New(nil, NewMockLogger(), datasheet.Config{})
			if tc.override {
				provider := "openai"
				require.NoError(t, ds.SetOverrides([]tables.TablePricingOverride{{ID: "decisions", ScopeKind: string(datasheet.ScopeKindProvider), ProviderID: &provider, MatchType: string(datasheet.MatchTypeExact), Pattern: "gpt-6-luna@decisions", RequestTypes: []schemas.RequestType{schemas.ChatCompletionRequest}, PricingPatchJSON: `{"input_cost_per_token":0.000003}`}}))
			}
			p.modelCatalog = modelcatalog.NewTestCatalogWithDatasheet(ds)
			store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
			coordinator := &DurableReservationCoordinator{Store: store, Estimator: ConfiguredReservationEstimator{MaxTokens: 20000, CostMicrosPerToken: 1}}
			p.SetReservationCoordinator(coordinator)
			ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
			handle, err := coordinator.Reserve(ctx, AdmissionRequest{RequestID: tc.name, Result: &EvaluationResult{BudgetInfo: []*tables.TableBudget{{ID: "decisions-budget"}}}})
			require.NoError(t, err)
			setReservationHandle(ctx, handle)
			usage := &schemas.BifrostLLMUsage{OpenAIDecisions: true, DecisionsRegional: tc.regional, PromptTokens: tc.input, CompletionTokens: tc.output, TotalTokens: tc.input + tc.output}
			routing := schemas.RoutingInfo{Provider: schemas.OpenAI, Model: "gpt-6-luna"}
			var response *schemas.BifrostResponse
			var billedError *schemas.BifrostError
			if tc.failed {
				billedError = &schemas.BifrostError{StatusCode: schemas.Ptr(502), ExtraFields: schemas.BifrostErrorExtraFields{RequestType: schemas.PassthroughRequest, RoutingInfo: routing, BilledUsage: usage}}
			} else {
				status := tc.status
				if status == 0 {
					status = 200
				}
				response = &schemas.BifrostResponse{PassthroughResponse: &schemas.BifrostPassthroughResponse{StatusCode: status, PassthroughUsage: &schemas.BifrostPassthroughUsage{LLMUsage: usage, DecisionsRegional: tc.regional}, ExtraFields: schemas.BifrostResponseExtraFields{RequestType: schemas.PassthroughRequest, PassthroughPath: "/v1/decisions", RoutingInfo: routing}}}
				if tc.status != 0 {
					response.PassthroughResponse.PassthroughUsage = nil
				}
			}
			_, _, err = p.PostLLMHook(ctx, response, billedError)
			require.NoError(t, err)
			_, _, _ = p.PostLLMHook(ctx, response, billedError) // Duplicate terminal hook cannot bill twice.
			row, err := store.Get(ctx, handle.(*durableReservationHandle).rows[0].ID)
			require.NoError(t, err)
			require.Equal(t, reservations.Amount{Tokens: int64(tc.input + tc.output), CostMicros: tc.wantMicros}, row.SettledAmount)
			if tc.status != 0 {
				require.Equal(t, row.ReservedAmount, row.RefundedAmount)
			}
			_, active := reservationHandleFromContext(ctx)
			require.False(t, active)
		})
	}
}

func TestDecisionsFailureDoesNotCountSuccessfulRequest(t *testing.T) {
	for _, status := range []int{200, 401, 429, 503} {
		rl := buildRateLimitWithUsage("decision-rl", 1000, 0, 10, 0)
		vk := buildVirtualKeyWithRateLimit("decision-vk", "test-vk", "local", rl)
		p, err := Init(context.Background(), &Config{IsVkMandatory: schemas.Ptr(true)}, NewMockLogger(), nil, &configstore.GovernanceConfig{VirtualKeys: []tables.TableVirtualKey{*vk}, RateLimits: []tables.TableRateLimit{*rl}}, nil, nil, nil)
		require.NoError(t, err)
		response := &schemas.BifrostResponse{PassthroughResponse: &schemas.BifrostPassthroughResponse{StatusCode: status, ExtraFields: schemas.BifrostResponseExtraFields{RoutingInfo: schemas.RoutingInfo{Provider: schemas.OpenAI, Model: "gpt-6-luna"}, PassthroughPath: "/v1/decisions"}}}
		p.postHookWorker(response, nil, schemas.OpenAI, "gpt-6-luna", schemas.PassthroughRequest, "test-vk", "count-fixture", "", false, 0, nil)
		got := p.store.LoadRateLimit(context.Background(), "decision-rl")
		require.NotNil(t, got)
		if status == 200 {
			require.EqualValues(t, 1, got.RequestCurrentUsage)
		} else {
			require.Zero(t, got.RequestCurrentUsage)
		}
		require.NoError(t, p.Cleanup())
	}
}

func TestDecisionsRefundRetainsBilledUsage(t *testing.T) {
	store := testBudgetReservationStore{InMemoryStore: reservations.NewInMemoryStore()}
	coordinator := &DurableReservationCoordinator{Store: store, Estimator: ConfiguredReservationEstimator{MaxTokens: 1000, CostMicrosPerToken: 1}}
	handle, err := coordinator.Reserve(context.Background(), AdmissionRequest{RequestID: "billed-refund", Result: &EvaluationResult{BudgetInfo: []*tables.TableBudget{{ID: "budget"}}}})
	require.NoError(t, err)
	settlement := AdmissionSettlement{Error: &schemas.BifrostError{ExtraFields: schemas.BifrostErrorExtraFields{BilledUsage: &schemas.BifrostLLMUsage{OpenAIDecisions: true, TotalTokens: 100, Cost: &schemas.BifrostCost{TotalCost: 0.00001}}}}}
	require.NoError(t, coordinator.Refund(context.Background(), handle, settlement))
	row, err := store.Get(context.Background(), handle.(*durableReservationHandle).rows[0].ID)
	require.NoError(t, err)
	require.Equal(t, reservations.Amount{Tokens: 100, CostMicros: 10}, row.SettledAmount)
}
