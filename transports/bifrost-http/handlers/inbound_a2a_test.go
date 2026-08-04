package handlers

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

func TestInboundA2ATaskPartitionFailsClosedAndSeparatesTenants(t *testing.T) {
	var first, second fasthttp.RequestCtx
	first.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer", Subject: "user"})
	second.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{Tenant: "tenant-b", Issuer: "issuer", Subject: "user"})
	left, err := inboundA2ATaskPartition(&first)
	if err != nil {
		t.Fatal(err)
	}
	right, err := inboundA2ATaskPartition(&second)
	if err != nil {
		t.Fatal(err)
	}
	if left == right || scopedA2ATaskKey(left, "same") == scopedA2ATaskKey(right, "same") {
		t.Fatal("A2A task idempotency keys must be tenant-scoped")
	}
	var missing fasthttp.RequestCtx
	if _, err := inboundA2ATaskPartition(&missing); err == nil {
		t.Fatal("missing trusted principal must fail closed")
	}
}

func TestInboundRecordCarriesLiveModelCatalogRevision(t *testing.T) {
	catalog := modelcatalog.NewTestCatalog(nil)
	config := &lib.Config{ModelCatalog: catalog}
	record := inboundRecordForConfig("https://gateway.example", config)
	if record.Card.Version == "1" || record.Card.Version == "" {
		t.Fatalf("expected live model catalog revision in card version, got %q", record.Card.Version)
	}
	raw, ok := record.Card.Extensions["frankengate.model_catalog"]
	if !ok {
		t.Fatal("expected model catalog metadata extension")
	}
	var metadata map[string]any
	if err := json.Unmarshal(raw, &metadata); err != nil || metadata["revision"] != record.Card.Version {
		t.Fatalf("invalid model catalog metadata: %s / %#v", raw, metadata)
	}
}

func TestInboundA2ATaskCacheHonorsInjectedClockAndTTL(t *testing.T) {
	clock := time.Date(2026, time.August, 4, 20, 0, 0, 0, time.UTC)
	handler := &InboundA2AHandler{tasks: make(map[string]storedA2ATask), now: func() time.Time { return clock }}
	task := a2aTask{ID: "task-1", Status: a2aTaskStatus{State: "completed"}}
	handler.storeTask("tenant\x00issuer\x00subject", task)
	if _, ok := handler.loadTask("tenant\x00issuer\x00subject", task.ID); !ok {
		t.Fatal("stored task should be available before TTL")
	}
	clock = clock.Add(maxA2ATaskTTL + time.Nanosecond)
	if _, ok := handler.loadTask("tenant\x00issuer\x00subject", task.ID); ok {
		t.Fatal("expired task must not be available")
	}
}

func TestInboundA2ATaskGetIsTenantScoped(t *testing.T) {
	handler := &InboundA2AHandler{tasks: make(map[string]storedA2ATask), now: time.Now}
	partitionA := "tenant-a\x00issuer\x00subject"
	handler.storeTask(partitionA, a2aTask{ID: "same", Status: a2aTaskStatus{State: "completed"}})

	allowed := &fasthttp.RequestCtx{}
	allowed.SetUserValue("task_id", "same")
	allowed.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer", Subject: "subject"})
	handler.taskGet(allowed)
	if allowed.Response.StatusCode() != fasthttp.StatusOK {
		t.Fatalf("same-tenant task lookup status = %d, want 200", allowed.Response.StatusCode())
	}

	denied := &fasthttp.RequestCtx{}
	denied.SetUserValue("task_id", "same")
	denied.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{Tenant: "tenant-b", Issuer: "issuer", Subject: "subject"})
	handler.taskGet(denied)
	if denied.Response.StatusCode() != fasthttp.StatusNotFound {
		t.Fatalf("cross-tenant task lookup status = %d, want 404", denied.Response.StatusCode())
	}
}
