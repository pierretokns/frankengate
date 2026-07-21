package privacy

import (
	"bytes"
	"compress/gzip"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws/protocol/eventstream"
)

const CaptureSanitizerRevision = "capture_sanitizer.v1"

const (
	defaultMaxEncodedBytes      = int64(1 << 20)
	defaultMaxDecodedBytes      = int64(4 << 20)
	defaultMaxCompressionRatio  = 20
	defaultMaxDecodeDepth       = 32
	defaultQuarantineFileMode   = 0o600
	quarantineEnvelopeVersionV1 = "capture_quarantine.v1"
)

var (
	safeLiteralRe   = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:@/+~-]{0,127}$`)
	hexLikeRe       = regexp.MustCompile(`^[a-fA-F0-9]{32,}$`)
	base64LikeRe    = regexp.MustCompile(`^[A-Za-z0-9+/=_-]{24,}$`)
	bearerLikeRe    = regexp.MustCompile(`(?i)\b(bearer|basic|aws4-hmac-sha256|sk-[a-z0-9_-]*|xox[baprs]-)[^\s"']+`)
	presignedURLRe  = regexp.MustCompile(`(?i)(x-amz-signature|x-amz-credential|signature=|sig=|client_secret=|api_key=)`)
	relationKeyName = map[string]string{
		"id":                   "id",
		"request_id":           "request",
		"response_id":          "response",
		"previous_response_id": "response",
		"conversation_id":      "conversation",
		"session_id":           "session",
		"trace_id":             "trace",
		"span_id":              "span",
		"tool_call_id":         "tool",
		"tool_use_id":          "tool",
		"project_id":           "project",
		"workspace_id":         "workspace",
	}
	safeStringEnums = map[string]struct{}{
		"assistant": {}, "user": {}, "system": {}, "tool": {}, "developer": {},
		"completed": {}, "in_progress": {}, "failed": {}, "cancelled": {},
		"text": {}, "input_text": {}, "output_text": {}, "message": {},
		"function_call": {}, "function_call_output": {}, "reasoning": {},
		"stop": {}, "length": {}, "content_filter": {}, "tool_calls": {},
		"chat.completion.chunk": {}, "response.output_text.delta": {}, "[DONE]": {},
	}
)

type RawCapture struct {
	ID              string
	CorpusID        string
	Method          string
	URL             string
	ContentType     string
	ContentEncoding string
	Headers         map[string][]string
	Body            []byte
	CapturedAt      time.Time
}

type SanitizerPolicy struct {
	Revision            string
	AllowedSchemes      []string
	AllowedHosts        []string
	AllowedPaths        []string
	AllowedQueryKeys    []string
	AllowedHeaderNames  []string
	MaxEncodedBytes     int64
	MaxDecodedBytes     int64
	MaxCompressionRatio float64
	MaxDecodeDepth      int
	CanarySecrets       map[string]string
	SourceRevision      string
}

type SanitizedCapture struct {
	CorpusID          string              `json:"corpus_id"`
	Method            string              `json:"method"`
	URL               SanitizedURL        `json:"url"`
	Headers           map[string][]string `json:"headers,omitempty"`
	PayloadFormat     string              `json:"payload_format"`
	Payload           any                 `json:"payload,omitempty"`
	Tokens            map[string]string   `json:"tokens,omitempty"`
	CanaryDetections  []string            `json:"canary_detections,omitempty"`
	SanitizerRevision string              `json:"sanitizer_revision"`
	SanitizerHash     string              `json:"sanitizer_hash"`
	PolicyRevision    string              `json:"policy_revision"`
	PolicyHash        string              `json:"policy_hash"`
	SourceHash        string              `json:"source_hash"`
}

type SanitizedURL struct {
	Scheme string            `json:"scheme"`
	Host   string            `json:"host"`
	Path   string            `json:"path"`
	Query  map[string]string `json:"query,omitempty"`
}

type CaptureSanitizer struct {
	policy        SanitizerPolicy
	policyHash    string
	sanitizerHash string

	mu      sync.Mutex
	tokens  map[string]map[string]string
	counts  map[string]map[string]int
	closed  bool
	allowed allowedCaptureSets
}

type allowedCaptureSets struct {
	schemes map[string]struct{}
	hosts   map[string]struct{}
	paths   map[string]struct{}
	queries map[string]struct{}
	headers map[string]struct{}
}

