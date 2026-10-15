package integrations

import (
	"strings"

	"github.com/fasthttp/router"
	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/providers/openai"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

// OpenAIDecisionsRouter provides validated native wire compatibility using the
// existing passthrough policy/queue/key/timeout pipeline. It deliberately does
// not translate to chat, Responses, or TypeSafe decisions.
type OpenAIDecisionsRouter struct{ *GenericRouter }

// IsOpenAIDecisionsHTTPPath also identifies rejected requests before the router
// runs, so outer access logs and root spans can suppress private query/error
// content regardless of which middleware returns the response.
func IsOpenAIDecisionsHTTPPath(path string) bool {
	return path == "/v1/decisions" || path == "/openai/v1/decisions" || path == "/openai/decisions"
}

func NewOpenAIDecisionsRouter(client *bifrost.Bifrost, store lib.HandlerStore, logger schemas.Logger) *OpenAIDecisionsRouter {
	return &OpenAIDecisionsRouter{NewGenericRouter(client, store, nil, &PassthroughConfig{
		Provider: schemas.OpenAI, StripPrefix: []string{"/openai"},
	}, logger)}
}

func (g *OpenAIDecisionsRouter) RegisterRoutes(r *router.Router, middlewares ...schemas.BifrostHTTPMiddleware) {
	markType := func(next fasthttp.RequestHandler) fasthttp.RequestHandler {
		return func(ctx *fasthttp.RequestCtx) {
			ctx.SetUserValue(schemas.BifrostContextKeyHTTPRequestType, schemas.PassthroughRequest)
			next(ctx)
		}
	}
	chain := append([]schemas.BifrostHTTPMiddleware{markType}, middlewares...)
	for _, path := range []string{"/v1/decisions", "/openai/v1/decisions", "/openai/decisions"} {
		r.POST(path, lib.ChainMiddlewares(g.handleDecisions, chain...))
	}
}

func (g *OpenAIDecisionsRouter) handleDecisions(ctx *fasthttp.RequestCtx) {
	contentType := strings.Split(string(ctx.Request.Header.ContentType()), ";")[0]
	async := len(ctx.Request.Header.Peek("x-bf-async")) != 0 || len(ctx.Request.Header.Peek("x-bf-async-id")) != 0 || len(ctx.Request.Header.Peek("x-bf-async-job-result-ttl")) != 0
	if async || strings.TrimSpace(strings.ToLower(contentType)) != "application/json" || getProviderFromHeader(ctx, schemas.OpenAI) != schemas.OpenAI {
		bctx, cancel := lib.ConvertToBifrostContext(ctx, g.handlerStore)
		defer cancel()
		g.sendError(ctx, bctx, func(_ *schemas.BifrostContext, err *schemas.BifrostError) interface{} { return err },
			openai.DecisionsGatewayError("decisions requires synchronous application/json and the openai provider", fasthttp.StatusBadRequest))
		return
	}
	g.handlePassthrough(ctx)
}
