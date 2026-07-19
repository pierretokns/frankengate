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

	"github.com/maximhq/bifrost/core/privacy"
	"github.com/maximhq/bifrost/core/schemas"
)

type ReplayRecord struct {
	SchemaVersion int            `json:"schema_version"`
	TraceID       string         `json:"trace_id"`
	RequestID     string         `json:"request_id,omitempty"`
	TenantID      string         `json:"tenant_id"`
	CapturedAt    time.Time      `json:"captured_at"`
	Trace         *schemas.Trace `json:"trace"`
	// RetrievalQuality is bounded evaluation metadata only; it never contains
	// queries, chunk IDs, embeddings, or payloads.
	RetrievalQuality *RetrievalQualitySummary `json:"retrieval_quality,omitempty"`
}

type RetrievalQualitySummary struct {
	Expected   int     `json:"expected"`
	Retrieved  int     `json:"retrieved"`
	Relevant   int     `json:"relevant"`
	ACLDenials int     `json:"acl_denials"`
	Stale      int     `json:"stale"`
	Deleted    int     `json:"deleted"`
	Fresh      int     `json:"fresh"`
	Precision  float64 `json:"precision"`
	Recall     float64 `json:"recall"`
	Freshness  float64 `json:"freshness"`
}

// retrievalQualityFromTrace copies only bounded numeric evaluation fields from
// trace attributes. Unknown or malformed values are ignored, preserving the
// metadata-only and fail-closed replay contract.
func retrievalQualityFromTrace(trace *schemas.Trace) *RetrievalQualitySummary {
	if trace == nil || len(trace.Attributes) == 0 {
		return nil
	}
	q := &RetrievalQualitySummary{}
	found := false
	ints := map[string]*int{"expected": &q.Expected, "retrieved": &q.Retrieved, "relevant": &q.Relevant, "acl_denials": &q.ACLDenials, "stale": &q.Stale, "deleted": &q.Deleted, "fresh": &q.Fresh}
	floatVals := map[string]*float64{"precision": &q.Precision, "recall": &q.Recall, "freshness": &q.Freshness}
	for name, dst := range ints {
		if v, ok := boundedIntAttr(trace.Attributes["frankengate.retrieval."+name]); ok {
			*dst = v
			found = true
		}
	}
	for name, dst := range floatVals {
		if v, ok := boundedFloatAttr(trace.Attributes["frankengate.retrieval."+name]); ok {
			*dst = v
			found = true
		}
	}
	if !found {
		return nil
	}
	return q
}

