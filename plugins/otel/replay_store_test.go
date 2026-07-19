package otel

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestJSONLReplayStoreTenantIsolationAndRedaction(t *testing.T) {
	dir := t.TempDir()
	store, err := NewJSONLReplayStore(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	trace := &schemas.Trace{TraceID: "trace-a", RequestID: "req-a", Attributes: map[string]any{"tenant": "acme"}, Spans: []*schemas.Span{{SpanID: "span-a", Attributes: map[string]any{"safe": "ok", "gen_ai.prompt": "secret", "gen_ai.output": "secret"}}}}
	if err := store.Put(context.Background(), trace); err != nil {
		t.Fatal(err)
	}
	record, err := store.Get(context.Background(), "acme", "trace-a")
	if err != nil {
		t.Fatal(err)
	}
	if record.TenantID != "acme" || record.Trace.Spans[0].Attributes["safe"] != "ok" {
		t.Fatalf("unexpected record: %#v", record)
	}
	if _, ok := record.Trace.Spans[0].Attributes["gen_ai.prompt"]; ok {
		t.Fatal("prompt content was persisted")
	}
	if _, err := store.Get(context.Background(), "other", "trace-a"); !os.IsNotExist(err) {
		t.Fatalf("cross-tenant lookup should fail closed, got %v", err)
	}
	if err := store.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(dir, "acme.jsonl")); err != nil {
		t.Fatal(err)
	}
}

func TestJSONLReplayStoreRequiresTenant(t *testing.T) {
	store, err := NewJSONLReplayStore(t.TempDir(), false)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	if err := store.Put(context.Background(), &schemas.Trace{TraceID: "no-tenant"}); err == nil {
		t.Fatal("expected tenant boundary error")
	}
}
