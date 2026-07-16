package handlers

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/valyala/fasthttp"
)

func listModelsVKHandler(vk *configstoreTables.TableVirtualKey, err error) *CompletionHandler {
	return &CompletionHandler{resolveListModelsVirtualKey: func(context.Context, string) (*configstoreTables.TableVirtualKey, error) {
		return vk, err
	}}
}

func TestApplyListModelsVirtualKeyProviderFilterSetsActiveVKProviders(t *testing.T) {
	h := listModelsVKHandler(&configstoreTables.TableVirtualKey{
		Value:    *schemas.NewSecretVar("sk-bf-active"),
		IsActive: new(true),
		ProviderConfigs: []configstoreTables.TableVirtualKeyProviderConfig{
			{Provider: "openai"},
			{Provider: " anthropic "},
			{Provider: ""},
		},
	}, nil)

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.Set("Authorization", "Bearer sk-bf-active")
	bifrostCtx := schemas.NewBifrostContext(context.Background(), time.Time{})

	if ok := h.applyListModelsVirtualKeyProviderFilter(ctx, bifrostCtx); !ok {
		t.Fatalf("expected active VK to apply provider filter")
	}
	got, ok := bifrostCtx.Value(schemas.BifrostContextKeyAvailableProviders).([]schemas.ModelProvider)
	if !ok {
		t.Fatalf("expected available providers to be set")
	}
	want := []schemas.ModelProvider{schemas.OpenAI, schemas.Anthropic}
	if len(got) != len(want) {
		t.Fatalf("expected providers %#v, got %#v", want, got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("expected providers %#v, got %#v", want, got)
		}
	}
}

func TestApplyListModelsVirtualKeyProviderFilterReturnsErrorOnLookupFailure(t *testing.T) {
	h := listModelsVKHandler(nil, errors.New("database unavailable"))

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.Set("Authorization", "Bearer sk-bf-active")
	bifrostCtx := schemas.NewBifrostContext(context.Background(), time.Time{})

	if ok := h.applyListModelsVirtualKeyProviderFilter(ctx, bifrostCtx); ok {
		t.Fatalf("expected lookup error to fail request")
	}
	if got := ctx.Response.StatusCode(); got != fasthttp.StatusInternalServerError {
		t.Fatalf("expected status %d, got %d", fasthttp.StatusInternalServerError, got)
	}
	if body := string(ctx.Response.Body()); !strings.Contains(body, "Failed to resolve virtual key") {
		t.Fatalf("expected virtual key lookup error response, got %q", body)
	}
}

func TestApplyListModelsVirtualKeyProviderFilterReturnsUnavailableWithoutAuthority(t *testing.T) {
	h := &CompletionHandler{}

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.Set("Authorization", "Bearer sk-bf-active")
	bifrostCtx := schemas.NewBifrostContext(context.Background(), time.Time{})

	if ok := h.applyListModelsVirtualKeyProviderFilter(ctx, bifrostCtx); ok {
		t.Fatalf("expected missing config store to fail request")
	}
	if got := ctx.Response.StatusCode(); got != fasthttp.StatusServiceUnavailable {
		t.Fatalf("expected status %d, got %d", fasthttp.StatusServiceUnavailable, got)
	}
	if body := string(ctx.Response.Body()); !strings.Contains(body, "virtual key authority unavailable") {
		t.Fatalf("expected unavailable response, got %q", body)
	}
}

func TestApplyListModelsVirtualKeyProviderFilterFailsClosedWhenAuthorityIsStale(t *testing.T) {
	h := listModelsVKHandler(nil, errListModelsVKAuthorityStale)
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.Set("Authorization", "Bearer sk-bf-active")
	bifrostCtx := schemas.NewBifrostContext(context.Background(), time.Time{})

	if ok := h.applyListModelsVirtualKeyProviderFilter(ctx, bifrostCtx); ok {
		t.Fatalf("expected stale authority to fail request")
	}
	if got := ctx.Response.StatusCode(); got != fasthttp.StatusServiceUnavailable {
		t.Fatalf("expected status %d, got %d", fasthttp.StatusServiceUnavailable, got)
	}
	if body := string(ctx.Response.Body()); !strings.Contains(body, "virtual key authority is stale") {
		t.Fatalf("expected stale authority response, got %q", body)
	}
}

func TestApplyListModelsVirtualKeyProviderFilterRejectsMissingVK(t *testing.T) {
	h := listModelsVKHandler(nil, configstore.ErrNotFound)

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.Set("Authorization", "Bearer sk-bf-missing")
	bifrostCtx := schemas.NewBifrostContext(context.Background(), time.Time{})

	if ok := h.applyListModelsVirtualKeyProviderFilter(ctx, bifrostCtx); ok {
		t.Fatalf("expected missing VK to fail closed")
	}
	if got := ctx.Response.StatusCode(); got != fasthttp.StatusUnauthorized {
		t.Fatalf("expected status %d, got %d", fasthttp.StatusUnauthorized, got)
	}
	if body := string(ctx.Response.Body()); !strings.Contains(body, "does not exist or has been revoked") {
		t.Fatalf("expected revoked VK response, got %q", body)
	}
}

func TestApplyListModelsVirtualKeyProviderFilterRejectsInactiveVK(t *testing.T) {
	h := listModelsVKHandler(&configstoreTables.TableVirtualKey{
		Value:    *schemas.NewSecretVar("sk-bf-inactive"),
		IsActive: new(false),
		ProviderConfigs: []configstoreTables.TableVirtualKeyProviderConfig{
			{Provider: "openai"},
		},
	}, nil)

	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.Set("Authorization", "Bearer sk-bf-inactive")
	bifrostCtx := schemas.NewBifrostContext(context.Background(), time.Time{})

	if ok := h.applyListModelsVirtualKeyProviderFilter(ctx, bifrostCtx); ok {
		t.Fatalf("expected inactive VK to fail closed")
	}
	if got := ctx.Response.StatusCode(); got != fasthttp.StatusUnauthorized {
		t.Fatalf("expected status %d, got %d", fasthttp.StatusUnauthorized, got)
	}
	if body := string(ctx.Response.Body()); !strings.Contains(body, "does not exist or has been revoked") {
		t.Fatalf("expected revoked VK response, got %q", body)
	}
}
