package openai

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

func decisionsFixture(t *testing.T, name string) []byte {
	t.Helper()
	b, err := os.ReadFile("testdata/decisions/" + name + ".json")
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestDecisionsContractFixtures(t *testing.T) {
	body := decisionsFixture(t, "request")
	req, err := ParseOpenAIDecisionsRequest(body)
	if err != nil {
		t.Fatal(err)
	}
	resp, err := ValidateOpenAIDecisionsResponse(decisionsFixture(t, "response"), req)
	if err != nil {
		t.Fatal(err)
	}
	if resp.Answers[3].Type != "refusal" || resp.Usage.InputTokens != 100 {
		t.Fatal("lost refusal or usage")
	}
	// Confidence is a separate numeric field; the official SDK does not bound it.
	extendedConfidence := strings.Replace(string(decisionsFixture(t, "response")), `"confidence": 0.9`, `"confidence": 1.7`, 1)
	if _, err := ValidateOpenAIDecisionsResponse([]byte(extendedConfidence), req); err != nil {
		t.Fatal("invented a confidence range outside the official contract", err)
	}
	// Ordinal values are JSON numbers, including decimal/exponent spellings.
	numericOrdinals := strings.Replace(string(decisionsFixture(t, "response")), `"value": 0`, `"value": 0.0`, 1)
	numericOrdinals = strings.Replace(numericOrdinals, `"value": 1`, `"value": 1e0`, 1)
	if _, err := ValidateOpenAIDecisionsResponse([]byte(numericOrdinals), req); err != nil {
		t.Fatal("rejected equivalent numeric ordinals", err)
	}
	// The boolean true and string "true" are different categories.
	req.Questions[1].Choices = []OpenAIDecisionChoice{{Value: json.RawMessage(`true`)}, {Value: json.RawMessage(`"true"`)}}
	b, _ := json.Marshal(req)
	if _, err := ParseOpenAIDecisionsRequest(b); err != nil {
		t.Fatal(err)
	}
	// Extension objects may use arbitrary keys without influencing typed fields.
	extension := strings.Replace(string(body), `"model":`, `"future_metadata":{"MODEL":"free-form"},"model":`, 1)
	if _, err := ParseOpenAIDecisionsRequest([]byte(extension)); err != nil {
		t.Fatal("rejected a non-colliding extension object", err)
	}
}

func TestDecisionsRejectInvalidRequests(t *testing.T) {
	base := `{"model":"gpt-6-luna","input":"private sentinel","questions":[{"type":"predicate","instructions":"check"}]}`
	for name, body := range map[string]string{
		"missing input":          `{"model":"gpt-6-luna","questions":[{"type":"predicate","instructions":"check"}]}`,
		"unsupported model":      strings.Replace(base, "gpt-6-luna", "gpt-6-sol", 1),
		"stream false":           strings.Replace(base, `"input":`, `"stream":false,"input":`, 1),
		"stream true":            strings.Replace(base, `"input":`, `"stream":true,"input":`, 1),
		"duplicate model":        strings.Replace(base, `"model":`, `"model":"gpt-6-sol","model":`, 1),
		"case variant model":     strings.Replace(base, `"model":`, `"MODEL":"gpt-6-sol","model":`, 1),
		"shadowed model":         strings.Replace(base, `"model":"gpt-6-luna"`, `"model":"gpt-6-sol","MODEL":"gpt-6-luna"`, 1),
		"case variant questions": strings.Replace(base, `"questions":`, `"QUESTIONS":`, 1),
		"case variant choices":   strings.Replace(base, `{"type":"predicate","instructions":"check"}`, `{"type":"choice","instructions":"check","CHOICES":[{"value":true}]}`, 1),
		"assistant":              strings.Replace(base, `"private sentinel"`, `[{"role":"assistant","content":"x"}]`, 1),
		"empty message type":     strings.Replace(base, `"private sentinel"`, `[{"role":"user","type":"","content":"x"}]`, 1),
		"null message type":      strings.Replace(base, `"private sentinel"`, `[{"role":"user","type":null,"content":"x"}]`, 1),
		"hosted image":           strings.Replace(base, `"private sentinel"`, `[{"role":"user","content":[{"type":"input_image","image_url":"https://example.com/image.png"}]}]`, 1),
		"file":                   strings.Replace(base, `"private sentinel"`, `[{"role":"user","content":[{"type":"input_file","file_id":"file-test"}]}]`, 1),
		"bad base64":             strings.Replace(base, `"private sentinel"`, `[{"role":"user","content":[{"type":"input_image","image_url":"data:image/png;base64,!!!"}]}]`, 1),
		"number choices":         strings.Replace(base, `{"type":"predicate","instructions":"check"}`, `{"type":"choice","instructions":"check","choices":[{"value":42}]}`, 1),
		"duplicate choice":       strings.Replace(base, `{"type":"predicate","instructions":"check"}`, `{"type":"choice","instructions":"check","choices":[{"value":true},{"value":true}]}`, 1),
		"missing instructions":   strings.Replace(base, `,"instructions":"check"`, "", 1),
		"null question name":     strings.Replace(base, `"instructions":"check"`, `"instructions":"check","name":null`, 1),
		"null description":       strings.Replace(base, `{"type":"predicate","instructions":"check"}`, `{"type":"choice","instructions":"check","choices":[{"value":true,"description":null}]}`, 1),
		"trailing":               base + ` {}`,
	} {
		t.Run(name, func(t *testing.T) {
			_, err := ParseOpenAIDecisionsRequest([]byte(body))
			if err == nil {
				t.Fatal("accepted invalid request")
			}
			if strings.Contains(err.Error(), "private sentinel") {
				t.Fatal("evidence in validation error")
			}
		})
	}
	var messages []any
	for i := 0; i < 129; i++ {
		messages = append(messages, map[string]any{"role": "user", "content": []any{map[string]any{"type": "input_image", "image_url": "data:image/png;base64,YQ=="}}})
	}
	b, _ := json.Marshal(messages)
	if _, err := ParseOpenAIDecisionsRequest([]byte(strings.Replace(base, `"private sentinel"`, string(b), 1))); err == nil {
		t.Fatal("accepted 129 images")
	}
}

func TestDecisionsRejectInvalidResponses(t *testing.T) {
	req, err := ParseOpenAIDecisionsRequest(decisionsFixture(t, "request"))
	if err != nil {
		t.Fatal(err)
	}
	good := string(decisionsFixture(t, "response"))
	for name, body := range map[string]string{
		"probability":      strings.Replace(good, `0.92`, `1.92`, 1),
		"choice":           strings.Replace(good, `"choice": "billing"`, `"choice": false`, 1),
		"name":             strings.Replace(good, `"name": "department"`, `"name": "other"`, 1),
		"score":            strings.Replace(good, `"score": 1.1`, `"score": 2.0`, 1),
		"distribution":     strings.Replace(good, `0.95`, `0.85`, 1),
		"negative usage":   strings.Replace(good, `"input_tokens": 100`, `"input_tokens": -100`, 1),
		"missing usage":    strings.Replace(good, `"input_tokens": 100,`, "", 1),
		"null score index": strings.Replace(good, `"value": 0`, `"value": null`, 1),
		"negative detail":  strings.Replace(good, `"cached_tokens": 20`, `"cached_tokens": -20`, 1),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := ValidateOpenAIDecisionsResponse([]byte(body), req); err == nil {
				t.Fatal("accepted invalid response")
			}
		})
	}
	// Required null names are distinct from omitted names.
	var missingName map[string]any
	_ = json.Unmarshal([]byte(good), &missingName)
	delete(missingName["answers"].([]any)[3].(map[string]any), "name")
	missingBody, _ := json.Marshal(missingName)
	if _, err := ValidateOpenAIDecisionsResponse(missingBody, req); err == nil {
		t.Fatal("accepted missing refusal name")
	}
	// -0 and 0 denote the same ordinal; raw token spelling cannot evade uniqueness.
	req.Questions[2].Levels[1].Label = req.Questions[2].Levels[0].Label
	duplicate := strings.Replace(good, `"value": 1`, `"value": -0`, 1)
	duplicate = strings.Replace(duplicate, `"label": "Workaround available"`, `"label": "Cosmetic"`, 1)
	if _, err := ValidateOpenAIDecisionsResponse([]byte(duplicate), req); err == nil {
		t.Fatal("accepted duplicate score ordinal")
	}
}

