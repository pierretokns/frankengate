package privacy

import (
	"bytes"
	"compress/gzip"
	"encoding/base64"
	"encoding/json"
	"errors"
	"os"
	"testing"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws/protocol/eventstream"
)

const (
	testCanary = "fg-canary-secret-07"
	testSecret = "sk-proj-test-secret-should-never-survive"
)

func TestCaptureSanitizerJSONTokenizesSecretsAndPreservesCorpusRelations(t *testing.T) {
	sanitizer, err := NewCaptureSanitizer(testCapturePolicy())
	if err != nil {
		t.Fatal(err)
	}
	raw := RawCapture{
		ID:          "cap-01",
		CorpusID:    "corpus-a",
		Method:      "POST",
		URL:         "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses?trace=" + testCanary + "&api_key=" + testSecret,
		ContentType: "application/json",
		Headers: map[string][]string{
			"Authorization":    {"Bearer " + testSecret},
			"Content-Type":     {"application/json"},
			"X-Request-ID":     {"req-secret-123"},
			"X-Unsafe-Header":  {testSecret},
			"X-BF-Client-Name": {"mantle-contract-capture"},
		},
		Body: []byte(`{
			"model":"gpt-5.6-sol",
			"previous_response_id":"resp_real_previous",
			"project_id":"proj_real",
			"workspace_id":"workspace_real",
			"tool_call_id":"call_real",
			"input":[{"role":"user","content":"prompt contains ` + testCanary + ` and alex@example.com"}],
			"metadata":{"api_key":"` + testSecret + `","encoded_canary":"` + base64.StdEncoding.EncodeToString([]byte(testCanary)) + `"},
			"url":"https://example.com/callback?signature=` + testSecret + `"
		}`),
	}

	first, err := sanitizer.Sanitize(raw)
	if err != nil {
		t.Fatalf("sanitize first capture: %v", err)
	}
	body := mustMarshal(t, first)
	assertNotContains(t, body, testCanary)
	assertNotContains(t, body, testSecret)
	assertNotContains(t, body, "alex@example.com")
	assertNotContains(t, body, "resp_real_previous")
	assertNotContains(t, body, "proj_real")
	assertNotContains(t, body, "workspace_real")
	assertNotContains(t, body, "call_real")
	assertNotContains(t, body, "signature=")
	if len(first.CanaryDetections) != 1 || first.CanaryDetections[0] != "prompt-canary" {
		t.Fatalf("canary detections = %#v", first.CanaryDetections)
	}
	if _, ok := first.URL.Query["trace"]; !ok {
		t.Fatalf("allowlisted query key was not retained as a token: %#v", first.URL.Query)
	}
	if _, ok := first.URL.Query["api_key"]; ok {
		t.Fatalf("non-allowlisted credential query survived: %#v", first.URL.Query)
	}
	if _, ok := first.Headers["Authorization"]; ok {
		t.Fatalf("authorization header survived: %#v", first.Headers)
	}
	if _, ok := first.Headers["X-Unsafe-Header"]; ok {
		t.Fatalf("unsafe header survived: %#v", first.Headers)
	}

	payload := first.Payload.(map[string]any)
	prevToken := payload["previous_response_id"].(string)
	if prevToken == "" || prevToken == "resp_real_previous" {
		t.Fatalf("previous_response_id was not tokenized: %#v", payload)
	}

	secondRaw := raw
	secondRaw.Body = []byte(`{"previous_response_id":"resp_real_previous","input":[{"role":"user","content":"retry body"}]}`)
	second, err := sanitizer.Sanitize(secondRaw)
	if err != nil {
		t.Fatalf("sanitize second capture: %v", err)
	}
	if second.Payload.(map[string]any)["previous_response_id"] != prevToken {
		t.Fatalf("same corpus did not preserve relation token: first=%q second=%q", prevToken, second.Payload.(map[string]any)["previous_response_id"])
	}

	thirdRaw := secondRaw
	thirdRaw.CorpusID = "corpus-b"
	third, err := sanitizer.Sanitize(thirdRaw)
	if err != nil {
		t.Fatalf("sanitize third capture: %v", err)
	}
	if third.Payload.(map[string]any)["previous_response_id"] == prevToken {
		t.Fatal("different corpus reused a relation token")
	}
}

