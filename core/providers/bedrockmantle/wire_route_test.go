package bedrockmantle

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	schemas "github.com/maximhq/bifrost/core/schemas"
	"github.com/valyala/fasthttp"
)

type wireTestLogger struct{}

func (wireTestLogger) Debug(string, ...any)                   {}
func (wireTestLogger) Info(string, ...any)                    {}
func (wireTestLogger) Warn(string, ...any)                    {}
func (wireTestLogger) Error(string, ...any)                   {}
func (wireTestLogger) Fatal(string, ...any)                   {}
func (wireTestLogger) SetLevel(schemas.LogLevel)              {}
func (wireTestLogger) SetOutputType(schemas.LoggerOutputType) {}
func (wireTestLogger) LogHTTPRequest(schemas.LogLevel, string) schemas.LogEventBuilder {
	return schemas.NoopLogEvent
}

func TestResponsesStreamParsesDeterministicMantleServiceGolden(t *testing.T) {
	golden, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "conformance", "lab", "mantleservice", "testdata", "responses-stream.golden.sse"))
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = w.Write(golden)
	}))
	defer ts.Close()
	config := &schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{DefaultRequestTimeoutInSeconds: 5}}
	provider, err := NewBedrockMantleProvider(config, wireTestLogger{})
	if err != nil {
		t.Fatal(err)
	}
	dial := func(string) (net.Conn, error) {
		return net.DialTimeout("tcp", ts.Listener.Addr().String(), 5*time.Second)
	}
	provider.mantleStreamingClient.Dial = dial
	provider.mantleStreamingClient.TLSConfig = &tls.Config{InsecureSkipVerify: true} // test server certificate
	region := schemas.NewSecretVar("us-east-1")
	key := schemas.Key{Value: *schemas.NewSecretVar("test-key"), BedrockMantleKeyConfig: &schemas.BedrockMantleKeyConfig{Region: region}}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	messageType := schemas.ResponsesMessageType("message")
	role := schemas.ResponsesMessageRoleType("user")
	content := "golden"
	request := &schemas.BifrostResponsesRequest{Model: "openai.gpt-5.5", Input: []schemas.ResponsesMessage{{Type: &messageType, Role: &role, Content: &schemas.ResponsesMessageContent{ContentStr: &content}}}}
	stream, bifrostErr := provider.ResponsesStream(ctx, func(_ *schemas.BifrostContext, result *schemas.BifrostResponse, err *schemas.BifrostError) (*schemas.BifrostResponse, *schemas.BifrostError) {
		return result, err
	}, nil, key, request)
	if bifrostErr != nil {
		t.Fatalf("ResponsesStream: %v", bifrostErr)
	}
	var types []schemas.ResponsesStreamResponseType
	var terminal *schemas.BifrostResponsesResponse
	for chunk := range stream {
		if chunk.BifrostError != nil {
			t.Fatalf("parse golden: %v", chunk.BifrostError)
		}
		if chunk.BifrostResponsesStreamResponse == nil {
			t.Fatalf("non-Responses chunk: %#v", chunk)
		}
		types = append(types, chunk.BifrostResponsesStreamResponse.Type)
		if chunk.BifrostResponsesStreamResponse.Type == schemas.ResponsesStreamResponseTypeCompleted {
			terminal = chunk.Response
		}
	}
	want := []schemas.ResponsesStreamResponseType{
		schemas.ResponsesStreamResponseTypeCreated, schemas.ResponsesStreamResponseTypeOutputItemAdded,
		schemas.ResponsesStreamResponseTypeContentPartAdded, schemas.ResponsesStreamResponseTypeOutputTextDelta,
		schemas.ResponsesStreamResponseTypeOutputTextDone, schemas.ResponsesStreamResponseTypeContentPartDone,
		schemas.ResponsesStreamResponseTypeOutputItemDone, schemas.ResponsesStreamResponseTypeCompleted,
	}
	if len(types) != len(want) {
		t.Fatalf("parsed types=%v want=%v", types, want)
	}
	for index := range want {
		if types[index] != want[index] {
			t.Fatalf("type[%d]=%q want=%q", index, types[index], want[index])
		}
	}
	if terminal == nil || terminal.ID == nil || *terminal.ID != "resp_3dd6c57733bf24a1" || terminal.Status == nil || *terminal.Status != "completed" || len(terminal.Output) != 1 {
		t.Fatalf("terminal output lost: %#v", terminal)
	}
}

