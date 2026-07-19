package otel

// Durable replay storage is deliberately a small, append-only JSONL boundary.
// Deployments can point it at a mounted volume (or an object-store sync sidecar)
// without putting replay payloads in the inference hot path. Every record is
// tenant-scoped and content is removed unless explicitly enabled.

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

type ReplayRecord struct {
	SchemaVersion int            `json:"schema_version"`
	TraceID       string         `json:"trace_id"`
	RequestID     string         `json:"request_id,omitempty"`
	TenantID      string         `json:"tenant_id"`
	CapturedAt    time.Time      `json:"captured_at"`
	Trace         *schemas.Trace `json:"trace"`
}

// ReplayStore is the durable evidence contract used by the OTEL plugin.
type ReplayStore interface {
	Put(ctx context.Context, trace *schemas.Trace) error
	Get(ctx context.Context, tenantID, traceID string) (*ReplayRecord, error)
	// List returns at most limit records for one tenant, newest first. A
	// tenant is always required; callers cannot enumerate other tenants.
	List(ctx context.Context, tenantID string, limit int) ([]ReplayRecord, error)
	Close() error
}

// JSONLReplayStore is safe for concurrent writers and survives process restarts.
// Files are partitioned by tenant to make accidental cross-tenant reads harder.
type JSONLReplayStore struct {
	dir            string
	includeContent bool
	mu             sync.Mutex
	files          map[string]*os.File
}

func NewJSONLReplayStore(dir string, includeContent bool) (*JSONLReplayStore, error) {
	if strings.TrimSpace(dir) == "" {
		return nil, fmt.Errorf("replay store directory is required")
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	return &JSONLReplayStore{dir: dir, includeContent: includeContent, files: make(map[string]*os.File)}, nil
}

func (s *JSONLReplayStore) Put(ctx context.Context, trace *schemas.Trace) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if trace == nil {
		return fmt.Errorf("trace is required")
	}
	tenant := traceTenant(trace)
	if tenant == "" {
		return fmt.Errorf("replay trace %s has no tenant", trace.TraceID)
	}
	clone := trace.SnapshotForExport()
	if !s.includeContent {
		redactReplayContent(clone)
	}
	record := ReplayRecord{SchemaVersion: 1, TraceID: clone.TraceID, RequestID: clone.RequestID, TenantID: tenant, CapturedAt: time.Now().UTC(), Trace: clone}
	payload, err := json.Marshal(record)
	if err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	f := s.files[tenant]
	if f == nil {
		name := filepath.Join(s.dir, safeTenant(tenant)+".jsonl")
		// Keep the handle readable as well as append-only: Get may scan a
		// tenant's live file while the process is still accepting records.
		f, err = os.OpenFile(name, os.O_CREATE|os.O_APPEND|os.O_RDWR, 0o600)
		if err != nil {
			return err
		}
		s.files[tenant] = f
	}
	if _, err = f.Write(append(payload, '\n')); err != nil {
		return err
	}
	return f.Sync()
}

func (s *JSONLReplayStore) Get(ctx context.Context, tenantID, traceID string) (*ReplayRecord, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if strings.TrimSpace(tenantID) == "" || strings.TrimSpace(traceID) == "" {
		return nil, fmt.Errorf("tenant and trace ID are required")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	f := s.files[tenantID]
	var r *os.File
	var err error
	if f != nil {
		r = f
		if _, err = r.Seek(0, 0); err != nil {
			return nil, err
		}
	} else {
		r, err = os.Open(filepath.Join(s.dir, safeTenant(tenantID)+".jsonl"))
		if err != nil {
			return nil, err
		}
		defer r.Close()
	}
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 4096), 16*1024*1024)
	var found *ReplayRecord
	for scanner.Scan() {
		var candidate ReplayRecord
		if json.Unmarshal(scanner.Bytes(), &candidate) == nil && candidate.TenantID == tenantID && candidate.TraceID == traceID {
			found = &candidate
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	if found == nil {
		return nil, os.ErrNotExist
	}
	return found, nil
}

// List is the backend-neutral export boundary for replay consumers. It scans
// only the requested tenant partition and bounds the result so an operator
// cannot accidentally load an unbounded history into memory. Records are
// returned newest first (append order is the durable order).
func (s *JSONLReplayStore) List(ctx context.Context, tenantID string, limit int) ([]ReplayRecord, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	tenantID = strings.TrimSpace(tenantID)
	if tenantID == "" {
		return nil, fmt.Errorf("tenant is required")
	}
	if limit <= 0 {
		return nil, fmt.Errorf("limit must be positive")
	}
	if limit > 1000 {
		limit = 1000
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	f := s.files[tenantID]
	var r *os.File
	var err error
	if f != nil {
		r = f
		if _, err = r.Seek(0, 0); err != nil {
			return nil, err
		}
	} else {
		r, err = os.Open(filepath.Join(s.dir, safeTenant(tenantID)+".jsonl"))
		if err != nil {
			if os.IsNotExist(err) {
				return []ReplayRecord{}, nil
			}
			return nil, err
		}
		defer r.Close()
	}

	// Keep only the newest limit records while scanning append order.
	records := make([]ReplayRecord, 0, limit)
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 4096), 16*1024*1024)
	for scanner.Scan() {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		var candidate ReplayRecord
		if json.Unmarshal(scanner.Bytes(), &candidate) != nil || candidate.TenantID != tenantID {
			continue
		}
		if len(records) == limit {
			copy(records, records[1:])
			records[len(records)-1] = candidate
		} else {
			records = append(records, candidate)
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	for i, j := 0, len(records)-1; i < j; i, j = i+1, j-1 {
		records[i], records[j] = records[j], records[i]
	}
	return records, nil
}

func (s *JSONLReplayStore) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	var first error
	for tenant, f := range s.files {
		if err := f.Close(); err != nil && first == nil {
			first = fmt.Errorf("close %s: %w", tenant, err)
		}
	}
	s.files = make(map[string]*os.File)
	return first
}

func traceTenant(t *schemas.Trace) string {
	for _, key := range []string{"bifrost.tenant_id", "tenant_id", "tenant"} {
		if v, ok := t.GetAttribute(key); ok {
			if str, ok := v.(string); ok {
				return strings.TrimSpace(str)
			}
		}
	}
	return ""
}
func safeTenant(v string) string {
	v = strings.TrimSpace(v)
	var b strings.Builder
	for _, r := range v {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '-' || r == '_' || r == '.' {
			b.WriteRune(r)
		} else {
			b.WriteByte('_')
		}
	}
	return b.String()
}
func redactReplayContent(t *schemas.Trace) {
	if t == nil {
		return
	}
	t.RequestHeaders = nil
	for _, span := range t.Spans {
		if span == nil {
			continue
		}
		for key := range span.Attributes {
			lower := strings.ToLower(key)
			if strings.Contains(lower, "content") || strings.Contains(lower, "message") || strings.Contains(lower, "prompt") || strings.Contains(lower, "completion") || strings.Contains(lower, "tool") || strings.Contains(lower, "input") || strings.Contains(lower, "output") {
				delete(span.Attributes, key)
			}
		}
	}
}
