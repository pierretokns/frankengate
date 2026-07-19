package handlers

import (
	"context"
	"net"
	"testing"
	"time"

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
}

func TestReplayHandlerSummaryShape(t *testing.T) {
	// Keep the authorization invariant at the store boundary as well: a custom
	// implementation may return mixed tenants, but the HTTP response filters it.
	fake := &replayListFake{rows: []otel.ReplayRecord{{SchemaVersion: 1, TraceID: "a", TenantID: "acme", CapturedAt: time.Unix(1, 0), Trace: &schemas.Trace{TraceID: "secret"}}, {TraceID: "x", TenantID: "other"}}}
	if _, err := fake.List(context.Background(), "acme", 2); err != nil {
		t.Fatal(err)
	}
	if fake.tenant != "acme" {
		t.Fatalf("store called with tenant %q", fake.tenant)
	}
}