func TestDecisionsProviderWire(t *testing.T) {
	reqBody, respBody := decisionsFixture(t, "request"), decisionsFixture(t, "response")
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if r.URL.Path != "/v1/decisions" || r.Method != "POST" {
			t.Errorf("wrong upstream method/path")
		}
		body, _ := io.ReadAll(r.Body)
		if string(body) != string(reqBody) {
			t.Error("wire request changed")
		}
		if r.Header.Get("Authorization") != "Bearer test-only" || r.Header.Get("X-Bf-Vk") != "" {
			t.Error("incorrect auth forwarding")
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Request-Id", "decision-local")
		_, _ = w.Write(respBody)
	}))
	defer server.Close()
	p := NewOpenAIProvider(&schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{BaseURL: server.URL, AllowPrivateNetwork: true, DefaultRequestTimeoutInSeconds: 1}}, passthroughTestLogger{})
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	key := schemas.Key{Value: *schemas.NewSecretVar("test-only")}
	req := &schemas.BifrostPassthroughRequest{Provider: schemas.OpenAI, Model: "gpt-6-luna", Method: "POST", Path: "/v1/decisions", Body: reqBody, SafeHeaders: map[string]string{"content-type": "application/json"}}
	resp, bErr := p.Passthrough(ctx, key, req)
	if bErr != nil {
		t.Fatalf("provider: %v", bErr)
	}
	if string(resp.Body) != string(respBody) || resp.PassthroughUsage == nil || !resp.PassthroughUsage.LLMUsage.OpenAIDecisions {
		t.Fatal("response/usage changed")
	}
	if resp.Headers["X-Request-Id"] != "decision-local" {
		t.Fatal("lost upstream request id")
	}
	bad := *req
	bad.Model = "unrelated"
	if _, err := p.Passthrough(ctx, key, &bad); err == nil {
		t.Fatal("model mismatch accepted")
	}
	if _, err := p.PassthroughStream(ctx, nil, nil, key, req); err == nil {
		t.Fatal("stream accepted")
	}
	if calls.Load() != 1 {
		t.Fatal("invalid request reached upstream")
	}
}

