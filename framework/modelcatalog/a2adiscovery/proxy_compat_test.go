package a2adiscovery

import (
	"encoding/json"
	"reflect"
	"testing"
)

// These tests are intentionally named after the behavioral cases in
// agentgateway/crates/agentgateway/src/a2a/tests.rs. They port the intent,
// not Rust implementation details: request bodies stay forwardable, cards
// are gateway-reachable, and response inspection never changes wire bytes.

func TestAgentgatewayClassifyRequestExtractsMethodAndPreservesBody(t *testing.T) {
	body := []byte(`{"jsonrpc":"2.0","method":"message/send","params":{}}`)
	original := append([]byte(nil), body...)
	classification := ClassifyProxyRequest("POST", "/a2a", "application/json", body, "", "")
	if classification.Kind != ProxyRequestCall || classification.Method != "message/send" {
		t.Fatalf("classification = %#v", classification)
	}
	if !reflect.DeepEqual(body, original) {
		t.Fatalf("classifying request mutated body: %q", body)
	}
}

func TestAgentgatewayClassifyRequestUsesOriginalURLForAgentCard(t *testing.T) {
	classification := ClassifyProxyRequest("GET", "/proxy/.well-known/agent-card.json", "", nil, "https://gateway.example/.well-known/agent-card.json", "")
	if classification.Kind != ProxyRequestAgentCard || classification.AgentCardURL != "https://gateway.example/.well-known/agent-card.json" {
		t.Fatalf("classification = %#v", classification)
	}
}

func TestAgentgatewayClassifyRequestUsesOriginalURLWithSubpath(t *testing.T) {
	classification := ClassifyProxyRequest("GET", "/proxy/.well-known/agent-card.json", "", nil, "https://gateway.example/api/.well-known/agent-card.json", "")
	if classification.AgentCardURL != "https://gateway.example/api/.well-known/agent-card.json" {
		t.Fatalf("agent card URL = %q", classification.AgentCardURL)
	}
}

func TestAgentgatewayClassifyRequestUsesForwardedProtoForAgentCard(t *testing.T) {
	classification := ClassifyProxyRequest("GET", "/.well-known/agent.json", "", nil, "http://gateway.example/.well-known/agent.json", "https")
	if classification.AgentCardURL != "https://gateway.example/.well-known/agent.json" {
		t.Fatalf("agent card URL = %q", classification.AgentCardURL)
	}
}

func TestAgentgatewayClassifyRequestReturnsUnknownMethodOnInvalidJSON(t *testing.T) {
	classification := ClassifyProxyRequest("POST", "/a2a", "application/json", []byte(`{"method"`), "", "")
	if classification.Kind != ProxyRequestCall || classification.Method != "unknown" {
		t.Fatalf("classification = %#v", classification)
	}
}

