package integrations

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"regexp"

	"github.com/valyala/fasthttp"
)

var sealedIntegrationRunID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)
var sealedIntegrationMarker = regexp.MustCompile(`SEALED_CODEX_RUN_ID:([A-Za-z0-9][A-Za-z0-9._-]{0,127})`)

// WrapSealedCodexIngressObserver wraps the final HTTP server handler only in the
// sealed lab. The disabled path returns next unchanged, so production requests
// have no observer branch.
func WrapSealedCodexIngressObserver(next fasthttp.RequestHandler) fasthttp.RequestHandler {
	return wrapSealedCodexIngressObserverWithWriter(next, os.Stdout)
}

// SealedCodexHeaderReceivedObserver records only run-bound predicate metadata
// after fasthttp has parsed the request header but before it reads the body.
// It is nil outside the sealed lab.
func SealedCodexHeaderReceivedObserver() func(*fasthttp.RequestHeader) fasthttp.RequestConfig {
	return sealedCodexHeaderReceivedObserverWithWriter(os.Stdout)
}

func sealedCodexHeaderReceivedObserverWithWriter(output io.Writer) func(*fasthttp.RequestHeader) fasthttp.RequestConfig {
	if os.Getenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER") != "1" {
		return nil
	}
	runID := os.Getenv("LAB_RUN_ID")
	if !sealedIntegrationRunID.MatchString(runID) {
		panic("BIFROST_SEALED_LAB_INGRESS_OBSERVER requires a valid LAB_RUN_ID")
	}
	return func(header *fasthttp.RequestHeader) fasthttp.RequestConfig {
		if string(header.Peek("x-sealed-codex-run-id")) != runID {
			return fasthttp.RequestConfig{}
		}
		contentEncoding := header.ContentEncoding()
		record, _ := json.Marshal(struct {
			Schema               string `json:"schema"`
			RunID                string `json:"run_id"`
			MethodPost           bool   `json:"method_post"`
			TargetExact          bool   `json:"target_exact"`
			ContentTypeJSON      bool   `json:"content_type_json"`
			ContentEncodingNone  bool   `json:"content_encoding_none"`
			ContentLengthBounded bool   `json:"content_length_bounded"`
			LiteHeaderOK         bool   `json:"lite_header_ok"`
		}{
			Schema:               "sealed-codex-bifrost-header/v1",
			RunID:                runID,
			MethodPost:           string(header.Method()) == fasthttp.MethodPost,
			TargetExact:          string(header.RequestURI()) == "/openai/v1/responses",
			ContentTypeJSON:      bytes.Equal(header.ContentType(), []byte("application/json")),
			ContentEncodingNone:  len(contentEncoding) == 0,
			ContentLengthBounded: header.ContentLength() > 0 && header.ContentLength() <= 1<<20,
			LiteHeaderOK:         string(header.Peek("x-openai-internal-codex-responses-lite")) == "true",
		})
		_, _ = fmt.Fprintln(output, string(record))
		return fasthttp.RequestConfig{}
	}
}

// SealedCodexParseErrorObserver preserves fasthttp's default error response and
// emits only an allowlisted parser failure class in the sealed lab.
func SealedCodexParseErrorObserver() func(*fasthttp.RequestCtx, error) {
	return sealedCodexParseErrorObserverWithWriter(os.Stdout)
}

func sealedCodexParseErrorObserverWithWriter(output io.Writer) func(*fasthttp.RequestCtx, error) {
	if os.Getenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER") != "1" {
		return nil
	}
	runID := os.Getenv("LAB_RUN_ID")
	if !sealedIntegrationRunID.MatchString(runID) {
		panic("BIFROST_SEALED_LAB_INGRESS_OBSERVER requires a valid LAB_RUN_ID")
	}
	return func(ctx *fasthttp.RequestCtx, err error) {
		class := "other"
		status, message := fasthttp.StatusBadRequest, "Error when parsing request"
		switch {
		case func() bool { _, ok := err.(*fasthttp.ErrSmallBuffer); return ok }():
			class, status, message = "header_too_large", fasthttp.StatusRequestHeaderFieldsTooLarge, "Too big request header"
		case errors.Is(err, fasthttp.ErrBodyTooLarge):
			class = "body_too_large"
		case func() bool { netError, ok := err.(*net.OpError); return ok && netError.Timeout() }():
			class, status, message = "timeout", fasthttp.StatusRequestTimeout, "Request timeout"
		case errors.Is(err, io.ErrUnexpectedEOF):
			class = "unexpected_eof"
		case errors.Is(err, io.EOF):
			class = "eof"
		}
		if string(ctx.Request.Header.Peek("x-sealed-codex-run-id")) == runID {
			record, _ := json.Marshal(struct {
				Schema      string `json:"schema"`
				RunID       string `json:"run_id"`
				Class       string `json:"class"`
				MethodPost  bool   `json:"method_post"`
				TargetExact bool   `json:"target_exact"`
			}{Schema: "sealed-codex-bifrost-parse-error/v1", RunID: runID, Class: class, MethodPost: string(ctx.Method()) == fasthttp.MethodPost, TargetExact: string(ctx.RequestURI()) == "/openai/v1/responses"})
			_, _ = fmt.Fprintln(output, string(record))
		}
		ctx.Error(message, status)
	}
}

