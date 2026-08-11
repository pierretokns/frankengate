package handlers

import (
	"context"
	"encoding/json"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/maximhq/bifrost/framework/modelcatalog"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2apush"
	"github.com/maximhq/bifrost/framework/modelcatalog/inbound"
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

func TestInboundAgentCardDoesNotAdvertiseUnimplementedGRPC(t *testing.T) {
	card, err := inbound.GenerateAgentCard(defaultInboundRecord("https://gateway.example"))
	if err != nil {
		t.Fatalf("generate inbound card: %v", err)
	}
	for _, iface := range card.SupportedInterfaces {
		if iface.ProtocolBinding == a2adiscovery.TransportGRPC {
			t.Fatal("native A2A gRPC is not implemented and must not be advertised")
		}
	}
	if card.PreferredTransport == a2adiscovery.TransportGRPC {
		t.Fatal("native A2A gRPC cannot be the preferred transport")
	}
	if card.Capabilities.PushNotifications {
		t.Fatal("default inbound card advertised push without an injected delivery implementation")
	}
}

type inboundPushDeliveryStub struct{}

func (inboundPushDeliveryStub) Deliver(context.Context, a2apush.DeliveryRequest) error { return nil }

func TestInboundA2APushConfigLifecycleIsTenantScopedAndRedacted(t *testing.T) {
	handler := &InboundA2AHandler{tasks: make(map[string]storedA2ATask), now: time.Now}
	handler.ConfigurePushNotifications(
		a2apush.NewMemoryStore(time.Now),
		a2apush.Policy{
			AllowedHosts:         []string{"notify.example.test"},
			RequireDNSResolution: true,
			Resolver: a2apush.ResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
				return []net.IPAddr{{IP: net.ParseIP("203.0.113.10")}}, nil
			}),
		},
		inboundPushDeliveryStub{},
	)
	if !handler.agentCardRecord("https://gateway.example").Card.Capabilities.PushNotifications {
		t.Fatal("configured push delivery was not advertised")
	}
	partition := "tenant-a\x00issuer\x00subject"
	if err := handler.storeTask(context.Background(), partition, a2aTask{ID: "task-push", Status: a2aTaskStatus{State: "TASK_STATE_WORKING", Timestamp: time.Now()}}); err != nil {
		t.Fatal(err)
	}
	principal := authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer", Subject: "subject"}
	call := func(method string, params any) map[string]any {
		ctx := &fasthttp.RequestCtx{}
		ctx.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, principal)
		ctx.Request.SetBody(mustJSON(map[string]any{"jsonrpc": "2.0", "id": 1, "method": method, "params": params}))
		handler.messageSend(ctx)
		var response map[string]any
		if err := json.Unmarshal(ctx.Response.Body(), &response); err != nil {
			t.Fatalf("decode %s: %v (%s)", method, err, ctx.Response.Body())
		}
		return response
	}
	created := call("CreateTaskPushNotificationConfig", map[string]any{
		"taskId": "task-push",
		"pushNotificationConfig": map[string]any{
			"id":             "push-1",
			"url":            "https://notify.example.test/a2a",
			"authentication": []any{map[string]any{"scheme": "bearer", "credentialRef": "vault://tenant-a/a2a"}},
		},
	})
	result, ok := created["result"].(map[string]any)
	if !ok || result["id"] != "push-1" || result["url"] != "https://notify.example.test/a2a" {
		t.Fatalf("create result = %#v", created)
	}
	if strings.Contains(string(mustJSON(created)), "vault://") {
		t.Fatal("push response leaked credential reference")
	}
	got := call("GetTaskPushNotificationConfig", map[string]any{"taskId": "task-push", "id": "push-1"})
	if got["error"] != nil {
		t.Fatalf("get failed: %#v", got)
	}
	listed := call("ListTaskPushNotificationConfigs", map[string]any{"taskId": "task-push"})
	if list, ok := listed["result"].(map[string]any)["configs"].([]any); !ok || len(list) != 1 {
		t.Fatalf("list result = %#v", listed)
	}
	deleted := call("DeleteTaskPushNotificationConfig", map[string]any{"taskId": "task-push", "id": "push-1"})
	if deleted["error"] != nil {
		t.Fatalf("delete failed: %#v", deleted)
	}
	deletedAgain := call("DeleteTaskPushNotificationConfig", map[string]any{"taskId": "task-push", "id": "push-1"})
	if deletedAgain["error"] != nil {
		t.Fatalf("delete should be idempotent: %#v", deletedAgain)
	}

	rawSecret := call("CreateTaskPushNotificationConfig", map[string]any{
		"taskId": "task-push",
		"url":    "https://notify.example.test/a2a",
		"authentication": []any{map[string]any{
			"scheme": "bearer", "credentials": "raw-token",
		}},
	})
	if rawSecret["error"] == nil {
		t.Fatal("raw push credential was accepted")
	}

	other := &fasthttp.RequestCtx{}
	other.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{Tenant: "tenant-b", Issuer: "issuer", Subject: "subject"})
	other.Request.SetBody(mustJSON(map[string]any{"jsonrpc": "2.0", "id": 1, "method": "GetTaskPushNotificationConfig", "params": map[string]any{"taskId": "task-push", "id": "push-1"}}))
	handler.messageSend(other)
	if !strings.Contains(string(other.Response.Body()), "Task not found") {
		t.Fatalf("cross-tenant push lookup leaked state: %s", other.Response.Body())
	}
}