func TestAgentgatewayBuildAgentPath(t *testing.T) {
	for _, tc := range []struct {
		name string
		in   string
		want string
	}{
		{name: "v03", in: "https://example.com/.well-known/agent.json", want: "https://example.com"},
		{name: "v1-subpath", in: "https://example.com/api/.well-known/agent-card.json?tenant=one", want: "https://example.com/api?tenant=one"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got, err := BuildGatewayAgentPath(tc.in)
			if err != nil {
				t.Fatal(err)
			}
			if got != tc.want {
				t.Fatalf("gateway path = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestAgentgatewayRewriteV03AgentCardURL(t *testing.T) {
	got := rewriteCard(t, `{"name":"example","url":"http://backend.internal/a2a"}`, "https://example.com")
	if got["url"] != "https://example.com" {
		t.Fatalf("rewritten card = %#v", got)
	}
}

func TestAgentgatewayRewriteV1AgentCardSingleInterface(t *testing.T) {
	got := rewriteCard(t, `{"supportedInterfaces":[{"protocolBinding":"JSONRPC","url":"http://backend.internal/a2a/jsonrpc"}]}`, "https://example.com")
	if got["supportedInterfaces"].([]any)[0].(map[string]any)["url"] != "https://example.com/a2a/jsonrpc" {
		t.Fatalf("rewritten card = %#v", got)
	}
}

func TestAgentgatewayRewriteV1AgentCardMultipleInterfaces(t *testing.T) {
	got := rewriteCard(t, `{"supportedInterfaces":[{"url":"http://backend.internal/jsonrpc"},{"url":"http://backend.internal/http?x=1"}]}`, "https://example.com/api")
	interfaces := got["supportedInterfaces"].([]any)
	if interfaces[0].(map[string]any)["url"] != "https://example.com/api/jsonrpc" || interfaces[1].(map[string]any)["url"] != "https://example.com/api/http?x=1" {
		t.Fatalf("rewritten card = %#v", got)
	}
}

func TestAgentgatewayRewriteV1AgentCardRootPath(t *testing.T) {
	got := rewriteCard(t, `{"supportedInterfaces":[{"url":"http://backend.internal/a2a/jsonrpc/"}]}`, "https://example.com")
	if got["supportedInterfaces"].([]any)[0].(map[string]any)["url"] != "https://example.com/a2a/jsonrpc/" {
		t.Fatalf("rewritten card = %#v", got)
	}
}

func TestAgentgatewayRewriteSkipsInterfaceWithoutURL(t *testing.T) {
	got := rewriteCard(t, `{"supportedInterfaces":[{"protocolBinding":"GRPC"},{"url":"http://backend.internal/a2a"}]}`, "https://example.com/api")
	interfaces := got["supportedInterfaces"].([]any)
	if _, exists := interfaces[0].(map[string]any)["url"]; exists {
		t.Fatal("interface without URL was changed")
	}
	if interfaces[1].(map[string]any)["url"] != "https://example.com/api/a2a" {
		t.Fatalf("rewritten card = %#v", got)
	}
}

func TestAgentgatewayRewriteErrorsWhenCardHasNoURL(t *testing.T) {
	if _, err := RewriteAgentCardForGateway([]byte(`{"name":"example"}`), "https://example.com", 0); err == nil {
		t.Fatal("card without URL was accepted")
	}
}

func TestAgentgatewayRewriteRejectsNonArrayInterfaces(t *testing.T) {
	if _, err := RewriteAgentCardForGateway([]byte(`{"supportedInterfaces":null}`), "https://example.com", 0); err == nil {
		t.Fatal("non-array interfaces were accepted")
	}
}

func TestAgentgatewayInspectSuccessResponse(t *testing.T) {
	info, ok := InspectA2AJSONResponse([]byte(`{"result":{"kind":"task","status":{"state":"completed"}}}`), "application/json", true, 0)
	if !ok || info.Outcome != ProxyResponseSuccess || info.ResultKind != "task" || info.TaskState != "completed" || info.ErrorCode != nil {
		t.Fatalf("info=%#v ok=%v", info, ok)
	}
}

func TestAgentgatewayInspectErrorResponse(t *testing.T) {
	info, ok := InspectA2AJSONResponse([]byte(`{"error":{"code":-32602}}`), "application/json", true, 0)
	if !ok || info.Outcome != ProxyResponseError || info.ErrorCode == nil || *info.ErrorCode != -32602 {
		t.Fatalf("info=%#v ok=%v", info, ok)
	}
}

func TestAgentgatewayInspectUnknownSizeJSONResponse(t *testing.T) {
	info, ok := InspectA2AJSONResponse([]byte(`{"result":{"kind":"task","status":{"state":"working"}}}`), "application/a2a+json", true, 0)
	if !ok || info.Outcome != ProxyResponseSuccess || info.TaskState != "working" {
		t.Fatalf("info=%#v ok=%v", info, ok)
	}
}

func TestAgentgatewayInspectUnknownResponse(t *testing.T) {
	info, ok := InspectA2AJSONResponse([]byte(`{"jsonrpc":"2.0","id":"1"}`), "application/json", true, 0)
	if !ok || info.Outcome != ProxyResponseUnknown {
		t.Fatalf("info=%#v ok=%v", info, ok)
	}
}

func TestAgentgatewaySkipsInvalidJSONResponseTelemetry(t *testing.T) {
	raw := []byte(`{"jsonrpc":"2.0"`)
	if _, ok := InspectA2AJSONResponse(raw, "application/json", true, 0); ok {
		t.Fatal("invalid JSON produced telemetry")
	}
}

func TestAgentgatewaySkipsNonJSONResponseTelemetry(t *testing.T) {
	if _, ok := InspectA2AJSONResponse([]byte("ok"), "text/plain", true, 0); ok {
		t.Fatal("non-JSON response produced telemetry")
	}
}

func TestAgentgatewaySkipsPartialResponseTelemetry(t *testing.T) {
	if _, ok := InspectA2AJSONResponse([]byte(`{"result":{"kind":"task"}}`), "application/json", false, 0); ok {
		t.Fatal("partial response produced telemetry")
	}
}

func TestAgentgatewaySkipsOversizedResponseTelemetry(t *testing.T) {
	if _, ok := InspectA2AJSONResponse([]byte(`{"result":{}}`), "application/json", true, 4); ok {
		t.Fatal("oversized response produced telemetry")
	}
}

func rewriteCard(t *testing.T, raw, base string) map[string]any {
	t.Helper()
	body, err := RewriteAgentCardForGateway([]byte(raw), base, 0)
	if err != nil {
		t.Fatal(err)
	}
	var card map[string]any
	if err := json.Unmarshal(body, &card); err != nil {
		t.Fatal(err)
	}
	return card
}