func TestDecisionsProviderErrorsAndCancellation(t *testing.T) {
	for _, tc := range []struct {
		name   string
		status int
		body   string
		cancel bool
	}{
		{"auth", 401, `{"error":{"message":"invalid api key","type":"authentication_error"}}`, false},
		{"throttle", 429, `{"error":{"message":"slow down","code":"slow_down"}}`, false},
		{"malformed", 200, `{"unexpected":"private upstream sentinel"}`, false},
		{"cancel", 200, `{}`, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			entered := make(chan struct{})
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				close(entered)
				if tc.cancel {
					time.Sleep(100 * time.Millisecond)
				}
				w.Header().Set("Retry-After", "1")
				w.WriteHeader(tc.status)
				_, _ = io.WriteString(w, tc.body)
			}))
			defer server.Close()
			p := NewOpenAIProvider(&schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{BaseURL: server.URL, AllowPrivateNetwork: true, DefaultRequestTimeoutInSeconds: 1}}, passthroughTestLogger{})
			ctx, cancel := schemas.NewBifrostContextWithCancel(context.Background())
			defer cancel()
			if tc.cancel {
				go func() { <-entered; cancel() }()
			}
			resp, bErr := p.Passthrough(ctx, schemas.Key{}, &schemas.BifrostPassthroughRequest{Provider: schemas.OpenAI, Model: "gpt-6-luna", Method: "POST", Path: "/v1/decisions", Body: decisionsFixture(t, "request")})
			if tc.status >= 400 {
				if bErr != nil || resp.StatusCode != tc.status || string(resp.Body) != tc.body || resp.Headers["Retry-After"] != "1" {
					t.Fatal("upstream error altered")
				}
			} else if bErr == nil {
				t.Fatal("expected gateway failure")
			}
			if bErr != nil && strings.Contains(bErr.Error.Message, "private upstream sentinel") {
				t.Fatal("payload leaked into gateway error")
			}
		})
	}
}

func TestDecisionsUsageAndMalformedAnswerSettlement(t *testing.T) {
	request := decisionsFixture(t, "request")
	good := string(decisionsFixture(t, "response"))
	for _, bad := range []string{
		strings.Replace(good, `"input_tokens": 100,`, "", 1),
		strings.Replace(good, `"cached_tokens": 20`, `"cached_tokens": null`, 1),
		strings.Replace(good, `"reasoning_tokens": 0`, `"reasoning_tokens": -1`, 1),
	} {
		if ExtractOpenAIPassthroughUsage("POST", "/v1/decisions", request, []byte(bad)) != nil {
			t.Fatal("invalid usage became billable")
		}
	}
	malformed := strings.Replace(good, `"probability": 0.92`, `"probability": "malformed"`, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, malformed)
	}))
	defer server.Close()
	p := NewOpenAIProvider(&schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{BaseURL: server.URL, AllowPrivateNetwork: true, DefaultRequestTimeoutInSeconds: 1}}, passthroughTestLogger{})
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	resp, bErr := p.Passthrough(ctx, schemas.Key{}, &schemas.BifrostPassthroughRequest{Provider: schemas.OpenAI, Model: "gpt-6-luna", Method: "POST", Path: "/v1/decisions", Body: request})
	if resp != nil || bErr == nil || bErr.StatusCode == nil || *bErr.StatusCode != 502 || bErr.ExtraFields.BilledUsage == nil || bErr.ExtraFields.BilledUsage.PromptTokens != 100 || !bErr.ExtraFields.BilledUsage.OpenAIDecisions {
		t.Fatal("invalid answers were accepted or valid billed usage was lost")
	}
}