func NewCaptureSanitizer(policy SanitizerPolicy) (*CaptureSanitizer, error) {
	normalized, allowed, err := normalizeSanitizerPolicy(policy)
	if err != nil {
		return nil, err
	}
	policyHash, err := hashPolicy(normalized)
	if err != nil {
		return nil, err
	}
	return &CaptureSanitizer{
		policy:        normalized,
		policyHash:    policyHash,
		sanitizerHash: digestString(CaptureSanitizerRevision),
		tokens:        make(map[string]map[string]string),
		counts:        make(map[string]map[string]int),
		allowed:       allowed,
	}, nil
}

func (s *CaptureSanitizer) Destroy() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tokens = nil
	s.counts = nil
	s.closed = true
}

func (s *CaptureSanitizer) Sanitize(capture RawCapture) (SanitizedCapture, error) {
	if err := s.ensureOpen(); err != nil {
		return SanitizedCapture{}, err
	}
	if capture.CorpusID == "" {
		return SanitizedCapture{}, errors.New("corpus_id is required")
	}
	safeURL, err := s.sanitizeURL(capture)
	if err != nil {
		return SanitizedCapture{}, err
	}
	decoded, err := s.decodeBody(capture.Body, capture.ContentEncoding)
	if err != nil {
		return SanitizedCapture{}, err
	}
	detections := s.detectCanaries(capture, decoded)
	headers := s.sanitizeHeaders(capture.CorpusID, capture.Headers)
	format, payload, err := s.sanitizePayload(capture.CorpusID, capture.ContentType, decoded)
	if err != nil {
		return SanitizedCapture{}, err
	}
	result := SanitizedCapture{
		CorpusID:          capture.CorpusID,
		Method:            strings.ToUpper(capture.Method),
		URL:               safeURL,
		Headers:           headers,
		PayloadFormat:     format,
		Payload:           payload,
		Tokens:            s.publicTokens(capture.CorpusID),
		CanaryDetections:  detections,
		SanitizerRevision: CaptureSanitizerRevision,
		SanitizerHash:     s.sanitizerHash,
		PolicyRevision:    s.policy.Revision,
		PolicyHash:        s.policyHash,
		SourceHash:        digestString(s.policy.SourceRevision),
	}
	if err := result.assertNoRawCanaryValues(s.policy.CanarySecrets); err != nil {
		return SanitizedCapture{}, err
	}
	return result, nil
}

func (s *CaptureSanitizer) ensureOpen() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return errors.New("capture sanitizer has been destroyed")
	}
	return nil
}

func (s *CaptureSanitizer) sanitizeURL(capture RawCapture) (SanitizedURL, error) {
	parsed, err := url.Parse(capture.URL)
	if err != nil {
		return SanitizedURL{}, fmt.Errorf("parse capture url: %w", err)
	}
	scheme := strings.ToLower(parsed.Scheme)
	host := strings.ToLower(parsed.Host)
	path := parsed.EscapedPath()
	if path == "" {
		path = "/"
	}
	if _, ok := s.allowed.schemes[scheme]; !ok {
		return SanitizedURL{}, fmt.Errorf("capture url scheme %q is not allowed", scheme)
	}
	if _, ok := s.allowed.hosts[host]; !ok {
		return SanitizedURL{}, fmt.Errorf("capture url host %q is not allowed", host)
	}
	if _, ok := s.allowed.paths[path]; !ok {
		return SanitizedURL{}, fmt.Errorf("capture url path %q is not allowed", path)
	}
	out := SanitizedURL{Scheme: scheme, Host: host, Path: path}
	values := parsed.Query()
	if len(values) == 0 {
		return out, nil
	}
	query := make(map[string]string)
	for key, vals := range values {
		if _, ok := s.allowed.queries[strings.ToLower(key)]; !ok {
			continue
		}
		query[key] = s.tokenFor(capture.CorpusID, "query_"+safeTokenKind(key), strings.Join(vals, "\x00"))
	}
	if len(query) > 0 {
		out.Query = query
	}
	return out, nil
}

