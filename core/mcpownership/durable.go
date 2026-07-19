package mcpownership

import (
	"context"
	"errors"
	"fmt"
	"reflect"
	"sync"
	"time"
)

// DurableRecord is the backend-neutral persistence envelope for one MCP
// connection. A SQL, key/value, or document adapter can store this shape
// without coupling the MCP manager to a particular database. Version is a
// compare-and-swap revision; Fence is never allowed to decrease.
type DurableRecord struct {
	Key              ConnectionKey      `json:"key"`
	Version          uint64             `json:"version"`
	OwnerPod         string             `json:"owner_pod,omitempty"`
	Fence            uint64             `json:"fence"`
	LeaseUntil       time.Time          `json:"lease_until"`
	ServerSessionID  string             `json:"server_session_id,omitempty"`
	SessionResumable bool               `json:"session_resumable"`
	Operations       []DurableOperation `json:"operations,omitempty"`
}

type DurableOperation struct {
	ID        string          `json:"id"`
	Status    OperationStatus `json:"status"`
	Attempt   uint32          `json:"attempt"`
	Ambiguous bool            `json:"ambiguous"`
	LastOwnerPod string       `json:"last_owner_pod,omitempty"`
	LastFence    uint64       `json:"last_fence,omitempty"`
}

// DurableBackend is the minimum atomic contract required by a shared MCP
// ownership adapter. Write must atomically compare Version and reject stale
// writers. Implementations must preserve Fence monotonicity and make writes
// idempotent when the same version/state is retried.
type DurableBackend interface {
	Read(ctx context.Context, key ConnectionKey) (DurableRecord, error)
	Write(ctx context.Context, expectedVersion uint64, record DurableRecord) error
}

// DurableStore adapts a DurableBackend to the execution-facing Store
// contract. It performs optimistic CAS retries so the backend remains the
// sole cross-replica authority; callers never fall back to process-local
// state when the backend is unavailable.
type DurableStore struct{ backend DurableBackend }

func NewDurableStore(backend DurableBackend) Store {
	if backend == nil {
		return nil
	}
	return &DurableStore{backend: backend}
}

func (s *DurableStore) load(key ConnectionKey) (DurableRecord, error) {
	return s.backend.Read(context.Background(), key)
}
func (s *DurableStore) mutate(key ConnectionKey, fn func(*Registry) error) error {
	if s == nil || s.backend == nil {
		return errors.New("mcp ownership: durable backend unavailable")
	}
	for attempt := 0; attempt < 8; attempt++ {
		rec, err := s.backend.Read(context.Background(), key)
		if errors.Is(err, ErrNotFound) {
			rec = DurableRecord{Key: key}
			err = nil
		}
		if err != nil {
			return err
		}
		reg := registryFromDurable(rec)
		if err := fn(reg); err != nil {
			return err
		}
		next := durableFromRegistry(reg, key, rec.Version+1)
		if err := s.backend.Write(context.Background(), rec.Version, next); err == nil {
			return nil
		} else if !errors.Is(err, ErrVersionConflict) {
			return err
		}
	}
	return ErrVersionConflict
}

func registryFromDurable(rec DurableRecord) *Registry {
	r := NewRegistry()
	if rec.Key.ClientID == "" {
		return r
	}
	r.records[rec.Key] = &record{key: rec.Key, ownerPod: rec.OwnerPod, fence: rec.Fence, leaseUntil: rec.LeaseUntil, serverSessionID: rec.ServerSessionID, sessionResumable: rec.SessionResumable, operations: map[string]*operation{}}
	for _, op := range rec.Operations {
		attempts := make([]attempt, op.Attempt)
		if len(attempts) > 0 {
			attempts[len(attempts)-1] = attempt{pod: op.LastOwnerPod, fence: op.LastFence}
		}
		r.records[rec.Key].operations[op.ID] = &operation{id: op.ID, status: op.Status, ambiguous: op.Ambiguous, attempts: attempts}
	}
	return r
}
func durableFromRegistry(r *Registry, key ConnectionKey, version uint64) DurableRecord {
	rec := r.records[key]
	out := DurableRecord{Key: key, Version: version}
	if rec == nil {
		return out
	}
	out.OwnerPod, out.Fence, out.LeaseUntil, out.ServerSessionID, out.SessionResumable = rec.ownerPod, rec.fence, rec.leaseUntil, rec.serverSessionID, rec.sessionResumable
	for _, op := range rec.operations {
		do := DurableOperation{ID: op.id, Status: op.status, Attempt: uint32(len(op.attempts)), Ambiguous: op.ambiguous}
		if len(op.attempts) > 0 {
			last := op.attempts[len(op.attempts)-1]
			do.LastOwnerPod, do.LastFence = last.pod, last.fence
		}
		out.Operations = append(out.Operations, do)
	}
	return out
}