func wrapSealedCodexIngressObserverWithWriter(next fasthttp.RequestHandler, output io.Writer) fasthttp.RequestHandler {
	if os.Getenv("BIFROST_SEALED_LAB_INGRESS_OBSERVER") != "1" {
		return next
	}
	runID := os.Getenv("LAB_RUN_ID")
	if !sealedIntegrationRunID.MatchString(runID) {
		panic("BIFROST_SEALED_LAB_INGRESS_OBSERVER requires a valid LAB_RUN_ID")
	}
	return func(ctx *fasthttp.RequestCtx) {
		uri := ctx.Request.URI()
		methodPost := string(ctx.Method()) == fasthttp.MethodPost
		pathExact := string(uri.PathOriginal()) == "/openai/v1/responses"
		queryEmpty := len(uri.QueryString()) == 0
		if sealedCodexRequestCarriesRunMarker(ctx.PostBody(), runID) {
			record, _ := json.Marshal(struct {
				Schema     string `json:"schema"`
				RunID      string `json:"run_id"`
				MethodPost bool   `json:"method_post"`
				PathExact  bool   `json:"path_exact"`
				QueryEmpty bool   `json:"query_empty"`
			}{Schema: "sealed-codex-bifrost-arrival/v1", RunID: runID, MethodPost: methodPost, PathExact: pathExact, QueryEmpty: queryEmpty})
			_, _ = fmt.Fprintln(output, string(record))
		}
		if methodPost && pathExact && queryEmpty {
			observeSealedCodexIntegrationIngress(ctx, runID, output)
		}
		next(ctx)
	}
}

func sealedCodexRequestCarriesRunMarker(body []byte, runID string) bool {
	if len(body) == 0 || len(body) > 1<<20 || rejectSealedDuplicateKeys(body) != nil {
		return false
	}
	var request struct {
		Input []struct {
			Type    string          `json:"type"`
			Role    string          `json:"role"`
			Content json.RawMessage `json:"content"`
		} `json:"input"`
	}
	if json.Unmarshal(body, &request) != nil {
		return false
	}
	matches := make([][][]byte, 0, 2)
	for _, item := range request.Input {
		if item.Type != "message" || item.Role != "user" || len(item.Content) == 0 {
			continue
		}
		itemMatches, ok := sealedSemanticUserMarkers(item.Content, 2-len(matches))
		if !ok {
			return false
		}
		matches = append(matches, itemMatches...)
		if len(matches) == 2 {
			break
		}
	}
	return len(matches) == 1 && string(matches[0][1]) == runID
}