func (s *CaptureSanitizer) sanitizeHeaders(corpusID string, headers map[string][]string) map[string][]string {
	if len(headers) == 0 {
		return nil
	}
	out := make(map[string][]string)
	for name, values := range headers {
		lower := strings.ToLower(name)
		if isSensitiveName(name) {
			continue
		}
		if _, ok := s.allowed.headers[lower]; !ok {
			continue
		}
		copied := make([]string, 0, len(values))
		for _, value := range values {
			if isSafeHeaderLiteral(lower, value) {
				copied = append(copied, value)
				continue
			}
			copied = append(copied, s.tokenFor(corpusID, "header_"+safeTokenKind(lower), value))
		}
		if len(copied) > 0 {
			out[name] = copied
		}
	}
	if len(out) == 0 {
		return nil
	}
	return out
}

func (s *CaptureSanitizer) decodeBody(body []byte, encoding string) ([]byte, error) {
	if int64(len(body)) > s.policy.MaxEncodedBytes {
		return nil, fmt.Errorf("encoded capture exceeds %d bytes", s.policy.MaxEncodedBytes)
	}
	switch strings.ToLower(strings.TrimSpace(encoding)) {
	case "", "identity":
		return append([]byte(nil), body...), nil
	case "gzip":
		zr, err := gzip.NewReader(bytes.NewReader(body))
		if err != nil {
			return nil, fmt.Errorf("decode gzip capture: %w", err)
		}
		defer zr.Close()
		decoded, err := readBounded(zr, s.policy.MaxDecodedBytes)
		if err != nil {
			return nil, err
		}
		if len(body) > 0 {
			ratio := float64(len(decoded)) / float64(len(body))
			if ratio > s.policy.MaxCompressionRatio {
				return nil, fmt.Errorf("gzip expansion ratio %.2f exceeds %.2f", ratio, s.policy.MaxCompressionRatio)
			}
		}
		return decoded, nil
	default:
		return nil, fmt.Errorf("unsupported capture content encoding %q", encoding)
	}
}

func readBounded(r io.Reader, limit int64) ([]byte, error) {
	buf, err := io.ReadAll(io.LimitReader(r, limit+1))
	if err != nil {
		return nil, err
	}
	if int64(len(buf)) > limit {
		return nil, fmt.Errorf("decoded capture exceeds %d bytes", limit)
	}
	return buf, nil
}

func (s *CaptureSanitizer) sanitizePayload(corpusID, contentType string, body []byte) (string, any, error) {
	if len(body) == 0 {
		return "empty", nil, nil
	}
	lower := strings.ToLower(contentType)
	switch {
	case strings.Contains(lower, "application/json") || strings.Contains(lower, "+json"):
		value, err := decodeJSON(body)
		if err != nil {
			return "", nil, err
		}
		sanitized, err := s.sanitizeJSONValue(corpusID, "", value, 0)
		if err != nil {
			return "", nil, err
		}
		return "json", sanitized, nil
	case strings.Contains(lower, "text/event-stream"):
		payload, err := s.sanitizeSSE(corpusID, body)
		return "sse", payload, err
	case strings.Contains(lower, "application/vnd.amazon.eventstream"):
		payload, err := s.sanitizeEventStream(corpusID, body)
		return "eventstream", payload, err
	default:
		return "", nil, fmt.Errorf("unsupported capture content type %q", contentType)
	}
}

func decodeJSON(body []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	var value any
	if err := dec.Decode(&value); err != nil {
		return nil, fmt.Errorf("decode json capture: %w", err)
	}
	var extra any
	if err := dec.Decode(&extra); err != io.EOF {
		if err == nil {
			return nil, errors.New("json capture contains multiple values")
		}
		return nil, err
	}
	return value, nil
}

