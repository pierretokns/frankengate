package openai

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"io"
	"math"
	"net/url"
	"strconv"
	"strings"

	"github.com/maximhq/bifrost/core/schemas"
)

// These wire types follow openai-node v7.30.0 src/resources/decisions.ts.
// Decisions is a native OpenAI API, distinct from TypeSafe's state/criteria API.
// Raw messages retain scalar choice types and leave beta extensions on the wire.
type OpenAIDecisionsRequest struct {
	Model     string                   `json:"model"`
	Input     json.RawMessage          `json:"input"`
	Questions []OpenAIDecisionQuestion `json:"questions"`
}

type OpenAIDecisionQuestion struct {
	Type         string                 `json:"type"`
	Name         *string                `json:"name,omitempty"`
	Instructions *string                `json:"instructions"`
	Choices      []OpenAIDecisionChoice `json:"choices,omitempty"`
	Levels       []OpenAIDecisionLevel  `json:"levels,omitempty"`
}

type OpenAIDecisionChoice struct {
	Value       json.RawMessage `json:"value"`
	Description *string         `json:"description,omitempty"`
}

type OpenAIDecisionLevel struct {
	Label       *string `json:"label"`
	Description *string `json:"description,omitempty"`
}

type OpenAIDecisionsResponse struct {
	Model   string                          `json:"model"`
	Answers []OpenAIDecisionAnswer          `json:"answers"`
	Usage   *schemas.ResponsesResponseUsage `json:"usage"`
}

type OpenAIDecisionAnswer struct {
	Type          string                      `json:"type"`
	Name          *string                     `json:"name"`
	Probability   *float64                    `json:"probability,omitempty"`
	Choice        json.RawMessage             `json:"choice,omitempty"`
	Score         *float64                    `json:"score,omitempty"`
	Confidence    *float64                    `json:"confidence,omitempty"`
	Probabilities []OpenAIDecisionProbability `json:"probabilities,omitempty"`
}

type OpenAIDecisionProbability struct {
	Value       json.RawMessage `json:"value"`
	Label       *string         `json:"label,omitempty"`
	Probability *float64        `json:"probability"`
}

// ParseOpenAIDecisionsRequest validates the supported beta contract without
// changing the original body. Errors contain field names only, never evidence.
func ParseOpenAIDecisionsRequest(body []byte) (*OpenAIDecisionsRequest, error) {
	if err := uniqueDecisionJSON(body); err != nil {
		return nil, err
	}
	var fields map[string]json.RawMessage
	var req OpenAIDecisionsRequest
	if json.Unmarshal(body, &fields) != nil || fields == nil || !canonicalDecisionFields(fields, "model", "input", "questions", "safety_identifier", "stream") || json.Unmarshal(body, &req) != nil {
		return nil, errors.New("invalid decisions JSON request")
	}
	if _, present := fields["stream"]; present {
		return nil, errors.New("decisions does not support streaming")
	}
	if req.Model != "gpt-6-luna" {
		return nil, errors.New("decisions requires model gpt-6-luna")
	}
	if v, present := fields["safety_identifier"]; present && string(v) != "null" {
		var identifier string
		if json.Unmarshal(v, &identifier) != nil {
			return nil, errors.New("invalid decisions safety_identifier")
		}
	}
	if err := validateDecisionInput(req.Input); err != nil {
		return nil, err
	}
	if len(req.Questions) == 0 {
		return nil, errors.New("decisions questions is required")
	}
	var questionFields []map[string]json.RawMessage
	_ = json.Unmarshal(fields["questions"], &questionFields)
	names := map[string]bool{}
	for i, q := range req.Questions {
		if !canonicalDecisionFields(questionFields[i], "type", "name", "instructions", "choices", "levels") || !optionalDecisionStrings(questionFields[i], "name") {
			return nil, errors.New("invalid decisions question name")
		}
		if q.Instructions == nil {
			return nil, errors.New("decisions question instructions is required")
		}
		if q.Name != nil {
			if names[*q.Name] {
				return nil, errors.New("duplicate decisions question name")
			}
			names[*q.Name] = true
		}
		switch q.Type {
		case "predicate":
			if len(q.Choices) != 0 || len(q.Levels) != 0 {
				return nil, errors.New("invalid predicate question fields")
			}
		case "choice":
			if len(q.Choices) == 0 || len(q.Levels) != 0 {
				return nil, errors.New("decisions choice requires choices")
			}
			values := map[string]bool{}
			var choiceFields []map[string]json.RawMessage
			_ = json.Unmarshal(questionFields[i]["choices"], &choiceFields)
			for j, c := range q.Choices {
				if !canonicalDecisionFields(choiceFields[j], "value", "description") || !optionalDecisionStrings(choiceFields[j], "description") {
					return nil, errors.New("invalid decisions choice description")
				}
				key, ok := decisionChoiceKey(c.Value)
				if !ok || values[key] {
					return nil, errors.New("decisions choices must be distinct strings or booleans")
				}
				values[key] = true
			}
		case "score":
			if len(q.Levels) == 0 || len(q.Choices) != 0 {
				return nil, errors.New("decisions score requires levels")
			}
			var levelFields []map[string]json.RawMessage
			_ = json.Unmarshal(questionFields[i]["levels"], &levelFields)
			for j, l := range q.Levels {
				if !canonicalDecisionFields(levelFields[j], "label", "description") || !optionalDecisionStrings(levelFields[j], "description") {
					return nil, errors.New("invalid decisions level description")
				}
				if l.Label == nil {
					return nil, errors.New("decisions level label is required")
				}
			}
		default:
			return nil, errors.New("unsupported decisions question type")
		}
	}
	return &req, nil
}

