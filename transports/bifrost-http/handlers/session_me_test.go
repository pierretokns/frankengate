package handlers

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/configstore"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/valyala/fasthttp"
)

type sessionMeStore struct {
	configstore.ConfigStore
	session *tables.SessionsTable
}

func (s *sessionMeStore) GetSession(_ context.Context, _ string) (*tables.SessionsTable, error) {
	return s.session, nil
}

func TestSessionMeRejectsMissingAndExpiredSessions(t *testing.T) {
	for name, store := range map[string]*sessionMeStore{
		"missing": {session: nil},
		"expired": {session: &tables.SessionsTable{ExpiresAt: time.Now().Add(-time.Minute)}},
	} {
		t.Run(name, func(t *testing.T) {
			h := NewSessionHandler(store, nil)
			ctx := &fasthttp.RequestCtx{}
			ctx.Request.Header.SetCookie("token", "stale")
			h.me(ctx)
			if ctx.Response.StatusCode() != fasthttp.StatusUnauthorized {
				t.Fatalf("status = %d, want %d", ctx.Response.StatusCode(), fasthttp.StatusUnauthorized)
			}
		})
	}
}

func TestSessionMeReturnsSafeBootstrapPayload(t *testing.T) {
	h := NewSessionHandler(&sessionMeStore{session: &tables.SessionsTable{ExpiresAt: time.Now().Add(time.Hour)}}, nil)
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetCookie("token", "valid")
	h.me(ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusOK {
		t.Fatalf("status = %d, want %d", ctx.Response.StatusCode(), fasthttp.StatusOK)
	}
	var payload map[string]any
	if err := json.Unmarshal(ctx.Response.Body(), &payload); err != nil {
		t.Fatal(err)
	}
	if payload["authenticated"] != true {
		t.Fatalf("authenticated = %#v, want true", payload["authenticated"])
	}
	if _, leaked := payload["token"]; leaked {
		t.Fatal("bootstrap payload must not expose the session token")
	}
}