func (s *CaptureSanitizer) sanitizeJSONValue(corpusID, key string, value any, depth int) (any, error) {
	if depth > s.policy.MaxDecodeDepth {
		return nil, fmt.Errorf("json capture exceeds decode depth %d", s.policy.MaxDecodeDepth)
	}
	switch node := value.(type) {
	case map[string]any:
		out := make(map[string]any, len(node))
		for childKey, child := range node {
			if isSensitiveName(childKey) || isCredentialKey(childKey) {
				out[childKey] = s.tokenFor(corpusID, "secret", stringifyJSON(child))
				continue
			}
			sanitized, err := s.sanitizeJSONValue(corpusID, childKey, child, depth+1)
			if err != nil {
				return nil, err
			}
			out[childKey] = sanitized
		}
		return out, nil
	case []any:
		out := make([]any, len(node))
		for i, child := range node {
			sanitized, err := s.sanitizeJSONValue(corpusID, key, child, depth+1)
			if err != nil {
				return nil, err
			}
			out[i] = sanitized
		}
		return out, nil
	case string:
		return s.sanitizeString(corpusID, key, node), nil
	case json.Number:
		if i, err := node.Int64(); err == nil {
			return i, nil
		}
		f, err := node.Float64()
		if err != nil || math.IsNaN(f) || math.IsInf(f, 0) {
			return nil, fmt.Errorf("invalid json number at %q", key)
		}
		return f, nil
	case nil, bool, float64:
		return node, nil
	default:
		return s.tokenFor(corpusID, "unknown", fmt.Sprintf("%v", node)), nil
	}
}

func (s *CaptureSanitizer) sanitizeString(corpusID, key, value string) string {
	if value == "" {
		return ""
	}
	lowerKey := strings.ToLower(key)
	if kind, ok := relationKeyName[lowerKey]; ok {
		return s.tokenFor(corpusID, kind, value)
	}
	if strings.HasSuffix(lowerKey, "_id") || strings.Contains(lowerKey, "id") {
		return s.tokenFor(corpusID, "id", value)
	}
	if strings.Contains(lowerKey, "url") || looksLikeURL(value) {
		return s.tokenFor(corpusID, "url", value)
	}
	if isSensitiveName(lowerKey) || isCredentialKey(lowerKey) || looksSensitive(value) {
		return s.tokenFor(corpusID, "secret", value)
	}
	if isFreeTextKey(lowerKey) {
		return s.tokenFor(corpusID, "text", value)
	}
	if _, ok := safeStringEnums[value]; ok {
		return value
	}
	if safeLiteralRe.MatchString(value) && !looksHighEntropy(value) && !strings.Contains(value, ".") {
		return value
	}
	return s.tokenFor(corpusID, "text", value)
}

func (s *CaptureSanitizer) sanitizeSSE(corpusID string, body []byte) ([]map[string]any, error) {
	events := make([]map[string]any, 0)
	current := make(map[string]any)
	lines := strings.Split(strings.ReplaceAll(string(body), "\r\n", "\n"), "\n")
	flush := func() {
		if len(current) > 0 {
			events = append(events, current)
			current = make(map[string]any)
		}
	}
	for _, line := range lines {
		if line == "" {
			flush()
			continue
		}
		if strings.HasPrefix(line, ":") {
			continue
		}
		field, value, ok := strings.Cut(line, ":")
		if !ok {
			return nil, fmt.Errorf("malformed sse line %q", line)
		}
		value = strings.TrimPrefix(value, " ")
		switch field {
		case "event":
			current["event"] = s.sanitizeString(corpusID, "event", value)
		case "id":
			current["id"] = s.tokenFor(corpusID, "sse_id", value)
		case "retry":
			current["retry"] = s.sanitizeString(corpusID, "retry", value)
		case "data":
			if value == "[DONE]" {
				current["data"] = "[DONE]"
				continue
			}
			decoded, err := decodeJSON([]byte(value))
			if err != nil {
				current["data"] = s.tokenFor(corpusID, "text", value)
				continue
			}
			sanitized, err := s.sanitizeJSONValue(corpusID, "data", decoded, 0)
			if err != nil {
				return nil, err
			}
			current["data"] = sanitized
		default:
			return nil, fmt.Errorf("unsupported sse field %q", field)
		}
	}
	flush()
	return events, nil
}

