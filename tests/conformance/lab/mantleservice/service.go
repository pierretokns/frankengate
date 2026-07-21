// Package mantleservice provides the deterministic, zero-paid-inference
// OpenAI surface used by the sealed conformance lab. It models only rows whose
// authority is recorded in coverage.v1.json; it is not an AWS emulator.
package mantleservice

import (
	"bytes"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strings"
)

const maxRequestBytes = 1 << 20
const expectedSourceLockSHA256 = "c2ba4e5348dcaddf8ca508f2f3fbcaeee966055057b852fe4899bf901e1e7350"
const syntheticAuthorization = "Bearer synthetic-mantle-contract"

//go:embed coverage.v1.json
var coverageJSON []byte

type Coverage struct {
	Schema           string         `json:"schema"`
	SourceLockSHA256 string         `json:"source_lock_sha256"`
	Sources          []Source       `json:"sources"`
	ModelRoutes      []OperationRow `json:"model_routes"`
	Omissions        []Omission     `json:"omissions"`
	Discrepancies    []Discrepancy  `json:"discrepancies"`
	Rows             []ModelRow     `json:"rows"`
}

type Omission struct {
	ID      string `json:"id"`
	Subject string `json:"subject"`
	Reason  string `json:"reason"`
}

type Discrepancy struct {
	ID         string   `json:"id"`
	Status     string   `json:"status"`
	Resolution string   `json:"resolution"`
	SourceIDs  []string `json:"source_ids"`
}

type Source struct {
	ID             string `json:"id"`
	AuthorityClass string `json:"authority_class"`
	ArtifactDigest string `json:"artifact_digest"`
}

type OperationRow struct {
	Method       string `json:"method"`
	Path         string `json:"path"`
	Auth         string `json:"auth"`
	ContentType  string `json:"content_type"`
	EventGrammar string `json:"event_grammar"`
	SourceID     string `json:"source_id"`
}

type ModelRow struct {
	ModelID               string `json:"model_id"`
	Revision              string `json:"revision"`
	Authority             string `json:"authority"`
	SourceID              string `json:"source_id"`
	Method                string `json:"method"`
	Path                  string `json:"path"`
	ChatPath              string `json:"chat_path,omitempty"`
	Auth                  string `json:"auth"`
	ContentType           string `json:"content_type"`
	ResponsesEventGrammar string `json:"responses_event_grammar"`
	ChatEventGrammar      string `json:"chat_event_grammar"`
	Responses             bool   `json:"responses"`
	Chat                  bool   `json:"chat"`
	ChatStreaming         bool   `json:"chat_streaming"`
	ExpectedStatus        int    `json:"expected_status,omitempty"`
	ExpectedErrorCode     string `json:"expected_error_code,omitempty"`
}

type Service struct {
	coverage Coverage
	models   map[string]ModelRow
}

func New() (*Service, error) {
	return newServiceFromCoverage(coverageJSON)
}

