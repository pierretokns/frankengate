package handlers

import (
	"context"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/plugins/otel"
	"github.com/valyala/fasthttp"
)

type replayListFake struct {
	rows   []otel.ReplayRecord
	tenant string
}

func (f *replayListFake) Put(context.Context, *schemas.Trace) error { return nil }
func (f *replayListFake) Get(context.Context, string, string) (*otel.ReplayRecord, error) {
	return nil, nil
}
func (f *replayListFake) List(_ context.Context, tenant string, _ int) ([]otel.ReplayRecord, error) {
	f.tenant = tenant
	return f.rows, nil
}
func (f *replayListFake) Close() error { return nil }

func TestReplayHandlerRequiresTenantAndRedactsTrace(t *testing.T) {
	fake := &replayListFake{rows: []otel.ReplayRecord{{SchemaVersion: 1, TraceID: "a", TenantID: "acme", CapturedAt: time.Unix(1, 0), Trace: &schemas.Trace{TraceID: "a"}}, {TraceID: "other", TenantID: "other"}}}
	h := NewReplayHandler(fake)
	var missing fasthttp.Request
	missing.SetRequestURI("/api/replays")
	missing.Header.SetMethod(fasthttp.MethodGet)
	var missingCtx fasthttp.RequestCtx
	missingCtx.Init(&missing, &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 12345}, nil)
	h.list(&missingCtx)
	if missingCtx.Response.StatusCode() != fasthttp.StatusBadRequest {
		t.Fatalf("missing tenant status=%d", missingCtx.Response.StatusCode())
	}
	var req fasthttp.Request
	req.SetRequestURI("/api/replays?tenant_id=acme&limit=2")
	req.Header.SetMethod(fasthttp.MethodGet)
	var ctx fasthttp.RequestCtx
	ctx.Init(&req, &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 12345}, nil)
	h.list(&ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusOK {
		t.Fatalf("status=%d body=%s", ctx.Response.StatusCode(), ctx.Response.Body())
	}
	if fake.tenant != "acme" {
		t.Fatalf("store called with tenant %q", fake.tenant)
	}
	if string(ctx.Response.Body()) == "" || string(ctx.Response.Body()) == "{}" {
		t.Fatal("expected response body")
	}
	if strings.Contains(string(ctx.Response.Body()), "secret") || !strings.Contains(string(ctx.Response.Body()), "content_redacted") {
		t.Fatalf("response leaked content or redaction marker: %s", ctx.Response.Body())
	}
}

func TestReplayHandlerSummaryShape(t *testing.T) {
	// Keep the authorization invariant at the store boundary as well: a custom
	// implementation may return mixed tenants, but the HTTP response filters it.
	fake := &replayListFake{rows: []otel.ReplayRecord{{SchemaVersion: 1, TraceID: "a", TenantID: "acme", ContentSHA256: strings.Repeat("a", 64), CapturedAt: time.Unix(1, 0), Trace: &schemas.Trace{TraceID: "secret"}}, {TraceID: "x", TenantID: "other"}}}
	if _, err := fake.List(context.Background(), "acme", 2); err != nil {
		t.Fatal(err)
	}
	if fake.tenant != "acme" {
		t.Fatalf("store called with tenant %q", fake.tenant)
	}
}

func TestReplayHandlerRejectsPrincipalTenantMismatch(t *testing.T) {
	fake := &replayListFake{rows: []otel.ReplayRecord{{TenantID: "other", TraceID: "secret"}}}
	h := NewReplayHandler(fake)
	var req fasthttp.Request
	req.SetRequestURI("/api/replays?tenant_id=other")
	req.Header.SetMethod(fasthttp.MethodGet)
	var ctx fasthttp.RequestCtx
	ctx.Init(&req, &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 12345}, nil)
	ctx.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{Tenant: "acme", Issuer: "issuer", Subject: "user"})
	h.list(&ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusForbidden {
		t.Fatalf("status=%d body=%s", ctx.Response.StatusCode(), ctx.Response.Body())
	}
	if fake.tenant != "" {
		t.Fatalf("store must not be queried on a tenant mismatch, got %q", fake.tenant)
	}
}
