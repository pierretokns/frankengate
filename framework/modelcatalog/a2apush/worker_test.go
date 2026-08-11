package a2apush

import (
	"context"
	"errors"
	"net"
	"testing"
	"time"
)

type workerDelivery struct {
	requests []DeliveryRequest
	err      error
}

func (d *workerDelivery) Deliver(_ context.Context, request DeliveryRequest) error {
	d.requests = append(d.requests, request)
	return d.err
}

func TestWorkerLoadsBoundedPayloadAndCompletesDurableRecord(t *testing.T) {
	now := time.Date(2026, time.August, 11, 12, 0, 0, 0, time.UTC)
	configs := NewMemoryStore(func() time.Time { return now })
	if err := configs.Create(context.Background(), Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: "https://notify.example.test/a2a"}); err != nil {
		t.Fatal(err)
	}
	outbox := NewMemoryOutboxStore(func() time.Time { return now })
	record := DeliveryRecord{ID: "delivery-1", TenantID: "tenant-1", TaskID: "task-1", ConfigID: "push-1", PayloadRef: "object://payload-1", PayloadHash: PayloadDigest([]byte("payload"))}
	if err := outbox.Enqueue(context.Background(), record); err != nil {
		t.Fatal(err)
	}
	delivery := &workerDelivery{}
	worker := Worker{
		Outbox: outbox, Configs: configs,
		Payloads: PayloadSourceFunc(func(context.Context, string) ([]byte, error) { return []byte("payload"), nil }),
		Delivery: delivery, Policy: workerTestPolicy(), Now: func() time.Time { return now },
	}
	stats, err := worker.RunOnce(context.Background(), "tenant-1")
	if err != nil || stats.Delivered != 1 || len(delivery.requests) != 1 {
		t.Fatalf("worker stats=%#v requests=%#v err=%v", stats, delivery.requests, err)
	}
	if string(delivery.requests[0].Payload) != "payload" || delivery.requests[0].Config.ID != "push-1" {
		t.Fatalf("delivery request=%#v", delivery.requests[0])
	}
	got, err := outbox.Get(context.Background(), "tenant-1", "task-1", "delivery-1")
	if err != nil || got.Status != DeliveryDelivered {
		t.Fatalf("outbox after delivery=%#v err=%v", got, err)
	}
}

func TestWorkerRetriesThenDeadLettersAndDoesNotCrossTenants(t *testing.T) {
	now := time.Date(2026, time.August, 11, 12, 0, 0, 0, time.UTC)
	configs := NewMemoryStore(func() time.Time { return now })
	if err := configs.Create(context.Background(), Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: "https://notify.example.test/a2a"}); err != nil {
		t.Fatal(err)
	}
	outbox := NewMemoryOutboxStore(func() time.Time { return now })
	if err := outbox.Enqueue(context.Background(), DeliveryRecord{ID: "delivery-1", TenantID: "tenant-1", TaskID: "task-1", ConfigID: "push-1", PayloadRef: "object://payload-1", PayloadHash: PayloadDigest([]byte("payload"))}); err != nil {
		t.Fatal(err)
	}
	delivery := &workerDelivery{err: errors.New("downstream unavailable")}
	worker := Worker{Outbox: outbox, Configs: configs, Payloads: PayloadSourceFunc(func(context.Context, string) ([]byte, error) { return []byte("payload"), nil }), Delivery: delivery, Policy: workerTestPolicy(), Now: func() time.Time { return now }, RetryAfter: time.Nanosecond, MaxAttempts: 2}
	if stats, err := worker.RunOnce(context.Background(), "tenant-2"); err != nil || stats.Claimed != 0 {
		t.Fatalf("cross-tenant worker touched state: %#v err=%v", stats, err)
	}
	if stats, err := worker.RunOnce(context.Background(), "tenant-1"); err != nil || stats.Retried != 1 {
		t.Fatalf("first failure stats=%#v err=%v", stats, err)
	}
	now = now.Add(time.Second)
	if stats, err := worker.RunOnce(context.Background(), "tenant-1"); err != nil || stats.DeadLetter != 1 {
		t.Fatalf("second failure stats=%#v err=%v", stats, err)
	}
}

func workerTestPolicy() Policy {
	return Policy{
		AllowedHosts: []string{"notify.example.test"},
		Resolver: ResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
			return []net.IPAddr{{IP: net.ParseIP("203.0.113.10")}}, nil
		}),
	}
}