func optionalDecisionStrings(fields map[string]json.RawMessage, keys ...string) bool {
	for _, key := range keys {
		if v, present := fields[key]; present {
			var s *string
			if json.Unmarshal(v, &s) != nil || s == nil {
				return false
			}
		}
	}
	return true
}

// encoding/json matches struct fields without case sensitivity; the wire API
// uses exact JSON names. Reject colliding spellings only in typed objects so a
// MODEL extension cannot overwrite the model seen by governance. Arbitrary
// unknown extension objects remain untouched and may use their own key names.
func canonicalDecisionFields(fields map[string]json.RawMessage, known ...string) bool {
	for field := range fields {
		for _, name := range known {
			if field != name && strings.EqualFold(field, name) {
				return false
			}
		}
	}
	return true
}

func validateDecisionInput(raw json.RawMessage) error {
	var text string
	if len(raw) != 0 && raw[0] == '"' && json.Unmarshal(raw, &text) == nil {
		return nil
	}
	var messages []struct {
		Role    string          `json:"role"`
		Type    *string         `json:"type"`
		Content json.RawMessage `json:"content"`
	}
	if json.Unmarshal(raw, &messages) != nil || len(messages) == 0 {
		return errors.New("decisions input must be text or user messages")
	}
	var messageFields []map[string]json.RawMessage
	_ = json.Unmarshal(raw, &messageFields)
	images := 0
	for i, m := range messages {
		if m.Role != "user" || !canonicalDecisionFields(messageFields[i], "role", "type", "content") || !optionalDecisionStrings(messageFields[i], "type") || (m.Type != nil && *m.Type != "message") {
			return errors.New("decisions supports only user messages")
		}
		if len(m.Content) != 0 && m.Content[0] == '"' && json.Unmarshal(m.Content, &text) == nil {
			continue
		}
		var parts []struct {
			Type     string  `json:"type"`
			Text     *string `json:"text"`
			ImageURL string  `json:"image_url"`
			Detail   *string `json:"detail"`
		}
		if json.Unmarshal(m.Content, &parts) != nil || len(parts) == 0 {
			return errors.New("invalid decisions message content")
		}
		var partFields []map[string]json.RawMessage
		_ = json.Unmarshal(m.Content, &partFields)
		for i, p := range parts {
			if !canonicalDecisionFields(partFields[i], "type", "text", "image_url", "detail") {
				return errors.New("invalid decisions input field spelling")
			}
			switch p.Type {
			case "input_text":
				if p.Text == nil {
					return errors.New("decisions input_text requires text")
				}
			case "input_image":
				images++
				if images > 128 {
					return errors.New("decisions supports at most 128 images")
				}
				header, payload, ok := strings.Cut(p.ImageURL, ",")
				if !ok || !strings.HasPrefix(header, "data:image/") || !strings.HasSuffix(header, ";base64") || payload == "" {
					return errors.New("decisions images require inline base64 data URLs")
				}
				if _, err := io.Copy(io.Discard, base64.NewDecoder(base64.StdEncoding, strings.NewReader(payload))); err != nil {
					return errors.New("invalid decisions image base64")
				}
				if p.Detail != nil && *p.Detail != "auto" && *p.Detail != "low" && *p.Detail != "high" && *p.Detail != "original" {
					return errors.New("invalid decisions image detail")
				}
			default:
				return errors.New("unsupported decisions input part")
			}
		}
	}
	return nil
}

