package a2adiscovery

import (
	"encoding/json"
	"errors"
	"fmt"
	"mime"
	"net/url"
	"strings"
)

// ProxyRequestKind describes the two A2A request classes that an edge proxy
// needs to understand. FrankenGate's hosted-agent handler owns task
// semantics; these helpers are deliberately transport-neutral so a future
// transparent proxy can preserve upstream envelopes while still providing
// Agentgateway-compatible routing and telemetry.
type ProxyRequestKind string

const (
	ProxyRequestUnknown   ProxyRequestKind = "unknown"
	ProxyRequestAgentCard ProxyRequestKind = "agent_card"
	ProxyRequestCall      ProxyRequestKind = "call"
	ProxyResponseSuccess  string           = "success"
	ProxyResponseError    string           = "error"
	ProxyResponseUnknown  string           = "unknown"
	defaultProxyBodyLimit                  = DefaultMaxResponseBytes
)

// ProxyRequestClassification is the non-mutating result of classifying an
// inbound request. Body is never returned or retained: callers remain the
// owner of the request body and can forward it unchanged.
type ProxyRequestClassification struct {
	Kind         ProxyRequestKind
	Method       string
	AgentCardURL string
}

// ClassifyProxyRequest mirrors Agentgateway's A2A request classification:
// well-known card GETs are card requests, JSON POSTs expose their JSON-RPC
// method, and malformed or unsupported requests remain observable as unknown.
// originalURL is used for rewritten gateway requests; forwardedProto, when
// present, replaces the URL scheme for the card URL returned to the upstream.
func ClassifyProxyRequest(httpMethod, requestPath, contentType string, body []byte, originalURL, forwardedProto string) ProxyRequestClassification {
	if strings.EqualFold(httpMethod, "GET") && (strings.HasSuffix(requestPath, LegacyAgentCardPath) || strings.HasSuffix(requestPath, WellKnownAgentCardPath)) {
		cardURL := originalURL
		if cardURL == "" {
			cardURL = requestPath
		}
		if forwardedProto != "" {
			if parsed, err := url.Parse(cardURL); err == nil && parsed.Scheme != "" {
				parsed.Scheme = forwardedProto
				cardURL = parsed.String()
			}
		}
		return ProxyRequestClassification{Kind: ProxyRequestAgentCard, AgentCardURL: cardURL}
	}
	if strings.EqualFold(httpMethod, "POST") {
		method := "unknown"
		if isJSONMediaType(contentType) {
			var envelope struct {
				Method string `json:"method"`
			}
			if json.Unmarshal(body, &envelope) == nil && envelope.Method != "" {
				method = envelope.Method
			}
		}
		return ProxyRequestClassification{Kind: ProxyRequestCall, Method: method}
	}
	return ProxyRequestClassification{Kind: ProxyRequestUnknown}
}

// BuildGatewayAgentPath strips the well-known card suffix and preserves the
// origin, any deployment prefix, and query string. This is the URL base that
// a transparent proxy advertises in a rewritten Agent Card.
func BuildGatewayAgentPath(rawURL string) (string, error) {
	parsed, err := url.Parse(rawURL)
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		if err == nil {
			err = errors.New("URL must be absolute")
		}
		return "", fmt.Errorf("build A2A gateway path: %w", err)
	}
	if strings.HasSuffix(parsed.Path, LegacyAgentCardPath) {
		parsed.Path = strings.TrimSuffix(parsed.Path, LegacyAgentCardPath)
	} else if strings.HasSuffix(parsed.Path, WellKnownAgentCardPath) {
		parsed.Path = strings.TrimSuffix(parsed.Path, WellKnownAgentCardPath)
	}
	parsed.RawPath = ""
	return parsed.String(), nil
}

