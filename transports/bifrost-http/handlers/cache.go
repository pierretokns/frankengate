package handlers

import (
	"fmt"
	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

// CacheClearer is the minimal contract the handler needs from the semantic
// cache plugin. Exported so the server wiring can supply a resolver without
// pulling in the plugin's concrete type and so tests can substitute a fake.
type CacheClearer interface {
	ClearCacheForCacheID(cacheID string) error
	ClearCacheForKey(cacheKey string) error
}

// ScopedCacheClearer is implemented by governed cache plugins.  The legacy
// CacheClearer methods remain available for administrative callers, while a
// request carrying a Bifrost context must use the authority-scoped variant.
type ScopedCacheClearer interface {
	ClearCacheForCacheIDForAuthority(*schemas.BifrostContext, string) error
	ClearCacheForKeyForAuthority(*schemas.BifrostContext, string) error
}

// CacheClearerResolver returns the currently-loaded cache plugin or nil if
// none is loaded. Called on every cache-clear request so plugin lifecycle
// (POST/PUT/DELETE /api/plugins) is honored — without this, the handler
// would hold a stale pointer after a plugin reload and the routes would
// silently misbehave (or never exist at all if the plugin was loaded
// post-boot rather than at startup).
type CacheClearerResolver func() CacheClearer

type CacheHandler struct {
	resolve CacheClearerResolver
}

// currentPlugin resolves the cache plugin defensively.  A nil resolver can
// occur during partially initialized server wiring or shutdown; cache admin
// routes must return a normal not-loaded response rather than panic the HTTP
// worker.
func (h *CacheHandler) currentPlugin() CacheClearer {
	if h == nil || h.resolve == nil {
		return nil
	}
	return h.resolve()
}

// NewCacheHandler returns a CacheHandler that resolves the current plugin
// at request time. The handler is safe to wire unconditionally — when no
// plugin is loaded, each cache-clear request returns HTTP 400 with a clear
// message rather than the route being absent (HTTP 405).
func NewCacheHandler(resolve CacheClearerResolver) *CacheHandler {
	return &CacheHandler{resolve: resolve}
}

func (h *CacheHandler) RegisterRoutes(r *router.Router, middlewares ...schemas.BifrostHTTPMiddleware) {
	r.DELETE("/api/cache/clear/{cacheId}", lib.ChainMiddlewares(h.clearCache, middlewares...))
	r.DELETE("/api/cache/clear-by-key/{cacheKey}", lib.ChainMiddlewares(h.clearCacheByKey, middlewares...))
}

func (h *CacheHandler) clearCache(ctx *fasthttp.RequestCtx) {
	plugin := h.currentPlugin()
	if plugin == nil {
		SendError(ctx, fasthttp.StatusBadRequest, "semantic_cache plugin is not loaded")
		return
	}
	cacheID, ok := ctx.UserValue("cacheId").(string)
	if !ok || cacheID == "" {
		SendError(ctx, fasthttp.StatusBadRequest, "Invalid cache ID")
		return
	}
	var err error
	usedScoped := false
	if scoped, ok := plugin.(ScopedCacheClearer); ok {
		if bifrostCtx, ok := ctx.UserValue(lib.FastHTTPUserValueBifrostContext).(*schemas.BifrostContext); ok && bifrostCtx != nil {
			usedScoped = true
			err = scoped.ClearCacheForCacheIDForAuthority(bifrostCtx, cacheID)
		}
	}
	if err == nil && !usedScoped {
		// A context-less request is an administrative operation and retains the
		// legacy behavior for compatibility with existing deployments.
		if _, governed := ctx.UserValue(lib.FastHTTPUserValueBifrostContext).(*schemas.BifrostContext); !governed {
			err = plugin.ClearCacheForCacheID(cacheID)
		} else {
			err = fmt.Errorf("governed cache clearer is unavailable")
		}
	}
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, "Failed to clear cache")
		return
	}

	SendJSON(ctx, map[string]any{
		"message": "Cache cleared successfully",
	})
}

func (h *CacheHandler) clearCacheByKey(ctx *fasthttp.RequestCtx) {
	plugin := h.currentPlugin()
	if plugin == nil {
		SendError(ctx, fasthttp.StatusBadRequest, "semantic_cache plugin is not loaded")
		return
	}
	cacheKey, ok := ctx.UserValue("cacheKey").(string)
	if !ok {
		SendError(ctx, fasthttp.StatusBadRequest, "Invalid cache key")
		return
	}
	var err error
	usedScoped := false
	if scoped, ok := plugin.(ScopedCacheClearer); ok {
		if bifrostCtx, ok := ctx.UserValue(lib.FastHTTPUserValueBifrostContext).(*schemas.BifrostContext); ok && bifrostCtx != nil {
			usedScoped = true
			err = scoped.ClearCacheForKeyForAuthority(bifrostCtx, cacheKey)
		}
	}
	if err == nil && !usedScoped {
		if _, governed := ctx.UserValue(lib.FastHTTPUserValueBifrostContext).(*schemas.BifrostContext); !governed {
			err = plugin.ClearCacheForKey(cacheKey)
		} else {
			err = fmt.Errorf("governed cache clearer is unavailable")
		}
	}
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, "Failed to clear cache")
		return
	}

	SendJSON(ctx, map[string]any{
		"message": "Cache cleared successfully",
	})
}