func (s *CaptureSanitizer) sanitizeEventStream(corpusID string, body []byte) ([]map[string]any, error) {
	decoder := eventstream.NewDecoder()
	reader := bytes.NewReader(body)
	payloadBuf := make([]byte, 0, 1024*1024)
	events := make([]map[string]any, 0)
	for {
		message, err := decoder.Decode(reader, payloadBuf)
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("decode eventstream capture: %w", err)
		}
		event := map[string]any{}
		headers := make(map[string]string)
		for _, header := range message.Headers {
			name := strings.ToLower(header.Name)
			if isSensitiveName(name) || isCredentialKey(name) {
				continue
			}
			switch name {
			case ":message-type", ":event-type", ":content-type", ":exception-type":
				headers[header.Name] = s.sanitizeString(corpusID, name, header.Value.String())
			}
		}
		if len(headers) > 0 {
			event["headers"] = headers
		}
		if len(message.Payload) > 0 {
			payload, err := decodeJSON(message.Payload)
			if err != nil {
				event["payload"] = s.tokenFor(corpusID, "binary_payload", base64.StdEncoding.EncodeToString(message.Payload))
			} else {
				sanitized, err := s.sanitizeJSONValue(corpusID, "payload", payload, 0)
				if err != nil {
					return nil, err
				}
				event["payload"] = sanitized
			}
		}
		events = append(events, event)
	}
	if len(events) == 0 {
		return nil, errors.New("eventstream capture contains no messages")
	}
	return events, nil
}

func (s *CaptureSanitizer) detectCanaries(capture RawCapture, decoded []byte) []string {
	if len(s.policy.CanarySecrets) == 0 {
		return nil
	}
	haystacks := [][]byte{
		[]byte(capture.URL),
		flattenHeaders(capture.Headers),
		capture.Body,
		decoded,
	}
	labels := make([]string, 0)
	for label, secret := range s.policy.CanarySecrets {
		if secret == "" {
			continue
		}
		if encodedCanaryPresent(haystacks, secret) {
			labels = append(labels, label)
		}
	}
	sort.Strings(labels)
	return labels
}

func flattenHeaders(headers map[string][]string) []byte {
	if len(headers) == 0 {
		return nil
	}
	var b strings.Builder
	for name, values := range headers {
		b.WriteString(name)
		b.WriteByte(':')
		b.WriteString(strings.Join(values, "\x00"))
		b.WriteByte('\n')
	}
	return []byte(b.String())
}

func encodedCanaryPresent(haystacks [][]byte, secret string) bool {
	forms := [][]byte{
		[]byte(secret),
		[]byte(url.QueryEscape(secret)),
		[]byte(base64.StdEncoding.EncodeToString([]byte(secret))),
		[]byte(base64.RawStdEncoding.EncodeToString([]byte(secret))),
		[]byte(base64.URLEncoding.EncodeToString([]byte(secret))),
		[]byte(base64.RawURLEncoding.EncodeToString([]byte(secret))),
		[]byte(hex.EncodeToString([]byte(secret))),
	}
	for _, haystack := range haystacks {
		for _, form := range forms {
			if len(form) > 0 && bytes.Contains(haystack, form) {
				return true
			}
		}
	}
	return false
}

func (s *CaptureSanitizer) tokenFor(corpusID, kind, raw string) string {
	kind = safeTokenKind(kind)
	scope := corpusID + "\x00" + kind
	key := scope + "\x00" + raw
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return "<destroyed>"
	}
	if s.tokens[scope] == nil {
		s.tokens[scope] = make(map[string]string)
	}
	if token, ok := s.tokens[scope][key]; ok {
		return token
	}
	if s.counts[corpusID] == nil {
		s.counts[corpusID] = make(map[string]int)
	}
	s.counts[corpusID][kind]++
	token := fmt.Sprintf("<%s:%s:%04d>", kind, shortTokenScope(corpusID), s.counts[corpusID][kind])
	s.tokens[scope][key] = token
	return token
}

func (s *CaptureSanitizer) publicTokens(corpusID string) map[string]string {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make(map[string]string)
	for scope, tokens := range s.tokens {
		if !strings.HasPrefix(scope, corpusID+"\x00") {
			continue
		}
		kind := strings.TrimPrefix(scope, corpusID+"\x00")
		for _, token := range tokens {
			out[token] = kind
		}
	}
	if len(out) == 0 {
		return nil
	}
	return out
}

type QuarantineRecord struct {
	ID              string    `json:"id"`
	Path            string    `json:"path"`
	CreatedAt       time.Time `json:"created_at"`
	ExpiresAt       time.Time `json:"expires_at"`
	CiphertextBytes int       `json:"ciphertext_bytes"`
}

type FileQuarantine struct {
	dir string
	ttl time.Duration

	mu        sync.Mutex
	key       []byte
	destroyed bool
	records   map[string]QuarantineRecord
}

type quarantineEnvelope struct {
	Version    string `json:"version"`
	Nonce      string `json:"nonce"`
	Ciphertext string `json:"ciphertext"`
}