func decisionChoiceKey(raw json.RawMessage) (string, bool) {
	var value any
	if json.Unmarshal(raw, &value) != nil {
		return "", false
	}
	switch v := value.(type) {
	case string:
		return "string:" + v, true
	case bool:
		if v {
			return "bool:true", true
		}
		return "bool:false", true
	default:
		return "", false
	}
}

// ValidateOpenAIDecisionsResponse rejects malformed success payloads. The raw
// response remains untouched, including future fields and per-question refusals.
func ValidateOpenAIDecisionsResponse(body []byte, req *OpenAIDecisionsRequest) (*OpenAIDecisionsResponse, error) {
	if req == nil {
		return nil, errors.New("decisions request is required to validate answers")
	}
	if uniqueDecisionJSON(body) != nil {
		return nil, errors.New("invalid decisions response JSON")
	}
	var fields map[string]json.RawMessage
	if json.Unmarshal(body, &fields) != nil || !canonicalDecisionFields(fields, "model", "answers", "usage") {
		return nil, errors.New("invalid decisions response field spelling")
	}
	var resp OpenAIDecisionsResponse
	if json.Unmarshal(body, &resp) != nil || resp.Model == "" || resp.Usage == nil || len(resp.Answers) != len(req.Questions) {
		return nil, errors.New("invalid decisions response envelope")
	}
	if !validDecisionUsage(body, resp.Usage) {
		return nil, errors.New("invalid decisions usage")
	}
	var envelope struct {
		Answers []map[string]json.RawMessage `json:"answers"`
	}
	_ = json.Unmarshal(body, &envelope)
	for i, a := range resp.Answers {
		q := req.Questions[i]
		if !canonicalDecisionFields(envelope.Answers[i], "type", "name", "probability", "choice", "score", "confidence", "probabilities") {
			return nil, errors.New("invalid decisions answer field spelling")
		}
		if _, present := envelope.Answers[i]["name"]; !present {
			return nil, errors.New("missing decisions answer name")
		}
		if (a.Name == nil) != (q.Name == nil) || (a.Name != nil && *a.Name != *q.Name) {
			return nil, errors.New("decisions answer name mismatch")
		}
		if a.Type == "refusal" {
			continue
		}
		if a.Type != q.Type {
			return nil, errors.New("decisions answer type mismatch")
		}
		if a.Type == "predicate" {
			if !decisionProbability(a.Probability) {
				return nil, errors.New("invalid decisions predicate probability")
			}
			continue
		}
		// The pinned SDK declares confidence as a number, without a range.
		// Do not invent probability bounds for this separate confidence field.
		if a.Confidence == nil {
			return nil, errors.New("invalid decisions confidence")
		}
		count := len(q.Choices)
		if a.Type == "score" {
			count = len(q.Levels)
		}
		if len(a.Probabilities) != count {
			return nil, errors.New("decisions distribution size mismatch")
		}
		seen := map[string]bool{}
		sum, weighted := 0.0, 0.0
		var probabilityFields []map[string]json.RawMessage
		_ = json.Unmarshal(envelope.Answers[i]["probabilities"], &probabilityFields)
		for i, p := range a.Probabilities {
			if !canonicalDecisionFields(probabilityFields[i], "value", "label", "probability") {
				return nil, errors.New("invalid decisions distribution field spelling")
			}
			if !decisionProbability(p.Probability) {
				return nil, errors.New("invalid decisions distribution probability")
			}
			sum += *p.Probability
			if a.Type == "choice" {
				key, ok := decisionChoiceKey(p.Value)
				found := false
				for _, c := range q.Choices {
					k, _ := decisionChoiceKey(c.Value)
					found = found || key == k
				}
				if !ok || !found || seen[key] {
					return nil, errors.New("invalid decisions distribution choice")
				}
				seen[key] = true
			} else {
				var ordinal *float64
				if json.Unmarshal(p.Value, &ordinal) != nil || ordinal == nil || *ordinal < 0 || *ordinal >= float64(count) || math.Trunc(*ordinal) != *ordinal {
					return nil, errors.New("invalid decisions score index")
				}
				index := int(*ordinal)
				if p.Label == nil || *p.Label != *q.Levels[index].Label {
					return nil, errors.New("invalid decisions score level")
				}
				key := strconv.Itoa(index)
				if seen[key] {
					return nil, errors.New("duplicate decisions score level")
				}
				seen[key] = true
				weighted += float64(index) * *p.Probability
			}
		}
		if math.Abs(sum-1) > 0.0001 {
			return nil, errors.New("invalid decisions probability sum")
		}
		if a.Type == "choice" {
			key, ok := decisionChoiceKey(a.Choice)
			if !ok || !seen[key] {
				return nil, errors.New("invalid decisions selected choice")
			}
		} else if a.Score == nil || math.Abs(*a.Score-weighted) > 0.0001 {
			return nil, errors.New("invalid decisions weighted score")
		}
	}
	return &resp, nil
}