func newServiceFromCoverage(data []byte) (*Service, error) {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var coverage Coverage
	if err := decoder.Decode(&coverage); err != nil {
		return nil, fmt.Errorf("decode Mantle coverage: %w", err)
	}
	if coverage.Schema != "bedrock-mantle-openai-service-coverage/v1" || coverage.SourceLockSHA256 != expectedSourceLockSHA256 || len(coverage.Sources) == 0 || len(coverage.ModelRoutes) != 2 || len(coverage.Omissions) < 3 || len(coverage.Discrepancies) == 0 || len(coverage.Rows) == 0 {
		return nil, fmt.Errorf("invalid Mantle coverage identity")
	}
	sources := make(map[string]Source, len(coverage.Sources))
	for _, source := range coverage.Sources {
		_, digestErr := hex.DecodeString(strings.TrimPrefix(source.ArtifactDigest, "sha256:"))
		if source.ID == "" || source.AuthorityClass == "" || !strings.HasPrefix(source.ArtifactDigest, "sha256:") || len(source.ArtifactDigest) != 71 || digestErr != nil || sources[source.ID].ID != "" {
			return nil, fmt.Errorf("invalid or duplicate coverage source %q", source.ID)
		}
		sources[source.ID] = source
	}
	seenOmissions := map[string]bool{}
	for index, omission := range coverage.Omissions {
		if omission.ID == "" || omission.Subject == "" || omission.Reason == "" || seenOmissions[omission.ID] || (index > 0 && coverage.Omissions[index-1].ID >= omission.ID) {
			return nil, fmt.Errorf("invalid or unsorted omission %q", omission.ID)
		}
		seenOmissions[omission.ID] = true
	}
	for _, required := range []string{"anthropic-separate-surface", "chat-streaming-excluded", "gemma-4-missing-authority"} {
		if !seenOmissions[required] {
			return nil, fmt.Errorf("missing required omission %q", required)
		}
	}
	seenDiscrepancies := map[string]bool{}
	for index, discrepancy := range coverage.Discrepancies {
		if discrepancy.ID == "" || discrepancy.Status == "" || discrepancy.Resolution == "" || len(discrepancy.SourceIDs) < 2 || seenDiscrepancies[discrepancy.ID] || (index > 0 && coverage.Discrepancies[index-1].ID >= discrepancy.ID) {
			return nil, fmt.Errorf("invalid or unsorted discrepancy %q", discrepancy.ID)
		}
		for _, sourceID := range discrepancy.SourceIDs {
			if sources[sourceID].ID == "" {
				return nil, fmt.Errorf("discrepancy %q references unknown source %q", discrepancy.ID, sourceID)
			}
		}
		seenDiscrepancies[discrepancy.ID] = true
	}
	modelPaths := map[string]bool{"/v1/models": false, "/openai/v1/models": false}
	for _, route := range coverage.ModelRoutes {
		if route.Method != http.MethodGet || route.Auth != "synthetic-bearer" || route.ContentType != "application/json" || route.EventGrammar != "openai-model-list-json" || sources[route.SourceID].ID == "" {
			return nil, fmt.Errorf("incomplete Models coverage route %q", route.Path)
		}
		if _, ok := modelPaths[route.Path]; !ok || modelPaths[route.Path] {
			return nil, fmt.Errorf("unsupported or duplicate Models route %q", route.Path)
		}
		modelPaths[route.Path] = true
	}
	models := make(map[string]ModelRow, len(coverage.Rows))
	for _, row := range coverage.Rows {
		positive := row.Responses && row.ResponsesEventGrammar == "openai-responses-sse-v1" && row.ExpectedStatus == 0 && row.ExpectedErrorCode == ""
		negative := !row.Responses && row.ResponsesEventGrammar == "" && row.ExpectedStatus == http.StatusUnauthorized && row.ExpectedErrorCode == "access_denied" && row.Authority == "aws-observed-sample"
		if row.ModelID == "" || row.Revision == "" || row.Authority == "" || sources[row.SourceID].ID == "" || row.Authority != sources[row.SourceID].AuthorityClass || row.Method != http.MethodPost || row.Auth != "synthetic-bearer" || row.ContentType != "application/json" || (!positive && !negative) {
			return nil, fmt.Errorf("incomplete coverage row %q", row.ModelID)
		}
		if row.Path != "/v1/responses" && row.Path != "/openai/v1/responses" {
			return nil, fmt.Errorf("unsupported response path %q", row.Path)
		}
		if row.Chat != (row.ChatPath != "") || row.Chat != (row.ChatEventGrammar == "openai-chat-completions-json-v1") || row.ChatStreaming || (row.ChatPath != "" && row.ChatPath != "/v1/chat/completions" && row.ChatPath != "/openai/v1/chat/completions") {
			return nil, fmt.Errorf("model %q has inconsistent Chat coverage", row.ModelID)
		}
		if negative && (row.Chat || row.ChatPath != "" || row.ChatEventGrammar != "" || row.ChatStreaming) {
			return nil, fmt.Errorf("negative observation model %q cannot authorize Chat", row.ModelID)
		}
		if _, exists := models[row.ModelID]; exists {
			return nil, fmt.Errorf("duplicate model %q", row.ModelID)
		}
		models[row.ModelID] = row
	}
	return &Service{coverage: coverage, models: models}, nil
}

func (s *Service) Coverage() Coverage {
	rows := append([]ModelRow(nil), s.coverage.Rows...)
	modelRoutes := append([]OperationRow(nil), s.coverage.ModelRoutes...)
	sources := append([]Source(nil), s.coverage.Sources...)
	omissions := append([]Omission(nil), s.coverage.Omissions...)
	discrepancies := append([]Discrepancy(nil), s.coverage.Discrepancies...)
	return Coverage{Schema: s.coverage.Schema, SourceLockSHA256: s.coverage.SourceLockSHA256, Sources: sources, ModelRoutes: modelRoutes, Omissions: omissions, Discrepancies: discrepancies, Rows: rows}
}

