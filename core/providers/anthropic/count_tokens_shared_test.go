package anthropic

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/valyala/fasthttp"
)

func TestHandleAnthropicCountTokensRequestSharedSurface(t *testing.T) {
	t.Parallel()
	var gotPath, gotAuth string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath, gotAuth = r.URL.Path, r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"input_tokens":7}`)
	}))
	defer server.Close()

	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	role := schemas.ResponsesInputMessageRoleUser
	text := "hello"
	request := &schemas.BifrostResponsesRequest{Provider: schemas.DeepSeek, Model: "deepseek-chat", Input: []schemas.ResponsesMessage{{Role: &role, Content: &schemas.ResponsesMessageContent{ContentStr: &text}}}}
	response, err := HandleAnthropicCountTokensRequest(ctx, &fasthttp.Client{}, server.URL+"/anthropic/v1/messages/count_tokens", request,
		AnthropicRequestBuildConfig{Provider: schemas.DeepSeek}, map[string]string{"Authorization": "Bearer test"}, nil, nil)
	if err != nil {
		t.Fatalf("count tokens returned error: %v", err.Error.Message)
	}
	if response == nil || response.InputTokens != 7 {
		t.Fatalf("count tokens response = %#v, want 7 input tokens", response)
	}
	if gotPath != "/anthropic/v1/messages/count_tokens" || gotAuth != "Bearer test" {
		t.Fatalf("request path/auth = %q/%q", gotPath, gotAuth)
	}
}