func decisionProbability(v *float64) bool { return v != nil && *v >= 0 && *v <= 1 }

// Validate usage independently of answers so malformed success responses can
// still settle valid upstream usage. Missing/null/negative counters are not zero.
func validDecisionUsage(body []byte, u *schemas.ResponsesResponseUsage) bool {
	if u == nil || u.InputTokens < 0 || u.OutputTokens < 0 || u.TotalTokens < u.InputTokens || u.TotalTokens-u.InputTokens != u.OutputTokens {
		return false
	}
	var envelope struct {
		Usage map[string]json.RawMessage `json:"usage"`
	}
	if json.Unmarshal(body, &envelope) != nil {
		return false
	}
	var fields map[string]json.RawMessage
	if json.Unmarshal(body, &fields) != nil || !canonicalDecisionFields(fields, "usage") || !canonicalDecisionFields(envelope.Usage, "input_tokens", "output_tokens", "total_tokens", "input_tokens_details", "output_tokens_details") {
		return false
	}
	counters := func(fields map[string]json.RawMessage, keys ...string) bool {
		for _, key := range keys {
			var n *int
			if json.Unmarshal(fields[key], &n) != nil || n == nil || *n < 0 {
				return false
			}
		}
		return true
	}
	if !counters(envelope.Usage, "input_tokens", "output_tokens", "total_tokens") {
		return false
	}
	var input, output map[string]json.RawMessage
	if json.Unmarshal(envelope.Usage["input_tokens_details"], &input) != nil || json.Unmarshal(envelope.Usage["output_tokens_details"], &output) != nil {
		return false
	}
	return canonicalDecisionFields(input, "cached_tokens", "cache_write_tokens") && canonicalDecisionFields(output, "reasoning_tokens") && counters(input, "cached_tokens", "cache_write_tokens") && counters(output, "reasoning_tokens")
}

// DecisionsGatewayError has no evidence, raw body, or retriable fallback path.
func DecisionsGatewayError(message string, status int) *schemas.BifrostError {
	return &schemas.BifrostError{
		IsBifrostError: true, StatusCode: &status, AllowFallbacks: schemas.Ptr(false),
		Error:       &schemas.ErrorField{Message: message},
		ExtraFields: schemas.BifrostErrorExtraFields{Provider: schemas.OpenAI, RequestType: schemas.PassthroughRequest},
	}
}

// Reject duplicate keys so governance and the provider cannot parse different
// model/input values from the same body. Do not expose parser error text.
func uniqueDecisionJSON(body []byte) error {
	d := json.NewDecoder(bytes.NewReader(body))
	d.UseNumber()
	var walk func(int) error
	walk = func(depth int) error {
		if depth > 10000 {
			return errors.New("JSON nesting exceeds decoder limit")
		}
		t, err := d.Token()
		if err != nil {
			return err
		}
		if delim, ok := t.(json.Delim); ok {
			keys := map[string]bool{}
			for d.More() {
				if delim == '{' {
					k, err := d.Token()
					if err != nil {
						return err
					}
					key, ok := k.(string)
					if !ok || keys[key] {
						return errors.New("duplicate JSON field")
					}
					keys[key] = true
				}
				if err := walk(depth + 1); err != nil {
					return err
				}
			}
			_, err = d.Token()
			return err
		}
		return nil
	}
	if walk(0) != nil {
		return errors.New("invalid or duplicate decisions JSON fields")
	}
	if _, err := d.Token(); err != io.EOF {
		return errors.New("invalid decisions JSON trailing data")
	}
	return nil
}

func isOpenAIDecisionsRegionalURL(rawURL string) bool {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return false
	}
	host := strings.ToLower(parsed.Hostname())
	return host == "us.api.openai.com" || host == "eu.api.openai.com"
}