func (s *Service) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.RawQuery != "" || strings.Contains(r.URL.EscapedPath(), "%2f") || strings.Contains(r.URL.Path, "//") || strings.Count(r.URL.Path, "/openai/") > 1 {
		writeError(w, http.StatusNotFound, "unsupported_route", "request target is not a covered Mantle route")
		return
	}
	authorizations := r.Header.Values("Authorization")
	if len(authorizations) != 1 || authorizations[0] != syntheticAuthorization {
		writeError(w, http.StatusUnauthorized, "invalid_auth", "a synthetic lab bearer credential is required")
		return
	}
	if r.Method == http.MethodGet && (r.URL.Path == "/v1/models" || r.URL.Path == "/openai/v1/models") {
		s.serveModels(w)
		return
	}
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed", "covered inference routes require POST")
		return
	}
	if media := strings.ToLower(strings.TrimSpace(strings.Split(r.Header.Get("Content-Type"), ";")[0])); media != "application/json" {
		writeError(w, http.StatusUnsupportedMediaType, "invalid_content_type", "content type must be application/json")
		return
	}
	body, err := io.ReadAll(io.LimitReader(r.Body, maxRequestBytes+1))
	if err != nil || len(body) > maxRequestBytes {
		writeError(w, http.StatusRequestEntityTooLarge, "request_too_large", "request exceeds deterministic service bound")
		return
	}
	if err := rejectDuplicateOrNullJSON(body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	var request struct {
		Model              string          `json:"model"`
		Input              json.RawMessage `json:"input"`
		Messages           json.RawMessage `json:"messages"`
		Stream             bool            `json:"stream"`
		Instructions       json.RawMessage `json:"instructions"`
		PreviousResponseID string          `json:"previous_response_id"`
		Reasoning          json.RawMessage `json:"reasoning"`
		Tools              json.RawMessage `json:"tools"`
		ToolChoice         json.RawMessage `json:"tool_choice"`
		ParallelToolCalls  *bool           `json:"parallel_tool_calls"`
	}
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&request); err != nil || request.Model == "" {
		writeError(w, http.StatusBadRequest, "invalid_request", "request must contain one JSON object and a model")
		return
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		writeError(w, http.StatusBadRequest, "invalid_request", "request must contain exactly one JSON object")
		return
	}
	if strings.Contains(request.Model, "/") {
		writeError(w, http.StatusNotFound, "unknown_model", "provider-prefixed and double-prefixed models are not upstream model IDs")
		return
	}
	row, ok := s.models[request.Model]
	if !ok {
		writeError(w, http.StatusNotFound, "unknown_model", "model is absent from the authority-scoped route table")
		return
	}
	switch r.URL.Path {
	case "/v1/responses", "/openai/v1/responses":
		if r.URL.Path != row.Path {
			writeError(w, http.StatusNotFound, "wrong_model_route", "model is not authorized on this route")
			return
		}
		if row.ExpectedStatus != 0 {
			writeError(w, row.ExpectedStatus, row.ExpectedErrorCode, "locked observation proves route reachability only; successful inference is not modeled")
			return
		}
		if len(request.Input) == 0 {
			writeError(w, http.StatusBadRequest, "invalid_request", "Responses requires input")
			return
		}
		if r.URL.Path == "/openai/v1/responses" && containsAdditionalTools(request.Input) {
			writeError(w, http.StatusBadRequest, "invalid_input", "value did not match any expected variant")
			return
		}
		if request.Stream {
			s.serveResponsesStream(w, r, row, body)
		} else {
			s.serveResponse(w, row, body)
		}
	case "/v1/chat/completions", "/openai/v1/chat/completions":
		if !row.Chat || r.URL.Path != row.ChatPath {
			writeError(w, http.StatusBadRequest, "unsupported_operation", "chat completions are not supported for this model")
			return
		}
		if len(request.Messages) == 0 {
			writeError(w, http.StatusBadRequest, "invalid_request", "Chat Completions requires messages")
			return
		}
		if request.Stream {
			writeError(w, http.StatusBadRequest, "streaming_not_covered", "Chat streaming is explicitly outside this coverage revision")
			return
		}
		s.serveChat(w, row, body)
	default:
		writeError(w, http.StatusNotFound, "unsupported_route", "request target is not a covered Mantle route")
	}
}

func containsAdditionalTools(input json.RawMessage) bool {
	var items []struct {
		Type string `json:"type"`
	}
	if json.Unmarshal(input, &items) != nil {
		return false
	}
	for _, item := range items {
		if item.Type == "additional_tools" {
			return true
		}
	}
	return false
}