func TestCaptureSanitizerFailsClosedForUnknownPathEncodingAndDepth(t *testing.T) {
	sanitizer, err := NewCaptureSanitizer(testCapturePolicy())
	if err != nil {
		t.Fatal(err)
	}
	base := RawCapture{
		CorpusID:    "corpus-a",
		Method:      "POST",
		URL:         "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses",
		ContentType: "application/json",
		Body:        []byte(`{"input":"safe"}`),
	}
	unknownPath := base
	unknownPath.URL = "https://bedrock-mantle.us-east-1.api.aws/openai/v1/unreviewed"
	if _, err := sanitizer.Sanitize(unknownPath); err == nil {
		t.Fatal("unknown path sanitized successfully; want fail-closed error")
	}
	unknownEncoding := base
	unknownEncoding.ContentEncoding = "br"
	if _, err := sanitizer.Sanitize(unknownEncoding); err == nil {
		t.Fatal("unknown content encoding sanitized successfully; want fail-closed error")
	}

	shallowPolicy := testCapturePolicy()
	shallowPolicy.MaxDecodeDepth = 2
	shallow, err := NewCaptureSanitizer(shallowPolicy)
	if err != nil {
		t.Fatal(err)
	}
	deep := base
	deep.Body = []byte(`{"a":{"b":{"c":{"d":"secret"}}}}`)
	if _, err := shallow.Sanitize(deep); err == nil {
		t.Fatal("over-deep JSON sanitized successfully; want fail-closed error")
	}
}

func TestCaptureSanitizerHandlesSSEGzipAndEventStreamWithoutLeakingRawContent(t *testing.T) {
	sanitizer, err := NewCaptureSanitizer(testCapturePolicy())
	if err != nil {
		t.Fatal(err)
	}

	sse := RawCapture{
		CorpusID:    "corpus-stream",
		Method:      "POST",
		URL:         "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses",
		ContentType: "text/event-stream",
		Body: []byte("event: response.output_text.delta\n" +
			"data: {\"id\":\"evt_real\",\"delta\":\"stream says " + testCanary + " and " + testSecret + "\"}\n\n" +
			"data: [DONE]\n\n"),
	}
	got, err := sanitizer.Sanitize(sse)
	if err != nil {
		t.Fatalf("sanitize sse: %v", err)
	}
	if got.PayloadFormat != "sse" {
		t.Fatalf("payload format = %q", got.PayloadFormat)
	}
	body := mustMarshal(t, got)
	assertNotContains(t, body, testCanary)
	assertNotContains(t, body, testSecret)
	assertContains(t, body, "[DONE]")

	gzipBody := gzipBytes(t, []byte(`{"output_text":"gzip says `+testCanary+` and `+testSecret+`"}`))
	gz := RawCapture{
		CorpusID:        "corpus-gzip",
		Method:          "POST",
		URL:             "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses",
		ContentType:     "application/json",
		ContentEncoding: "gzip",
		Body:            gzipBody,
	}
	got, err = sanitizer.Sanitize(gz)
	if err != nil {
		t.Fatalf("sanitize gzip: %v", err)
	}
	body = mustMarshal(t, got)
	assertNotContains(t, body, testCanary)
	assertNotContains(t, body, testSecret)

	eventBody := eventStreamBytes(t, []byte(`{"bytes":"`+base64.StdEncoding.EncodeToString([]byte(testCanary))+`","delta":{"text":"eventstream `+testSecret+`"}}`))
	es := RawCapture{
		CorpusID:    "corpus-eventstream",
		Method:      "POST",
		URL:         "https://bedrock-mantle.us-east-1.api.aws/converse-stream",
		ContentType: "application/vnd.amazon.eventstream",
		Body:        eventBody,
	}
	got, err = sanitizer.Sanitize(es)
	if err != nil {
		t.Fatalf("sanitize eventstream: %v", err)
	}
	body = mustMarshal(t, got)
	assertNotContains(t, body, testCanary)
	assertNotContains(t, body, testSecret)
}

func TestCaptureSanitizerRejectsCompressionBombs(t *testing.T) {
	policy := testCapturePolicy()
	policy.MaxCompressionRatio = 2
	policy.MaxDecodedBytes = 1024
	sanitizer, err := NewCaptureSanitizer(policy)
	if err != nil {
		t.Fatal(err)
	}
	capture := RawCapture{
		CorpusID:        "corpus-a",
		Method:          "POST",
		URL:             "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses",
		ContentType:     "application/json",
		ContentEncoding: "gzip",
		Body:            gzipBytes(t, bytes.Repeat([]byte("A"), 4096)),
	}
	if _, err := sanitizer.Sanitize(capture); err == nil {
		t.Fatal("compression bomb sanitized successfully; want fail-closed error")
	}
}

func TestFileQuarantineEncryptsCleansUpAndDestroysMemoryKey(t *testing.T) {
	now := time.Unix(1_700_000_000, 0).UTC()
	q, err := NewFileQuarantine(t.TempDir(), time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	raw := []byte(`{"authorization":"Bearer ` + testSecret + `"}`)
	record, err := q.Put("cap-01", raw, now)
	if err != nil {
		t.Fatalf("put quarantine record: %v", err)
	}
	onDisk, err := os.ReadFile(record.Path)
	if err != nil {
		t.Fatal(err)
	}
	assertNotContains(t, onDisk, testSecret)
	assertNotContains(t, onDisk, "authorization")
	plaintext, err := q.Read(record)
	if err != nil {
		t.Fatalf("read quarantine record: %v", err)
	}
	if !bytes.Equal(plaintext, raw) {
		t.Fatalf("decrypted quarantine plaintext mismatch: %s", plaintext)
	}
	if err := q.Delete(record); err != nil {
		t.Fatalf("delete quarantine record: %v", err)
	}
	if _, err := os.Stat(record.Path); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("quarantine record still exists after cleanup: %v", err)
	}

	record, err = q.Put("cap-02", raw, now)
	if err != nil {
		t.Fatal(err)
	}
	q.Destroy()
	if _, err := q.Read(record); err == nil {
		t.Fatal("destroyed memory key still decrypted quarantine record")
	}

	q2, err := NewFileQuarantine(t.TempDir(), time.Second)
	if err != nil {
		t.Fatal(err)
	}
	expired, err := q2.Put("cap-03", raw, now)
	if err != nil {
		t.Fatal(err)
	}
	if err := q2.Janitor(now.Add(2 * time.Second)); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(expired.Path); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("expired quarantine record still exists after janitor: %v", err)
	}
}

