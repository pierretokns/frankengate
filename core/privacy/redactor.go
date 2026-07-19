package privacy

import (
	"encoding/json"
	"regexp"
	"strings"
)

const RedactedValue = "[REDACTED]"

var (
	emailPattern = regexp.MustCompile(`(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b`)
	phonePattern = regexp.MustCompile(`\+?\d[\d(). -]{7,}\d`)
)

// RedactText replaces common direct identifiers in free text. It is a small
// deterministic guard, not a substitute for a model-backed detector; callers
// should record detector status separately when stronger coverage is required.
func RedactText(text string) string {
	text = emailPattern.ReplaceAllString(text, RedactedValue)
	return phonePattern.ReplaceAllString(text, RedactedValue)
}

// RedactHeaders returns a copy safe for traces, audit records, and metrics.
// Identity/attribution headers are intentionally preserved; credential-bearing
// headers are replaced regardless of casing or spelling convention.
func RedactHeaders(headers map[string][]string) map[string][]string {
	if headers == nil {
		return nil
	}
	out := make(map[string][]string, len(headers))
	for name, values := range headers {
		if isSensitiveName(name) {
			out[name] = []string{RedactedValue}
			continue
		}
		out[name] = append([]string(nil), values...)
	}
	return out
}

// RedactJSON removes credential-bearing fields from an arbitrary JSON object
// while retaining its shape. Invalid JSON is returned unchanged with ok=false
// so callers can fail closed instead of accidentally logging a partial parse.
func RedactJSON(payload []byte) (redacted []byte, ok bool) {
	var value any
	if err := json.Unmarshal(payload, &value); err != nil {
		return append([]byte(nil), payload...), false
	}
	value = redactJSONValue(value)
	redacted, err := json.Marshal(value)
	if err != nil {
		return append([]byte(nil), payload...), false
	}
	return redacted, true
}

func redactJSONValue(value any) any {
	switch node := value.(type) {
	case map[string]any:
		for key, child := range node {
			if isSensitiveName(key) {
				node[key] = RedactedValue
				continue
			}
			node[key] = redactJSONValue(child)
		}
		return node
	case []any:
		for i, child := range node {
			node[i] = redactJSONValue(child)
		}
		return node
	case string:
		return RedactText(node)
	}
	return value
}

func isSensitiveName(name string) bool {
	compact := strings.NewReplacer("-", "", "_", "", " ", "").Replace(strings.ToLower(name))
	if compact == "authorization" || compact == "cookie" || compact == "setcookie" || compact == "xapikey" || compact == "apikey" || compact == "accesstoken" || compact == "refreshtoken" || compact == "clientsecret" || compact == "virtualkey" || compact == "xbf"+"vk" || compact == "vksecret" {
		return true
	}
	return strings.Contains(compact, "secret") || strings.Contains(compact, "password") || strings.Contains(compact, "token") && !strings.Contains(compact, "tokenusage")
}