func (s *DurableStore) Claim(now time.Time, key ConnectionKey, pod string, ttl time.Duration) (Claim, error) {
	var out Claim
	err := s.mutate(key, func(r *Registry) error { var e error; out, e = r.Claim(now, key, pod, ttl); return e })
	return out, err
}
func (s *DurableStore) Renew(now time.Time, key ConnectionKey, pod string, fence uint64, ttl time.Duration) (Claim, error) {
	var out Claim
	err := s.mutate(key, func(r *Registry) error { var e error; out, e = r.Renew(now, key, pod, fence, ttl); return e })
	return out, err
}
func (s *DurableStore) AttachServerSession(now time.Time, key ConnectionKey, pod string, fence uint64, id string, res bool) error {
	return s.mutate(key, func(r *Registry) error { return r.AttachServerSession(now, key, pod, fence, id, res) })
}
func (s *DurableStore) StartCall(now time.Time, key ConnectionKey, pod string, fence uint64, id string) (CallReceipt, error) {
	var out CallReceipt
	err := s.mutate(key, func(r *Registry) error { var e error; out, e = r.StartCall(now, key, pod, fence, id); return e })
	return out, err
}
func (s *DurableStore) CompleteCall(now time.Time, key ConnectionKey, pod string, fence uint64, id string, ok bool) (CallReceipt, error) {
	var out CallReceipt
	err := s.mutate(key, func(r *Registry) error { var e error; out, e = r.CompleteCall(now, key, pod, fence, id, ok); return e })
	return out, err
}
func (s *DurableStore) BeginOAuth(now time.Time, key ConnectionKey, pod string, fence uint64, state string, ttl time.Duration) error {
	return s.mutate(key, func(r *Registry) error { return r.BeginOAuth(now, key, pod, fence, state, ttl) })
}
func (s *DurableStore) RouteOAuthCallback(now time.Time, state string) (OAuthRoute, error) {
	return OAuthRoute{}, errors.New("durable ownership: OAuth callback routing requires a shared state index")
}
func (s *DurableStore) Operations(key ConnectionKey) []OperationSnapshot {
	rec, err := s.load(key)
	if err != nil {
		return nil
	}
	r := registryFromDurable(rec)
	return r.Operations(key)
}

var (
	ErrVersionConflict = errors.New("durable ownership version conflict")
	ErrFenceRegression = errors.New("durable ownership fence regression")
)

// MemoryBackend is a deterministic fake for adapter and contract tests. It is
// intentionally not a production multi-replica store; NewProcessLocalStore
// remains the explicit process-local implementation.
type MemoryBackend struct {
	mu      sync.Mutex
	records map[ConnectionKey]DurableRecord
}

func NewMemoryBackend() *MemoryBackend {
	return &MemoryBackend{records: make(map[ConnectionKey]DurableRecord)}
}

func (b *MemoryBackend) Read(ctx context.Context, key ConnectionKey) (DurableRecord, error) {
	if err := ctx.Err(); err != nil {
		return DurableRecord{}, err
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	rec, ok := b.records[key]
	if !ok {
		return DurableRecord{}, ErrNotFound
	}
	return cloneDurableRecord(rec), nil
}

func (b *MemoryBackend) Write(ctx context.Context, expectedVersion uint64, record DurableRecord) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if record.Key.ClientID == "" || record.Key.Principal == "" || record.Key.SessionKey == "" {
		return fmt.Errorf("%w: connection key is required", ErrInvalidClaim)
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	current, exists := b.records[record.Key]
	if exists {
		// A retried write after a transport timeout is idempotent when the
		// durable row already contains the exact intended state.
		if current.Version == record.Version && reflect.DeepEqual(current, record) {
			return nil
		}
		if current.Version != expectedVersion {
			return ErrVersionConflict
		}
		if record.Fence < current.Fence {
			return ErrFenceRegression
		}
	} else if expectedVersion != 0 || record.Version == 0 {
		return ErrVersionConflict
	}
	if record.Version != expectedVersion+1 {
		return fmt.Errorf("%w: version must advance by one", ErrVersionConflict)
	}
	b.records[record.Key] = cloneDurableRecord(record)
	return nil
}

func cloneDurableRecord(in DurableRecord) DurableRecord {
	out := in
	out.Operations = append([]DurableOperation(nil), in.Operations...)
	return out
}
