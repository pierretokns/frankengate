package governance

import (
	"context"
	"sync/atomic"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

func TestEvaluateGovernanceRequest_DeniesVirtualKeyWhenAuthorityIsStale(t *testing.T) {
	logger := NewMockLogger()
	vk := buildVirtualKeyWithProviders("vk1", "sk-bf-stale", "Stale VK", nil)
	store, err := NewLocalGovernanceStore(context.Background(), logger, nil, &configstore.GovernanceConfig{
		VirtualKeys: []configstoreTables.TableVirtualKey{*vk},
	}, nil)
	require.NoError(t, err)

	plugin := &GovernancePlugin{
		store:    store,
		resolver: NewBudgetResolver(store, nil, logger, nil),
	}
	var fresh atomic.Bool
	plugin.SetAuthorityFreshnessSource(AuthorityFreshnessFunc(fresh.Load))

	result, bifrostErr := plugin.EvaluateGovernanceRequest(
		schemas.NewBifrostContext(context.Background(), schemas.NoDeadline),
		&EvaluationRequest{VirtualKey: "sk-bf-stale", Provider: schemas.OpenAI, Model: "gpt-4"},
		schemas.ChatCompletionRequest,
	)

	require.NotNil(t, result)
	require.Equal(t, DecisionVirtualKeyAuthorityStale, result.Decision)
	require.Equal(t, VirtualKeyAuthorityStaleReason, result.Reason)
	require.NotNil(t, bifrostErr)
	require.Equal(t, string(DecisionVirtualKeyAuthorityStale), *bifrostErr.Type)
	require.Equal(t, 503, *bifrostErr.StatusCode)
	require.Equal(t, VirtualKeyAuthorityStaleReason, bifrostErr.Error.Message)
}

func TestEvaluateGovernanceRequest_StaleAuthorityDoesNotAffectNonVirtualKeyTraffic(t *testing.T) {
	logger := NewMockLogger()
	store, err := NewLocalGovernanceStore(context.Background(), logger, nil, &configstore.GovernanceConfig{}, nil)
	require.NoError(t, err)
	plugin := &GovernancePlugin{
		store:    store,
		resolver: NewBudgetResolver(store, nil, logger, nil),
	}
	plugin.SetAuthorityFreshnessSource(AuthorityFreshnessFunc(func() bool { return false }))

	result, bifrostErr := plugin.EvaluateGovernanceRequest(
		schemas.NewBifrostContext(context.Background(), schemas.NoDeadline),
		&EvaluationRequest{Provider: schemas.OpenAI, Model: "gpt-4"},
		schemas.ChatCompletionRequest,
	)

	require.Nil(t, bifrostErr)
	require.Equal(t, DecisionAllow, result.Decision)
}

func TestEvaluateGovernanceRequest_AllowsVirtualKeyWhenAuthorityRecovers(t *testing.T) {
	logger := NewMockLogger()
	vk := buildVirtualKeyWithProviders("vk1", "sk-bf-fresh", "Fresh VK", []configstoreTables.TableVirtualKeyProviderConfig{
		buildProviderConfig("openai", []string{"gpt-4"}),
	})
	store, err := NewLocalGovernanceStore(context.Background(), logger, nil, &configstore.GovernanceConfig{
		VirtualKeys: []configstoreTables.TableVirtualKey{*vk},
	}, nil)
	require.NoError(t, err)
	plugin := &GovernancePlugin{
		store:    store,
		resolver: NewBudgetResolver(store, nil, logger, nil),
	}
	var fresh atomic.Bool
	plugin.SetAuthorityFreshnessSource(AuthorityFreshnessFunc(fresh.Load))
	fresh.Store(true)

	result, bifrostErr := plugin.EvaluateGovernanceRequest(
		schemas.NewBifrostContext(context.Background(), schemas.NoDeadline),
		&EvaluationRequest{VirtualKey: "sk-bf-fresh", Provider: schemas.OpenAI, Model: "gpt-4"},
		schemas.ChatCompletionRequest,
	)

	require.Nil(t, bifrostErr)
	require.Equal(t, DecisionAllow, result.Decision)
}

func TestPreMCPHook_DeniesNonExecuteRequestWithVirtualKeyWhenAuthorityIsStale(t *testing.T) {
	plugin := &GovernancePlugin{}
	plugin.SetAuthorityFreshnessSource(AuthorityFreshnessFunc(func() bool { return false }))
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyVirtualKey, "sk-bf-stale")
	req := &schemas.BifrostMCPRequest{RequestType: schemas.MCPRequestTypeListTools}

	_, shortCircuit, err := plugin.PreMCPHook(ctx, req)
	require.NoError(t, err)
	require.NotNil(t, shortCircuit)
	require.NotNil(t, shortCircuit.Error)
	require.Equal(t, 503, *shortCircuit.Error.StatusCode)
	require.Equal(t, string(DecisionVirtualKeyAuthorityStale), *shortCircuit.Error.Type)
}

func TestPreMCPConnectionHook_DeniesBeforeReadingStaleVirtualKeyCache(t *testing.T) {
	plugin := &GovernancePlugin{}
	plugin.SetAuthorityFreshnessSource(AuthorityFreshnessFunc(func() bool { return false }))
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyVirtualKey, "sk-bf-stale")
	req := &schemas.BifrostMCPConnectRequest{ClientName: "internal-tools"}

	_, shortCircuit, err := plugin.PreMCPConnectionHook(ctx, req)
	require.NoError(t, err)
	require.NotNil(t, shortCircuit)
	require.NotNil(t, shortCircuit.Error)
	require.Equal(t, 503, *shortCircuit.Error.StatusCode)
	require.Equal(t, string(DecisionVirtualKeyAuthorityStale), *shortCircuit.Error.Type)
}
