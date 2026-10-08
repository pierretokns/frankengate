package integrations

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"sync/atomic"
	"testing"

	"github.com/fasthttp/router"
	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	tables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/plugins/governance"
	"github.com/stretchr/testify/require"
	"github.com/valyala/fasthttp"
)

type decisionsAccount struct{ baseURL string }

func (a decisionsAccount) GetConfiguredProviders() ([]schemas.ModelProvider, error) {
	return []schemas.ModelProvider{schemas.OpenAI}, nil
}
func (a decisionsAccount) GetKeysForProvider(context.Context, schemas.ModelProvider) ([]schemas.Key, error) {
	return []schemas.Key{{ID: "local", Value: *schemas.NewSecretVar("test-only"), Models: schemas.WhiteList{"gpt-6-luna"}, Weight: 1}}, nil
}
func (a decisionsAccount) GetConfigForProvider(schemas.ModelProvider) (*schemas.ProviderConfig, error) {
	return &schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{BaseURL: a.baseURL, AllowPrivateNetwork: true, DefaultRequestTimeoutInSeconds: 1, MaxRetries: 0}, ConcurrencyAndBufferSize: schemas.ConcurrencyAndBufferSize{Concurrency: 1, BufferSize: 8}}, nil
}

type decisionsProbe struct {
	pre, post atomic.Int32
	t         *testing.T
}

func (*decisionsProbe) GetName() string { return "decisions-test-probe" }
func (*decisionsProbe) Cleanup() error  { return nil }
func (*decisionsProbe) PreRequestHook(*schemas.BifrostContext, *schemas.BifrostRequest) error {
	return nil
}
func (p *decisionsProbe) PreLLMHook(ctx *schemas.BifrostContext, req *schemas.BifrostRequest) (*schemas.BifrostRequest, *schemas.LLMPluginShortCircuit, error) {
	p.pre.Add(1)
	if req.RequestType != schemas.PassthroughRequest || req.PassthroughRequest.Model != "gpt-6-luna" || ctx.Value(schemas.BifrostContextKeySuppressContentLogging) != true {
		p.t.Error("lost governance model/type or content restriction")
	}
	return req, nil, nil
}
func (p *decisionsProbe) PostLLMHook(_ *schemas.BifrostContext, resp *schemas.BifrostResponse, err *schemas.BifrostError) (*schemas.BifrostResponse, *schemas.BifrostError, error) {
	p.post.Add(1)
	if resp != nil && resp.PassthroughResponse.PassthroughUsage == nil {
		p.t.Error("usage absent before post-hook")
	}
	return resp, err, nil
}

