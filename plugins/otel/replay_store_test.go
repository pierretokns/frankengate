package otel

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

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

func TestReplayOptInStillRedactsHeadersIdentityAndToolPayloads(t *testing.T) {
	store, err := NewJSONLReplayStore(t.TempDir(), true)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	trace := &schemas.Trace{
		TraceID: "pii", RequestHeaders: map[string]string{
			"authorization": "Bearer top-secret", "x-coder-user": "alice@example.com", "x-forwarded-for": "203.0.113.4",
		},
		Attributes: map[string]any{"tenant": "acme", "coder.workspace": "alice@example.com", "safe": "hello alice@example.com"},
		PluginLogs: []schemas.PluginLogEntry{{Message: "contact alice@example.com"}},
		Spans: []*schemas.Span{{Attributes: map[string]any{
			"mcp.tool.name": "lookup", "mcp.tool.input": `{"ssn":"123"}`, "mcp.tool.result": "private result", "safe": "bob@example.com",
		}}},
	}
	if err := store.Put(context.Background(), trace); err != nil {
		t.Fatal(err)
	}
	record, err := store.Get(context.Background(), "acme", "pii")
	if err != nil {
		t.Fatal(err)
	}
	if record.Trace.RequestHeaders != nil {
		t.Fatal("request headers must never be persisted in replay")
	}
	if _, ok := record.Trace.Attributes["coder.workspace"]; ok {
		t.Fatal("Coder identity leaked into replay")
	}
	if _, ok := record.Trace.Spans[0].Attributes["mcp.tool.input"]; ok {
		t.Fatal("tool arguments leaked into replay")
	}
	if _, ok := record.Trace.Spans[0].Attributes["mcp.tool.result"]; ok {
		t.Fatal("tool result leaked into replay")
	}
	if got := record.Trace.Attributes["safe"]; got != "hello [REDACTED]" {
		t.Fatalf("safe metadata was not PII-redacted: %#v", got)
	}
}

func TestReplayRedactsStructuredStringMapAttributes(t *testing.T) {
	store, err := NewJSONLReplayStore(t.TempDir(), true)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	trace := &schemas.Trace{TraceID: "dimensions", Attributes: map[string]any{
		"tenant": "acme",
		// x-bf-dim-* headers are represented as map[string]string. This must
		// receive the same PII treatment as ordinary string attributes.
		"bifrost.dimensions": map[string]string{
			"desk": "alice@example.com",
			"safe": "research",
			"email": "alice@example.com",
		},
	}}
	if err := store.Put(context.Background(), trace); err != nil {
		t.Fatal(err)
	}
	record, err := store.Get(context.Background(), "acme", "dimensions")
	if err != nil {
		t.Fatal(err)
	}
	dimensions, ok := record.Trace.Attributes["bifrost.dimensions"].(map[string]any)
	if !ok {
		t.Fatalf("structured dimensions changed type or missing: %#v", record.Trace.Attributes["bifrost.dimensions"])
	}
	if got := dimensions["desk"]; got != "[REDACTED]" {
		t.Fatalf("dimension PII leaked: %#v", got)
	}
	if _, ok := dimensions["email"]; ok {
		t.Fatal("identity-like dimension key was persisted")
	}
	if got := dimensions["safe"]; got != "research" {
		t.Fatalf("safe dimension changed: %#v", got)
	}
}

func TestReplayRedactsNestedStructuredSlices(t *testing.T) {
	store, err := NewJSONLReplayStore(t.TempDir(), true)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	trace := &schemas.Trace{TraceID: "nested", Attributes: map[string]any{
		"tenant": "acme",
		"dimensions": []map[string]any{{
			"desk":  "alice@example.com",
			"email": "alice@example.com",
			"safe":  "research",
		}},
	}}
	if err := store.Put(context.Background(), trace); err != nil {
		t.Fatal(err)
	}
	record, err := store.Get(context.Background(), "acme", "nested")
	if err != nil {
		t.Fatal(err)
	}
	dimensions, ok := record.Trace.Attributes["dimensions"].([]any)
	if !ok || len(dimensions) != 1 {
		t.Fatalf("nested dimensions changed type or missing: %#v", record.Trace.Attributes["dimensions"])
	}
	clean, ok := dimensions[0].(map[string]any)
	if !ok {
		t.Fatalf("nested dimensions item changed type: %#v", dimensions[0])
	}
	if got := clean["desk"]; got != "[REDACTED]" {
		t.Fatalf("nested dimension PII leaked: %#v", got)
	}
	if _, ok := clean["email"]; ok {
		t.Fatal("identity-like nested dimension key was persisted")
	}
	if got := clean["safe"]; got != "research" {
		t.Fatalf("safe nested dimension changed: %#v", got)
	}
}

