package handlers

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/valyala/fasthttp"
)

type sessionMeConfigStore struct {
	configstore.ConfigStore
	session *tables.SessionsTable
}

func (s *sessionMeConfigStore) GetSession(context.Context, string) (*tables.SessionsTable, error) {
	return s.session, nil
}

func TestSessionMeUsesServerSessionWithoutExposingToken(t *testing.T) {
	token := "must-not-appear"
	h := &SessionHandler{configStore: &sessionMeConfigStore{session: &tables.SessionsTable{Token: token, ExpiresAt: time.Now().Add(time.Hour)}}}
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetCookie("token", token)

	h.me(ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusOK {
		t.Fatalf("status = %d, want %d", ctx.Response.StatusCode(), fasthttp.StatusOK)
	}
	body := string(ctx.Response.Body())
	if strings.Contains(body, token) {
		t.Fatalf("session token leaked in response: %s", body)
	}
	if !strings.Contains(body, `"authenticated":true`) {
		t.Fatalf("response = %s, want authenticated session", body)
	}
	if got := string(ctx.Response.Header.Peek("Cache-Control")); got != "no-store" {
		t.Fatalf("Cache-Control = %q, want no-store", got)
	}
}

func TestSessionMeRejectsExpiredOrMissingSession(t *testing.T) {
	for name, store := range map[string]*sessionMeConfigStore{
		"missing": {session: nil},
		"expired": {session: &tables.SessionsTable{ExpiresAt: time.Now().Add(-time.Minute)}},
	} {
		t.Run(name, func(t *testing.T) {
			h := &SessionHandler{configStore: store}
			ctx := &fasthttp.RequestCtx{}
			ctx.Request.Header.SetCookie("token", "token")
			h.me(ctx)
			if ctx.Response.StatusCode() != fasthttp.StatusUnauthorized {
				t.Fatalf("status = %d, want %d", ctx.Response.StatusCode(), fasthttp.StatusUnauthorized)
			}
		})
	}
}

func TestSessionCapabilitiesFailClosedAndExposeVersionedContract(t *testing.T) {
	h := &SessionHandler{configStore: &sessionMeConfigStore{session: &tables.SessionsTable{ExpiresAt: time.Now().Add(time.Hour)}}}
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetCookie("token", "token")
	h.capabilities(ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusOK {
		t.Fatalf("status = %d, want %d", ctx.Response.StatusCode(), fasthttp.StatusOK)
	}
	body := string(ctx.Response.Body())
	for _, want := range []string{`"version":1`, `"session_bootstrap":true`, `"governance":false`, `"alerting":true`, `"dashboard_oidc":false`, `"scim_entitlements":false`, `"analytics_replay":false`} {
		if !strings.Contains(body, want) {
			t.Fatalf("response = %s, missing %s", body, want)
		}
	}

	unauthenticated := &SessionHandler{configStore: &sessionMeConfigStore{session: nil}}
	ctx = &fasthttp.RequestCtx{}
	unauthenticated.capabilities(ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusUnauthorized {
		t.Fatalf("unauthenticated status = %d, want %d", ctx.Response.StatusCode(), fasthttp.StatusUnauthorized)
	}
}

type loginDecodeConfigStore struct {
	configstore.ConfigStore
}

func TestSessionLoginInvalidPayloadDoesNotExposeDecoderDetails(t *testing.T) {
	h := &SessionHandler{configStore: &loginDecodeConfigStore{}}
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.SetBodyString(`{"username":1234,"password":"Suresh"}`)

	h.login(ctx)

	body := string(ctx.Response.Body())
	if ctx.Response.StatusCode() != fasthttp.StatusBadRequest {
		t.Fatalf("status = %d, want %d; body=%s", ctx.Response.StatusCode(), fasthttp.StatusBadRequest, body)
	}
	if !strings.Contains(body, "Invalid request payload") {
		t.Fatalf("body = %s, want generic invalid payload message", body)
	}
	if strings.Contains(body, "cannot unmarshal") || strings.Contains(body, "username") || strings.Contains(body, "Go struct field") {
		t.Fatalf("body exposes decoder internals: %s", body)
	}
}

func TestPrepareRequestInvalidPayloadDoesNotExposeDecoderDetails(t *testing.T) {
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.SetBodyString(`{"model":1234,"prompt":"hello"}`)

	_, _, err := prepareRequest[TextRequest](ctx, nil, nil)
	if err == nil {
		t.Fatal("expected error for invalid payload")
	}
	msg := err.Error()
	if msg != "Invalid request payload" {
		t.Fatalf("error = %q, want generic invalid payload message", msg)
	}
	if strings.Contains(msg, "cannot unmarshal") || strings.Contains(msg, "model") || strings.Contains(msg, "Go struct field") {
		t.Fatalf("error exposes decoder internals: %s", msg)
	}
}
