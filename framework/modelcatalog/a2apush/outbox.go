package a2apush

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/maximhq/bifrost/framework/objectstore"
)

// DeliveryStatus describes state that a future operator-approved sender can
// consume. Payload bytes are deliberately absent: PayloadRef points to an
// separately governed task/artifact store and PayloadHash supports audit
// correlation without duplicating sensitive content in the outbox.
type DeliveryStatus string

const (
	DeliveryPending    DeliveryStatus = "pending"
	DeliveryInFlight   DeliveryStatus = "in_flight"
	DeliveryDelivered  DeliveryStatus = "delivered"
	DeliveryDeadLetter DeliveryStatus = "dead_letter"
)

// Observation contains only bounded operational labels. It deliberately
// excludes tenant IDs, task IDs, URLs, payloads, and error text.
type Observation struct {
	Outcome    string
	Status     DeliveryStatus
	ErrorClass string
}

// Observer is the optional runtime metrics/audit projection for push delivery.
// Implementations must treat the callback as best-effort and must not persist
// credential material.
type Observer interface {
	ObserveA2APush(context.Context, Observation)
}

type ObserverFunc func(context.Context, Observation)

func (f ObserverFunc) ObserveA2APush(ctx context.Context, observation Observation) {
	if f != nil {
		f(ctx, observation)
	}
}

type DeliveryRecord struct {
	ID          string         `json:"id"`
	TenantID    string         `json:"tenantId"`
	TaskID      string         `json:"taskId"`
	ConfigID    string         `json:"configId"`
	PayloadRef  string         `json:"payloadRef"`
	PayloadHash string         `json:"payloadHash"`
	Status      DeliveryStatus `json:"status"`
	Attempts    int            `json:"attempts"`
	NextAttempt time.Time      `json:"nextAttempt"`
	LeaseUntil  time.Time      `json:"leaseUntil,omitempty"`
	LastError   string         `json:"lastError,omitempty"`
	CreatedAt   time.Time      `json:"createdAt"`
	UpdatedAt   time.Time      `json:"updatedAt"`
}

var ErrOutboxConflict = errors.New("A2A push outbox state conflict")

type OutboxStore interface {
	Enqueue(context.Context, DeliveryRecord) error
	Get(context.Context, string, string, string) (DeliveryRecord, error)
	List(context.Context, string) ([]DeliveryRecord, error)
	ListTenants(context.Context) ([]string, error)
	Claim(context.Context, string, string, string, time.Time, time.Duration) (DeliveryRecord, error)
	Complete(context.Context, string, string, string, time.Time) error
	Fail(context.Context, string, string, string, time.Time, time.Duration, int, error) (DeliveryRecord, error)
}

type MemoryOutboxStore struct {
	mu    sync.Mutex
	now   func() time.Time
	items map[string]DeliveryRecord
}

func NewMemoryOutboxStore(now func() time.Time) *MemoryOutboxStore {
	if now == nil {
		now = time.Now
	}
	return &MemoryOutboxStore{now: now, items: make(map[string]DeliveryRecord)}
}

