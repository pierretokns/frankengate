package trust

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"

	"github.com/maximhq/bifrost/framework/modelcatalog/agentcard"
)

// canonicalizeJSON implements the package's versioned JCS-style subset:
// objects are sorted by UTF-8 key bytes, arrays preserve order, insignificant
// whitespace is removed, strings use encoding/json escaping, and numbers must
// already be finite base-10 JSON integers or decimals without exponent syntax.
// This is intentionally narrower than RFC 8785 JCS; full JCS number and UTF-16
// key ordering are a follow-up before accepting arbitrary publisher JSON.
func canonicalizeJSON(data []byte) ([]byte, error) {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()

	var value any
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return nil, fmt.Errorf("multiple JSON values are not allowed")
		}
		return nil, err
	}

	var out bytes.Buffer
	if err := writeCanonicalJSON(&out, value); err != nil {
		return nil, err
	}
	return out.Bytes(), nil
}

func canonicalCardPayload(card agentcard.AgentModelCard) ([]byte, error) {
	card.Signatures = nil
	data, err := json.Marshal(card)
	if err != nil {
		return nil, err
	}
	return canonicalizeJSON(data)
}

func decodeCanonicalCardPayload(payload []byte) (agentcard.AgentModelCard, []byte, error) {
	var card agentcard.AgentModelCard
	if err := json.Unmarshal(payload, &card); err != nil {
		return agentcard.AgentModelCard{}, nil, err
	}
	if len(card.Signatures) > 0 {
		return agentcard.AgentModelCard{}, nil, fmt.Errorf("embedded signatures are not part of the envelope payload contract")
	}
	canonical, err := canonicalCardPayload(card)
	if err != nil {
		return agentcard.AgentModelCard{}, nil, err
	}
	if !bytes.Equal(canonical, payload) {
		return agentcard.AgentModelCard{}, nil, fmt.Errorf("payload is not %s canonical JSON", CanonicalizationSubsetV1)
	}
	if err := card.Validate(); err != nil {
		return agentcard.AgentModelCard{}, nil, err
	}
	return card, canonical, nil
}

func writeCanonicalJSON(out *bytes.Buffer, value any) error {
	switch v := value.(type) {
	case nil:
		out.WriteString("null")
	case bool:
		if v {
			out.WriteString("true")
		} else {
			out.WriteString("false")
		}
	case string:
		encoded, err := json.Marshal(v)
		if err != nil {
			return err
		}
		out.Write(encoded)
	case json.Number:
		number, err := canonicalNumber(v.String())
		if err != nil {
			return err
		}
		out.WriteString(number)
	case []any:
		out.WriteByte('[')
		for i, item := range v {
			if i > 0 {
				out.WriteByte(',')
			}
			if err := writeCanonicalJSON(out, item); err != nil {
				return err
			}
		}
		out.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(v))
		for key := range v {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		out.WriteByte('{')
		for i, key := range keys {
			if i > 0 {
				out.WriteByte(',')
			}
			encodedKey, err := json.Marshal(key)
			if err != nil {
				return err
			}
			out.Write(encodedKey)
			out.WriteByte(':')
			if err := writeCanonicalJSON(out, v[key]); err != nil {
				return err
			}
		}
		out.WriteByte('}')
	default:
		return fmt.Errorf("unsupported JSON value %T", value)
	}
	return nil
}

func canonicalNumber(value string) (string, error) {
	if value == "" {
		return "", fmt.Errorf("empty JSON number")
	}
	if strings.ContainsAny(value, "eE+") {
		return "", fmt.Errorf("number %q is outside %s", value, CanonicalizationSubsetV1)
	}
	if value == "-0" {
		return "", fmt.Errorf("negative zero is outside %s", CanonicalizationSubsetV1)
	}

	negative := strings.HasPrefix(value, "-")
	unsigned := value
	if negative {
		unsigned = strings.TrimPrefix(value, "-")
		if unsigned == "" {
			return "", fmt.Errorf("invalid JSON number %q", value)
		}
	}

	integer, fraction, hasFraction := strings.Cut(unsigned, ".")
	if integer == "" {
		return "", fmt.Errorf("invalid JSON number %q", value)
	}
	if len(integer) > 1 && strings.HasPrefix(integer, "0") {
		return "", fmt.Errorf("number %q has a leading zero", value)
	}
	for _, r := range integer {
		if r < '0' || r > '9' {
			return "", fmt.Errorf("invalid JSON number %q", value)
		}
	}
	if !hasFraction {
		return value, nil
	}
	if fraction == "" {
		return "", fmt.Errorf("invalid JSON number %q", value)
	}
	if strings.HasSuffix(fraction, "0") {
		return "", fmt.Errorf("number %q has non-canonical trailing fractional zeroes", value)
	}
	for _, r := range fraction {
		if r < '0' || r > '9' {
			return "", fmt.Errorf("invalid JSON number %q", value)
		}
	}
	return value, nil
}
