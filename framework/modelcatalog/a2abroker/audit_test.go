package a2abroker

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/objectstore"
)

func TestDurableCredentialAuditStorePersistsRedactedEvent(t *testing.T) {
	backend := objectstore.NewInMemoryObjectStore()
	store := NewDurableCredentialAuditStore(backend, "a2a/credential-audit", func() time.Time {
		return time.Unix(100, 0).UTC()
	})
	event := CredentialAuditEvent{
		TenantID:   "tenant-a",
		TaskID:     "task-a",
		Endpoint:   "https://agent.example/a2a",
		CardDigest: "sha256:card",
		Kind:       CredentialBearer,
		Outcome:    "resolved",
	}
	if err := store.AppendCredentialAudit(context.Background(), event); err != nil {
		t.Fatal(err)
	}
	objects, err := backend.ListByPrefix(context.Background(), "a2a/credential-audit/")
	if err != nil || len(objects) != 1 {
		t.Fatalf("audit objects=%#v err=%v", objects, err)
	}
	payload, err := backend.Get(context.Background(), objects[0].Key)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(payload), "Bearer opaque") || strings.Contains(string(payload), "secret") {
		t.Fatalf("credential material leaked into audit payload: %s", payload)
	}
	var got CredentialAuditEvent
	if err := json.Unmarshal(payload, &got); err != nil {
		t.Fatal(err)
	}
	if got.TenantID != event.TenantID || got.TaskID != event.TaskID || got.Kind != CredentialBearer || got.Outcome != "resolved" || got.At.IsZero() {
		t.Fatalf("unexpected audit event: %#v", got)
	}
	if strings.Contains(objects[0].Key, "tenant-a") || strings.Contains(objects[0].Key, "task-a") {
		t.Fatalf("object key leaked routing identity: %s", objects[0].Key)
	}
}
