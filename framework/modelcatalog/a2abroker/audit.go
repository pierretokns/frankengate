package a2abroker

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/maximhq/bifrost/framework/objectstore"
)

// CredentialAuditEvent is the durable, redacted record of one credential
// decision. It contains routing and correlation metadata, but never headers,
// tokens, secret references, payloads, or authorization-code material.
type CredentialAuditEvent struct {
	ID         string         `json:"id"`
	TenantID   string         `json:"tenantId,omitempty"`
	TaskID     string         `json:"taskId"`
	Endpoint   string         `json:"endpoint"`
	CardDigest string         `json:"cardDigest"`
	Kind       CredentialKind `json:"kind"`
	Outcome    string         `json:"outcome"`
	At         time.Time      `json:"at"`
}

type CredentialAuditStore interface {
	AppendCredentialAudit(context.Context, CredentialAuditEvent) error
}

type CredentialAuditStoreFunc func(context.Context, CredentialAuditEvent) error

func (f CredentialAuditStoreFunc) AppendCredentialAudit(ctx context.Context, event CredentialAuditEvent) error {
	if f == nil {
		return nil
	}
	return f(ctx, event)
}

var ErrCredentialAuditUnavailable = errors.New("A2A credential audit store unavailable")

// DurableCredentialAuditStore persists one bounded JSON object per decision.
// Keys are hashed so tenant IDs, task IDs, endpoints, and digests do not leak
// into object-store listings or provider logs.
type DurableCredentialAuditStore struct {
	store  objectstore.ObjectStore
	prefix string
	now    func() time.Time
}

func NewDurableCredentialAuditStore(store objectstore.ObjectStore, prefix string, now func() time.Time) *DurableCredentialAuditStore {
	if now == nil {
		now = time.Now
	}
	prefix = strings.TrimSuffix(strings.TrimSpace(prefix), "/")
	if prefix == "" {
		prefix = "a2a/credential-audit"
	}
	return &DurableCredentialAuditStore{store: store, prefix: prefix, now: now}
}

func (s *DurableCredentialAuditStore) AppendCredentialAudit(ctx context.Context, event CredentialAuditEvent) error {
	if s == nil || s.store == nil {
		return ErrCredentialAuditUnavailable
	}
	if strings.TrimSpace(event.TaskID) == "" || strings.TrimSpace(event.Endpoint) == "" || strings.TrimSpace(event.CardDigest) == "" {
		return fmt.Errorf("credential audit task, endpoint, and card digest are required")
	}
	if event.At.IsZero() {
		event.At = s.now().UTC()
	} else {
		event.At = event.At.UTC()
	}
	if event.ID == "" {
		event.ID = auditID(event)
	}
	payload, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal credential audit event: %w", err)
	}
	return s.store.Put(ctx, s.prefix+"/"+hashAuditPart(event.ID)+".json", payload, map[string]string{
		"kind":    "a2a_credential_audit",
		"outcome": boundedAuditOutcome(event.Outcome),
	})
}

func auditID(event CredentialAuditEvent) string {
	material := strings.Join([]string{event.TaskID, event.CardDigest, string(event.Kind), event.Outcome, event.At.UTC().Format(time.RFC3339Nano)}, "\x00")
	sum := sha256.Sum256([]byte(material))
	return hex.EncodeToString(sum[:])
}

func hashAuditPart(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func boundedAuditOutcome(outcome string) string {
	switch strings.ToLower(strings.TrimSpace(outcome)) {
	case "resolved", "auth_required", "rejected":
		return strings.ToLower(strings.TrimSpace(outcome))
	default:
		return "other"
	}
}
