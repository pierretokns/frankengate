package a2apush

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/framework/objectstore"
)

func TestMemoryOutboxClaimRetryLeaseAndDeadLetter(t *testing.T) {
	now := time.Date(2026, time.August, 11, 12, 0, 0, 0, time.UTC)
	store := NewMemoryOutboxStore(func() time.Time { return now })
	record := DeliveryRecord{ID: "delivery-1", TenantID: "tenant-1", TaskID: "task-1", ConfigID: "push-1", PayloadRef: "object://payload-1", PayloadHash: PayloadDigest([]byte("task"))}
	if err := store.Enqueue(context.Background(), record); err != nil {
		t.Fatalf("enqueue: %v", err)
	}
	claimed, err := store.Claim(context.Background(), record.TenantID, record.TaskID, record.ID, now, time.Minute)
	if err != nil || claimed.Status != DeliveryInFlight || claimed.Attempts != 1 {
		t.Fatalf("claim = %#v, err=%v", claimed, err)
	}
	if _, err := store.Claim(context.Background(), record.TenantID, record.TaskID, record.ID, now.Add(30*time.Second), time.Minute); !errors.Is(err, ErrOutboxConflict) {
		t.Fatalf("active lease was not enforced: %v", err)
	}
	failed, err := store.Fail(context.Background(), record.TenantID, record.TaskID, record.ID, now, time.Second, 2, errors.New("temporary downstream failure"))
	if err != nil || failed.Status != DeliveryPending || failed.NextAttempt.IsZero() {
		t.Fatalf("retry state = %#v, err=%v", failed, err)
	}
	claimed, err = store.Claim(context.Background(), record.TenantID, record.TaskID, record.ID, now.Add(time.Second), time.Minute)
	if err != nil || claimed.Attempts != 2 {
		t.Fatalf("second claim = %#v, err=%v", claimed, err)
	}
	dead, err := store.Fail(context.Background(), record.TenantID, record.TaskID, record.ID, now.Add(time.Second), time.Second, 2, errors.New("permanent downstream failure"))
	if err != nil || dead.Status != DeliveryDeadLetter {
		t.Fatalf("dead-letter state = %#v, err=%v", dead, err)
	}
}

func TestMemoryOutboxTenantIsolationAndCompletion(t *testing.T) {
	store := NewMemoryOutboxStore(nil)
	record := DeliveryRecord{ID: "delivery-1", TenantID: "tenant-1", TaskID: "task-1", ConfigID: "push-1", PayloadRef: "object://payload-1", PayloadHash: PayloadDigest([]byte("task"))}
	if err := store.Enqueue(context.Background(), record); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Get(context.Background(), "tenant-2", record.TaskID, record.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("cross-tenant outbox lookup returned %v", err)
	}
	claimed, err := store.Claim(context.Background(), record.TenantID, record.TaskID, record.ID, time.Now(), time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Complete(context.Background(), record.TenantID, record.TaskID, record.ID, claimed.UpdatedAt); err != nil {
		t.Fatalf("complete: %v", err)
	}
	if _, err := store.Claim(context.Background(), record.TenantID, record.TaskID, record.ID, time.Now().Add(time.Hour), time.Minute); !errors.Is(err, ErrOutboxConflict) {
		t.Fatalf("terminal delivery was claimable: %v", err)
	}
}

func TestOutboxListsTenantsForRestartRecovery(t *testing.T) {
	store := NewMemoryOutboxStore(nil)
	for _, tenant := range []string{"tenant-b", "tenant-a", "tenant-a"} {
		record := DeliveryRecord{ID: "delivery-" + tenant, TenantID: tenant, TaskID: "task-1", ConfigID: "push-1", PayloadRef: "object://payload-1", PayloadHash: PayloadDigest([]byte(tenant))}
		if err := store.Enqueue(context.Background(), record); err != nil && !errors.Is(err, ErrAlreadyExists) {
			t.Fatal(err)
		}
	}
	tenants, err := store.ListTenants(context.Background())
	if err != nil || strings.Join(tenants, ",") != "tenant-a,tenant-b" {
		t.Fatalf("tenants=%v err=%v", tenants, err)
	}
}

func TestDurableOutboxPersistsRecoveryStateWithoutIdentityLeaks(t *testing.T) {
	backend := objectstore.NewInMemoryObjectStore()
	now := time.Date(2026, time.August, 11, 12, 0, 0, 0, time.UTC)
	store := NewDurableOutboxStore(backend, "a2a/outbox", func() time.Time { return now })
	record := DeliveryRecord{
		ID: "delivery-1", TenantID: "tenant-1", TaskID: "task-1", ConfigID: "push-1",
		PayloadRef: "object://payload-1", PayloadHash: PayloadDigest([]byte("task")),
	}
	if err := store.Enqueue(context.Background(), record); err != nil {
		t.Fatalf("enqueue: %v", err)
	}
	for _, key := range backend.Keys() {
		if strings.Contains(key, record.TenantID) || strings.Contains(key, record.TaskID) || strings.Contains(key, record.ID) {
			t.Fatalf("durable outbox key leaked identity: %q", key)
		}
	}
	claimed, err := store.Claim(context.Background(), record.TenantID, record.TaskID, record.ID, now, time.Minute)
	if err != nil || claimed.Status != DeliveryInFlight {
		t.Fatalf("claim: %#v / %v", claimed, err)
	}
	if _, err := store.Get(context.Background(), "tenant-2", record.TaskID, record.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("cross-tenant lookup returned %v", err)
	}
	failed, err := store.Fail(context.Background(), record.TenantID, record.TaskID, record.ID, now, time.Second, 2, errors.New("temporary"))
	if err != nil || failed.Status != DeliveryPending {
		t.Fatalf("failed delivery state: %#v / %v", failed, err)
	}
	rows, err := store.List(context.Background(), record.TenantID)
	if err != nil || len(rows) != 1 || rows[0].Status != DeliveryPending {
		t.Fatalf("list after recovery: %#v / %v", rows, err)
	}
}