func TestDecisionsProviderTimeout(t *testing.T) {
	response := decisionsFixture(t, "response")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(1200 * time.Millisecond)
		_, _ = w.Write(response)
	}))
	defer server.Close()
	p := NewOpenAIProvider(&schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{BaseURL: server.URL, AllowPrivateNetwork: true, DefaultRequestTimeoutInSeconds: 1}}, passthroughTestLogger{})
	started := time.Now()
	_, bErr := p.Passthrough(schemas.NewBifrostContext(context.Background(), schemas.NoDeadline), schemas.Key{}, &schemas.BifrostPassthroughRequest{Provider: schemas.OpenAI, Model: "gpt-6-luna", Method: "POST", Path: "/v1/decisions", Body: decisionsFixture(t, "request")})
	if bErr == nil || time.Since(started) > 3*time.Second {
		t.Fatal("configured provider timeout was not enforced")
	}
}

func TestDecisionsMalformedSuccessAccountingMarker(t *testing.T) {
	good := string(decisionsFixture(t, "response"))
	for _, tc := range []struct{ name, body, encoding string }{
		{"missing usage", `{"answers":[]}`, ""},
		{"invalid usage", strings.Replace(good, `"input_tokens": 100,`, "", 1), ""},
		{"malformed JSON", `{"private upstream sentinel":`, ""},
		{"invalid gzip", "private upstream sentinel", "gzip"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
				if tc.encoding != "" {
					w.Header().Set("Content-Encoding", tc.encoding)
				}
				_, _ = io.WriteString(w, tc.body)
			}))
			defer server.Close()
			p := NewOpenAIProvider(&schemas.ProviderConfig{NetworkConfig: schemas.NetworkConfig{BaseURL: server.URL, AllowPrivateNetwork: true, DefaultRequestTimeoutInSeconds: 1}}, passthroughTestLogger{})
			resp, bErr := p.Passthrough(schemas.NewBifrostContext(context.Background(), schemas.NoDeadline), schemas.Key{}, &schemas.BifrostPassthroughRequest{Provider: schemas.OpenAI, Model: "gpt-6-luna", Method: "POST", Path: "/v1/decisions", Body: decisionsFixture(t, "request")})
			if resp != nil || bErr == nil || !bErr.ExtraFields.OpenAIDecisionsUpstreamSuccess || bErr.ExtraFields.BilledUsage != nil {
				t.Fatal("known upstream success with unknown usage lost its conservative settlement marker")
			}
			encoded, err := json.Marshal(bErr)
			if err != nil || strings.Contains(string(encoded), "OpenAIDecisionsUpstreamSuccess") || strings.Contains(string(encoded), "private upstream sentinel") {
				t.Fatal("internal marker or evidence leaked into wire error")
			}
		})
	}
}

func TestDecisionsPassthroughPermission(t *testing.T) {
	p := NewOpenAIProvider(&schemas.ProviderConfig{CustomProviderConfig: &schemas.CustomProviderConfig{AllowedRequests: &schemas.AllowedRequests{ChatCompletion: true}}}, passthroughTestLogger{})
	_, bErr := p.Passthrough(schemas.NewBifrostContext(context.Background(), schemas.NoDeadline), schemas.Key{}, &schemas.BifrostPassthroughRequest{Provider: schemas.OpenAI, Model: "gpt-6-luna", Method: "POST", Path: "/v1/decisions", Body: decisionsFixture(t, "request")})
	if bErr == nil {
		t.Fatal("chat permission granted Decisions passthrough")
	}
}

func TestDecisionsRegionalHosts(t *testing.T) {
	for url, want := range map[string]bool{
		"https://us.api.openai.com/v1/decisions":         true,
		"https://eu.api.openai.com/v1/decisions":         true,
		"https://api.openai.com/v1/decisions":            false,
		"https://eu.api.openai.com.invalid/v1/decisions": false,
	} {
		if isOpenAIDecisionsRegionalURL(url) != want {
			t.Fatal("incorrect regional billing host classification")
		}
	}
}
