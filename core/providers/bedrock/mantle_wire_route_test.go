package bedrock

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	schemas "github.com/maximhq/bifrost/core/schemas"
	"github.com/valyala/fasthttp"
)

type capturedBedrockMantleRequest struct {
	method, host, path, model string
	hasAdditionalTools        bool
	toolCount                 int
}

func TestLegacyBedrockResponsesPublicOperationsUsePinnedMantleWireRoute(t *testing.T) {
	captured := make(chan capturedBedrockMantleRequest, 3)
	ts := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Errorf("read request: %v", err)
			return
		}
		var payload struct {
			Model  string            `json:"model"`
			Stream bool              `json:"stream"`
			Input  []json.RawMessage `json:"input"`
			Tools  []json.RawMessage `json:"tools"`
		}
		if err := json.Unmarshal(body, &payload); err != nil {
			t.Errorf("decode request: %v; body=%s", err, body)
			return
		}
		hasAdditionalTools := false
		for _, item := range payload.Input {
			var discriminator struct {
				Type string `json:"type"`
			}
			if json.Unmarshal(item, &discriminator) == nil && discriminator.Type == "additional_tools" {
				hasAdditionalTools = true
			}
		}
		captured <- capturedBedrockMantleRequest{r.Method, r.Host, r.URL.Path, payload.Model, hasAdditionalTools, len(payload.Tools)}
		if payload.Stream {
			w.Header().Set("Content-Type", "text/event-stream")
			fmt.Fprint(w, "data: {\"type\":\"response.completed\",\"sequence_number\":0,\"response\":{\"id\":\"resp_test\",\"object\":\"response\",\"created_at\":1,\"status\":\"completed\",\"model\":\"openai.gpt-5.5\",\"output\":[]}}\n\n")
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"id":"resp_test","object":"response","created_at":1,"status":"completed","model":"openai.gpt-5.5","output":[]}`)
	}))
	defer ts.Close()

	config := &schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{DefaultRequestTimeoutInSeconds: 5}}
	provider, err := NewBedrockProvider(config, noopLogger{})
	if err != nil {
		t.Fatal(err)
	}
	dial := func(string) (net.Conn, error) {
		return net.DialTimeout("tcp", ts.Listener.Addr().String(), 5*time.Second)
	}
	for _, client := range []*fasthttp.Client{provider.mantleClient, provider.mantleStreamingClient} {
		client.Dial = dial
		client.TLSConfig = &tls.Config{InsecureSkipVerify: true} // test server certificate
	}

	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	messageType := schemas.ResponsesMessageType("message")
	role := schemas.ResponsesMessageRoleType("user")
	content := "hello"
	newRequest := func(model string) *schemas.BifrostResponsesRequest {
		var additional schemas.ResponsesMessage
		if err := json.Unmarshal([]byte(`{"type":"additional_tools","role":"developer","tools":[{"type":"function","name":"lookup","parameters":{"type":"object"}}]}`), &additional); err != nil {
			t.Fatal(err)
		}
		return &schemas.BifrostResponsesRequest{Model: model, Input: []schemas.ResponsesMessage{additional, {Type: &messageType, Role: &role, Content: &schemas.ResponsesMessageContent{ContentStr: &content}}}}
	}
	if _, bifrostErr := provider.Responses(ctx, testBedrockKey(), newRequest("openai.gpt-5.5")); bifrostErr != nil {
		t.Fatalf("Responses: %v", bifrostErr)
	}
	if _, bifrostErr := provider.Responses(ctx, testBedrockKey(), newRequest("openai.gpt-oss-120b")); bifrostErr != nil {
		t.Fatalf("GPT-OSS Responses: %v", bifrostErr)
	}

	modelName := "openai.gpt-5.5"
	ctx.SetValue(schemas.BifrostContextKeyResolvedAlias, &schemas.ResolvedAlias{Key: "frontier", Config: &schemas.AliasConfig{ModelID: "opaque-deployment", ModelName: &modelName}})
	stream, bifrostErr := provider.ResponsesStream(ctx, noopPostHookRunner, nil, testBedrockKey(), newRequest("opaque-deployment"))
	if bifrostErr != nil {
		t.Fatalf("ResponsesStream: %v", bifrostErr)
	}
	for range stream {
	}

	want := []capturedBedrockMantleRequest{
		{http.MethodPost, "bedrock-mantle.us-east-1.api.aws", "/openai/v1/responses", "openai.gpt-5.5", false, 1},
		{http.MethodPost, "bedrock-mantle.us-east-1.api.aws", "/v1/responses", "openai.gpt-oss-120b", true, 0},
		{http.MethodPost, "bedrock-mantle.us-east-1.api.aws", "/openai/v1/responses", "opaque-deployment", false, 1},
	}
	for i, expected := range want {
		select {
		case got := <-captured:
			if got != expected {
				t.Errorf("request %d = %#v, want %#v", i, got, expected)
			}
		case <-time.After(2 * time.Second):
			t.Fatalf("timed out waiting for request %d", i)
		}
	}
	select {
	case got := <-captured:
		t.Fatalf("unexpected fourth request: %#v", got)
	default:
	}
}
