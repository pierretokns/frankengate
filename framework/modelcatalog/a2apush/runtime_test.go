package a2apush

import (
	"context"
	"net"
	"testing"
	"time"
)

type runtimeDelivery struct{ requests []DeliveryRequest }

func (d *runtimeDelivery) Deliver(_ context.Context, request DeliveryRequest) error {
	d.requests = append(d.requests, request)
	return nil
}

func TestRuntimeEnqueuesDurablePayloadAndWorkerDelivers(t *testing.T) {
	configs := NewMemoryStore(time.Now)
	if err := configs.Create(context.Background(), Config{ID: "push-1", TaskID: "task-1", TenantID: "tenant-1", URL: "https://notify.example.test/a2a"}); err != nil {
		t.Fatal(err)
	}
	outbox := NewMemoryOutboxStore(time.Now)
	payloads := NewMemoryPayloadStore()
	delivery := &runtimeDelivery{}
	runtime := NewRuntime(configs, outbox, payloads, delivery, Policy{
		AllowedHosts:         []string{"notify.example.test"},
		RequireDNSResolution: true,
		Resolver: ResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
			return []net.IPAddr{{IP: net.ParseIP("203.0.113.10")}}, nil
		}),
	})
	payload := []byte(`{"id":"task-1","state":"completed"}`)
	if err := runtime.Enqueue(context.Background(), "tenant-1", "task-1", payload); err != nil {
		t.Fatal(err)
	}
	stats, err := runtime.Worker.RunOnce(context.Background(), "tenant-1")
	if err != nil || stats.Delivered != 1 || len(delivery.requests) != 1 {
		t.Fatalf("stats=%#v requests=%#v err=%v", stats, delivery.requests, err)
	}
	if string(delivery.requests[0].Payload) != string(payload) || delivery.requests[0].DeliveryID == "" || delivery.requests[0].PayloadHash == "" {
		t.Fatalf("delivery request=%#v", delivery.requests[0])
	}
}

func TestRuntimeStopIsIdempotent(t *testing.T) {
	runtime := NewRuntime(nil, nil, nil, nil, Policy{})
	ctx, cancel := context.WithCancel(context.Background())
	runtime.Start(ctx)
	cancel()
	runtime.Stop()
	runtime.Stop()
}
