package vllm

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	schemas "github.com/maximhq/bifrost/core/schemas"
)

func TestResponsesUsesNativeResponsesEndpoint(t *testing.T) {
	t.Parallel()
	var gotPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"id":"resp_test","object":"response","status":"completed","output":[],"usage":{"input_tokens":1,"output_tokens":1,"total_tokens":2}}`)
	}))
	defer server.Close()

	provider := newTestVLLMProvider()
	key := schemas.Key{Value: schemas.SecretVar{Val: "test-key"}, VLLMKeyConfig: &schemas.VLLMKeyConfig{URL: schemas.SecretVar{Val: server.URL}}}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	role := schemas.ResponsesInputMessageRoleUser
	hello := "hello"
	request := &schemas.BifrostResponsesRequest{Provider: schemas.VLLM, Model: "test-model", Input: []schemas.ResponsesMessage{{Role: &role, Content: &schemas.ResponsesMessageContent{ContentStr: &hello}}}}

	if _, err := provider.Responses(ctx, key, request); err != nil {
		t.Fatalf("Responses returned error: %v", err.Error.Message)
	}
	if gotPath != "/v1/responses" {
		t.Fatalf("expected native /v1/responses endpoint, got %q", gotPath)
	}
}
