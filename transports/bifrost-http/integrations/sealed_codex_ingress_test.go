package integrations

import (
	"bytes"
	"fmt"
	"reflect"
	"strings"
	"testing"

	"github.com/valyala/fasthttp"
)

func TestSealedCodexResponsesObserverDisabledReturnsHandlerUnchanged(t *testing.T) {
	t.Setenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER", "")
	next := func(*fasthttp.RequestCtx) {}
	wrapped := wrapSealedCodexIngressObserverWithWriter(next, &bytes.Buffer{})
	if reflect.ValueOf(wrapped).Pointer() != reflect.ValueOf(next).Pointer() {
		t.Fatal("disabled observer added a production request wrapper")
	}
}

func TestSealedCodexResponsesObserverRunsOutsideServerHandler(t *testing.T) {
	t.Setenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER", "1")
	t.Setenv("LAB_RUN_ID", "run-1")
	var output bytes.Buffer
	nextCalls := 0
	observer := wrapSealedCodexIngressObserverWithWriter(func(*fasthttp.RequestCtx) { nextCalls++ }, &output)
	valid := `{"model":"bedrock_mantle/gpt-5.5","stream":true,"parallel_tool_calls":false,"input":[{"type":"additional_tools","role":"developer","tools":[{"type":"tool_search","execution":"client","description":"search tools","parameters":{"type":"object"}}]},{"type":"message","role":"user","content":"SEALED_CODEX_RUN_ID:run-1"}]}`
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetMethod(fasthttp.MethodPost)
	ctx.Request.SetRequestURI("/openai/v1/responses")
	ctx.Request.Header.Set("x-openai-internal-codex-responses-lite", "true")
	ctx.Request.SetBodyString(valid)
	observer(ctx)
	if nextCalls != 1 {
		t.Fatalf("wrapped handler calls = %d", nextCalls)
	}
	if !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-arrival/v1"`) || !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-ingress/v1"`) || strings.Contains(output.String(), "rejected") {
		t.Fatalf("valid integration Lite ingress not accepted: %s", output.String())
	}

	output.Reset()
	ctx.Request.SetBodyString(strings.Replace(valid, `"execution":"client"`, `"execution":"server"`, 1))
	observer(ctx)
	if !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-ingress-rejected/v1"`) || !strings.Contains(output.String(), `"tool_shapes_ok":false`) {
		t.Fatalf("invalid integration Lite ingress not diagnosed: %s", output.String())
	}

	output.Reset()
	toolMarker := strings.Replace(valid, `"description":"search tools"`, `"description":"SEALED_CODEX_RUN_ID:run-1"`, 1)
	toolMarker = strings.Replace(toolMarker, `SEALED_CODEX_RUN_ID:run-1"}]}`, `no user marker"}]}`, 1)
	ctx.Request.SetBodyString(toolMarker)
	observer(ctx)
	if !strings.Contains(output.String(), `"input_run_id_count":0`) || !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-ingress-rejected/v1"`) {
		t.Fatalf("tool metadata falsely satisfied run binding: %s", output.String())
	}

	output.Reset()
	ctx.Request.SetBodyString(strings.Replace(valid, `SEALED_CODEX_RUN_ID:run-1`, `SEALED_CODEX_RUN_ID:run-1 SEALED_CODEX_RUN_ID:run-1 SEALED_CODEX_RUN_ID:run-1`, 1))
	observer(ctx)
	if !strings.Contains(output.String(), `"input_run_id_count":2`) || !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-ingress-rejected/v1"`) {
		t.Fatalf("duplicate input markers not rejected with bounded count: %s", output.String())
	}

	for name, content := range map[string]string{
		"annotation": `[{"type":"input_text","text":"no marker","annotation":"SEALED_CODEX_RUN_ID:run-1"}]`,
		"type":       `[{"type":"SEALED_CODEX_RUN_ID:run-1","text":"no marker"}]`,
	} {
		output.Reset()
		mutant := strings.Replace(valid, `"content":"SEALED_CODEX_RUN_ID:run-1"`, `"content":`+content, 1)
		ctx.Request.SetBodyString(mutant)
		observer(ctx)
		if !strings.Contains(output.String(), `"input_run_id_matches":false`) || !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-ingress-rejected/v1"`) {
			t.Fatalf("%s content metadata falsely satisfied run binding: %s", name, output.String())
		}
	}

	output.Reset()
	arrayContent := strings.Replace(valid, `"content":"SEALED_CODEX_RUN_ID:run-1"`, `"content":[{"type":"input_text","text":"SEALED_CODEX_RUN_ID:run-1"}]`, 1)
	ctx.Request.SetBodyString(arrayContent)
	observer(ctx)
	if !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-ingress/v1"`) || strings.Contains(output.String(), "rejected") {
		t.Fatalf("semantic input_text marker not accepted: %s", output.String())
	}
}