func (s *Service) serveModels(w http.ResponseWriter) {
	ids := make([]string, 0, len(s.models))
	for id := range s.models {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	data := make([]map[string]any, 0, len(ids))
	for _, id := range ids {
		data = append(data, map[string]any{"id": id, "object": "model", "owned_by": "bedrock-mantle-contract"})
	}
	writeJSON(w, http.StatusOK, map[string]any{"object": "list", "data": data})
}

func deterministicID(prefix string, body []byte) string {
	digest := sha256.Sum256(body)
	return prefix + hex.EncodeToString(digest[:8])
}

func (s *Service) serveResponse(w http.ResponseWriter, row ModelRow, body []byte) {
	id := deterministicID("resp_", body)
	writeJSON(w, http.StatusOK, map[string]any{"id": id, "object": "response", "model": row.ModelID, "status": "completed", "output": []any{map[string]any{"id": "msg_" + id[5:], "type": "message", "role": "assistant", "content": []any{map[string]any{"type": "output_text", "text": "deterministic mantle response"}}}}, "usage": map[string]int{"input_tokens": 4, "output_tokens": 3, "total_tokens": 7}})
}

func (s *Service) serveResponsesStream(w http.ResponseWriter, r *http.Request, row ModelRow, body []byte) {
	if err := r.Context().Err(); err != nil {
		writeError(w, 499, "cancelled", "request was cancelled before stream start")
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	id := deterministicID("resp_", body)
	messageID := "msg_" + id[5:]
	part := map[string]any{"type": "output_text", "text": "deterministic mantle response", "annotations": []any{}}
	item := map[string]any{"id": messageID, "type": "message", "status": "completed", "role": "assistant", "content": []any{part}}
	events := []map[string]any{
		{"type": "response.created", "sequence_number": 0, "response": map[string]any{"id": id, "object": "response", "model": row.ModelID, "status": "in_progress", "output": []any{}}},
		{"type": "response.output_item.added", "sequence_number": 1, "output_index": 0, "item": map[string]any{"id": messageID, "type": "message", "status": "in_progress", "role": "assistant", "content": []any{}}},
		{"type": "response.content_part.added", "sequence_number": 2, "item_id": messageID, "output_index": 0, "content_index": 0, "part": map[string]any{"type": "output_text", "text": "", "annotations": []any{}}},
		{"type": "response.output_text.delta", "sequence_number": 3, "item_id": messageID, "output_index": 0, "content_index": 0, "delta": "deterministic mantle response"},
		{"type": "response.output_text.done", "sequence_number": 4, "item_id": messageID, "output_index": 0, "content_index": 0, "text": "deterministic mantle response"},
		{"type": "response.content_part.done", "sequence_number": 5, "item_id": messageID, "output_index": 0, "content_index": 0, "part": part},
		{"type": "response.output_item.done", "sequence_number": 6, "output_index": 0, "item": item},
		{"type": "response.completed", "sequence_number": 7, "response": map[string]any{"id": id, "object": "response", "model": row.ModelID, "status": "completed", "output": []any{item}, "usage": map[string]int{"input_tokens": 4, "output_tokens": 3, "total_tokens": 7}}},
	}
	for _, event := range events {
		encoded, _ := json.Marshal(event)
		fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event["type"], encoded)
		if flusher, ok := w.(http.Flusher); ok {
			flusher.Flush()
		}
	}
}

func rejectDuplicateOrNullJSON(data []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	var walk func() error
	walk = func() error {
		token, err := decoder.Token()
		if err != nil {
			return err
		}
		if token == nil {
			return fmt.Errorf("JSON null is not permitted in the deterministic contract")
		}
		delim, ok := token.(json.Delim)
		if !ok {
			return nil
		}
		switch delim {
		case '{':
			seen := map[string]bool{}
			for decoder.More() {
				keyToken, err := decoder.Token()
				if err != nil {
					return err
				}
				key, ok := keyToken.(string)
				if !ok {
					return fmt.Errorf("JSON object key is not a string")
				}
				if seen[key] {
					return fmt.Errorf("duplicate JSON key %q", key)
				}
				seen[key] = true
				if err := walk(); err != nil {
					return err
				}
			}
			_, err = decoder.Token()
			return err
		case '[':
			for decoder.More() {
				if err := walk(); err != nil {
					return err
				}
			}
			_, err = decoder.Token()
			return err
		default:
			return fmt.Errorf("unexpected JSON delimiter")
		}
	}
	if err := walk(); err != nil {
		return err
	}
	if _, err := decoder.Token(); err != io.EOF {
		return fmt.Errorf("request contains trailing JSON")
	}
	return nil
}

func (s *Service) serveChat(w http.ResponseWriter, row ModelRow, body []byte) {
	id := deterministicID("chatcmpl_", body)
	writeJSON(w, http.StatusOK, map[string]any{"id": id, "object": "chat.completion", "model": row.ModelID, "choices": []any{map[string]any{"index": 0, "finish_reason": "stop", "message": map[string]string{"role": "assistant", "content": "deterministic mantle chat"}}}, "usage": map[string]int{"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}})
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, map[string]any{"error": map[string]string{"type": "invalid_request_error", "code": code, "message": message}})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
