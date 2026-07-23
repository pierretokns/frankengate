package contractfixture

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"regexp"
	"sort"
	"strings"
)

const maxJSONBytes = 1 << 20

var digestPattern = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)

func decodeStrict(data []byte, dst interface{}, label string) error {
	if len(data) > maxJSONBytes {
		return fmt.Errorf("%s exceeds 1 MiB", label)
	}
	if err := rejectDuplicateJSONKeys(data); err != nil {
		return fmt.Errorf("%s: %w", label, err)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(dst); err != nil {
		return fmt.Errorf("decode %s: %w", label, err)
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return fmt.Errorf("%s contains trailing JSON", label)
	}
	return nil
}

func rejectDuplicateJSONKeys(data []byte) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	var walk func() error
	walk = func() error {
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
			_, err := decoder.Token()
			return err
		case '[':
			for decoder.More() {
				if err := walk(); err != nil {
					return err
				}
			}
			_, err := decoder.Token()
			return err
		default:
			return fmt.Errorf("unexpected JSON delimiter %q", delim)
		}
	}
	if err := walk(); err != nil {
		return err
	}
	if _, err := decoder.Token(); err != io.EOF {
		return fmt.Errorf("trailing JSON")
	}
	return nil
}

func canonicalJSON(value interface{}) ([]byte, error) {
	var buf bytes.Buffer
	encoder := json.NewEncoder(&buf)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(buf.Bytes(), []byte{'\n'}), nil
}

func digestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return fmt.Sprintf("sha256:%x", sum[:])
}

func digestValue(value interface{}) (string, error) {
	data, err := canonicalJSON(value)
	if err != nil {
		return "", err
	}
	return digestBytes(data), nil
}

func digestAssertion(sourceID string, assertion DerivedAssertion) string {
	data := strings.Join([]string{sourceID, assertion.ID, assertion.Assertion, assertion.Citation}, "\n")
	return digestBytes([]byte(data))
}

func normalizeObject(input map[string]json.RawMessage, label string) (map[string]json.RawMessage, error) {
	if len(input) == 0 {
		return nil, fmt.Errorf("%s must be a non-empty object", label)
	}
	output := make(map[string]json.RawMessage, len(input))
	for key, raw := range input {
		if key == "" {
			return nil, fmt.Errorf("%s contains an empty key", label)
		}
		normalized, err := normalizeRawJSON(raw)
		if err != nil {
			return nil, fmt.Errorf("%s.%s: %w", label, key, err)
		}
		output[key] = normalized
	}
	return output, nil
}

func normalizeRawJSON(raw json.RawMessage) (json.RawMessage, error) {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var value interface{}
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return nil, fmt.Errorf("contains trailing JSON")
	}
	data, err := canonicalJSON(value)
	if err != nil {
		return nil, err
	}
	return json.RawMessage(data), nil
}

func decodeRaw(raw json.RawMessage) (interface{}, error) {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var value interface{}
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return nil, fmt.Errorf("contains trailing JSON")
	}
	return value, nil
}

func sortedUnique(values []string) bool {
	if len(values) == 0 {
		return false
	}
	for index, value := range values {
		if value == "" {
			return false
		}
		if index > 0 && values[index-1] >= value {
			return false
		}
	}
	return true
}

func sortedCopy(values []string) []string {
	copied := append([]string(nil), values...)
	sort.Strings(copied)
	return copied
}

func containsString(values []string, needle string) bool {
	for _, value := range values {
		if value == needle {
			return true
		}
	}
	return false
}

func validDigest(value string) bool {
	return digestPattern.MatchString(value)
}