func TestUnaryResponsesAndGPTOSSChatParseDeterministicServiceGoldens(t *testing.T) {
	goldenDir := filepath.Join("..", "..", "..", "tests", "conformance", "lab", "mantleservice", "testdata")
	responseGolden, err := os.ReadFile(filepath.Join(goldenDir, "response.golden.json"))
	if err != nil {
		t.Fatal(err)
	}
	chatGolden, err := os.ReadFile(filepath.Join(goldenDir, "chat.golden.json"))
	if err != nil {
		t.Fatal(err)
	}
	ts := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.URL.Path == "/v1/chat/completions" {
			_, _ = w.Write(chatGolden)
			return
		}
		if r.URL.Path == "/openai/v1/responses" {
			_, _ = w.Write(responseGolden)
			return
		}
		http.NotFound(w, r)
	}))
	defer ts.Close()
	provider, err := NewBedrockMantleProvider(&schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{DefaultRequestTimeoutInSeconds: 5}}, wireTestLogger{})
	if err != nil {
		t.Fatal(err)
	}
	dial := func(string) (net.Conn, error) {
		return net.DialTimeout("tcp", ts.Listener.Addr().String(), 5*time.Second)
	}
	provider.mantleClient.Dial = dial
	provider.mantleClient.TLSConfig = &tls.Config{InsecureSkipVerify: true} // test server certificate
	region := schemas.NewSecretVar("us-east-1")
	key := schemas.Key{Value: *schemas.NewSecretVar("test-key"), BedrockMantleKeyConfig: &schemas.BedrockMantleKeyConfig{Region: region}}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	messageType := schemas.ResponsesMessageType("message")
	responseRole := schemas.ResponsesMessageRoleType("user")
	golden := "golden"
	response, bifrostErr := provider.Responses(ctx, key, &schemas.BifrostResponsesRequest{Model: "openai.gpt-5.5", Input: []schemas.ResponsesMessage{{Type: &messageType, Role: &responseRole, Content: &schemas.ResponsesMessageContent{ContentStr: &golden}}}})
	if bifrostErr != nil {
		t.Fatalf("Responses: %v", bifrostErr)
	}
	if response.ID == nil || *response.ID != "resp_86aab3a4055fa4de" || response.Status == nil || *response.Status != "completed" || len(response.Output) != 1 {
		t.Fatalf("unary golden lost fields: %#v", response)
	}
	chat, bifrostErr := provider.ChatCompletion(ctx, key, &schemas.BifrostChatRequest{Model: "openai.gpt-oss-120b", Input: []schemas.ChatMessage{{Role: schemas.ChatMessageRoleUser, Content: &schemas.ChatMessageContent{ContentStr: &golden}}}})
	if bifrostErr != nil {
		t.Fatalf("ChatCompletion: %v", bifrostErr)
	}
	if chat.ID != "chatcmpl_5a3bc44d08783f97" || chat.Model != "openai.gpt-oss-120b" || len(chat.Choices) != 1 {
		t.Fatalf("Chat golden lost fields: %#v", chat)
	}
}

type capturedMantleRequest struct {
	method, host, path, model string
	hasAdditionalTools        bool
	toolCount                 int
}

func TestResponsesPublicOperationsUsePinnedMantleWireRoute(t *testing.T) {
	captured := make(chan capturedMantleRequest, 4)
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
		captured <- capturedMantleRequest{r.Method, r.Host, r.URL.Path, payload.Model, hasAdditionalTools, len(payload.Tools)}
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
	provider, err := NewBedrockMantleProvider(config, wireTestLogger{})
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

	region := schemas.NewSecretVar("us-east-1")
	key := schemas.Key{Value: *schemas.NewSecretVar("test-key"), BedrockMantleKeyConfig: &schemas.BedrockMantleKeyConfig{Region: region}}
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
	req := newRequest("openai.gpt-5.5")
	if _, bifrostErr := provider.Responses(ctx, key, req); bifrostErr != nil {
		t.Fatalf("Responses: %v", bifrostErr)
	}
	if _, bifrostErr := provider.Responses(ctx, key, newRequest("openai.gpt-oss-120b")); bifrostErr != nil {
		t.Fatalf("GPT-OSS Responses: %v", bifrostErr)
	}

	modelName := "openai.gpt-5.5"
	ctx.SetValue(schemas.BifrostContextKeyResolvedAlias, &schemas.ResolvedAlias{Key: "frontier", Config: &schemas.AliasConfig{ModelID: "opaque-deployment", ModelName: &modelName}})
	stream, bifrostErr := provider.ResponsesStream(ctx, func(_ *schemas.BifrostContext, result *schemas.BifrostResponse, err *schemas.BifrostError) (*schemas.BifrostResponse, *schemas.BifrostError) {
		return result, err
	}, nil, key, newRequest("opaque-deployment"))
	if bifrostErr != nil {
		t.Fatalf("ResponsesStream: %v", bifrostErr)
	}
	for range stream {
	}

	want := []capturedMantleRequest{
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
