package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/fasthttp/router"
	"github.com/google/uuid"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/framework/encrypt"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

// SessionHandler manages HTTP requests for session operations
type SessionHandler struct {
	configStore   configstore.ConfigStore
	wsTicketStore *WSTicketStore
}

// NewSessionHandler creates a new session handler instance
func NewSessionHandler(configStore configstore.ConfigStore, wsTicketStore *WSTicketStore) *SessionHandler {
	return &SessionHandler{
		configStore:   configStore,
		wsTicketStore: wsTicketStore,
	}
}

// RegisterRoutes registers the session-related routes
func (h *SessionHandler) RegisterRoutes(r *router.Router, middlewares ...schemas.BifrostHTTPMiddleware) {
	r.POST("/api/session/login", lib.ChainMiddlewares(h.login, middlewares...))
	r.POST("/api/session/logout", lib.ChainMiddlewares(h.logout, middlewares...))
	r.GET("/api/session/is-auth-enabled", lib.ChainMiddlewares(h.isAuthEnabled, middlewares...))
	r.GET("/api/session/me", lib.ChainMiddlewares(h.me, middlewares...))
	r.GET("/api/session/capabilities", lib.ChainMiddlewares(h.capabilities, middlewares...))
	r.POST("/api/session/ws-ticket", lib.ChainMiddlewares(h.issueWSTicket, middlewares...))
}

// me returns the server-side dashboard session without exposing its bearer
// token.  Keeping this as a dedicated bootstrap endpoint lets the dashboard
// (and a future OIDC callback) establish identity from the HttpOnly cookie
// rather than copying credentials into browser storage.
func (h *SessionHandler) me(ctx *fasthttp.RequestCtx) {
	session, ok := h.sessionForRequest(ctx)
	if !ok {
		SendError(ctx, fasthttp.StatusUnauthorized, "Unauthorized")
		return
	}
	ctx.Response.Header.Set("Cache-Control", "no-store")
	ctx.Response.Header.Set("Pragma", "no-cache")
	SendJSON(ctx, map[string]any{
		"authenticated": true,
		"expires_at":    session.ExpiresAt.UTC().Format(time.RFC3339),
	})
}

// capabilities is a small, versioned contract for dashboard feature gating.
// A capability is true only when this process can actually serve it; unknown
// or unimplemented enterprise surfaces remain false rather than being
// inferred from UI routes.
func (h *SessionHandler) capabilities(ctx *fasthttp.RequestCtx) {
	if _, ok := h.sessionForRequest(ctx); !ok {
		SendError(ctx, fasthttp.StatusUnauthorized, "Unauthorized")
		return
	}
	SendJSON(ctx, map[string]any{
		"version": 1,
		"capabilities": map[string]bool{
			"session_bootstrap": true,
			"governance":        false,
			// Alerting CRUD/history is backed by the same ConfigStore used by
			// this session handler. Advertise it only when that backend exists;
			// otherwise the UI would render a dead feature surface.
			"alerting": h.configStore != nil,
		},
	})
}

func (h *SessionHandler) sessionForRequest(ctx *fasthttp.RequestCtx) (*tables.SessionsTable, bool) {
	if h.configStore == nil {
		return nil, false
	}
	token, _ := ctx.UserValue(schemas.BifrostContextKeySessionToken).(string)
	if token == "" {
		if auth := string(ctx.Request.Header.Peek("Authorization")); strings.HasPrefix(auth, "Bearer ") {
			token = strings.TrimPrefix(auth, "Bearer ")
		}
	}
	if token == "" {
		token = string(ctx.Request.Header.Cookie("token"))
	}
	if token == "" {
		return nil, false
	}
	session, err := h.configStore.GetSession(ctx, token)
	if err != nil || session == nil || !session.ExpiresAt.After(time.Now()) {
		return nil, false
	}
	return session, true
}

// isAuthEnabled handles GET /api/session/is-auth-enabled - Check if auth is enabled
func (h *SessionHandler) isAuthEnabled(ctx *fasthttp.RequestCtx) {
	if h.configStore == nil {
		SendJSON(ctx, map[string]any{
			"is_auth_enabled": false,
			"has_valid_token": false,
			"auth_type":       "none",
		})
		return
	}
	authConfig, err := h.configStore.GetAuthConfig(ctx)
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, fmt.Sprintf("Failed to get auth config: %v", err))
		return
	}
	if authConfig == nil {
		SendJSON(ctx, map[string]any{
			"is_auth_enabled": false,
			"has_valid_token": false,
			"auth_type":       "none",
		})
		return
	}
	// Check if the header has a token and is valid (Authorization header or cookie)
	token := ""
	if authHeader := string(ctx.Request.Header.Peek("Authorization")); strings.HasPrefix(authHeader, "Bearer ") {
		token = strings.TrimPrefix(authHeader, "Bearer ")
	}
	if token == "" {
		token = string(ctx.Request.Header.Cookie("token"))
	}
	hasValidToken := false
	if token != "" {
		session, err := h.configStore.GetSession(ctx, token)
		if err == nil && session != nil && session.ExpiresAt.After(time.Now()) {
			hasValidToken = true
		}
	}
	SendJSON(ctx, map[string]any{
		"is_auth_enabled": authConfig.IsEnabled,
		"has_valid_token": hasValidToken,
		"auth_type":       dashboardAuthType(authConfig.IsEnabled),
	})
}

// dashboardAuthType reports the dashboard session auth mode for frontend flows.
func dashboardAuthType(isEnabled bool) string {
	if isEnabled {
		return "password"
	}
	return "none"
}

