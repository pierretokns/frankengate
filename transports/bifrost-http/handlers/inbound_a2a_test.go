package handlers

import (
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/authorityepoch"
	"github.com/maximhq/bifrost/core/schemas"
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
