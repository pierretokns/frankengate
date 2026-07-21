package contractscenario

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/url"
	"sort"
	"strings"
)

type SigV4Input struct {
	Method        string
	RawPath       string
	RawQuery      string
	Headers       []Header
	SignedHeaders []string
	Payload       []byte
	AmzDate       string
	Date          string
	Region        string
	Service       string
}

type SigV4Material struct {
	CanonicalRequest string
	CredentialScope  string
	StringToSign     string
	Signature        string
}

func SignSigV4(secret string, input SigV4Input) (SigV4Material, error) {
	if secret == "" || len(input.AmzDate) != 16 || len(input.Date) != 8 || input.Region == "" || input.Service == "" {
		return SigV4Material{}, fmt.Errorf("incomplete SigV4 input")
	}
	canonicalPath, err := canonicalURI(input.RawPath)
	if err != nil {
		return SigV4Material{}, err
	}
	canonicalQuery, err := canonicalQuery(input.RawQuery)
	if err != nil {
		return SigV4Material{}, err
	}
	canonicalHeaders, signedHeaders, err := canonicalSignedHeaders(input.Headers, input.SignedHeaders)
	if err != nil {
		return SigV4Material{}, err
	}
	payloadHash := sha256.Sum256(input.Payload)
	canonicalRequest := strings.Join([]string{
		strings.ToUpper(input.Method),
		canonicalPath,
		canonicalQuery,
		canonicalHeaders,
		signedHeaders,
		hex.EncodeToString(payloadHash[:]),
	}, "\n")
	requestHash := sha256.Sum256([]byte(canonicalRequest))
	scope := input.Date + "/" + input.Region + "/" + input.Service + "/aws4_request"
	stringToSign := "AWS4-HMAC-SHA256\n" + input.AmzDate + "\n" + scope + "\n" + hex.EncodeToString(requestHash[:])
	kDate := hmacSHA256([]byte("AWS4"+secret), input.Date)
	kRegion := hmacSHA256(kDate, input.Region)
	kService := hmacSHA256(kRegion, input.Service)
	kSigning := hmacSHA256(kService, "aws4_request")
	signature := hex.EncodeToString(hmacSHA256(kSigning, stringToSign))
	return SigV4Material{CanonicalRequest: canonicalRequest, CredentialScope: scope, StringToSign: stringToSign, Signature: signature}, nil
}

func hmacSHA256(key []byte, value string) []byte {
	h := hmac.New(sha256.New, key)
	_, _ = h.Write([]byte(value))
	return h.Sum(nil)
}

func canonicalURI(rawPath string) (string, error) {
	if rawPath == "" {
		return "/", nil
	}
	segments := strings.Split(rawPath, "/")
	for i := range segments {
		decoded, err := url.PathUnescape(segments[i])
		if err != nil {
			return "", fmt.Errorf("invalid escaped path segment: %w", err)
		}
		segments[i] = sigV4Escape(decoded)
	}
	result := strings.Join(segments, "/")
	if !strings.HasPrefix(result, "/") {
		result = "/" + result
	}
	return result, nil
}

func canonicalQuery(raw string) (string, error) {
	if raw == "" {
		return "", nil
	}
	type pair struct{ key, value string }
	pairs := make([]pair, 0, strings.Count(raw, "&")+1)
	for _, field := range strings.Split(raw, "&") {
		parts := strings.SplitN(field, "=", 2)
		key, err := url.PathUnescape(parts[0])
		if err != nil {
			return "", fmt.Errorf("invalid query key: %w", err)
		}
		value := ""
		if len(parts) == 2 {
			value, err = url.PathUnescape(parts[1])
			if err != nil {
				return "", fmt.Errorf("invalid query value: %w", err)
			}
		}
		pairs = append(pairs, pair{key: sigV4Escape(key), value: sigV4Escape(value)})
	}
	sort.SliceStable(pairs, func(i, j int) bool {
		if pairs[i].key == pairs[j].key {
			return pairs[i].value < pairs[j].value
		}
		return pairs[i].key < pairs[j].key
	})
	parts := make([]string, len(pairs))
	for i, pair := range pairs {
		parts[i] = pair.key + "=" + pair.value
	}
	return strings.Join(parts, "&"), nil
}

func canonicalSignedHeaders(headers []Header, signed []string) (string, string, error) {
	if len(signed) == 0 {
		return "", "", fmt.Errorf("signed headers are required")
	}
	names := append([]string(nil), signed...)
	for i := range names {
		names[i] = strings.ToLower(strings.TrimSpace(names[i]))
		if names[i] == "" {
			return "", "", fmt.Errorf("empty signed header")
		}
	}
	sort.Strings(names)
	for i := 1; i < len(names); i++ {
		if names[i] == names[i-1] {
			return "", "", fmt.Errorf("duplicate signed header %q", names[i])
		}
	}
	values := make(map[string][]string, len(names))
	allowed := make(map[string]struct{}, len(names))
	for _, name := range names {
		allowed[name] = struct{}{}
	}
	for _, header := range headers {
		name := strings.ToLower(strings.TrimSpace(header.Name))
		if _, ok := allowed[name]; ok {
			values[name] = append(values[name], normalizeHeaderValue(header.Value))
		}
	}
	var canonical strings.Builder
	for _, name := range names {
		if len(values[name]) == 0 {
			return "", "", fmt.Errorf("signed header %q is absent", name)
		}
		canonical.WriteString(name)
		canonical.WriteByte(':')
		canonical.WriteString(strings.Join(values[name], ","))
		canonical.WriteByte('\n')
	}
	return canonical.String(), strings.Join(names, ";"), nil
}

func normalizeHeaderValue(value string) string {
	return strings.Join(strings.Fields(value), " ")
}

func sigV4Escape(value string) string {
	return strings.ReplaceAll(url.QueryEscape(value), "+", "%20")
}
