package mantleservice

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
)

const (
	IntegrationHost  = "bedrock-mantle.us-east-1.api.aws"
	TranscriptSchema = "sealed-mantle-upstream-transcript/v1"
	ResponseMarker   = "deterministic mantle response"
)

type TranscriptRecord struct {
	Schema          string `json:"schema"`
	Sequence        uint64 `json:"sequence"`
	Method          string `json:"method"`
	Host            string `json:"host"`
	Path            string `json:"path"`
	Model           string `json:"model,omitempty"`
	Stream          bool   `json:"stream"`
	BodySHA256      string `json:"body_sha256"`
	Status          int    `json:"status"`
	Authorization   string `json:"authorization_class"`
	RunID           string `json:"run_id"`
	TopLevelTools   int    `json:"top_level_tool_count"`
	AdditionalTools int    `json:"additional_tools_input_count"`
}

type transcriptWriter struct {
	mu       sync.Mutex
	sequence uint64
	writer   io.Writer
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (w *statusRecorder) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}

func (w *statusRecorder) Write(data []byte) (int, error) {
	if w.status == 0 {
		w.WriteHeader(http.StatusOK)
	}
	return w.ResponseWriter.Write(data)
}

func (w *statusRecorder) Flush() {
	if flusher, ok := w.ResponseWriter.(http.Flusher); ok {
		flusher.Flush()
	}
}

// NewIntegrationHandler preserves the real Mantle authority and records a
// bounded, secret-free upstream transcript. It is intentionally a wrapper
// around the same deterministic service used by unit conformance tests.
func NewIntegrationHandler(writer io.Writer) (http.Handler, error) {
	if writer == nil {
		return nil, fmt.Errorf("transcript writer is required")
	}
	service, err := New()
	if err != nil {
		return nil, err
	}
	recorder := &transcriptWriter{writer: writer}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/healthz" && r.Method == http.MethodGet {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if r.Host != IntegrationHost {
			writeError(w, http.StatusNotFound, "wrong_authority", "integration requests require the exact Mantle authority")
			return
		}
		body, err := io.ReadAll(io.LimitReader(r.Body, maxRequestBytes+1))
		if err != nil || len(body) > maxRequestBytes {
			writeError(w, http.StatusRequestEntityTooLarge, "request_too_large", "request exceeds deterministic service bound")
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(body))
		var envelope struct {
			Model  string            `json:"model"`
			Stream bool              `json:"stream"`
			Tools  []json.RawMessage `json:"tools"`
			Input  []struct {
				Type string `json:"type"`
			} `json:"input"`
		}
		_ = json.Unmarshal(body, &envelope)
		additionalTools := 0
		for _, item := range envelope.Input {
			if item.Type == "additional_tools" {
				additionalTools++
			}
		}
		runID := extractRunID(body)
		status := &statusRecorder{ResponseWriter: w}
		service.ServeHTTP(status, r)
		digest := sha256.Sum256(body)
		record := TranscriptRecord{
			Schema: TranscriptSchema, Method: r.Method, Host: r.Host, RunID: runID,
			Path: r.URL.Path, Model: envelope.Model, Stream: envelope.Stream,
			BodySHA256: hex.EncodeToString(digest[:]), Status: status.status,
			Authorization: "synthetic-bearer",
			TopLevelTools: len(envelope.Tools), AdditionalTools: additionalTools,
		}
		recorder.mu.Lock()
		recorder.sequence++
		record.Sequence = recorder.sequence
		encoded, encodeErr := json.Marshal(record)
		if encodeErr == nil {
			_, _ = fmt.Fprintf(recorder.writer, "%s\n", encoded)
		}
		recorder.mu.Unlock()
	}), nil
}

func extractRunID(body []byte) string {
	const prefix = "SEALED_CODEX_RUN_ID:"
	index := bytes.Index(body, []byte(prefix))
	if index < 0 {
		return ""
	}
	value := body[index+len(prefix):]
	end := bytes.IndexAny(value, `\"\\ \n\r`)
	if end >= 0 {
		value = value[:end]
	}
	if len(value) == 0 || len(value) > 48 {
		return ""
	}
	for _, c := range value {
		if !((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-') {
			return ""
		}
	}
	return string(value)
}