func (s *MemoryOutboxStore) Enqueue(_ context.Context, record DeliveryRecord) error {
	if strings.TrimSpace(record.ID) == "" || strings.TrimSpace(record.TenantID) == "" || strings.TrimSpace(record.TaskID) == "" || strings.TrimSpace(record.ConfigID) == "" || strings.TrimSpace(record.PayloadRef) == "" || strings.TrimSpace(record.PayloadHash) == "" {
		return errors.New("A2A push outbox identity and payload reference are required")
	}
	if record.Status == "" {
		record.Status = DeliveryPending
	}
	if record.Status != DeliveryPending {
		return errors.New("new A2A push outbox records must be pending")
	}
	if record.CreatedAt.IsZero() {
		record.CreatedAt = s.now().UTC()
	}
	if record.UpdatedAt.IsZero() {
		record.UpdatedAt = record.CreatedAt
	}
	if record.NextAttempt.IsZero() {
		record.NextAttempt = record.CreatedAt
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	key := itemKey(record.TenantID, record.TaskID, record.ID)
	if _, exists := s.items[key]; exists {
		return ErrAlreadyExists
	}
	s.items[key] = record
	return nil
}

func (s *MemoryOutboxStore) Get(_ context.Context, tenant, task, id string) (DeliveryRecord, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	record, ok := s.items[itemKey(tenant, task, id)]
	if !ok {
		return DeliveryRecord{}, ErrNotFound
	}
	return record, nil
}

func (s *MemoryOutboxStore) List(_ context.Context, tenant string) ([]DeliveryRecord, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	result := make([]DeliveryRecord, 0)
	for _, record := range s.items {
		if record.TenantID == tenant {
			result = append(result, record)
		}
	}
	SortDeliveryRecords(result)
	return result, nil
}

func (s *MemoryOutboxStore) ListTenants(_ context.Context) ([]string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	seen := make(map[string]struct{})
	for _, record := range s.items {
		if record.TenantID != "" {
			seen[record.TenantID] = struct{}{}
		}
	}
	tenants := make([]string, 0, len(seen))
	for tenant := range seen {
		tenants = append(tenants, tenant)
	}
	sort.Strings(tenants)
	return tenants, nil
}

func (s *MemoryOutboxStore) Claim(_ context.Context, tenant, task, id string, now time.Time, lease time.Duration) (DeliveryRecord, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := itemKey(tenant, task, id)
	record, ok := s.items[key]
	if !ok {
		return DeliveryRecord{}, ErrNotFound
	}
	if record.Status == DeliveryDelivered || record.Status == DeliveryDeadLetter {
		return DeliveryRecord{}, ErrOutboxConflict
	}
	if record.Status == DeliveryInFlight && record.LeaseUntil.After(now) {
		return DeliveryRecord{}, ErrOutboxConflict
	}
	if record.NextAttempt.After(now) {
		return DeliveryRecord{}, ErrOutboxConflict
	}
	record.Status = DeliveryInFlight
	record.Attempts++
	record.LeaseUntil = now.Add(lease)
	record.UpdatedAt = now.UTC()
	s.items[key] = record
	return record, nil
}

func (s *MemoryOutboxStore) Complete(_ context.Context, tenant, task, id string, now time.Time) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := itemKey(tenant, task, id)
	record, ok := s.items[key]
	if !ok {
		return ErrNotFound
	}
	if record.Status != DeliveryInFlight {
		return ErrOutboxConflict
	}
	record.Status = DeliveryDelivered
	record.LeaseUntil = time.Time{}
	record.UpdatedAt = now.UTC()
	s.items[key] = record
	return nil
}

func (s *MemoryOutboxStore) Fail(_ context.Context, tenant, task, id string, now time.Time, retryAfter time.Duration, maxAttempts int, deliveryErr error) (DeliveryRecord, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := itemKey(tenant, task, id)
	record, ok := s.items[key]
	if !ok {
		return DeliveryRecord{}, ErrNotFound
	}
	if record.Status != DeliveryInFlight {
		return DeliveryRecord{}, ErrOutboxConflict
	}
	record.LeaseUntil = time.Time{}
	record.LastError = safeDeliveryError(deliveryErr)
	if maxAttempts > 0 && record.Attempts >= maxAttempts {
		record.Status = DeliveryDeadLetter
	} else {
		record.Status = DeliveryPending
		record.NextAttempt = now.Add(retryAfter)
	}
	record.UpdatedAt = now.UTC()
	s.items[key] = record
	return record, nil
}

func safeDeliveryError(err error) string {
	if err == nil {
		return "delivery failed"
	}
	message := strings.TrimSpace(err.Error())
	if len(message) > 512 {
		message = message[:512]
	}
	return message
}

