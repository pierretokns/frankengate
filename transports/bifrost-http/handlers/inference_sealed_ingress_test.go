package handlers

import (
	"github.com/valyala/fasthttp"
	"strings"
	"testing"
)

func TestSealedCodexIngressRequiresExactLiteShape(t *testing.T) {
	valid := `{"model":"bedrock_mantle/gpt-5.5","stream":true,"parallel_tool_calls":false,"input":[{"type":"additional_tools","role":"developer","tools":[]}]}`
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
	mutants := []struct {
		body    string
		headers map[string]string
	}{{strings.Replace(valid, `"stream":true`, `"stream":false`, 1), header}, {strings.Replace(valid, `"parallel_tool_calls":false`, `"parallel_tool_calls":true`, 1), header}, {strings.Replace(valid, `"additional_tools"`, `"message"`, 1), header}, {strings.TrimSuffix(valid, "}") + `,"instructions":"x"}`, header}, {strings.TrimSuffix(valid, "}") + `,"tools":[]}`, header}, {valid, map[string]string{}}, {valid, map[string]string{"x-openai-internal-codex-responses-lite": "false"}}, {valid, map[string]string{"x-openai-internal-codex-responses-lite": "true", "upgrade": "websocket"}}}
	for i, m := range mutants {
		if check(m.body, m.headers) == nil {
			t.Fatalf("mutant %d accepted", i)
		}
	}
}
