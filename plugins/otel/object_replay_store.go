package otel

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/objectstore"
)

// ObjectReplayStore stores the same bounded ReplayRecord contract as the
// local JSONL store in an S3-compatible object store. The object store is a
// payload sink, not an authorization authority: every read remains pinned to
// one tenant and callers must authenticate before constructing the view.
type ObjectReplayStore struct {
	store  objectstore.ObjectStore
	prefix string
}

func NewObjectReplayStore(store objectstore.ObjectStore, prefix string) (*ObjectReplayStore, error) {
	if store == nil {
		return nil, fmt.Errorf("object replay store requires an object store")
	}
	prefix = strings.Trim(strings.TrimSpace(prefix), "/")
	if prefix == "" {
		prefix = "frankengate/replay"
	}
	return &ObjectReplayStore{store: store, prefix: prefix}, nil
}

func (s *ObjectReplayStore) key(tenant, traceID string) (string, error) {
	tenant = strings.Trim(strings.TrimSpace(tenant), "/")
	traceID = strings.Trim(strings.TrimSpace(traceID), "/")
	if tenant == "" || traceID == "" || strings.ContainsAny(tenant+traceID, "\\\r\n") {
		return "", fmt.Errorf("tenant and trace ID are required")
	}
	return s.prefix + "/" + tenant + "/" + traceID + ".json", nil
}

func (s *ObjectReplayStore) Put(ctx context.Context, trace *schemas.Trace) error {
	if trace == nil {
		return fmt.Errorf("trace is required")
	}
	tenant := traceTenant(trace)
	if tenant == "" {
		return fmt.Errorf("replay trace %s has no tenant", trace.TraceID)
	}
	clone := trace.SnapshotForExport()
	redactReplayContent(clone)
	sanitizeReplayPII(clone)
	record := ReplayRecord{
		SchemaVersion:    1,
		TraceID:          clone.TraceID,
		RequestID:        clone.RequestID,
		TenantID:         tenant,
		CapturedAt:       time.Now().UTC(),
		Trace:            clone,
		RetrievalQuality: retrievalQualityFromTrace(clone),
	}
	payload, err := json.Marshal(record)
	if err != nil {
		return fmt.Errorf("marshal replay record: %w", err)
	}
	key, err := s.key(tenant, record.TraceID)
	if err != nil {
		return err
	}
	return s.store.Put(ctx, key, payload, map[string]string{"tenant_id": tenant, "schema_version": "1"})
}

func (s *ObjectReplayStore) Get(ctx context.Context, tenantID, traceID string) (*ReplayRecord, error) {
	key, err := s.key(tenantID, traceID)
	if err != nil {
		return nil, os.ErrPermission
	}
	payload, err := s.store.Get(ctx, key)
	if err != nil {
		return nil, err
	}
	var record ReplayRecord
	if err := json.Unmarshal(payload, &record); err != nil {
		return nil, fmt.Errorf("decode replay record: %w", err)
	}
	if record.TenantID != strings.TrimSpace(tenantID) || record.TraceID != strings.TrimSpace(traceID) {
		return nil, os.ErrPermission
	}
	return &record, nil
}

func (s *ObjectReplayStore) List(ctx context.Context, tenantID string, limit int) ([]ReplayRecord, error) {
	tenantID = strings.TrimSpace(tenantID)
	if tenantID == "" || limit <= 0 {
		return nil, os.ErrPermission
	}
	prefix := s.prefix + "/" + strings.Trim(tenantID, "/") + "/"
	objects, err := s.store.ListByPrefix(ctx, prefix)
	if err != nil {
		return nil, err
	}
	sort.Slice(objects, func(i, j int) bool { return objects[i].LastModified.After(objects[j].LastModified) })
	if len(objects) > limit {
		objects = objects[:limit]
	}
	result := make([]ReplayRecord, 0, len(objects))
	for _, object := range objects {
		payload, err := s.store.Get(ctx, object.Key)
		if err != nil {
			return nil, err
		}
		var record ReplayRecord
		if err := json.Unmarshal(payload, &record); err != nil {
			return nil, fmt.Errorf("decode replay record %s: %w", object.Key, err)
		}
		if record.TenantID == tenantID {
			result = append(result, record)
		}
	}
	return result, nil
}

func (s *ObjectReplayStore) DeleteBefore(ctx context.Context, tenantID string, cutoff time.Time) (int, error) {
	tenantID = strings.TrimSpace(tenantID)
	if tenantID == "" || cutoff.IsZero() {
		return 0, os.ErrPermission
	}
	objects, err := s.store.ListByPrefix(ctx, s.prefix+"/"+strings.Trim(tenantID, "/")+"/")
	if err != nil {
		return 0, err
	}
	var keys []string
	for _, object := range objects {
		if object.LastModified.Before(cutoff) {
			keys = append(keys, object.Key)
		}
	}
	if len(keys) == 0 {
		return 0, nil
	}
	if err := s.store.DeleteBatch(ctx, keys); err != nil {
		return 0, err
	}
	return len(keys), nil
}

func (s *ObjectReplayStore) Close() error { return s.store.Close() }
