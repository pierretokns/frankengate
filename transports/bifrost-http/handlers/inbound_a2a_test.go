package handlers

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/framework/modelcatalog"
	"github.com/maximhq/bifrost/framework/objectstore"
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
	if err := handler.storeTask(context.Background(), "tenant\x00issuer\x00subject", task); err != nil {
		t.Fatal(err)
	}
	if _, ok, err := handler.loadTask(context.Background(), "tenant\x00issuer\x00subject", task.ID); err != nil || !ok {
		t.Fatal("stored task should be available before TTL")
	}
	clock = clock.Add(maxA2ATaskTTL + time.Nanosecond)
	if _, ok, err := handler.loadTask(context.Background(), "tenant\x00issuer\x00subject", task.ID); err != nil || ok {
		t.Fatal("expired task must not be available")
	}
}

func TestInboundA2ATaskPersistsThroughObjectStore(t *testing.T) {
	store := objectstore.NewInMemoryObjectStore()
	config := &lib.Config{ObjectStore: store}
	first := &InboundA2AHandler{config: config, tasks: make(map[string]storedA2ATask), now: time.Now}
	task := a2aTask{ID: "durable-task", Status: a2aTaskStatus{State: "completed"}}
	partition := "tenant\x00issuer\x00subject"
	if err := first.storeTask(context.Background(), partition, task); err != nil {
		t.Fatalf("store durable task: %v", err)
	}
	second := &InboundA2AHandler{config: config, tasks: make(map[string]storedA2ATask), now: time.Now}
	got, ok, err := second.loadTask(context.Background(), partition, task.ID)
	if err != nil || !ok || got.ID != task.ID || got.Status.State != task.Status.State {
		t.Fatalf("object-store task round trip = %#v, ok=%v, err=%v", got, ok, err)
	}
}

func TestInboundA2ARejectsMissingOrStaleDurableAuthorityEpoch(t *testing.T) {
	principal := authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer", Subject: "subject"}
	handler := &InboundA2AHandler{authorityStore: authorityValidationStore{err: authorityepoch.ErrStaleEpoch}}
	ctx := &fasthttp.RequestCtx{}
	ctx.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, principal)
	if err := handler.validateInboundA2AAuthority(ctx, "task-1"); err == nil {
		t.Fatal("missing epoch reference must fail closed when durable authority is configured")
	}
	ctx.SetUserValue(schemas.BifrostContextKeyAuthorizationEpochReference, authorityepoch.Reference{Principal: principal, Epoch: 3, Kind: authorityepoch.ArtifactA2ATask, ID: "task-1"})
	if err := handler.validateInboundA2AAuthority(ctx, "task-1"); err != authorityepoch.ErrStaleEpoch {
		t.Fatalf("stale epoch error = %v, want %v", err, authorityepoch.ErrStaleEpoch)
	}

	valid := &InboundA2AHandler{authorityStore: inboundA2AAuthorityStore{
		authorityValidationStore: authorityValidationStore{},
		row:                      &configstoreTables.TablePrincipalAuthorizationEpoch{Epoch: 4, Active: true},
	}}
	validCtx := &fasthttp.RequestCtx{}
	validCtx.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, principal)
	if err := valid.validateInboundA2AAuthority(validCtx, "task-2"); err != nil {
		t.Fatalf("current durable epoch should authorize the task: %v", err)
	}
}

type inboundA2AAuthorityStore struct {
	authorityValidationStore
	row *configstoreTables.TablePrincipalAuthorizationEpoch
}

func (s inboundA2AAuthorityStore) GetPrincipalAuthorizationEpoch(context.Context, authorityepoch.Principal) (*configstoreTables.TablePrincipalAuthorizationEpoch, error) {
	return s.row, nil
}

func TestInboundA2ATaskGetIsTenantScoped(t *testing.T) {
	handler := &InboundA2AHandler{tasks: make(map[string]storedA2ATask), now: time.Now}
	partitionA := "tenant-a\x00issuer\x00subject"
	if err := handler.storeTask(context.Background(), partitionA, a2aTask{ID: "same", Status: a2aTaskStatus{State: "completed"}}); err != nil {
		t.Fatal(err)
	}

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