// RewriteAgentCardForGateway applies Agentgateway's transparent-proxy card
// rewrite rules. v1 cards rewrite every interface URL's path/query; legacy
// cards rewrite the top-level URL. The returned bytes are newly marshaled and
// the input is never modified.
func RewriteAgentCardForGateway(body []byte, gatewayBase string, maxBytes int) ([]byte, error) {
	if maxBytes <= 0 {
		maxBytes = defaultProxyBodyLimit
	}
	if len(body) > maxBytes {
		return nil, fmt.Errorf("A2A agent card exceeds %d bytes", maxBytes)
	}
	base, err := url.Parse(gatewayBase)
	if err != nil || base.Scheme == "" || base.Host == "" {
		if err == nil {
			err = errors.New("gateway base must be an absolute URL")
		}
		return nil, fmt.Errorf("rewrite A2A agent card: %w", err)
	}
	var card map[string]any
	if err := json.Unmarshal(body, &card); err != nil {
		return nil, fmt.Errorf("decode A2A agent card: %w", err)
	}
	if rawInterfaces, exists := card["supportedInterfaces"]; exists {
		interfaces, ok := rawInterfaces.([]any)
		if !ok {
			return nil, errors.New("A2A agent card supportedInterfaces is not an array")
		}
		for _, rawInterface := range interfaces {
			iface, ok := rawInterface.(map[string]any)
			if !ok {
				continue
			}
			rawURL, ok := iface["url"].(string)
			if !ok || rawURL == "" {
				continue
			}
			interfaceURL, err := url.Parse(rawURL)
			if err != nil {
				continue
			}
			pathAndQuery := interfaceURL.EscapedPath()
			if pathAndQuery == "" {
				pathAndQuery = "/"
			}
			if interfaceURL.RawQuery != "" {
				pathAndQuery += "?" + interfaceURL.RawQuery
			}
			iface["url"] = strings.TrimRight(gatewayBase, "/") + "/" + strings.TrimLeft(pathAndQuery, "/")
		}
	} else if _, exists := card["url"]; exists {
		card["url"] = gatewayBase
	} else {
		return nil, errors.New("A2A agent card missing URL (no 'url' or 'supportedInterfaces' field)")
	}
	return json.Marshal(card)
}

// ProxyResponseInfo is the bounded telemetry projection of an A2A JSON
// response. It intentionally does not expose or mutate the response body.
type ProxyResponseInfo struct {
	Outcome    string
	ErrorCode  *int64
	ResultKind string
	TaskState  string
}

// InspectA2AJSONResponse mirrors Agentgateway's response inspection. A false
// return means that telemetry must be omitted, for example for non-JSON,
// malformed, partial, or over-limit bodies. The proxy must still forward the
// original bytes unchanged.
func InspectA2AJSONResponse(body []byte, contentType string, complete bool, maxBytes int) (ProxyResponseInfo, bool) {
	if !complete || !isJSONMediaType(contentType) {
		return ProxyResponseInfo{}, false
	}
	if maxBytes <= 0 {
		maxBytes = defaultProxyBodyLimit
	}
	if len(body) > maxBytes {
		return ProxyResponseInfo{}, false
	}
	var envelope map[string]any
	if json.Unmarshal(body, &envelope) != nil {
		return ProxyResponseInfo{}, false
	}
	info := ProxyResponseInfo{Outcome: ProxyResponseUnknown}
	if rawError, ok := envelope["error"]; ok && rawError != nil {
		info.Outcome = ProxyResponseError
		if errorObject, ok := rawError.(map[string]any); ok {
			if number, ok := errorObject["code"].(float64); ok {
				code := int64(number)
				info.ErrorCode = &code
			}
		}
	} else if rawResult, ok := envelope["result"]; ok && rawResult != nil {
		info.Outcome = ProxyResponseSuccess
		if resultObject, ok := rawResult.(map[string]any); ok {
			info.ResultKind, _ = resultObject["kind"].(string)
			if status, ok := resultObject["status"].(map[string]any); ok {
				info.TaskState, _ = status["state"].(string)
			}
		}
	}
	return info, true
}

func isJSONMediaType(raw string) bool {
	mediaType, _, err := mime.ParseMediaType(raw)
	if err != nil {
		mediaType = strings.TrimSpace(strings.SplitN(raw, ";", 2)[0])
	}
	mediaType = strings.ToLower(mediaType)
	return mediaType == "application/json" || mediaType == "application/a2a+json" || mediaType == "application/agent-card+json"
}