func TestInboundA2APushConfigAcceptsCurrentFlatWireShape(t *testing.T) {
	cfg, err := pushConfigFromRequest(a2aPushConfigRequest{
		ID:             "push-current",
		TaskID:         "task-1",
		URL:            "https://notify.example.test/a2a",
		Authentication: mustJSON(map[string]string{"scheme": "bearer", "credentialRef": "vault://ref"}),
	}, "tenant-1", "task-1")
	if err != nil || cfg.ID != "push-current" || cfg.AuthScheme != "bearer" || cfg.CredentialRef != "vault://ref" {
		t.Fatalf("current flat push config = %#v err=%v", cfg, err)
	}
	encoded, err := json.Marshal(pushConfigResult(cfg))
	if err != nil || strings.Contains(string(encoded), "vault://") || !strings.Contains(string(encoded), `"authentication":{"scheme":"bearer"}`) {
		t.Fatalf("redacted current push response = %s err=%v", encoded, err)
	}
}

func TestInboundA2AStreamReplayCursorSuppressesDuplicates(t *testing.T) {
	handler := &InboundA2AHandler{streamStates: make(map[string]*a2aStreamState)}
	first := handler.publishA2AStreamEvent("task-stream", []byte(`{"state":"working"}`), false)
	second := handler.publishA2AStreamEvent("task-stream", []byte(`{"state":"completed"}`), true)
	if first.ID != "1" || second.ID != "2" {
		t.Fatalf("stream event ids = %q, %q", first.ID, second.ID)
	}
	replay, subscriber, unsubscribe, terminal := handler.subscribeA2AStream("task-stream", 1)
	defer unsubscribe()
	if !terminal || subscriber != nil || len(replay) != 1 || replay[0].ID != "2" || string(replay[0].Body) != `{"state":"completed"}` {
		t.Fatalf("replay=%#v subscriber=%v terminal=%v", replay, subscriber, terminal)
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

func TestInboundA2AJSONRPCTaskLifecycleMethodsAreScoped(t *testing.T) {
	handler := &InboundA2AHandler{tasks: make(map[string]storedA2ATask), now: time.Now}
	partition := "tenant-a\x00issuer\x00subject"
	if err := handler.storeTask(context.Background(), partition, a2aTask{ID: "working", ContextID: "ctx-1", Status: a2aTaskStatus{State: "TASK_STATE_WORKING", Timestamp: time.Now()}}); err != nil {
		t.Fatal(err)
	}
	principal := authorityepoch.Principal{Tenant: "tenant-a", Issuer: "issuer", Subject: "subject"}
	call := func(method string, params string) map[string]any {
		ctx := &fasthttp.RequestCtx{}
		ctx.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, principal)
		ctx.Request.Header.SetMethod("POST")
		ctx.Request.SetBody([]byte(`{"jsonrpc":"2.0","id":1,"method":"` + method + `","params":` + params + `}`))
		handler.messageSend(ctx)
		var response map[string]any
		if err := json.Unmarshal(ctx.Response.Body(), &response); err != nil {
			t.Fatalf("decode %s response: %v (%s)", method, err, ctx.Response.Body())
		}
		return response
	}
	get := call("GetTask", `{"id":"working"}`)
	if get["error"] != nil {
		t.Fatalf("GetTask unexpectedly failed: %#v", get)
	}
	cancel := call("CancelTask", `{"id":"working"}`)
	result, ok := cancel["result"].(map[string]any)
	if !ok || result["status"].(map[string]any)["state"] != "TASK_STATE_CANCELED" {
		t.Fatalf("CancelTask result = %#v", cancel)
	}
	list := call("ListTasks", `{"contextId":"ctx-1","includeArtifacts":true}`)
	if list["error"] != nil || len(list["result"].(map[string]any)["tasks"].([]any)) != 1 {
		t.Fatalf("ListTasks result = %#v", list)
	}
	other := &fasthttp.RequestCtx{}
	other.SetUserValue(schemas.BifrostContextKeyAuthorizationPrincipal, authorityepoch.Principal{Tenant: "tenant-b", Issuer: "issuer", Subject: "subject"})
	other.Request.SetBody([]byte(`{"jsonrpc":"2.0","id":1,"method":"GetTask","params":{"id":"working"}}`))
	handler.messageSend(other)
	if !strings.Contains(string(other.Response.Body()), "Task not found") {
		t.Fatalf("cross-tenant JSON-RPC lookup leaked task: %s", other.Response.Body())
	}
}
