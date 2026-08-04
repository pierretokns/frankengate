// Package provenance defines the metadata-only join envelope for model-card,
// A2A, MCP, and evaluation observability. It intentionally contains no
// prompt, response, credential, or raw tool payload fields.
package provenance

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

const SchemaVersion = "frankengate.provenance.event.v1"

type Event struct {
	SchemaVersion      string    `json:"schema_version"`
	EventID            string    `json:"event_id"`
	TenantID           string    `json:"tenant_id,omitempty"`
	RequestID          string    `json:"request_id,omitempty"`
	TraceID            string    `json:"trace_id,omitempty"`
	TaskID             string    `json:"task_id,omitempty"`
	CardDigest         string    `json:"card_digest,omitempty"`
	CardRevision       string    `json:"card_revision,omitempty"`
	PolicyEpoch        string    `json:"policy_epoch,omitempty"`
	CapabilityDecision string    `json:"capability_decision,omitempty"`
	RemoteAgent        string    `json:"remote_agent,omitempty"`
	Outcome            string    `json:"outcome"`
	ArtifactRef        string    `json:"artifact_ref,omitempty"`
	CostMicros         int64     `json:"cost_micros,omitempty"`
	ObservedAt         time.Time `json:"observed_at"`
}

func (e Event) Validate() error {
	if e.SchemaVersion != SchemaVersion {
		return fmt.Errorf("schema_version must be %q", SchemaVersion)
	}
	if strings.TrimSpace(e.EventID) == "" || strings.TrimSpace(e.Outcome) == "" || e.ObservedAt.IsZero() {
		return fmt.Errorf("event_id, outcome, and observed_at are required")
	}
	if e.CostMicros < 0 {
		return fmt.Errorf("cost_micros must not be negative")
	}
	for field, value := range map[string]string{
		"card_digest": e.CardDigest, "card_revision": e.CardRevision, "policy_epoch": e.PolicyEpoch,
	} {
		if value != "" && len(value) > 256 {
			return fmt.Errorf("%s is too long", field)
		}
	}
	return nil
}

func (e Event) CanonicalJSON() ([]byte, error) {
	if err := e.Validate(); err != nil {
		return nil, err
	}
	return json.Marshal(e)
}

func Digest(e Event) (string, error) {
	payload, err := e.CanonicalJSON()
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(payload)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

// TraceAttributes returns bounded metadata suitable for live trace injection.
// Raw prompts, responses, credentials, and tool payloads are intentionally not
// representable here.
func TraceAttributes(e Event) (map[string]any, error) {
	if err := e.Validate(); err != nil {
		return nil, err
	}
	attributes := map[string]any{
		"frankengate.provenance.schema_version": e.SchemaVersion,
		"frankengate.provenance.event_id":       e.EventID,
		"frankengate.provenance.outcome":        e.Outcome,
	}
	optional := map[string]string{
		"frankengate.provenance.tenant_id":           e.TenantID,
		"frankengate.provenance.request_id":          e.RequestID,
		"frankengate.provenance.trace_id":            e.TraceID,
		"frankengate.provenance.task_id":             e.TaskID,
		"frankengate.provenance.card_digest":         e.CardDigest,
		"frankengate.provenance.card_revision":       e.CardRevision,
		"frankengate.provenance.policy_epoch":        e.PolicyEpoch,
		"frankengate.provenance.capability_decision": e.CapabilityDecision,
		"frankengate.provenance.remote_agent":        e.RemoteAgent,
		"frankengate.provenance.artifact_ref":        e.ArtifactRef,
	}
	for key, value := range optional {
		if value != "" {
			attributes[key] = value
		}
	}
	if e.CostMicros != 0 {
		attributes["frankengate.provenance.cost_micros"] = e.CostMicros
	}
	return attributes, nil
}
