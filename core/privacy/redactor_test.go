package privacy

import (
	"encoding/json"
	"testing"
)

func TestRedactHeadersPreservesAttributionAndCopiesValues(t *testing.T) {
	input := map[string][]string{
		"Authorization":   {"Bearer secret"},
		"X-BF-VK":         {"vk-secret"},
		"X-Workstation":   {"coder-17"},
		"X-Forwarded-For": {"192.0.2.1"},
	}
	got := RedactHeaders(input)
	if got["Authorization"][0] != RedactedValue || got["X-BF-VK"][0] != RedactedValue {
		t.Fatalf("credentials were not redacted: %#v", got)
	}
	if got["X-Workstation"][0] != "coder-17" || got["X-Forwarded-For"][0] != "192.0.2.1" {
		t.Fatalf("attribution was unexpectedly removed: %#v", got)
	}
	input["X-Workstation"][0] = "mutated"
	if got["X-Workstation"][0] != "coder-17" {
		t.Fatal("redacted header result aliases caller storage")
	}
}

func TestRedactJSONRecursesAndRetainsShape(t *testing.T) {
	input := []byte(`{"user":"alice","api_key":"abc","metadata":{"refresh_token":"xyz","workstation":"coder-17"},"items":[{"password":"pw","note":"email alex@example.com"}]}`)
	got, ok := RedactJSON(input)
	if !ok {
		t.Fatal("valid JSON was rejected")
	}
	var decoded map[string]any
	if err := json.Unmarshal(got, &decoded); err != nil {
		t.Fatal(err)
	}
	if decoded["api_key"] != RedactedValue || decoded["metadata"].(map[string]any)["refresh_token"] != RedactedValue {
		t.Fatalf("nested credentials were not redacted: %s", got)
	}
	if decoded["metadata"].(map[string]any)["workstation"] != "coder-17" {
		t.Fatalf("attribution was removed: %s", got)
	}
	if decoded["items"].([]any)[0].(map[string]any)["note"] != "email [REDACTED]" {
		t.Fatalf("PII inside string value was not redacted: %s", got)
	}
}

func TestRedactJSONInvalidFailsClosed(t *testing.T) {
	input := []byte(`{"authorization":"secret"`)
	got, ok := RedactJSON(input)
	if ok || string(got) != string(input) {
		t.Fatalf("invalid payload should be returned unchanged: ok=%v payload=%s", ok, got)
	}
}

func TestRedactTextMasksDirectIdentifiers(t *testing.T) {
	got := RedactText("Contact alex.rivera@example.com or +1 (212) 555-0199 from coder-17.")
	if got != "Contact [REDACTED] or [REDACTED] from coder-17." {
		t.Fatalf("unexpected redaction: %q", got)
	}
}
