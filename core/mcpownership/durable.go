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
}

// DurableBackend is the minimum atomic contract required by a shared MCP
// ownership adapter. Write must atomically compare Version and reject stale
// writers. Implementations must preserve Fence monotonicity and make writes
// idempotent when the same version/state is retried.
type DurableBackend interface {
	Read(ctx context.Context, key ConnectionKey) (DurableRecord, error)
	Write(ctx context.Context, expectedVersion uint64, record DurableRecord) error
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
