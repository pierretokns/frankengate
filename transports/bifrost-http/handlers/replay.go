package handlers

// Replay routes expose durable OTEL evidence without making the replay store
// itself an HTTP concern. Authentication and authorization are supplied by the
// server middleware chain; this handler adds a mandatory tenant partition and
// never returns trace content (including when the durable store was configured
// to retain it for offline operators).

import (
	"context"
	"strconv"
	"strings"
	"time"

	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/plugins/otel"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

const replayHTTPMaxLimit = 100

type ReplayHandler struct{ store otel.ReplayStore }

func NewReplayHandler(store otel.ReplayStore) *ReplayHandler {
	return &ReplayHandler{store: store}
}

func (h *ReplayHandler) RegisterRoutes(r *router.Router, middlewares ...schemas.BifrostHTTPMiddleware) {
	if h == nil || h.store == nil {
		return
	}
	r.GET("/api/replays", lib.ChainMiddlewares(h.list, middlewares...))
}

func (h *ReplayHandler) list(ctx *fasthttp.RequestCtx) {
	tenant := strings.TrimSpace(string(ctx.QueryArgs().Peek("tenant_id")))
	if tenant == "" {
		SendError(ctx, fasthttp.StatusBadRequest, "tenant_id is required")
		return
	}
	// A trusted JWT principal constrains the tenant independently of the
	// caller-controlled query string. Local-admin/session compatibility is
	// preserved by the auth middleware, but a principal-bearing request can
	// never enumerate another tenant's replay metadata.
	if principal, ok := ctx.UserValue(schemas.BifrostContextKeyAuthorizationPrincipal).(authorityepoch.Principal); ok {
		if strings.TrimSpace(principal.Tenant) == "" || principal.Tenant != tenant {
			SendError(ctx, fasthttp.StatusForbidden, "replay tenant is not authorized")
			return
		}
	}
	limit := 50
	if raw := string(ctx.QueryArgs().Peek("limit")); raw != "" {
		parsed, err := strconv.Atoi(raw)
		if err != nil || parsed < 1 || parsed > replayHTTPMaxLimit {
			SendError(ctx, fasthttp.StatusBadRequest, "limit must be between 1 and 100")
			return
		}
		limit = parsed
	}
	requestCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	rows, err := h.store.List(requestCtx, tenant, limit)
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, "replay listing failed")
		return
	}
	// Metadata-only responses are intentional. A replay may have content
	// enabled for offline workflows, but the dashboard/API never returns it.
	type replaySummary struct {
		SchemaVersion    int                           `json:"schema_version"`
		TraceID          string                        `json:"trace_id"`
		RequestID        string                        `json:"request_id,omitempty"`
		TenantID         string                        `json:"tenant_id"`
		CapturedAt       time.Time                     `json:"captured_at"`
		ContentSHA256    string                        `json:"content_sha256"`
		ContentRedacted  bool                          `json:"content_redacted"`
		RetrievalQuality *otel.RetrievalQualitySummary `json:"retrieval_quality,omitempty"`
	}
	out := make([]replaySummary, 0, len(rows))
	for _, row := range rows {
		// The store is tenant partitioned; retain a defensive check at the HTTP
		// boundary in case a custom implementation violates that contract.
		if row.TenantID != tenant {
			continue
		}
		out = append(out, replaySummary{SchemaVersion: row.SchemaVersion, TraceID: row.TraceID, RequestID: row.RequestID, TenantID: row.TenantID, CapturedAt: row.CapturedAt, ContentSHA256: row.ContentSHA256, ContentRedacted: true, RetrievalQuality: row.RetrievalQuality})
	}
	SendJSON(ctx, map[string]any{"tenant_id": tenant, "records": out, "content_redacted": true})
}