func NewFileQuarantine(dir string, ttl time.Duration) (*FileQuarantine, error) {
	if dir == "" {
		return nil, errors.New("quarantine dir is required")
	}
	if ttl <= 0 {
		return nil, errors.New("quarantine ttl must be positive")
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		return nil, err
	}
	return &FileQuarantine{
		dir:     dir,
		ttl:     ttl,
		key:     key,
		records: make(map[string]QuarantineRecord),
	}, nil
}

func (q *FileQuarantine) Put(id string, plaintext []byte, now time.Time) (QuarantineRecord, error) {
	if !safeLiteralRe.MatchString(id) {
		return QuarantineRecord{}, errors.New("quarantine id must be a safe token")
	}
	if now.IsZero() {
		now = time.Now().UTC()
	}
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.destroyed {
		return QuarantineRecord{}, errors.New("quarantine key has been destroyed")
	}
	block, err := aes.NewCipher(q.key)
	if err != nil {
		return QuarantineRecord{}, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return QuarantineRecord{}, err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := rand.Read(nonce); err != nil {
		return QuarantineRecord{}, err
	}
	ciphertext := gcm.Seal(nil, nonce, plaintext, []byte(id))
	env := quarantineEnvelope{
		Version:    quarantineEnvelopeVersionV1,
		Nonce:      base64.StdEncoding.EncodeToString(nonce),
		Ciphertext: base64.StdEncoding.EncodeToString(ciphertext),
	}
	data, err := json.Marshal(env)
	if err != nil {
		return QuarantineRecord{}, err
	}
	path := filepath.Join(q.dir, id+".qcap")
	if err := os.WriteFile(path, data, defaultQuarantineFileMode); err != nil {
		return QuarantineRecord{}, err
	}
	record := QuarantineRecord{
		ID:              id,
		Path:            path,
		CreatedAt:       now,
		ExpiresAt:       now.Add(q.ttl),
		CiphertextBytes: len(ciphertext),
	}
	q.records[id] = record
	return record, nil
}

func (q *FileQuarantine) Read(record QuarantineRecord) ([]byte, error) {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.destroyed {
		return nil, errors.New("quarantine key has been destroyed")
	}
	data, err := os.ReadFile(record.Path)
	if err != nil {
		return nil, err
	}
	var env quarantineEnvelope
	if err := json.Unmarshal(data, &env); err != nil {
		return nil, err
	}
	if env.Version != quarantineEnvelopeVersionV1 {
		return nil, errors.New("unsupported quarantine envelope version")
	}
	nonce, err := base64.StdEncoding.DecodeString(env.Nonce)
	if err != nil {
		return nil, err
	}
	ciphertext, err := base64.StdEncoding.DecodeString(env.Ciphertext)
	if err != nil {
		return nil, err
	}
	block, err := aes.NewCipher(q.key)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	return gcm.Open(nil, nonce, ciphertext, []byte(record.ID))
}

func (q *FileQuarantine) Delete(record QuarantineRecord) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	delete(q.records, record.ID)
	if err := os.Remove(record.Path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return nil
}

func (q *FileQuarantine) Janitor(now time.Time) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	var firstErr error
	for id, record := range q.records {
		if now.Before(record.ExpiresAt) {
			continue
		}
		delete(q.records, id)
		if err := os.Remove(record.Path); err != nil && !errors.Is(err, os.ErrNotExist) && firstErr == nil {
			firstErr = err
		}
	}
	return firstErr
}

func (q *FileQuarantine) Destroy() {
	q.mu.Lock()
	defer q.mu.Unlock()
	for i := range q.key {
		q.key[i] = 0
	}
	q.key = nil
	q.destroyed = true
}

type ReviewApproval struct {
	ReviewerID    string
	ProducerID    string
	ApprovedAt    time.Time
	SanitizerHash string
	PolicyHash    string
	SourceHash    string
}

type PromotableArtifact struct {
	Body          []byte
	ArtifactHash  string
	SanitizerHash string
	PolicyHash    string
	SourceHash    string
	ReviewerID    string
	ApprovedAt    time.Time
}

