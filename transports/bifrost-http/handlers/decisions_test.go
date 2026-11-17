package handlers

import (
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/tracing"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/stretchr/testify/require"
	"github.com/valyala/fasthttp"
)

func TestDecisionsHTTPPrivacy(t *testing.T) {
	for _, path := range []string{"/v1/decisions", "/openai/v1/decisions", "/openai/decisions", "/openai/v1/chat/completions"} {
		t.Run(path, func(t *testing.T) {
			logger := &captureLogger{}
			SetLogger(logger)
			defer SetLogger(&mockLogger{})
			cors := NewCorsMiddleware(&lib.Config{ClientConfig: &configstore.ClientConfig{DumpErrorsInConsoleLogs: true}}).Middleware()
			store := tracing.NewTraceStore(time.Minute, nil)
			defer store.Stop()
			tracer := tracing.NewTracer(store, nil, nil)
			defer tracer.Stop()
			ctx := &fasthttp.RequestCtx{}
			ctx.Request.SetRequestURI(path + "?evidence=PRIVATE_QUERY_SENTINEL")
			ctx.Request.Header.SetMethod("POST")
			cors(NewTracingMiddleware(tracer).Middleware()(func(ctx *fasthttp.RequestCtx) {
				id, _ := ctx.UserValue(schemas.BifrostContextKeyTraceID).(string)
				trace := store.GetTrace(id)
				require.NotNil(t, trace)
				require.NotNil(t, trace.RootSpan)
				if path != "/openai/v1/chat/completions" {
					require.Equal(t, path, trace.RootSpan.Name)
					require.Equal(t, path, trace.RootSpan.Attributes["http.url"])
				} else {
					require.Contains(t, trace.RootSpan.Name, "PRIVATE_QUERY_SENTINEL")
				}
				// Also covers errors returned before the Decisions router/core runs.
				ctx.SetStatusCode(429)
				ctx.Response.SetBodyString(`{"error":{"message":"PRIVATE_EVIDENCE_SENTINEL"}}`)
			}))(ctx)
			require.Len(t, logger.events, 1)
			fields := logger.events[0].strFields
			if path != "/openai/v1/chat/completions" {
				require.Equal(t, path, fields["http.target"])
				require.Empty(t, fields["http.error"])
			} else {
				require.Contains(t, fields["http.target"], "PRIVATE_QUERY_SENTINEL")
				require.Contains(t, fields["http.error"], "PRIVATE_EVIDENCE_SENTINEL")
			}
			require.Equal(t, 429, ctx.Response.StatusCode())
			require.Contains(t, string(ctx.Response.Body()), "PRIVATE_EVIDENCE_SENTINEL", "upstream wire error remains available to the caller")
		})
	}
}
