package a2apush

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/maximhq/bifrost/framework/objectstore"
)

const defaultRuntimePollInterval = 2 * time.Second

// PayloadWriter is the durable payload side of the push outbox. Payload bytes
// are stored separately from delivery metadata so retries do not duplicate
// sensitive task data in the outbox records.
type PayloadWriter interface {
	PayloadSource
	Put(context.Context, string, []byte) error
}

type MemoryPayloadStore struct {
	mu    sync.RWMutex
	items map[string][]byte
}

func NewMemoryPayloadStore() *MemoryPayloadStore {
	return &MemoryPayloadStore{items: make(map[string][]byte)}
}

func (s *MemoryPayloadStore) Put(_ context.Context, ref string, payload []byte) error {
	if s == nil || strings.TrimSpace(ref) == "" {
		return ErrDisabled
	}
	s.mu.Lock()
	s.items[ref] = append([]byte(nil), payload...)
	s.mu.Unlock()
	return nil
}

func (s *MemoryPayloadStore) Load(_ context.Context, ref string) ([]byte, error) {
	if s == nil {
		return nil, ErrDisabled
	}
	s.mu.RLock()
	payload, ok := s.items[ref]
	s.mu.RUnlock()
	if !ok {
		return nil, ErrNotFound
	}
	return append([]byte(nil), payload...), nil
}

type DurablePayloadStore struct {
	store  objectstore.ObjectStore
	prefix string
}

func NewDurablePayloadStore(store objectstore.ObjectStore, prefix string) *DurablePayloadStore {
	return &DurablePayloadStore{store: store, prefix: strings.TrimSuffix(prefix, "/") + "/"}
}

func (s *DurablePayloadStore) Put(ctx context.Context, ref string, payload []byte) error {
	if s == nil || s.store == nil {
		return ErrDisabled
	}
	return s.store.Put(ctx, s.key(ref), payload, map[string]string{"kind": "a2a_push_payload", "digest": PayloadDigest(payload)})
}

func (s *DurablePayloadStore) Load(ctx context.Context, ref string) ([]byte, error) {
	if s == nil || s.store == nil {
		return nil, ErrDisabled
	}
	payload, err := s.store.Get(ctx, s.key(ref))
	if err != nil {
		return nil, ErrNotFound
	}
	return payload, nil
}

func (s *DurablePayloadStore) key(ref string) string {
	return s.prefix + hashPart(ref) + ".json"
}

// Runtime owns the operational bridge between task updates and the durable
// worker. The gateway calls Enqueue after persisting a task snapshot; Start
// then polls only tenants observed by this process and stops with the parent
// context. No goroutine is started by construction.
type Runtime struct {
	Configs  Store
	Outbox   OutboxStore
	Payloads PayloadWriter
	Delivery Delivery
	Policy   Policy

	PollInterval time.Duration
	Worker       Worker

	mu      sync.Mutex
	tenants map[string]struct{}
	stop    context.CancelFunc
	wg      sync.WaitGroup
}

func NewRuntime(configs Store, outbox OutboxStore, payloads PayloadWriter, delivery Delivery, policy Policy) *Runtime {
	runtime := &Runtime{Configs: configs, Outbox: outbox, Payloads: payloads, Delivery: delivery, Policy: policy, tenants: make(map[string]struct{})}
	runtime.Worker = Worker{Outbox: outbox, Configs: configs, Payloads: payloads, Delivery: delivery, Policy: policy}
	return runtime
}

func (r *Runtime) Enqueue(ctx context.Context, tenant, task string, payload []byte) error {
	if r == nil || r.Configs == nil || r.Outbox == nil || r.Payloads == nil {
		return ErrDisabled
	}
	if strings.TrimSpace(tenant) == "" || strings.TrimSpace(task) == "" {
		return errors.New("A2A push tenant and task are required")
	}
	configs, err := r.Configs.List(ctx, tenant, task)
	if err != nil {
		return err
	}
	payloadHash := PayloadDigest(payload)
	for _, cfg := range configs {
		if err := ValidateConfig(ctx, cfg, r.Policy); err != nil {
			return fmt.Errorf("validate A2A push configuration %s: %w", cfg.ID, err)
		}
		ref := runtimePayloadRef(tenant, task, cfg.ID, payloadHash)
		if err := r.Payloads.Put(ctx, ref, payload); err != nil {
			return fmt.Errorf("persist A2A push payload: %w", err)
		}
		record := DeliveryRecord{ID: runtimeDeliveryID(tenant, task, cfg.ID, payloadHash), TenantID: tenant, TaskID: task, ConfigID: cfg.ID, PayloadRef: ref, PayloadHash: payloadHash}
		if err := r.Outbox.Enqueue(ctx, record); err != nil && !errors.Is(err, ErrAlreadyExists) {
			return fmt.Errorf("enqueue A2A push delivery: %w", err)
		}
	}
	r.mu.Lock()
	r.tenants[tenant] = struct{}{}
	r.mu.Unlock()
	return nil
}

func (r *Runtime) Start(ctx context.Context) {
	if r == nil || r.Delivery == nil {
		return
	}
	interval := r.PollInterval
	if interval <= 0 {
		interval = defaultRuntimePollInterval
	}
	workerCtx, cancel := context.WithCancel(ctx)
	r.mu.Lock()
	if r.stop != nil {
		r.mu.Unlock()
		cancel()
		return
	}
	r.stop = cancel
	r.mu.Unlock()
	if tenants, err := r.Outbox.ListTenants(workerCtx); err == nil {
		r.mu.Lock()
		for _, tenant := range tenants {
			r.tenants[tenant] = struct{}{}
		}
		r.mu.Unlock()
	}
	r.wg.Add(1)
	go func() {
		defer r.wg.Done()
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			r.runTenants(workerCtx)
			select {
			case <-workerCtx.Done():
				return
			case <-ticker.C:
			}
		}
	}()
}

func (r *Runtime) Stop() {
	if r == nil {
		return
	}
	r.mu.Lock()
	stop := r.stop
	r.mu.Unlock()
	if stop == nil {
		return
	}
	stop()
	r.wg.Wait()
	r.mu.Lock()
	r.stop = nil
	r.mu.Unlock()
}

func (r *Runtime) runTenants(ctx context.Context) {
	r.mu.Lock()
	tenants := make([]string, 0, len(r.tenants))
	for tenant := range r.tenants {
		tenants = append(tenants, tenant)
	}
	r.mu.Unlock()
	for _, tenant := range tenants {
		if _, err := r.Worker.RunOnce(ctx, tenant); err != nil && !errors.Is(err, ErrDisabled) {
			continue
		}
	}
}

func runtimePayloadRef(tenant, task, configID, payloadHash string) string {
	return "a2a-push/" + runtimeDeliveryID(tenant, task, configID, payloadHash)
}

func runtimeDeliveryID(tenant, task, configID, payloadHash string) string {
	sum := sha256.Sum256([]byte(tenant + "\x00" + task + "\x00" + configID + "\x00" + payloadHash))
	return hex.EncodeToString(sum[:])
}