func BuildPromotableArtifact(capture SanitizedCapture, approval ReviewApproval) (PromotableArtifact, error) {
	if approval.ReviewerID == "" {
		return PromotableArtifact{}, errors.New("independent reviewer is required")
	}
	if approval.ProducerID != "" && approval.ReviewerID == approval.ProducerID {
		return PromotableArtifact{}, errors.New("reviewer must be independent of producer")
	}
	if approval.ApprovedAt.IsZero() {
		return PromotableArtifact{}, errors.New("approval time is required")
	}
	if approval.SanitizerHash != capture.SanitizerHash || approval.PolicyHash != capture.PolicyHash || approval.SourceHash != capture.SourceHash {
		return PromotableArtifact{}, errors.New("approval hashes do not match sanitized capture")
	}
	body, err := json.Marshal(capture)
	if err != nil {
		return PromotableArtifact{}, err
	}
	return PromotableArtifact{
		Body:          body,
		ArtifactHash:  digestBytes(body),
		SanitizerHash: capture.SanitizerHash,
		PolicyHash:    capture.PolicyHash,
		SourceHash:    capture.SourceHash,
		ReviewerID:    approval.ReviewerID,
		ApprovedAt:    approval.ApprovedAt,
	}, nil
}

func normalizeSanitizerPolicy(policy SanitizerPolicy) (SanitizerPolicy, allowedCaptureSets, error) {
	if policy.Revision == "" {
		return SanitizerPolicy{}, allowedCaptureSets{}, errors.New("policy revision is required")
	}
	if policy.SourceRevision == "" {
		return SanitizerPolicy{}, allowedCaptureSets{}, errors.New("source revision is required")
	}
	if len(policy.AllowedSchemes) == 0 || len(policy.AllowedHosts) == 0 || len(policy.AllowedPaths) == 0 {
		return SanitizerPolicy{}, allowedCaptureSets{}, errors.New("allowed schemes, hosts, and paths are required")
	}
	if policy.MaxEncodedBytes <= 0 {
		policy.MaxEncodedBytes = defaultMaxEncodedBytes
	}
	if policy.MaxDecodedBytes <= 0 {
		policy.MaxDecodedBytes = defaultMaxDecodedBytes
	}
	if policy.MaxCompressionRatio <= 0 {
		policy.MaxCompressionRatio = defaultMaxCompressionRatio
	}
	if policy.MaxDecodeDepth <= 0 {
		policy.MaxDecodeDepth = defaultMaxDecodeDepth
	}
	allowed := allowedCaptureSets{
		schemes: setOf(policy.AllowedSchemes, strings.ToLower),
		hosts:   setOf(policy.AllowedHosts, strings.ToLower),
		paths:   setOf(policy.AllowedPaths, func(v string) string { return v }),
		queries: setOf(policy.AllowedQueryKeys, strings.ToLower),
		headers: setOf(policy.AllowedHeaderNames, strings.ToLower),
	}
	sort.Strings(policy.AllowedSchemes)
	sort.Strings(policy.AllowedHosts)
	sort.Strings(policy.AllowedPaths)
	sort.Strings(policy.AllowedQueryKeys)
	sort.Strings(policy.AllowedHeaderNames)
	return policy, allowed, nil
}

func setOf(values []string, normalize func(string) string) map[string]struct{} {
	out := make(map[string]struct{}, len(values))
	for _, value := range values {
		value = normalize(strings.TrimSpace(value))
		if value != "" {
			out[value] = struct{}{}
		}
	}
	return out
}

