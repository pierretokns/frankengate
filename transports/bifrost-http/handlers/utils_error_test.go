package handlers

import (
	"strings"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/valyala/fasthttp"
)

func TestSendBifrostErrorEmitsRetryAfterWithoutChangingJSONShape(t *testing.T) {
	ctx := &fasthttp.RequestCtx{}
	ctx.Response.Header.SetContentType("application/json")
	seconds := 7
	status := fasthttp.StatusTooManyRequests
	SendBifrostError(ctx, &schemas.BifrostError{
		StatusCode:        &status,
		Type:              schemas.Ptr("rate_limited"),
		RetryAfterSeconds: &seconds,
		Error:             &schemas.ErrorField{Message: "limit reached"},
	})
	if got := string(ctx.Response.Header.Peek("Retry-After")); got != "7" {
		t.Fatalf("Retry-After = %q, want 7", got)
	}
	if got := string(ctx.Response.Body()); got == "" || strings.Contains(got, "retry_after_seconds") {
		t.Fatalf("transport metadata leaked into JSON body: %s", got)
	}
}