func observeSealedCodexIntegrationIngress(ctx *fasthttp.RequestCtx, runID string, output io.Writer) {
	diagnostic := map[string]any{
		"schema": "sealed-codex-bifrost-ingress-rejected/v1", "run_id": runID,
		"body_bounded": false, "json_unique": false, "json_decoded": false,
		"method_ok": false, "model_ok": false, "stream_ok": false,
		"lite_header_ok": false, "no_websocket_upgrade": false,
		"instructions_absent": false, "top_level_tools_absent": false,
		"parallel_false_present": false, "input_present": false,
		"first_input_type_ok": false, "first_input_role_ok": false,
		"tool_count_ok": false, "tool_shapes_ok": false,
		"tool_types": []string{}, "invalid_tool_indices": []int{},
		"input_run_id_count": 0, "input_run_id_matches": false,
	}
	reject := func(reason string) {
		diagnostic["reason"] = reason
		if encoded, err := json.Marshal(diagnostic); err == nil && len(encoded) <= 8<<10 {
			_, _ = fmt.Fprintln(output, string(encoded))
		}
	}
	body := ctx.PostBody()
	if len(body) == 0 || len(body) > 1<<20 {
		reject("body_out_of_bounds")
		return
	}
	diagnostic["body_bounded"] = true
	if rejectSealedDuplicateKeys(body) != nil {
		reject("invalid_or_duplicate_json")
		return
	}
	diagnostic["json_unique"] = true
	var request struct {
		Model        string          `json:"model"`
		Stream       bool            `json:"stream"`
		Instructions json.RawMessage `json:"instructions"`
		Tools        json.RawMessage `json:"tools"`
		Parallel     *bool           `json:"parallel_tool_calls"`
		Input        []struct {
			Type    string            `json:"type"`
			Role    string            `json:"role"`
			Tools   []json.RawMessage `json:"tools"`
			Content json.RawMessage   `json:"content"`
		} `json:"input"`
	}
	if json.Unmarshal(body, &request) != nil {
		reject("json_shape_decode_failed")
		return
	}
	diagnostic["json_decoded"] = true
	liteHeaders := ctx.Request.Header.PeekAll("x-openai-internal-codex-responses-lite")
	headerCount, headerValue := len(liteHeaders), ""
	if headerCount == 1 {
		headerValue = string(liteHeaders[0])
	}
	diagnostic["method_ok"] = string(ctx.Method()) == fasthttp.MethodPost
	diagnostic["model_ok"] = request.Model == "bedrock_mantle/gpt-5.5"
	diagnostic["stream_ok"] = request.Stream
	diagnostic["lite_header_ok"] = headerCount == 1 && headerValue == "true"
	diagnostic["no_websocket_upgrade"] = len(ctx.Request.Header.PeekAll("Upgrade")) == 0
	diagnostic["instructions_absent"] = len(request.Instructions) == 0
	diagnostic["top_level_tools_absent"] = len(request.Tools) == 0
	diagnostic["parallel_false_present"] = request.Parallel != nil && !*request.Parallel
	diagnostic["input_present"] = len(request.Input) > 0
	diagnostic["first_input_type_ok"] = len(request.Input) > 0 && request.Input[0].Type == "additional_tools"
	diagnostic["first_input_role_ok"] = len(request.Input) > 0 && request.Input[0].Role == "developer"
	toolsValid := len(request.Input) > 0 && len(request.Input[0].Tools) > 0 && len(request.Input[0].Tools) <= 128
	diagnostic["tool_count_ok"] = toolsValid
	toolTypes := []string{}
	invalid := []int{}
	if len(request.Input) > 0 {
		for index, tool := range request.Input[0].Tools {
			var shape struct {
				Type              string          `json:"type"`
				Name              string          `json:"name"`
				Execution         string          `json:"execution"`
				Description       string          `json:"description"`
				Parameters        json.RawMessage `json:"parameters"`
				Tools             json.RawMessage `json:"tools"`
				ExternalWebAccess *bool           `json:"external_web_access"`
				IndexedWebAccess  *bool           `json:"indexed_web_access"`
			}
			shapeOK := len(tool) > 0 && len(tool) <= 64<<10 && json.Unmarshal(tool, &shape) == nil
			if sealedIntegrationToolType(shape.Type) {
				toolTypes = append(toolTypes, shape.Type)
			}
			switch shape.Type {
			case "custom":
				shapeOK = shapeOK && shape.Name != ""
			case "function":
				shapeOK = shapeOK && shape.Name != "" && len(shape.Parameters) > 0
			case "namespace":
				shapeOK = shapeOK && shape.Name != "" && len(shape.Tools) > 0
			case "tool_search":
				var parameters struct {
					Type string `json:"type"`
				}
				trimmed := bytes.TrimSpace(shape.Parameters)
				object := len(trimmed) >= 2 && trimmed[0] == '{' && trimmed[len(trimmed)-1] == '}' && json.Unmarshal(trimmed, &parameters) == nil && parameters.Type == "object"
				shapeOK = shapeOK && shape.Execution == "client" && shape.Description != "" && object
			case "web_search":
				shapeOK = shapeOK && shape.ExternalWebAccess != nil && (shape.IndexedWebAccess == nil || (*shape.ExternalWebAccess && *shape.IndexedWebAccess))
			default:
				shapeOK = false
			}
			if !shapeOK {
				toolsValid = false
				if len(invalid) < 16 {
					invalid = append(invalid, index)
				}
			}
		}
	}
	diagnostic["tool_types"] = toolTypes
	diagnostic["invalid_tool_indices"] = invalid
	diagnostic["tool_shapes_ok"] = toolsValid
	matches := make([][][]byte, 0)
	contentValid := true
	for _, item := range request.Input {
		if item.Type == "message" && item.Role == "user" && len(item.Content) > 0 {
			itemMatches, ok := sealedSemanticUserMarkers(item.Content, 3-len(matches))
			if !ok {
				contentValid = false
				break
			}
			matches = append(matches, itemMatches...)
			if len(matches) == 3 {
				break
			}
		}
	}
	markerCount := len(matches)
	if markerCount > 2 {
		markerCount = 2
	}
	diagnostic["input_run_id_count"] = markerCount
	markerMatches := contentValid && len(matches) == 1 && string(matches[0][1]) == runID
	diagnostic["input_run_id_matches"] = markerMatches
	valid := diagnostic["method_ok"] == true && diagnostic["model_ok"] == true && diagnostic["stream_ok"] == true && diagnostic["lite_header_ok"] == true && diagnostic["no_websocket_upgrade"] == true && diagnostic["instructions_absent"] == true && diagnostic["top_level_tools_absent"] == true && diagnostic["parallel_false_present"] == true && diagnostic["first_input_type_ok"] == true && diagnostic["first_input_role_ok"] == true && toolsValid && markerMatches
	if !valid {
		reject("lite_predicate_mismatch")
		return
	}
	sum := sha256.Sum256(body)
	record := map[string]any{"schema": "sealed-codex-bifrost-ingress/v1", "run_id": runID, "input_run_id": runID, "method": "POST", "path": "/openai/v1/responses", "model": request.Model, "stream": true, "lite_header_count": headerCount, "lite_header_value": headerValue, "websocket_upgrade": false, "top_level_instructions": false, "top_level_tools": false, "parallel_tool_calls": false, "first_input_type": "additional_tools", "first_input_role": "developer", "first_input_tool_count": len(request.Input[0].Tools), "body_bytes": len(body), "body_sha256": fmt.Sprintf("%x", sum)}
	encoded, _ := json.Marshal(record)
	_, _ = fmt.Fprintln(output, string(encoded))
}

