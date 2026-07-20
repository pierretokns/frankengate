package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestValidatePricingDocument(t *testing.T) {
	valid, err := validate([]byte(`{"models":{"gpt-test":{"input":1}}}`))
	if err != nil {
		t.Fatalf("valid document rejected: %v", err)
	}
	if len(valid) == 0 {
		t.Fatal("canonical document is empty")
	}
	for name, raw := range map[string]string{
		"invalid JSON":       `{`,
		"empty object":       `{}`,
		"non-object model":   `{"models":{"gpt-test":1}}`,
		"empty model name":   `{"models":{"":{}}}`,
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := validate([]byte(raw)); err == nil {
				t.Fatal("malformed document was accepted")
			}
		})
	}
}

func TestPublishWritesBrandedEnvelopeAndUpstreamSnapshot(t *testing.T) {
	dir := t.TempDir()
	raw := []byte(`{"gpt-test":{"input":1}}`)
	if err := publish(dir, "https://approved.example/pricing.json", raw, time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)); err != nil {
		t.Fatal(err)
	}
	upstream, err := os.ReadFile(filepath.Join(dir, "latest-upstream.json"))
	if err != nil || string(upstream) != string(append(raw, '\n')) {
		t.Fatalf("upstream snapshot mismatch: %v %q", err, upstream)
	}
	envelope, err := os.ReadFile(filepath.Join(dir, "latest.json"))
	if err != nil {
		t.Fatal(err)
	}
	var got artifact
	if err := json.Unmarshal(envelope, &got); err != nil {
		t.Fatal(err)
	}
	if got.Brand != "FrankenGate" || got.Source != "https://approved.example/pricing.json" {
		t.Fatalf("unexpected envelope metadata: %+v", got)
	}
}