func hashPolicy(policy SanitizerPolicy) (string, error) {
	type hashablePolicy struct {
		Revision            string   `json:"revision"`
		AllowedSchemes      []string `json:"allowed_schemes"`
		AllowedHosts        []string `json:"allowed_hosts"`
		AllowedPaths        []string `json:"allowed_paths"`
		AllowedQueryKeys    []string `json:"allowed_query_keys"`
		AllowedHeaderNames  []string `json:"allowed_header_names"`
		MaxEncodedBytes     int64    `json:"max_encoded_bytes"`
		MaxDecodedBytes     int64    `json:"max_decoded_bytes"`
		MaxCompressionRatio float64  `json:"max_compression_ratio"`
		MaxDecodeDepth      int      `json:"max_decode_depth"`
		CanaryLabels        []string `json:"canary_labels"`
	}
	labels := make([]string, 0, len(policy.CanarySecrets))
	for label := range policy.CanarySecrets {
		labels = append(labels, label)
	}
	sort.Strings(labels)
	body, err := json.Marshal(hashablePolicy{
		Revision:            policy.Revision,
		AllowedSchemes:      policy.AllowedSchemes,
		AllowedHosts:        policy.AllowedHosts,
		AllowedPaths:        policy.AllowedPaths,
		AllowedQueryKeys:    policy.AllowedQueryKeys,
		AllowedHeaderNames:  policy.AllowedHeaderNames,
		MaxEncodedBytes:     policy.MaxEncodedBytes,
		MaxDecodedBytes:     policy.MaxDecodedBytes,
		MaxCompressionRatio: policy.MaxCompressionRatio,
		MaxDecodeDepth:      policy.MaxDecodeDepth,
		CanaryLabels:        labels,
	})
	if err != nil {
		return "", err
	}
	return digestBytes(body), nil
}

func (c SanitizedCapture) assertNoRawCanaryValues(canaries map[string]string) error {
	if len(canaries) == 0 {
		return nil
	}
	body, err := json.Marshal(c)
	if err != nil {
		return err
	}
	for label, secret := range canaries {
		if secret == "" {
			continue
		}
		if encodedCanaryPresent([][]byte{body}, secret) {
			return fmt.Errorf("sanitized capture still contains canary %q", label)
		}
	}
	return nil
}

func digestString(value string) string {
	return digestBytes([]byte(value))
}

func digestBytes(value []byte) string {
	sum := sha256.Sum256(value)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func stringifyJSON(value any) string {
	body, err := json.Marshal(value)
	if err != nil {
		return fmt.Sprintf("%v", value)
	}
	return string(body)
}

func isCredentialKey(key string) bool {
	compact := strings.NewReplacer("-", "", "_", "", " ", "").Replace(strings.ToLower(key))
	return strings.Contains(compact, "credential") ||
		strings.Contains(compact, "signature") ||
		strings.Contains(compact, "authorization") ||
		strings.Contains(compact, "apikey") ||
		strings.Contains(compact, "privatekey")
}

func isFreeTextKey(key string) bool {
	compact := strings.NewReplacer("-", "", "_", "", " ", "").Replace(strings.ToLower(key))
	return strings.Contains(compact, "prompt") ||
		compact == "input" ||
		compact == "output" ||
		strings.Contains(compact, "message") ||
		strings.Contains(compact, "content") ||
		strings.Contains(compact, "text") ||
		strings.Contains(compact, "delta") ||
		strings.Contains(compact, "arguments") ||
		strings.Contains(compact, "error")
}

func shortTokenScope(corpusID string) string {
	sum := sha256.Sum256([]byte(corpusID))
	return hex.EncodeToString(sum[:])[:8]
}

func looksLikeURL(value string) bool {
	parsed, err := url.Parse(value)
	return err == nil && parsed.Scheme != "" && parsed.Host != ""
}

func looksSensitive(value string) bool {
	return bearerLikeRe.MatchString(value) || presignedURLRe.MatchString(value) || strings.Contains(value, RedactedValue) || looksHighEntropy(value)
}

func looksHighEntropy(value string) bool {
	if len(value) < 24 {
		return false
	}
	if hexLikeRe.MatchString(value) || base64LikeRe.MatchString(value) {
		return true
	}
	counts := make(map[rune]int)
	for _, r := range value {
		counts[r]++
	}
	var entropy float64
	length := float64(len([]rune(value)))
	for _, count := range counts {
		p := float64(count) / length
		entropy -= p * math.Log2(p)
	}
	return entropy >= 4.2
}

func isSafeHeaderLiteral(name, value string) bool {
	switch name {
	case "content-type", "accept":
		return !looksSensitive(value)
	default:
		return safeLiteralRe.MatchString(value) && !looksSensitive(value)
	}
}

func safeTokenKind(kind string) string {
	kind = strings.ToLower(kind)
	var b strings.Builder
	for _, r := range kind {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
			continue
		}
		if b.Len() > 0 && b.String()[b.Len()-1] != '_' {
			b.WriteByte('_')
		}
	}
	out := strings.Trim(b.String(), "_")
	if out == "" {
		return "token"
	}
	if len(out) > 48 {
		return out[:48]
	}
	return out
}