func sealedSemanticUserMarkers(content json.RawMessage, limit int) ([][][]byte, bool) {
	if limit <= 0 {
		return nil, true
	}
	var text string
	if json.Unmarshal(content, &text) == nil {
		return sealedIntegrationMarker.FindAllSubmatch([]byte(text), limit), true
	}
	var items []map[string]json.RawMessage
	if json.Unmarshal(content, &items) != nil || len(items) == 0 {
		return nil, false
	}
	matches := make([][][]byte, 0)
	for _, item := range items {
		if len(item) != 2 {
			return nil, false
		}
		var itemType, itemText string
		if json.Unmarshal(item["type"], &itemType) != nil || itemType != "input_text" || json.Unmarshal(item["text"], &itemText) != nil {
			return nil, false
		}
		matches = append(matches, sealedIntegrationMarker.FindAllSubmatch([]byte(itemText), limit-len(matches))...)
		if len(matches) == limit {
			break
		}
	}
	return matches, true
}

func sealedIntegrationToolType(value string) bool {
	switch value {
	case "custom", "function", "namespace", "tool_search", "web_search":
		return true
	default:
		return false
	}
}

func rejectSealedDuplicateKeys(body []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(body))
	var parse func() error
	parse = func() error {
		token, err := decoder.Token()
		if err != nil {
			return err
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
				if !ok || seen[key] {
					return fmt.Errorf("invalid or duplicate JSON object key")
				}
				seen[key] = true
				if err := parse(); err != nil {
					return err
				}
			}
			_, err = decoder.Token()
			return err
		case '[':
			for decoder.More() {
				if err := parse(); err != nil {
					return err
				}
			}
			_, err = decoder.Token()
			return err
		default:
			return fmt.Errorf("invalid JSON delimiter")
		}
	}
	if err := parse(); err != nil {
		return err
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		return fmt.Errorf("JSON must contain exactly one value")
	}
	return nil
}
