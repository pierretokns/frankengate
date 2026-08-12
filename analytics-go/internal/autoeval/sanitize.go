package autoeval

import (
	"bytes"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"
)

var secretPattern = regexp.MustCompile(`(?i)(sk-[A-Za-z0-9_-]{12,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]+PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._-]{16,})`)
var emailPattern = regexp.MustCompile(`(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b`)

func scrub(raw string) (string, int, error) {
	if len(raw) > MaxFieldBytes {
		return "", 0, fmt.Errorf("field exceeds %d bytes", MaxFieldBytes)
	}
	if secretPattern.MatchString(raw) {
		return "", 0, fmt.Errorf("secret-like content detected")
	}
	redactions := 0
	redacted := emailPattern.ReplaceAllStringFunc(raw, func(string) string {
		redactions++
		return "[REDACTED_EMAIL]"
	})
	return strings.TrimSpace(redacted), redactions, nil
}

func digestRaw(raw string, provided string) (string, int, error) {
	if provided != "" {
		return provided, 0, nil
	}
	if raw == "" {
		return "", 0, nil
	}
	scrubbed, count, err := scrub(raw)
	if err != nil {
		return "", 0, err
	}
	return DigestString(scrubbed), count, nil
}

func digestJSON(raw json.RawMessage, provided string) (string, int, error) {
	if provided != "" {
		return provided, 0, nil
	}
	if len(raw) == 0 {
		return "", 0, nil
	}
	if len(raw) > MaxFieldBytes {
		return "", 0, fmt.Errorf("json field exceeds %d bytes", MaxFieldBytes)
	}
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		return "", 0, fmt.Errorf("invalid json field: %w", err)
	}
	canonical, err := json.Marshal(value)
	if err != nil {
		return "", 0, err
	}
	if secretPattern.Match(canonical) {
		return "", 0, fmt.Errorf("secret-like content detected")
	}
	// Email replacement is deliberately performed before hashing so the
	// digest represents the privacy-transformed observation, not the raw one.
	scrubbed, count, err := scrub(string(canonical))
	if err != nil {
		return "", 0, err
	}
	return DigestString(scrubbed), count, nil
}

func Prepare(t Trace) (PreparedTrace, AdmissionReport, error) {
	report := AdmissionReport{}
	if err := t.validateEnvelope(); err != nil {
		return PreparedTrace{}, report, err
	}
	seen := make(map[string]struct{}, len(t.Events))
	byID := make(map[string]struct{}, len(t.Events))
	prepared := PreparedTrace{
		SchemaVersion: t.SchemaVersion, TraceID: t.TraceID, TenantID: t.TenantID,
		Source: t.Source, TaskFamily: t.TaskFamily, HarnessRevision: t.HarnessRevision,
		SourceRevision: t.SourceRevision, SourceDigest: t.SourceDigest,
		ModelRevision: t.ModelRevision, SkillRevision: t.SkillRevision, KBRevision: t.KBRevision,
		PrivacyReceipt: t.Privacy.ReceiptID, LossReceipt: receiptDigest(t),
		DeletionSubject: t.Deletion.SubjectID, CreatedAt: t.CreatedAt,
	}
	if prepared.CreatedAt.IsZero() {
		prepared.CreatedAt = time.Now().UTC()
	}
	for i, event := range t.Events {
		if event.TraceID != "" && event.TraceID != t.TraceID {
			return PreparedTrace{}, report, fmt.Errorf("event %q has mismatched trace_id", event.EventID)
		}
		if event.EventID == "" || event.Kind == "" {
			return PreparedTrace{}, report, fmt.Errorf("event %d requires event_id and kind", i)
		}
		if _, exists := seen[event.EventID]; exists {
			return PreparedTrace{}, report, fmt.Errorf("duplicate event_id %q", event.EventID)
		}
		seen[event.EventID] = struct{}{}
		byID[event.EventID] = struct{}{}
		if event.Sequence != i {
			return PreparedTrace{}, report, fmt.Errorf("event %q sequence must be %d", event.EventID, i)
		}
		if event.Observation != "observed" && event.Observation != "reconstructed" && event.Observation != "inferred" && event.Observation != "missing" {
			return PreparedTrace{}, report, fmt.Errorf("event %q has invalid observation_status", event.EventID)
		}
		contentDigest, c, err := digestRaw(event.Content, event.ContentDigest)
		if err != nil {
			return PreparedTrace{}, report, fmt.Errorf("event %q content: %w", event.EventID, err)
		}
		argsDigest, a, err := digestJSON(event.Arguments, event.ArgumentsDigest)
		if err != nil {
			return PreparedTrace{}, report, fmt.Errorf("event %q arguments: %w", event.EventID, err)
		}
		resultDigest, r, err := digestJSON(event.Result, event.ResultDigest)
		if err != nil {
			return PreparedTrace{}, report, fmt.Errorf("event %q result: %w", event.EventID, err)
		}
		report.RedactedFields += c + a + r
		prepared.Events = append(prepared.Events, PreparedEvent{
			TraceID: t.TraceID, EventID: event.EventID, Sequence: event.Sequence,
			ParentEventID: event.ParentEventID, Kind: event.Kind, Observation: event.Observation,
			SourceRole: event.SourceRole, ToolName: event.ToolName, SkillName: event.SkillName,
			KnowledgeBase: event.KnowledgeBase, ContentDigest: contentDigest,
			ArgumentsDigest: argsDigest, ResultDigest: resultDigest, ObservedAt: event.ObservedAt,
		})
	}
	for _, event := range prepared.Events {
		if event.ParentEventID != "" {
			if _, ok := byID[event.ParentEventID]; !ok {
				return PreparedTrace{}, report, fmt.Errorf("event %q references missing parent %q", event.EventID, event.ParentEventID)
			}
		}
	}
	if t.Outcome != nil {
		prepared.OutcomeStatus = t.Outcome.Status
		prepared.OutcomeObserved = t.Outcome.Observed
	} else {
		report.OutcomeMissing = true
		report.AbstentionReasons = append(report.AbstentionReasons, "outcome_missing")
	}
	prepared.Eligible = len(report.AbstentionReasons) == 0
	report.Eligible = prepared.Eligible
	return prepared, report, nil
}

func ContainsRawPayload(v any) bool {
	b, err := json.Marshal(v)
	if err != nil {
		return true
	}
	return bytes.Contains(bytes.ToLower(b), []byte(`"content"`)) || bytes.Contains(bytes.ToLower(b), []byte(`"arguments"`)) || bytes.Contains(bytes.ToLower(b), []byte(`"result"`))
}
