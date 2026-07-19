package governance

import (
	"context"
	"sync/atomic"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/stretchr/testify/require"
)

func TestValidatePrincipalEpochUsesFencedLocalRegistry(t *testing.T) {
	principal := authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer-a", Subject: "user-a"}
	registry := authorityepoch.NewRegistry()
	require.NoError(t, registry.Activate(principal, 7))
	ref := authorityepoch.Reference{Principal: principal, Epoch: 7, Kind: authorityepoch.ArtifactUnary, ID: "req-1"}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	require.NoError(t, schemas.SetAuthorizationEpochReference(ctx, ref))

	plugin := &GovernancePlugin{isEnterprise: true}
	plugin.SetPrincipalAuthorityRegistry(registry)
	require.Nil(t, plugin.validatePrincipalEpoch(ctx, "user-a"))

	stale := ref
	stale.Epoch = 6
	ctx = schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	require.NoError(t, schemas.SetAuthorizationEpochReference(ctx, stale))
	err := plugin.validatePrincipalEpoch(ctx, "user-a")
	require.NotNil(t, err)
	require.Equal(t, "authorization_epoch_invalid", *err.Type)
}

func TestRateLimitRetryAfterSecondsRoundsUpToResetBoundary(t *testing.T) {
	d := "30s"
	limit := &configstoreTables.TableRateLimit{RequestResetDuration: &d, RequestLastReset: time.Now().Add(-29 * time.Second)}
	got := rateLimitRetryAfterSeconds(limit)
	require.GreaterOrEqual(t, got, 1)
	require.LessOrEqual(t, got, 2)
}

func TestRateLimitRetryAfterSecondsUsesRequestWindow(t *testing.T) {
	d := "1m"
	limit := &configstoreTables.TableRateLimit{RequestResetDuration: &d, RequestLastReset: time.Now().Add(-59 * time.Second)}
	got := rateLimitRetryAfterSeconds(limit)
	require.GreaterOrEqual(t, got, 1)
	require.LessOrEqual(t, got, 2)
}

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

func TestPreMCPHookRejectsStalePrincipalBeforeToolResolution(t *testing.T) {
	principal := authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer-a", Subject: "user-a"}
	registry := authorityepoch.NewRegistry()
	require.NoError(t, registry.Activate(principal, 9))
	ref := authorityepoch.Reference{Principal: principal, Epoch: 8, Kind: authorityepoch.ArtifactUnary, ID: "mcp-1"}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	ctx.SetValue(schemas.BifrostContextKeyUserID, "user-a")
	require.NoError(t, schemas.SetAuthorizationEpochReference(ctx, ref))
	plugin := &GovernancePlugin{isEnterprise: true}
	plugin.SetPrincipalAuthorityRegistry(registry)

	_, shortCircuit, err := plugin.PreMCPHook(ctx, &schemas.BifrostMCPRequest{
		RequestType: schemas.MCPRequestTypeExecuteTool,
	})
	require.NoError(t, err)
	require.NotNil(t, shortCircuit)
	require.Equal(t, "authorization_epoch_invalid", *shortCircuit.Error.Type)
	require.Equal(t, 401, *shortCircuit.Error.StatusCode)
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