func TestReplayRedactsRootSpanAndEventAttributes(t *testing.T) {
	store, err := NewJSONLReplayStore(t.TempDir(), true)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	root := &schemas.Span{SpanID: "root", StatusMsg: "failed for alice@example.com", Events: []schemas.SpanEvent{{
		Name: "mcp.tool", Attributes: map[string]any{
			"tool.arguments": `{"email":"alice@example.com"}`,
			"safe":           "contact bob@example.com",
		},
	}}}
	trace := &schemas.Trace{TraceID: "root-events", Attributes: map[string]any{"tenant": "acme"}, RootSpan: root}
	if err := store.Put(context.Background(), trace); err != nil {
		t.Fatal(err)
	}
	record, err := store.Get(context.Background(), "acme", "root-events")
	if err != nil {
		t.Fatal(err)
	}
	if record.Trace.RootSpan == nil || len(record.Trace.RootSpan.Events) != 1 {
		t.Fatalf("root span/events were not persisted: %#v", record.Trace.RootSpan)
	}
	event := record.Trace.RootSpan.Events[0]
	if _, ok := event.Attributes["tool.arguments"]; ok {
		t.Fatal("tool event arguments leaked into replay")
	}
	if got := event.Attributes["safe"]; got != "contact [REDACTED]" {
		t.Fatalf("event PII was not redacted: %#v", got)
	}
	if got := record.Trace.RootSpan.StatusMsg; got != "failed for [REDACTED]" {
		t.Fatalf("span status PII was not redacted: %q", got)
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

func TestJSONLReplayStoreRetentionIsTenantScopedAndFailClosed(t *testing.T) {
	dir := t.TempDir()
	store, err := NewJSONLReplayStore(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	old := time.Now().UTC().Add(-48 * time.Hour)
	recent := time.Now().UTC().Add(-time.Hour)
	write := func(tenant, id string, captured time.Time) {
		record := ReplayRecord{SchemaVersion: 1, TenantID: tenant, TraceID: id, CapturedAt: captured, Trace: &schemas.Trace{TraceID: id}}
		payload, _ := json.Marshal(record)
		if err := os.WriteFile(filepath.Join(dir, safeTenant(tenant)+".jsonl"), append(payload, '\n'), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	write("acme", "old", old)
	write("acme", "recent", recent)
	// An invalid row must survive because the retention predicate cannot
	// authenticate its tenant or timestamp.
	if err := os.WriteFile(filepath.Join(dir, "acme.jsonl"), []byte("not-json\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	// Recreate the complete partition after the malformed-row append.
	for _, r := range []ReplayRecord{{SchemaVersion: 1, TenantID: "acme", TraceID: "old", CapturedAt: old}, {SchemaVersion: 1, TenantID: "acme", TraceID: "recent", CapturedAt: recent}} {
		payload, _ := json.Marshal(r)
		f, err := os.OpenFile(filepath.Join(dir, "acme.jsonl"), os.O_APPEND|os.O_WRONLY, 0o600)
		if err != nil {
			t.Fatal(err)
		}
		_, _ = f.Write(append(payload, '\n'))
		_ = f.Close()
	}
	if _, err := store.DeleteBefore(context.Background(), "", recent); err == nil {
		t.Fatal("blank tenant must fail closed")
	}
	removed, err := store.DeleteBefore(context.Background(), "acme", recent)
	if err != nil || removed != 1 {
		t.Fatalf("retention deletion removed=%d err=%v", removed, err)
	}
	if _, err := store.Get(context.Background(), "acme", "old"); !os.IsNotExist(err) {
		t.Fatalf("old record should be deleted, got %v", err)
	}
	if _, err := store.Get(context.Background(), "acme", "recent"); err != nil {
		t.Fatalf("recent record should remain: %v", err)
	}
	if _, err := store.DeleteBefore(context.Background(), "other", time.Now().UTC()); err != nil && !os.IsNotExist(err) {
		t.Fatalf("other tenant should not affect acme: %v", err)
	}
	data, err := os.ReadFile(filepath.Join(dir, "acme.jsonl"))
	if err != nil || !strings.Contains(string(data), "not-json") {
		t.Fatalf("malformed row was not preserved: %q err=%v", data, err)
	}
}
