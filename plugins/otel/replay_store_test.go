package otel

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
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

func TestReplayQualityMetadataIsBoundedAndRedacted(t *testing.T) {
	dir := t.TempDir()
	store, err := NewJSONLReplayStore(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	trace := &schemas.Trace{TraceID: "quality", Attributes: map[string]any{
		"tenant": "acme", "frankengate.retrieval.expected": 4,
		"frankengate.retrieval.retrieved": 2, "frankengate.retrieval.precision": 0.5,
		"frankengate.retrieval.recall": 0.25, "frankengate.retrieval.query": "secret",
	}}
	if err := store.Put(context.Background(), trace); err != nil {
		t.Fatal(err)
	}
	record, err := store.Get(context.Background(), "acme", "quality")
	if err != nil {
		t.Fatal(err)
	}
	if record.RetrievalQuality == nil || record.RetrievalQuality.Expected != 4 || record.RetrievalQuality.Precision != 0.5 {
		t.Fatalf("quality metadata missing: %+v", record.RetrievalQuality)
	}
	encoded, err := json.Marshal(record)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(encoded), "secret") {
		t.Fatalf("raw retrieval content leaked: %s", encoded)
	}
}

func TestJSONLReplayStoreListIsTenantScopedBoundedAndRestartSafe(t *testing.T) {
	dir := t.TempDir()
	store, err := NewJSONLReplayStore(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	for _, id := range []string{"trace-1", "trace-2", "trace-3"} {
		if err := store.Put(context.Background(), &schemas.Trace{TraceID: id, Attributes: map[string]any{"tenant": "acme"}}); err != nil {
			t.Fatal(err)
		}
	}
	if err := store.Put(context.Background(), &schemas.Trace{TraceID: "other-1", Attributes: map[string]any{"tenant": "other"}}); err != nil {
		t.Fatal(err)
	}
	rows, err := store.List(context.Background(), "acme", 2)
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 2 || rows[0].TraceID != "trace-3" || rows[1].TraceID != "trace-2" {
		t.Fatalf("expected newest bounded records, got %#v", rows)
	}
	if _, err := store.List(context.Background(), "", 2); err == nil {
		t.Fatal("expected tenant requirement")
	}
	if err := store.Close(); err != nil {
		t.Fatal(err)
	}

	// A new process can export the same tenant partition without access to
	// another tenant's records.
	restarted, err := NewJSONLReplayStore(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	defer restarted.Close()
	rows, err = restarted.List(context.Background(), "acme", 10)
	if err != nil || len(rows) != 3 {
		t.Fatalf("restart list failed: len=%d err=%v", len(rows), err)
	}
	if rows[0].TenantID != "acme" || rows[0].TraceID != "trace-3" {
		t.Fatalf("unexpected tenant/export result: %#v", rows[0])
	}
	other, err := restarted.List(context.Background(), "other", 10)
	if err != nil || len(other) != 1 || other[0].TenantID != "other" {
		t.Fatalf("other tenant partition unavailable: %#v err=%v", other, err)
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

func TestTenantReplayStorePinsAuthorizationBoundary(t *testing.T) {
	store, err := NewJSONLReplayStore(t.TempDir(), false)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	view, err := NewTenantReplayStore(store, "acme")
	if err != nil {
		t.Fatal(err)
	}
	if err := view.Put(context.Background(), &schemas.Trace{TraceID: "ok", Attributes: map[string]any{"tenant": "acme"}}); err != nil {
		t.Fatal(err)
	}
	if err := view.Put(context.Background(), &schemas.Trace{TraceID: "wrong", Attributes: map[string]any{"tenant": "other"}}); err == nil {
		t.Fatal("tenant-pinned view accepted a trace from another tenant")
	}
	if _, err := view.Get(context.Background(), "other", "ok"); !os.IsPermission(err) {
		t.Fatalf("cross-tenant get should fail closed with permission error, got %v", err)
	}
	if _, err := view.List(context.Background(), "other", 10); !os.IsPermission(err) {
		t.Fatalf("cross-tenant list should fail closed with permission error, got %v", err)
	}
	if _, err := NewTenantReplayStore(store, " "); err == nil {
		t.Fatal("blank tenant must not create an unrestricted replay view")
	}
}
