package a2apush

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"sort"
	"strings"
	"sync"
	"time"
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