func PayloadDigest(payload []byte) string {
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func SortDeliveryRecords(records []DeliveryRecord) {
	sort.SliceStable(records, func(i, j int) bool {
		if records[i].NextAttempt.Equal(records[j].NextAttempt) {
			return records[i].ID < records[j].ID
		}
		return records[i].NextAttempt.Before(records[j].NextAttempt)
	})
}

// DurableOutboxStore persists delivery state in the configured object store.
// Claim is at-least-once: the object-store abstraction has no conditional
// write primitive, so multi-process deployments must use delivery IDs as
// idempotency keys at the eventual sender. Leases still recover abandoned
// claims after a process crash.
type DurableOutboxStore struct {
	mu         sync.Mutex
	store      objectstore.ObjectStore
	prefix     string
	now        func() time.Time
	IsNotFound func(error) bool
}

func NewDurableOutboxStore(store objectstore.ObjectStore, prefix string, now func() time.Time) *DurableOutboxStore {
	if now == nil {
		now = time.Now
	}
	return &DurableOutboxStore{store: store, prefix: strings.TrimSuffix(prefix, "/") + "/", now: now, IsNotFound: defaultIsNotFound}
}

func (s *DurableOutboxStore) Enqueue(ctx context.Context, record DeliveryRecord) error {
	if err := validateDeliveryRecord(record); err != nil {
		return err
	}
	if s == nil || s.store == nil {
		return ErrDisabled
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	key := s.key(record.TenantID, record.TaskID, record.ID)
	if _, err := s.store.Get(ctx, key); err == nil {
		return ErrAlreadyExists
	} else if !s.isNotFound(err) {
		return fmt.Errorf("check existing A2A delivery: %w", err)
	}
	if record.Status == "" {
		record.Status = DeliveryPending
	}
	if record.CreatedAt.IsZero() {
		record.CreatedAt = s.now().UTC()
	}
	if record.UpdatedAt.IsZero() {
		record.UpdatedAt = record.CreatedAt
	}
	if record.NextAttempt.IsZero() {
		record.NextAttempt = record.CreatedAt
	}
	return s.save(ctx, record)
}

func (s *DurableOutboxStore) Get(ctx context.Context, tenant, task, id string) (DeliveryRecord, error) {
	if s == nil || s.store == nil {
		return DeliveryRecord{}, ErrDisabled
	}
	return s.load(ctx, tenant, task, id)
}

func (s *DurableOutboxStore) List(ctx context.Context, tenant string) ([]DeliveryRecord, error) {
	if s == nil || s.store == nil {
		return nil, ErrDisabled
	}
	items, err := s.store.ListByPrefix(ctx, s.prefix+hashPart(tenant)+"/")
	if err != nil {
		return nil, err
	}
	result := make([]DeliveryRecord, 0, len(items))
	for _, item := range items {
		body, getErr := s.store.Get(ctx, item.Key)
		if getErr != nil {
			return nil, getErr
		}
		var record DeliveryRecord
		if err := json.Unmarshal(body, &record); err != nil {
			return nil, fmt.Errorf("decode A2A delivery: %w", err)
		}
		if record.TenantID == tenant {
			result = append(result, record)
		}
	}
	SortDeliveryRecords(result)
	return result, nil
}

func (s *DurableOutboxStore) ListTenants(ctx context.Context) ([]string, error) {
	if s == nil || s.store == nil {
		return nil, ErrDisabled
	}
	items, err := s.store.ListByPrefix(ctx, s.prefix)
	if err != nil {
		return nil, err
	}
	seen := make(map[string]struct{})
	for _, item := range items {
		body, getErr := s.store.Get(ctx, item.Key)
		if getErr != nil {
			return nil, getErr
		}
		var record DeliveryRecord
		if err := json.Unmarshal(body, &record); err != nil {
			return nil, fmt.Errorf("decode A2A delivery: %w", err)
		}
		if record.TenantID != "" {
			seen[record.TenantID] = struct{}{}
		}
	}
	tenants := make([]string, 0, len(seen))
	for tenant := range seen {
		tenants = append(tenants, tenant)
	}
	sort.Strings(tenants)
	return tenants, nil
}

func (s *DurableOutboxStore) Claim(ctx context.Context, tenant, task, id string, now time.Time, lease time.Duration) (DeliveryRecord, error) {
	if s == nil || s.store == nil {
		return DeliveryRecord{}, ErrDisabled
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	record, err := s.load(ctx, tenant, task, id)
	if err != nil {
		return DeliveryRecord{}, err
	}
	if record.Status == DeliveryDelivered || record.Status == DeliveryDeadLetter || (record.Status == DeliveryInFlight && record.LeaseUntil.After(now)) || record.NextAttempt.After(now) {
		return DeliveryRecord{}, ErrOutboxConflict
	}
	record.Status = DeliveryInFlight
	record.Attempts++
	record.LeaseUntil = now.Add(lease)
	record.UpdatedAt = now.UTC()
	if err := s.save(ctx, record); err != nil {
		return DeliveryRecord{}, err
	}
	return record, nil
}

func (s *DurableOutboxStore) Complete(ctx context.Context, tenant, task, id string, now time.Time) error {
	if s == nil || s.store == nil {
		return ErrDisabled
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	record, err := s.load(ctx, tenant, task, id)
	if err != nil {
		return err
	}
	if record.Status != DeliveryInFlight {
		return ErrOutboxConflict
	}
	record.Status = DeliveryDelivered
	record.LeaseUntil = time.Time{}
	record.UpdatedAt = now.UTC()
	return s.save(ctx, record)
}

func (s *DurableOutboxStore) Fail(ctx context.Context, tenant, task, id string, now time.Time, retryAfter time.Duration, maxAttempts int, deliveryErr error) (DeliveryRecord, error) {
	if s == nil || s.store == nil {
		return DeliveryRecord{}, ErrDisabled
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	record, err := s.load(ctx, tenant, task, id)
	if err != nil {
		return DeliveryRecord{}, err
	}
	if record.Status != DeliveryInFlight {
		return DeliveryRecord{}, ErrOutboxConflict
	}
	record.LeaseUntil = time.Time{}
	record.LastError = safeDeliveryError(deliveryErr)
	if maxAttempts > 0 && record.Attempts >= maxAttempts {
		record.Status = DeliveryDeadLetter
	} else {
		record.Status = DeliveryPending
		record.NextAttempt = now.Add(retryAfter)
	}
	record.UpdatedAt = now.UTC()
	if err := s.save(ctx, record); err != nil {
		return DeliveryRecord{}, err
	}
	return record, nil
}

func (s *DurableOutboxStore) load(ctx context.Context, tenant, task, id string) (DeliveryRecord, error) {
	body, err := s.store.Get(ctx, s.key(tenant, task, id))
	if err != nil {
		if s.isNotFound(err) {
			return DeliveryRecord{}, ErrNotFound
		}
		return DeliveryRecord{}, fmt.Errorf("load A2A delivery: %w", err)
	}
	var record DeliveryRecord
	if err := json.Unmarshal(body, &record); err != nil {
		return DeliveryRecord{}, fmt.Errorf("decode A2A delivery: %w", err)
	}
	if record.TenantID != tenant || record.TaskID != task || record.ID != id {
		return DeliveryRecord{}, ErrNotFound
	}
	return record, nil
}

func (s *DurableOutboxStore) save(ctx context.Context, record DeliveryRecord) error {
	body, err := json.Marshal(record)
	if err != nil {
		return err
	}
	return s.store.Put(ctx, s.key(record.TenantID, record.TaskID, record.ID), body, map[string]string{"kind": "a2a_delivery", "tenant": hashPart(record.TenantID), "task": hashPart(record.TaskID)})
}

func (s *DurableOutboxStore) key(tenant, task, id string) string {
	return s.prefix + hashPart(tenant) + "/" + hashPart(task) + "/" + hashPart(id) + ".json"
}

func (s *DurableOutboxStore) isNotFound(err error) bool {
	if s != nil && s.IsNotFound != nil {
		return s.IsNotFound(err)
	}
	return defaultIsNotFound(err)
}

func validateDeliveryRecord(record DeliveryRecord) error {
	if strings.TrimSpace(record.ID) == "" || strings.TrimSpace(record.TenantID) == "" || strings.TrimSpace(record.TaskID) == "" || strings.TrimSpace(record.ConfigID) == "" || strings.TrimSpace(record.PayloadRef) == "" || strings.TrimSpace(record.PayloadHash) == "" {
		return errors.New("A2A push outbox identity and payload reference are required")
	}
	if record.Status != "" && record.Status != DeliveryPending {
		return errors.New("new A2A push outbox records must be pending")
	}
	return nil
}