func boundedIntAttr(v any) (int, bool) {
	n, ok := v.(int)
	if !ok || n < 0 || n > 1000000000 {
		return 0, false
	}
	return n, true
}
func boundedFloatAttr(v any) (float64, bool) {
	n, ok := v.(float64)
	if !ok || n < 0 || n > 1 {
		return 0, false
	}
	return n, true
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

// ReplayRetentionStore is an optional maintenance boundary for durable
// stores. Deletion is always tenant-scoped; implementations must reject a
// blank tenant or non-positive cutoff rather than interpreting either as a
// wildcard. Keeping this separate preserves compatibility with read-only
// replay implementations.
type ReplayRetentionStore interface {
	DeleteBefore(ctx context.Context, tenantID string, cutoff time.Time) (int, error)
}

// TenantReplayStore is a fail-closed view over a ReplayStore.  The durable
// store itself is partitioned by tenant, but a tenant string supplied by a
// caller is not an authorization decision.  Consumers should hand the view
// to a request after authenticating the principal; the view then prevents a
// confused deputy from selecting another tenant (including an empty tenant).
// Admin callers must deliberately construct one view per authorized tenant
// rather than bypassing this boundary with user-controlled query parameters.
type TenantReplayStore struct {
	store  ReplayStore
	tenant string
}

// NewTenantReplayStore returns a tenant-pinned replay view.  A blank tenant is
// rejected so there is no wildcard/admin interpretation hidden in this API.
func NewTenantReplayStore(store ReplayStore, tenant string) (*TenantReplayStore, error) {
	if store == nil {
		return nil, fmt.Errorf("replay store is required")
	}
	tenant = strings.TrimSpace(tenant)
	if tenant == "" {
		return nil, fmt.Errorf("tenant is required")
	}
	return &TenantReplayStore{store: store, tenant: tenant}, nil
}

func (s *TenantReplayStore) Put(ctx context.Context, trace *schemas.Trace) error {
	if s == nil || s.store == nil {
		return fmt.Errorf("replay store is unavailable")
	}
	if trace == nil || traceTenant(trace) != s.tenant {
		return fmt.Errorf("replay tenant is not authorized")
	}
	return s.store.Put(ctx, trace)
}

func (s *TenantReplayStore) Get(ctx context.Context, tenantID, traceID string) (*ReplayRecord, error) {
	if s == nil || s.store == nil || strings.TrimSpace(tenantID) != s.tenant {
		return nil, os.ErrPermission
	}
	return s.store.Get(ctx, s.tenant, traceID)
}

func (s *TenantReplayStore) List(ctx context.Context, tenantID string, limit int) ([]ReplayRecord, error) {
	if s == nil || s.store == nil || strings.TrimSpace(tenantID) != s.tenant {
		return nil, os.ErrPermission
	}
	return s.store.List(ctx, s.tenant, limit)
}

func (s *TenantReplayStore) DeleteBefore(ctx context.Context, tenantID string, cutoff time.Time) (int, error) {
	if s == nil || s.store == nil || strings.TrimSpace(tenantID) != s.tenant {
		return 0, os.ErrPermission
	}
	retainer, ok := s.store.(ReplayRetentionStore)
	if !ok {
		return 0, fmt.Errorf("replay store does not support retention deletion")
	}
	return retainer.DeleteBefore(ctx, s.tenant, cutoff)
}

func (s *TenantReplayStore) Close() error {
	if s == nil || s.store == nil {
		return nil
	}
	return s.store.Close()
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
	// Replay is an evidence store, not an identity or credential store.  Even
	// when payload capture is explicitly enabled, transport headers (including
	// Coder/Okta identity and peer-address headers) and tool arguments/results
	// must never be persisted.  Apply this boundary after SnapshotForExport so
	// the live trace remains available to the configured OTEL exporters.
	sanitizeReplayPII(clone)
	// Retrieval quality counters are safe to retain, but query text is never
	// part of the replay metadata contract, even when content capture is opted in.
	redactReplayQueryMetadata(clone)
	record := ReplayRecord{SchemaVersion: 1, TraceID: clone.TraceID, RequestID: clone.RequestID, TenantID: tenant, CapturedAt: time.Now().UTC(), Trace: clone, RetrievalQuality: retrievalQualityFromTrace(clone)}
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

// DeleteBefore removes only records in one tenant partition whose captured
// timestamp is strictly older than cutoff. Malformed records are preserved
// (fail closed) rather than deleted, so retention maintenance cannot destroy
// evidence it cannot authenticate. The rewrite is atomic within the local
// filesystem and the live append handle is reopened after replacement.
func (s *JSONLReplayStore) DeleteBefore(ctx context.Context, tenantID string, cutoff time.Time) (int, error) {
	if err := ctx.Err(); err != nil {
		return 0, err
	}
	tenantID = strings.TrimSpace(tenantID)
	if tenantID == "" {
		return 0, fmt.Errorf("tenant is required")
	}
	if cutoff.IsZero() {
		return 0, fmt.Errorf("retention cutoff is required")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	name := filepath.Join(s.dir, safeTenant(tenantID)+".jsonl")
	input, err := os.Open(name)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	tmp, err := os.CreateTemp(s.dir, ".replay-retention-*")
	if err != nil {
		input.Close()
		return 0, err
	}
	tmpName := tmp.Name()
	cleanup := func() { _ = input.Close(); _ = tmp.Close(); _ = os.Remove(tmpName) }
	removed := 0
	scanner := bufio.NewScanner(input)
	scanner.Buffer(make([]byte, 4096), 16*1024*1024)
	for scanner.Scan() {
		if err := ctx.Err(); err != nil {
			cleanup()
			return 0, err
		}
		line := scanner.Bytes()
		var record ReplayRecord
		// Preserve malformed, cross-tenant, and timestamp-less rows. Deletion
		// must never broaden beyond a verified tenant and timestamp predicate.
		deleteRow := json.Unmarshal(line, &record) == nil && record.TenantID == tenantID && !record.CapturedAt.IsZero() && record.CapturedAt.Before(cutoff)
		if deleteRow {
			removed++
			continue
		}
		if _, err := tmp.Write(append(append([]byte(nil), line...), '\n')); err != nil {
			cleanup()
			return 0, err
		}
	}
	if err := scanner.Err(); err != nil {
		cleanup()
		return 0, err
	}
	if err := input.Close(); err != nil {
		cleanup()
		return 0, err
	}
	if err := tmp.Sync(); err != nil {
		cleanup()
		return 0, err
	}
	if err := tmp.Close(); err != nil {
		_ = os.Remove(tmpName)
		return 0, err
	}
	if old := s.files[tenantID]; old != nil {
		_ = old.Close()
		delete(s.files, tenantID)
	}
	if err := os.Rename(tmpName, name); err != nil {
		_ = os.Remove(tmpName)
		return 0, err
	}
	// Reopen now so subsequent Put/Get operations retain the normal live-file
	// behavior. A zero-row rewrite is still useful for atomic compaction.
	f, err := os.OpenFile(name, os.O_CREATE|os.O_APPEND|os.O_RDWR, 0o600)
	if err != nil {
		return 0, err
	}
	s.files[tenantID] = f
	return removed, nil
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
	for key := range t.Attributes {
		lower := strings.ToLower(key)
		if strings.Contains(lower, "query") || strings.Contains(lower, "content") || strings.Contains(lower, "prompt") || strings.Contains(lower, "message") || strings.Contains(lower, "input") || strings.Contains(lower, "output") || strings.Contains(lower, "tool") {
			delete(t.Attributes, key)
		}
	}
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

func redactReplayQueryMetadata(t *schemas.Trace) {
	if t == nil {
		return
	}
	for key := range t.Attributes {
		if strings.Contains(strings.ToLower(key), "query") {
			delete(t.Attributes, key)
		}
	}
}

// sanitizeReplayPII applies the replay-store privacy boundary independently of
// includeContent.  Header values are not needed for replay and are therefore
// dropped wholesale; trace/span metadata is retained only when it is bounded
// operational data.  This prevents Coder identity, IP/user-agent attribution,
// tool arguments/results, and accidental email/phone values from escaping via
// an opted-in replay directory.
func sanitizeReplayPII(t *schemas.Trace) {
	if t == nil {
		return
	}
	t.RequestHeaders = nil
	for key := range t.Attributes {
		if replayPIIKey(key) {
			delete(t.Attributes, key)
			continue
		}
		t.Attributes[key] = redactReplayStrings(t.Attributes[key])
	}
	// RootSpan is not guaranteed to be present in t.Spans (callers may build a
	// trace with only the root pointer).  Sanitize it explicitly so event
	// attributes cannot bypass the replay privacy boundary.
	sanitizeReplaySpan(t.RootSpan)
	for _, span := range t.Spans {
		sanitizeReplaySpan(span)
	}
	for i := range t.PluginLogs {
		t.PluginLogs[i].Message = privacy.RedactText(t.PluginLogs[i].Message)
	}
}

// sanitizeReplaySpan applies the same boundary to span attributes and event
// attributes.  Events are a common OTEL location for tool arguments/results
// and error details, and are otherwise easy to miss when sanitizing a trace.
func sanitizeReplaySpan(span *schemas.Span) {
	if span == nil {
		return
	}
	for key := range span.Attributes {
		if replayPIIKey(key) {
			delete(span.Attributes, key)
			continue
		}
		span.Attributes[key] = redactReplayStrings(span.Attributes[key])
	}
	span.StatusMsg = privacy.RedactText(span.StatusMsg)
	for i := range span.Events {
		for key := range span.Events[i].Attributes {
			if replayPIIKey(key) {
				delete(span.Events[i].Attributes, key)
				continue
			}
			span.Events[i].Attributes[key] = redactReplayStrings(span.Events[i].Attributes[key])
		}
	}
}

func replayPIIKey(key string) bool {
	lower := strings.ToLower(strings.NewReplacer("-", "", "_", "", ".", "").Replace(key))
	// Keep tenant and bounded governance IDs; remove direct identity and
	// request-content dimensions.  Tool names remain useful operational data,
	// but arguments/results are always removed.
	if lower == "tenant" || lower == "tenantid" || lower == "bifrosttenantid" {
		return false
	}
	for _, marker := range []string{"prompt", "completion", "content", "message", "query", "toolinput", "tooloutput", "toolargs", "toolarguments", "toolresult", "coder", "email", "username", "principal", "peeraddress", "clientpeer", "forwardedfor", "sourceip", "remoteaddr", "useragent", "sessionid", "authorization", "bearer", "password", "secret", "credential", "cookie", "apikey", "accesskey", "privatekey", "jwt"} {
		if strings.Contains(lower, marker) {
			return true
		}
	}
	return false
}

func redactReplayStrings(value any) any {
	switch v := value.(type) {
	case string:
		return privacy.RedactText(v)
	case map[string]string:
		// Trace dimensions and other structured attributes are commonly kept as
		// map[string]string (rather than map[string]any).  Leaving this concrete
		// type untouched would bypass the recursive privacy boundary and persist
		// emails, phone numbers, or other user data in an opted-in replay file.
		out := make(map[string]string, len(v))
		for key, child := range v {
			if replayPIIKey(key) {
				continue
			}
			out[key] = privacy.RedactText(child)
		}
		return out
	case []string:
		out := append([]string(nil), v...)
		for i := range out {
			out[i] = privacy.RedactText(out[i])
		}
		return out
	case []any:
		out := make([]any, len(v))
		for i := range v {
			out[i] = redactReplayStrings(v[i])
		}
		return out
	case []map[string]any:
		// Some OTEL/connector integrations retain structured dimensions as a
		// slice of maps.  JSON decoding normally turns this into []any, but
		// traces assembled in Go can contain the concrete slice type directly.
		// Handle it explicitly so nested tool/user data cannot bypass the
		// recursive map sanitizer.
		out := make([]map[string]any, len(v))
		for i := range v {
			if v[i] == nil {
				continue
			}
			clean := redactReplayStrings(v[i])
			if m, ok := clean.(map[string]any); ok {
				out[i] = m
			}
		}
		return out
	case []map[string]string:
		out := make([]map[string]string, len(v))
		for i := range v {
			if v[i] == nil {
				continue
			}
			clean := redactReplayStrings(v[i])
			if m, ok := clean.(map[string]string); ok {
				out[i] = m
			}
		}
		return out
	case map[string]any:
		out := make(map[string]any, len(v))
		for key, child := range v {
			if replayPIIKey(key) {
				continue
			}
			out[key] = redactReplayStrings(child)
		}
		return out
	default:
		return value
	}
}