func TestBuildPromotableArtifactRequiresIndependentReviewAndMatchingHashes(t *testing.T) {
	sanitizer, err := NewCaptureSanitizer(testCapturePolicy())
	if err != nil {
		t.Fatal(err)
	}
	capture, err := sanitizer.Sanitize(RawCapture{
		CorpusID:    "corpus-a",
		Method:      "POST",
		URL:         "https://bedrock-mantle.us-east-1.api.aws/openai/v1/responses",
		ContentType: "application/json",
		Body:        []byte(`{"input":"` + testCanary + `","api_key":"` + testSecret + `"}`),
	})
	if err != nil {
		t.Fatal(err)
	}
	approval := ReviewApproval{
		ReviewerID:    "reviewer-security",
		ProducerID:    "recorder-worker",
		ApprovedAt:    time.Unix(1_700_000_100, 0).UTC(),
		SanitizerHash: capture.SanitizerHash,
		PolicyHash:    capture.PolicyHash,
		SourceHash:    capture.SourceHash,
	}
	artifact, err := BuildPromotableArtifact(capture, approval)
	if err != nil {
		t.Fatalf("build promotable artifact: %v", err)
	}
	assertNotContains(t, artifact.Body, testCanary)
	assertNotContains(t, artifact.Body, testSecret)
	if artifact.ArtifactHash == "" || artifact.PolicyHash != capture.PolicyHash {
		t.Fatalf("artifact evidence hashes missing: %#v", artifact)
	}

	sameReviewer := approval
	sameReviewer.ReviewerID = sameReviewer.ProducerID
	if _, err := BuildPromotableArtifact(capture, sameReviewer); err == nil {
		t.Fatal("producer approved its own artifact")
	}
	tampered := approval
	tampered.PolicyHash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	if _, err := BuildPromotableArtifact(capture, tampered); err == nil {
		t.Fatal("approval with mismatched hashes promoted artifact")
	}
}

func testCapturePolicy() SanitizerPolicy {
	return SanitizerPolicy{
		Revision:            "policy-2026-07-21",
		AllowedSchemes:      []string{"https"},
		AllowedHosts:        []string{"bedrock-mantle.us-east-1.api.aws"},
		AllowedPaths:        []string{"/openai/v1/responses", "/v1/chat/completions", "/anthropic/v1/messages", "/converse-stream"},
		AllowedQueryKeys:    []string{"trace", "request_id"},
		AllowedHeaderNames:  []string{"content-type", "accept", "x-request-id", "x-bf-client-name"},
		MaxEncodedBytes:     1 << 20,
		MaxDecodedBytes:     1 << 20,
		MaxCompressionRatio: 200,
		MaxDecodeDepth:      32,
		CanarySecrets:       map[string]string{"prompt-canary": testCanary},
		SourceRevision:      "source@sha256:1111111111111111111111111111111111111111111111111111111111111111",
	}
}

func gzipBytes(t *testing.T, body []byte) []byte {
	t.Helper()
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	if _, err := zw.Write(body); err != nil {
		t.Fatal(err)
	}
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func eventStreamBytes(t *testing.T, payload []byte) []byte {
	t.Helper()
	var buf bytes.Buffer
	encoder := eventstream.NewEncoder()
	err := encoder.Encode(&buf, eventstream.Message{
		Headers: eventstream.Headers{
			{Name: ":message-type", Value: eventstream.StringValue("event")},
			{Name: ":event-type", Value: eventstream.StringValue("contentBlockDelta")},
			{Name: ":content-type", Value: eventstream.StringValue("application/json")},
		},
		Payload: payload,
	})
	if err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func mustMarshal(t *testing.T, value any) []byte {
	t.Helper()
	body, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	return body
}

func assertNotContains(t *testing.T, body []byte, needle string) {
	t.Helper()
	if bytes.Contains(body, []byte(needle)) {
		t.Fatalf("body leaked %q: %s", needle, body)
	}
}

func assertContains(t *testing.T, body []byte, needle string) {
	t.Helper()
	if !bytes.Contains(body, []byte(needle)) {
		t.Fatalf("body did not contain %q: %s", needle, body)
	}
}