// login handles POST /api/session/login - Login a user
func (h *SessionHandler) login(ctx *fasthttp.RequestCtx) {
	if h.configStore == nil {
		SendError(ctx, fasthttp.StatusForbidden, "Authentication is not enabled")
		return
	}
	payload := struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}{}
	if err := json.Unmarshal(ctx.PostBody(), &payload); err != nil {
		SendError(ctx, fasthttp.StatusBadRequest, "Invalid request payload")
		return
	}

	// Get auth config
	authConfig, err := h.configStore.GetAuthConfig(ctx)
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, fmt.Sprintf("Failed to get auth config: %v", err))
		return
	}

	// Check if auth is enabled
	if authConfig == nil || !authConfig.IsEnabled {
		SendError(ctx, fasthttp.StatusForbidden, "Authentication is not enabled")
		return
	}

	// Verify credentials
	if payload.Username != authConfig.AdminUserName.GetValue() {
		SendError(ctx, fasthttp.StatusUnauthorized, "Invalid username or password")
		return
	}
	compare, err := encrypt.CompareHash(authConfig.AdminPassword.GetValue(), payload.Password)
	if err != nil {
		SendError(ctx, fasthttp.StatusUnauthorized, "Unauthorized")
		return
	}
	if !compare {
		SendError(ctx, fasthttp.StatusUnauthorized, "Invalid username or password")
		return
	}

	// Creating a new session
	token := uuid.New().String()
	session := &tables.SessionsTable{
		Token:     token,
		ExpiresAt: time.Now().Add(time.Hour * 24 * 30), // 30 days
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}
	err = h.configStore.CreateSession(ctx, session)
	if err != nil {
		SendError(ctx, fasthttp.StatusInternalServerError, fmt.Sprintf("Failed to create session: %v", err))
		return
	}

	// Setting cookies
	cookie := fasthttp.AcquireCookie()
	defer fasthttp.ReleaseCookie(cookie)
	cookie.SetKey("token")
	cookie.SetValue(token)
	cookie.SetExpire(time.Now().Add(time.Hour * 24 * 30))
	cookie.SetPath("/")
	cookie.SetHTTPOnly(true)
	cookie.SetSameSite(fasthttp.CookieSameSiteLaxMode)
	// Check if source is https then set secure
	if string(ctx.Request.Header.Peek("X-Forwarded-Proto")) == "https" {
		cookie.SetSecure(true)
	}
	ctx.Response.Header.SetCookie(cookie)

	SendJSON(ctx, map[string]any{
		"message": "Login successful",
	})
}

// logout handles POST /api/session/logout - Logout a user
func (h *SessionHandler) logout(ctx *fasthttp.RequestCtx) {
	if h.configStore == nil {
		SendError(ctx, fasthttp.StatusForbidden, "Authentication is not enabled")
		return
	}
	// Get token from Authorization header
	token := string(ctx.Request.Header.Peek("Authorization"))
	token = strings.TrimPrefix(token, "Bearer ")

	// If no token in header, try to get from cookie
	if token == "" {
		token = string(ctx.Request.Header.Cookie("token"))
	}

	// clear token from cookies
	cookie := fasthttp.AcquireCookie()
	defer fasthttp.ReleaseCookie(cookie)
	cookie.SetKey("token")
	cookie.SetValue("")
	cookie.SetExpire(time.Now().Add(-time.Hour * 24 * 30))
	cookie.SetPath("/")
	cookie.SetHTTPOnly(true)
	cookie.SetSameSite(fasthttp.CookieSameSiteLaxMode)
	// Check if source is https then set secure
	if string(ctx.Request.Header.Peek("X-Forwarded-Proto")) == "https" {
		cookie.SetSecure(true)
	}
	ctx.Response.Header.SetCookie(cookie)

	// delete session from database if token exists
	if token != "" {
		err := h.configStore.DeleteSession(ctx, token)
		if err != nil && !errors.Is(err, configstore.ErrNotFound) {
			logger.Error("failed to delete session during logout: %v", err)
			SendError(ctx, fasthttp.StatusInternalServerError, "Failed to invalidate session. Please try again.")
			return
		}
	}

	SendJSON(ctx, map[string]any{
		"message": "Logout successful",
	})
}

// issueWSTicket handles POST /api/session/ws-ticket - Issue a short-lived ticket for WebSocket auth.
// The caller must already be authenticated (via cookie or Authorization header).
// Returns a one-time-use ticket that the frontend passes as ?ticket= when opening the WebSocket.
func (h *SessionHandler) issueWSTicket(ctx *fasthttp.RequestCtx) {
	if h.wsTicketStore == nil {
		SendError(ctx, fasthttp.StatusServiceUnavailable, "WebSocket tickets are not available")
		return
	}
	sessionToken, ok := ctx.UserValue(schemas.BifrostContextKeySessionToken).(string)
	if !ok {
		SendError(ctx, fasthttp.StatusUnauthorized, "Unauthorized")
		return
	}
	if sessionToken == "" {
		// This is the case where auth is not configured or not enabled
		sessionToken = "dummy-session"
	}
	ticket, err := h.wsTicketStore.Issue(sessionToken)
	if err != nil {
		logger.Error("failed to issue WS ticket: %v", err)
		SendError(ctx, fasthttp.StatusInternalServerError, "Failed to issue WebSocket ticket")
		return
	}
	SendJSON(ctx, map[string]any{
		"ticket": ticket,
	})
}
