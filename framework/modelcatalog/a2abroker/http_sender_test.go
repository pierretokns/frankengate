package a2abroker

import (
	"context"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
)

func TestHTTPJSONSenderSendsCredentialsAndTraceAndMapsTask(t *testing.T) {
	var got http.Header
	var body []byte
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Clone()
		body, _ = io.ReadAll(r.Body)
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"result":{"id":"remote-task","status":{"state":"TASK_STATE_COMPLETED"}}}`)
	}))
	defer server.Close()

	previous := otel.GetTextMapPropagator()
	otel.SetTextMapPropagator(propagation.TraceContext{})
	defer otel.SetTextMapPropagator(previous)
	traceID, _ := trace.TraceIDFromHex("4bf92f3577b34da6a3ce929d0e0e4736")
	spanID, _ := trace.SpanIDFromHex("00f067aa0ba902b7")
	ctx := trace.ContextWithSpanContext(context.Background(), trace.NewSpanContext(trace.SpanContextConfig{TraceID: traceID, SpanID: spanID, TraceFlags: trace.FlagsSampled}))

	sender := HTTPJSONSender{Client: server.Client(), AllowedHosts: []string{"127.0.0.1"}, AllowLoopback: true}
	event, err := sender.Send(ctx, SendRequest{
		TaskID:     "local-task",
		Endpoint:   server.URL,
		CardDigest: "sha256:card",
		Payload:    []byte(`{"message":"hello"}`),
		Headers:    http.Header{"Authorization": []string{"Bearer runtime-token"}},
	})
	if err != nil {
		t.Fatalf("send: %v", err)
	}
	if event.State != StateCompleted {
		t.Fatalf("event state = %q, want completed", event.State)
	}
	if got.Get("Authorization") != "Bearer runtime-token" || got.Get("X-A2A-Task-ID") != "local-task" || got.Get("X-A2A-Card-Digest") != "sha256:card" {
		t.Fatalf("outbound headers = %#v", got)
	}
	if got.Get("traceparent") != "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" {
		t.Fatalf("traceparent = %q", got.Get("traceparent"))
	}
	if string(body) != `{"message":"hello"}` {
		t.Fatalf("payload = %s", body)
	}
}

func TestHTTPJSONSenderMapsAuthAndJSONRPCFailuresWithoutLeakingBody(t *testing.T) {
	for _, test := range []struct {
		name       string
		statusCode int
		body       string
		wantState  State
		wantText   string
	}{
		{name: "auth", statusCode: http.StatusUnauthorized, body: `secret-token`, wantState: StateAuthRequired, wantText: "secret-token"},
		{name: "jsonrpc", statusCode: http.StatusOK, body: `{"error":{"code":-32000,"message":"credential secret-token"}}`, wantState: StateRejected, wantText: "secret-token"},
	} {
		t.Run(test.name, func(t *testing.T) {
			server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(test.statusCode)
				_, _ = io.WriteString(w, test.body)
			}))
			defer server.Close()
			sender := HTTPJSONSender{Client: server.Client(), AllowedHosts: []string{"127.0.0.1"}, AllowLoopback: true}
			event, err := sender.Send(context.Background(), SendRequest{TaskID: "task-1", Endpoint: server.URL, Payload: []byte(`{}`)})
			if err != nil {
				t.Fatalf("send: %v", err)
			}
			if event.State != test.wantState || strings.Contains(event.Error+event.Message, test.wantText) {
				t.Fatalf("event = %#v, want state %q without body material", event, test.wantState)
			}
		})
	}
}

func TestHTTPJSONSenderRejectsUnsafeResolutionAndHeaders(t *testing.T) {
	sender := HTTPJSONSender{
		AllowedHosts: []string{"agent.example"},
		Resolver: IPResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
			return []net.IPAddr{{IP: net.ParseIP("10.0.0.8")}}, nil
		}),
	}
	if _, err := sender.Send(context.Background(), SendRequest{TaskID: "task-1", Endpoint: "https://agent.example/a2a", Payload: []byte(`{}`)}); err == nil {
		t.Fatalf("private DNS result was accepted: %v", err)
	}

	unsafe := HTTPJSONSender{AllowedHosts: []string{"agent.example"}}
	if _, err := unsafe.Send(context.Background(), SendRequest{TaskID: "task-1", Endpoint: "https://agent.example/a2a", Headers: http.Header{"X-Forwarded-For": []string{"10.0.0.1"}}}); err == nil || !strings.Contains(err.Error(), "forbidden header") {
		t.Fatalf("unsafe header was accepted: %v", err)
	}
}
