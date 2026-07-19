package bifrost

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/providers/utils"
	schemas "github.com/maximhq/bifrost/core/schemas"
)

func TestProviderTimeoutRemainsFallbackEligible(t *testing.T) {
	logger := NewDefaultLogger(schemas.LogLevelError)
	b := &Bifrost{logger: logger}
	err := utils.NewBifrostTimeoutError(schemas.ErrProviderRequestTimedOut, context.DeadlineExceeded)
	if err.Error == nil || err.Error.Type == nil || *err.Error.Type != schemas.RequestTimedOut {
		t.Fatalf("expected provider timeout error, got %#v", err)
	}
	if !b.shouldContinueWithFallbacks(schemas.Fallback{Provider: schemas.OpenAI, Model: "fallback"}, err) {
		t.Fatal("provider timeout must continue to configured fallbacks")
	}
}

func TestFallbackCancellationIsTerminal(t *testing.T) {
	logger := NewDefaultLogger(schemas.LogLevelError)
	b := &Bifrost{logger: logger}
	typ := schemas.RequestCancelled
	err := &schemas.BifrostError{Error: &schemas.ErrorField{Type: &typ}}
	if b.shouldContinueWithFallbacks(schemas.Fallback{Provider: schemas.OpenAI, Model: "fallback"}, err) {
		t.Fatal("client cancellation must not start another provider attempt")
	}
}
