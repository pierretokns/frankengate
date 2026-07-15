// Modified by the FrankenGate project: health probe behavior tests.
package handlers

import (
	"testing"

	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/stretchr/testify/require"
	"github.com/valyala/fasthttp"
)

func TestLivezIsProcessOnly(t *testing.T) {
	r := router.New()
	NewHealthHandler(nil).RegisterRoutes(r)

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.SetRequestURI("/livez")
	ctx.Request.Header.SetMethod(fasthttp.MethodGet)
	r.Handler(ctx)

	require.Equal(t, fasthttp.StatusOK, ctx.Response.StatusCode())
	require.JSONEq(t, `{"status":"ok","components":{"process":"alive"}}`, string(ctx.Response.Body()))
}

func TestReadyzUsesDependencyReadinessChecks(t *testing.T) {
	r := router.New()
	NewHealthHandler(&lib.Config{ClientConfig: &configstore.ClientConfig{DisableDBPingsInHealth: true}}).RegisterRoutes(r)

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.SetRequestURI("/readyz")
	ctx.Request.Header.SetMethod(fasthttp.MethodGet)
	r.Handler(ctx)

	require.Equal(t, fasthttp.StatusOK, ctx.Response.StatusCode())
	require.JSONEq(t, `{"status":"ok","components":{"db_pings":"disabled"}}`, string(ctx.Response.Body()))
}

func TestStartupzIsAvailableAfterBootstrap(t *testing.T) {
	r := router.New()
	NewHealthHandler(&lib.Config{ClientConfig: &configstore.ClientConfig{DisableDBPingsInHealth: true}}).RegisterRoutes(r)

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.SetRequestURI("/startupz")
	ctx.Request.Header.SetMethod(fasthttp.MethodGet)
	r.Handler(ctx)

	require.Equal(t, fasthttp.StatusOK, ctx.Response.StatusCode())
}