func TestDecisionsGatewayRoutesAndGovernance(t *testing.T) {
	reqBody, err := os.ReadFile("../../../core/providers/openai/testdata/decisions/request.json")
	require.NoError(t, err)
	respBody, err := os.ReadFile("../../../core/providers/openai/testdata/decisions/response.json")
	require.NoError(t, err)
	var calls atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		require.Equal(t, "/v1/decisions", r.URL.Path)
		b, _ := io.ReadAll(r.Body)
		require.Equal(t, string(reqBody), string(b))
		require.Equal(t, "Bearer test-only", r.Header.Get("Authorization"))
		require.Empty(t, r.Header.Get("X-Bf-Vk"))
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(respBody)
	}))
	defer upstream.Close()
	gov, err := governance.Init(context.Background(), &governance.Config{IsVkMandatory: schemas.Ptr(true)}, &testLogger{}, nil, &configstore.GovernanceConfig{VirtualKeys: []tables.TableVirtualKey{{ID: "local-vk", Name: "local", Value: *schemas.NewSecretVar("test-vk"), IsActive: schemas.Ptr(true), ProviderConfigs: []tables.TableVirtualKeyProviderConfig{{Provider: "openai", AllowedModels: schemas.WhiteList{"gpt-6-luna"}}}}}}, nil, nil, nil)
	require.NoError(t, err)
	probe := &decisionsProbe{t: t}
	client, err := bifrost.Init(context.Background(), schemas.BifrostConfig{Account: decisionsAccount{upstream.URL}, LLMPlugins: []schemas.LLMPlugin{gov, probe}, Logger: &testLogger{}})
	require.NoError(t, err)
	defer client.Shutdown()
	r := router.New()
	adapter := NewOpenAIDecisionsRouter(client, &mockHandlerStore{}, &testLogger{})
	var middlewareCalls int
	adapter.RegisterRoutes(r, func(next fasthttp.RequestHandler) fasthttp.RequestHandler {
		return func(ctx *fasthttp.RequestCtx) {
			middlewareCalls++
			require.Equal(t, schemas.PassthroughRequest, ctx.UserValue(schemas.BifrostContextKeyHTTPRequestType))
			next(ctx)
		}
	})
	for _, path := range []string{"/v1/decisions", "/openai/v1/decisions", "/openai/decisions"} {
		var ctx fasthttp.RequestCtx
		ctx.Request.Header.SetMethod("POST")
		ctx.Request.SetRequestURI(path)
		ctx.Request.Header.SetContentType("application/json")
		ctx.Request.Header.Set("x-bf-vk", "test-vk")
		ctx.Request.SetBody(reqBody)
		r.Handler(&ctx)
		require.Equal(t, 200, ctx.Response.StatusCode(), string(ctx.Response.Body()))
		require.Equal(t, string(respBody), string(ctx.Response.Body()))
	}
	require.Equal(t, int32(3), calls.Load())
	require.Equal(t, int32(3), probe.pre.Load())
	require.Equal(t, probe.pre.Load(), probe.post.Load())
	require.Equal(t, 3, middlewareCalls)
	for _, key := range []string{"", "invalid-vk"} {
		var ctx fasthttp.RequestCtx
		ctx.Request.Header.SetMethod("POST")
		ctx.Request.SetRequestURI("/v1/decisions")
		ctx.Request.Header.SetContentType("application/json")
		ctx.Request.Header.Set("x-bf-vk", key)
		ctx.Request.SetBody(reqBody)
		r.Handler(&ctx)
		require.GreaterOrEqual(t, ctx.Response.StatusCode(), 400)
	}
	require.Equal(t, int32(3), calls.Load(), "denied virtual keys reached provider")
	for _, header := range []struct{ name, value string }{{"content-type", "text/plain"}, {"x-model-provider", "anthropic"}, {"x-bf-async", "true"}, {"x-bf-async-id", "local-job"}} {
		var ctx fasthttp.RequestCtx
		ctx.Request.Header.SetMethod("POST")
		ctx.Request.SetRequestURI("/v1/decisions")
		ctx.Request.Header.SetContentType("application/json")
		ctx.Request.Header.Set("x-bf-vk", "test-vk")
		ctx.Request.Header.Set(header.name, header.value)
		ctx.Request.SetBody(reqBody)
		r.Handler(&ctx)
		require.Equal(t, 400, ctx.Response.StatusCode())
	}
	require.Equal(t, int32(3), calls.Load(), "unsupported headers reached provider")
}

func TestDecisionsRoutesRetainMiddlewareDenial(t *testing.T) {
	r := router.New()
	NewOpenAIDecisionsRouter(nil, nil, &testLogger{}).RegisterRoutes(r, func(next fasthttp.RequestHandler) fasthttp.RequestHandler {
		return func(ctx *fasthttp.RequestCtx) { ctx.SetStatusCode(403) }
	})
	for _, path := range []string{"/v1/decisions", "/openai/v1/decisions", "/openai/decisions"} {
		var ctx fasthttp.RequestCtx
		ctx.Request.Header.SetMethod("POST")
		ctx.Request.SetRequestURI(path)
		r.Handler(&ctx)
		require.Equal(t, 403, ctx.Response.StatusCode())
	}
}
