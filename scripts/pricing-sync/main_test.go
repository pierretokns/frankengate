package main

import (
	"context"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestValidatePricingDocument(t *testing.T) {
	if _, err := validate([]byte(`{"gpt-x":{"input_cost_per_token":1}}`)); err != nil {
		t.Fatal(err)
	}
	if _, err := validate([]byte(`{"models":{"gpt-x":{}}}`)); err != nil {
		t.Fatal(err)
	}
	for _, raw := range []string{`[]`, `{}`, `{"models":[]}`, `{"gpt-x":null}`, `not-json`} {
		if _, err := validate([]byte(raw)); err == nil {
			t.Errorf("expected rejection for %s", raw)
		}
	}
}

func TestFetchAndPublishLastKnownGood(t *testing.T) {
	raw, err := validate([]byte(`{"models":{"model-a":{"input_cost_per_token":0.1}}}`))
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	now := time.Date(2026, 7, 19, 12, 0, 0, 0, time.UTC)
	if err := publish(dir, "https://example.invalid/pricing.json", raw, now); err != nil {
		t.Fatal(err)
	}
	want, err := os.ReadFile(filepath.Join(dir, "latest-upstream.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(want), "model-a") {
		t.Fatal("published cache missing model")
	}
	before, _ := os.ReadFile(filepath.Join(dir, "latest.json"))
	if _, err := fetch(context.Background(), &http.Client{}, "http://127.0.0.1:1"); err == nil {
		t.Fatal("expected failed fetch")
	}
	after, _ := os.ReadFile(filepath.Join(dir, "latest.json"))
	if string(before) != string(after) {
		t.Fatal("last-known-good artifact changed after failed fetch")
	}
}
