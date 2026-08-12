// Modified by the FrankenGate project to separate process liveness from dependency readiness.
package handlers

import (
	"context"
	"sync"
	"time"

	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

// HealthHandler manages HTTP requests for health checks.
type HealthHandler struct {
	config         *lib.Config
	readinessCheck func() bool
	a2aPushHealth  func() any
}

// SetA2APushHealth adds a redacted push-runtime component to health responses.
// It is intentionally separate from liveness and does not expose credentials,
// destinations, tenant IDs, or payload data.
func (h *HealthHandler) SetA2APushHealth(check func() any) {
	h.a2aPushHealth = check
}

// NewHealthHandler creates a new health handler instance.
func NewHealthHandler(config *lib.Config) *HealthHandler {
	return &HealthHandler{
		config: config,
	}
}

// SetReadinessCheck installs the process-local readiness gate. Liveness and
// dependency health remain independent; callers use this for gates such as a
// completed authority snapshot and a fresh durable outbox consumer.
func (h *HealthHandler) SetReadinessCheck(check func() bool) {
	h.readinessCheck = check
}

// RegisterRoutes registers the health-related routes.
func (h *HealthHandler) RegisterRoutes(r *router.Router, middlewares ...schemas.BifrostHTTPMiddleware) {
	r.GET("/health", lib.ChainMiddlewares(h.getHealth, middlewares...))
	r.GET("/livez", lib.ChainMiddlewares(h.getLiveness, middlewares...))
	r.GET("/readyz", lib.ChainMiddlewares(h.getHealth, middlewares...))
	r.GET("/startupz", lib.ChainMiddlewares(h.getHealth, middlewares...))
}

// getLiveness reports only whether the gateway process can serve HTTP. It must
// never probe external dependencies: Kubernetes uses failure here as a signal
// to restart the process.
func (h *HealthHandler) getLiveness(ctx *fasthttp.RequestCtx) {
	SendJSON(ctx, map[string]any{"status": "ok", "components": map[string]any{"process": "alive"}})
}

// getHealth handles GET /api/health - Get the health status of the server.
func (h *HealthHandler) getHealth(ctx *fasthttp.RequestCtx) {
	if string(ctx.Path()) == "/readyz" && h.readinessCheck != nil && !h.readinessCheck() {
		SendError(ctx, fasthttp.StatusServiceUnavailable, "authority readiness gate is not satisfied")
		return
	}
	// If DB pings are disabled, just return OK
	components := map[string]any{}
	if h.a2aPushHealth != nil {
		components["a2a_push"] = h.a2aPushHealth()
	}
	if h.config.ClientConfig.DisableDBPingsInHealth {
		components["db_pings"] = "disabled"
		SendJSON(ctx, map[string]any{"status": "ok", "components": components})
		return
	}
	// Pinging config store
	reqCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	var errors []string
	var mu sync.Mutex
	var wg sync.WaitGroup

	if h.config.ConfigStore != nil {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := h.config.ConfigStore.Ping(reqCtx); err != nil {
				mu.Lock()
				errors = append(errors, "config store not available")
				mu.Unlock()
			}
		}()
	}

	// Pinging log store
	if h.config.LogsStore != nil {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := h.config.LogsStore.Ping(reqCtx); err != nil {
				mu.Lock()
				errors = append(errors, "log store not available")
				mu.Unlock()
			}
		}()
	}

	// Pinging vector store
	if h.config.VectorStore != nil {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := h.config.VectorStore.Ping(reqCtx); err != nil {
				mu.Lock()
				errors = append(errors, "vector store not available")
				mu.Unlock()
			}
		}()
	}

	wg.Wait()

	if len(errors) > 0 {
		SendError(ctx, fasthttp.StatusServiceUnavailable, errors[0])
		return
	}
	components["db_pings"] = "ok"
	SendJSON(ctx, map[string]any{"status": "ok", "components": components})
}
