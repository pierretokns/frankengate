package handlers

import (
	"strings"
	"testing"

	"github.com/valyala/fasthttp"
)

func TestSealedCodexIngressRequiresExactLiteShape(t *testing.T) {
	valid := `{"model":"bedrock_mantle/gpt-5.5","stream":true,"parallel_tool_calls":false,"input":[{"type":"additional_tools","role":"developer","tools":[{"type":"custom","name":"apply_patch"}]},{"type":"message","role":"user","content":"SEALED_CODEX_RUN_ID:run-1"}]}`
	check := func(body string, headers map[string]string) error {
		ctx := &fasthttp.RequestCtx{}
		ctx.Request.Header.SetMethod("POST")
		ctx.Request.SetBodyString(body)
		for k, v := range headers {
			ctx.Request.Header.Set(k, v)
		}
		return observeSealedCodexIngress(ctx, "run-1")
	}
	header := map[string]string{"x-openai-internal-codex-responses-lite": "true"}
	if err := check(valid, header); err != nil {
		t.Fatal(err)
	}
	// 0.144.5 ToolSpec serializes client tool search as type=tool_search in Lite input.
	toolSearch := strings.Replace(valid, `{"type":"custom","name":"apply_patch"}`, `{"type":"tool_search","execution":"client","description":"search tools","parameters":{"type":"object"}}`, 1)
	if err := check(toolSearch, header); err != nil {
		t.Fatal("0.144.5 tool_search Lite shape rejected")
	}
	webSearch := strings.Replace(valid, `{"type":"custom","name":"apply_patch"}`, `{"type":"web_search","external_web_access":false}`, 1)
	if err := check(webSearch, header); err != nil {
		t.Fatal("0.144.5 web_search Lite shape rejected")
	}
	indexedWebSearch := strings.Replace(webSearch, `"external_web_access":false`, `"external_web_access":true,"indexed_web_access":true`, 1)
	if err := check(indexedWebSearch, header); err != nil {
		t.Fatal("0.144.5 indexed web_search Lite shape rejected")
	}
	mutants := []struct {
		body    string
		headers map[string]string
	}{
		{strings.Replace(valid, `"stream":true`, `"stream":false`, 1), header},
		{strings.Replace(valid, `"parallel_tool_calls":false`, `"parallel_tool_calls":true`, 1), header},
		{strings.Replace(valid, `,"parallel_tool_calls":false`, ``, 1), header},
		{strings.Replace(valid, `"additional_tools"`, `"message"`, 1), header},
		{strings.Replace(valid, `,"input":[{"type":"additional_tools","role":"developer","tools":[{"type":"custom","name":"apply_patch"}]},{"type":"message","role":"user","content":"SEALED_CODEX_RUN_ID:run-1"}]`, ``, 1), header},
		{strings.Replace(valid, `[{"type":"additional_tools","role":"developer","tools":[{"type":"custom","name":"apply_patch"}]},{"type":"message","role":"user","content":"SEALED_CODEX_RUN_ID:run-1"}]`, `[]`, 1), header},
		{strings.Replace(valid, `[{"type":"custom","name":"apply_patch"}]`, `[]`, 1), header},
		{strings.Replace(valid, `"custom"`, `"unknown"`, 1), header},
		{strings.Replace(toolSearch, `"execution":"client"`, `"execution":"server"`, 1), header},
		{strings.Replace(toolSearch, `"parameters":{"type":"object"}`, `"parameters":null`, 1), header},
		{strings.Replace(toolSearch, `"parameters":{"type":"object"}`, `"parameters":"object"`, 1), header},
		{strings.Replace(toolSearch, `"parameters":{"type":"object"}`, `"parameters":{"type":"string"}`, 1), header},
		{strings.Replace(webSearch, `"external_web_access":false`, `"external_web_access":false,"indexed_web_access":true`, 1), header},
		{strings.Replace(webSearch, `"external_web_access":false`, `"external_web_access":true,"indexed_web_access":false`, 1), header},
		{strings.Replace(valid, `SEALED_CODEX_RUN_ID:run-1`, `SEALED_CODEX_RUN_ID:other`, 1), header},
		{strings.Replace(valid, `SEALED_CODEX_RUN_ID:run-1`, `no marker`, 1), header},
		{strings.Replace(valid, `SEALED_CODEX_RUN_ID:run-1`, `SEALED_CODEX_RUN_ID:run-1 SEALED_CODEX_RUN_ID:run-1`, 1), header},
		{strings.Replace(valid, `"model":`, `"model":"duplicate","model":`, 1), header},
		{strings.Replace(valid, `"name":"apply_patch"`, `"name":"a","name":"b"`, 1), header},
		{strings.TrimSuffix(valid, "}") + `,"instructions":"x"}`, header},
		{strings.TrimSuffix(valid, "}") + `,"tools":[]}`, header},
		{valid, map[string]string{}},
		{valid, map[string]string{"x-openai-internal-codex-responses-lite": "false"}},
		{valid, map[string]string{"x-openai-internal-codex-responses-lite": "true", "upgrade": "websocket"}},
	}
	for i, m := range mutants {
		if check(m.body, m.headers) == nil {
			t.Fatalf("mutant %d accepted", i)
		}
	}
	if err := observeSealedCodexIngress(&fasthttp.RequestCtx{}, "bad run id"); err == nil {
		t.Fatal("invalid configured run ID accepted")
	}
	duplicate := &fasthttp.RequestCtx{}
	duplicate.Request.Header.SetMethod("POST")
	duplicate.Request.SetBodyString(valid)
	duplicate.Request.Header.Add("x-openai-internal-codex-responses-lite", "true")
	duplicate.Request.Header.Add("x-openai-internal-codex-responses-lite", "true")
	if observeSealedCodexIngress(duplicate, "run-1") == nil {
		t.Fatal("duplicate Lite headers accepted")
	}
}

func TestSealedIngressObserverRequiresBothStartupGates(t *testing.T) {
	t.Setenv("LAB_RUN_ID", "run-1")
	t.Setenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER", "")
	if got := sealedIngressObserverRunID(); got != "" {
		t.Fatalf("observer enabled without explicit gate: %q", got)
	}
	t.Setenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER", "1")
	if got := sealedIngressObserverRunID(); got != "run-1" {
		t.Fatalf("observer did not bind valid run ID: %q", got)
	}
	t.Setenv("LAB_RUN_ID", "bad run id")
	defer func() {
		if recover() == nil {
			t.Fatal("invalid gated run ID did not fail startup")
		}
	}()
	sealedIngressObserverRunID()
}
