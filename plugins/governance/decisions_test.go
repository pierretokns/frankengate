package governance

import (
	"context"
	"os"
	"path/filepath"
	"testing"

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