func TestSealedCodexResponsesObserverClassifiesMarkedRouteMismatches(t *testing.T) {
	t.Setenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER", "1")
	t.Setenv("LAB_RUN_ID", "run-1")
	var output bytes.Buffer
	nextCalls := 0
	handler := wrapSealedCodexIngressObserverWithWriter(func(*fasthttp.RequestCtx) { nextCalls++ }, &output)
	for _, testCase := range []struct {
		path       string
		pathExact  bool
		queryEmpty bool
	}{
		{"/openai/responses", false, true},
		{"/openai//v1/responses", false, true},
		{"/openai/%76%31/responses", false, true},
		{"/openai/x/../v1/responses", false, true},
		{"/openai/v1/responses?model=bedrock_mantle%2Fgpt-5.5", true, false},
	} {
		output.Reset()
		ctx := &fasthttp.RequestCtx{}
		ctx.Request.Header.SetMethod(fasthttp.MethodPost)
		ctx.Request.SetRequestURI(testCase.path)
		ctx.Request.SetBodyString(`{"input":[{"type":"message","role":"user","content":"SEALED_CODEX_RUN_ID:run-1"}]}`)
		handler(ctx)
		wantPath := fmt.Sprintf(`"path_exact":%t`, testCase.pathExact)
		wantQuery := fmt.Sprintf(`"query_empty":%t`, testCase.queryEmpty)
		if !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-arrival/v1"`) ||
			!strings.Contains(output.String(), `"method_post":true`) || !strings.Contains(output.String(), wantPath) ||
			!strings.Contains(output.String(), wantQuery) || strings.Contains(output.String(), "ingress-rejected") {
			t.Fatalf("non-canonical route %q not safely classified: %q", testCase.path, output.String())
		}
	}
	if nextCalls != 5 {
		t.Fatalf("non-canonical routes were swallowed: calls=%d", nextCalls)
	}
}

func TestSealedCodexResponsesObserverDoesNotCorrelateMetadataMarker(t *testing.T) {
	t.Setenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER", "1")
	t.Setenv("LAB_RUN_ID", "run-1")
	var output bytes.Buffer
	handler := wrapSealedCodexIngressObserverWithWriter(func(*fasthttp.RequestCtx) {}, &output)
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetMethod(fasthttp.MethodPost)
	ctx.Request.SetRequestURI("/wrong")
	ctx.Request.SetBodyString(`{"input":[{"type":"message","role":"user","content":"no marker","metadata":"SEALED_CODEX_RUN_ID:run-1"}]}`)
	handler(ctx)
	if output.Len() != 0 {
		t.Fatalf("metadata marker falsely correlated request: %s", output.String())
	}
}

func TestSealedCodexResponsesObserverPreservesWrappedResponse(t *testing.T) {
	t.Setenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER", "1")
	t.Setenv("LAB_RUN_ID", "run-1")
	var output bytes.Buffer
	handler := wrapSealedCodexIngressObserverWithWriter(func(ctx *fasthttp.RequestCtx) {
		ctx.SetStatusCode(fasthttp.StatusBadRequest)
	}, &output)
	ctx := &fasthttp.RequestCtx{}
	ctx.Request.Header.SetMethod(fasthttp.MethodPost)
	ctx.Request.SetRequestURI("/openai/v1/responses")
	ctx.Request.Header.Set("x-openai-internal-codex-responses-lite", "true")
	ctx.Request.SetBodyString(`{"model":"bedrock_mantle/gpt-5.5","stream":true,"parallel_tool_calls":false,"input":[{"type":"additional_tools","role":"developer","tools":[{"type":"tool_search","execution":"client","description":"search tools","parameters":{"type":"object"}}]},{"type":"message","role":"user","content":"SEALED_CODEX_RUN_ID:run-1"}]}`)
	handler(ctx)
	if ctx.Response.StatusCode() != fasthttp.StatusBadRequest || !strings.Contains(output.String(), `"schema":"sealed-codex-bifrost-ingress/v1"`) {
		t.Fatalf("outer observer altered response or missed ingress: status=%d output=%s", ctx.Response.StatusCode(), output.String())
	}
}
