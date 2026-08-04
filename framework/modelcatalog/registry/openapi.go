package registry

// This adapter deliberately parses OpenAPI as data. It never fetches a
// referenced document, resolves an external $ref, or creates a credential
// source. The returned tools are catalog evidence and must still pass the
// normal trust/admission pipeline before they can be exposed to an agent.

import (
	"encoding/json"
	"fmt"
	"net/url"
	"regexp"
	"sort"
	"strings"

	"github.com/maximhq/bifrost/core/schemas"
)

const (
	MaxOpenAPIBytes      = 512 * 1024
	MaxOpenAPIOperations = 256
)

type OpenAPIOptions struct {
	AllowedHosts []string
	AllowHTTP    bool
	Namespace    string
}

type OpenAPIResult struct {
	Title   string
	Version string
	BaseURL string
	Tools   []schemas.ChatTool
}

type openAPIDocument struct {
	OpenAPI string                          `json:"openapi"`
	Swagger string                          `json:"swagger"`
	Info    struct{ Title, Version string } `json:"info"`
	Servers []struct{ URL string }          `json:"servers"`
	Paths   map[string]json.RawMessage      `json:"paths"`
}

type openAPIOperation struct {
	OperationID string              `json:"operationId"`
	Summary     string              `json:"summary"`
	Description string              `json:"description"`
	Parameters  []openAPIParameter  `json:"parameters"`
	RequestBody *openAPIRequestBody `json:"requestBody"`
}

type openAPIParameter struct {
	Name        string          `json:"name"`
	In          string          `json:"in"`
	Description string          `json:"description"`
	Required    bool            `json:"required"`
	Schema      json.RawMessage `json:"schema"`
}

type openAPIRequestBody struct {
	Description string `json:"description"`
	Required    bool   `json:"required"`
	Content     map[string]struct {
		Schema json.RawMessage `json:"schema"`
	} `json:"content"`
}

var toolNameUnsafe = regexp.MustCompile(`[^a-zA-Z0-9_-]+`)

// ParseOpenAPIToMCP parses OpenAPI 3.x (and the compatible Swagger 2 marker)
// into neutral Bifrost function tools. It is intentionally deterministic.
func ParseOpenAPIToMCP(data []byte, options OpenAPIOptions) (OpenAPIResult, error) {
	if len(data) == 0 || len(data) > MaxOpenAPIBytes {
		return OpenAPIResult{}, fmt.Errorf("openapi document exceeds %d bytes or is empty", MaxOpenAPIBytes)
	}
	var doc openAPIDocument
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	if err := decoder.Decode(&doc); err != nil {
		return OpenAPIResult{}, fmt.Errorf("decode openapi document: %w", err)
	}
	if doc.OpenAPI == "" && doc.Swagger == "" {
		return OpenAPIResult{}, fmt.Errorf("openapi or swagger version is required")
	}
	baseURL, err := selectServer(doc.Servers, options)
	if err != nil {
		return OpenAPIResult{}, err
	}

	paths := make([]string, 0, len(doc.Paths))
	for path := range doc.Paths {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	result := OpenAPIResult{Title: strings.TrimSpace(doc.Info.Title), Version: strings.TrimSpace(doc.Info.Version), BaseURL: baseURL}
	seenNames := map[string]struct{}{}
	for _, path := range paths {
		if !strings.HasPrefix(path, "/") || strings.Contains(path, "..") {
			return OpenAPIResult{}, fmt.Errorf("path %q is not a safe absolute path", path)
		}
		var pathItem map[string]json.RawMessage
		if err := json.Unmarshal(doc.Paths[path], &pathItem); err != nil {
			return OpenAPIResult{}, fmt.Errorf("decode path %q: %w", path, err)
		}
		methods := make([]string, 0, len(pathItem))
		for method := range pathItem {
			if isHTTPMethod(method) {
				methods = append(methods, method)
			}
		}
		sort.Strings(methods)
		for _, method := range methods {
			var operation openAPIOperation
			if err := json.Unmarshal(pathItem[method], &operation); err != nil {
				return OpenAPIResult{}, fmt.Errorf("decode %s %s: %w", method, path, err)
			}
			tool, err := operationTool(method, path, operation, options.Namespace, seenNames)
			if err != nil {
				return OpenAPIResult{}, fmt.Errorf("convert %s %s: %w", method, path, err)
			}
			result.Tools = append(result.Tools, tool)
			if len(result.Tools) > MaxOpenAPIOperations {
				return OpenAPIResult{}, fmt.Errorf("openapi document contains more than %d operations", MaxOpenAPIOperations)
			}
		}
	}
	return result, nil
}

func selectServer(servers []struct{ URL string }, options OpenAPIOptions) (string, error) {
	if len(servers) == 0 {
		return "", nil
	}
	if len(servers) > 1 {
		// Multiple servers are ambiguous for a single tool target. Operators can
		// publish separate pinned manifests when they need separate targets.
		return "", fmt.Errorf("openapi document must declare at most one server")
	}
	parsed, err := url.Parse(strings.TrimSpace(servers[0].URL))
	if err != nil || parsed.Host == "" || parsed.User != nil || parsed.Fragment != "" {
		return "", fmt.Errorf("openapi server must be an absolute URL without userinfo or fragment")
	}
	if parsed.Scheme != "https" && !(options.AllowHTTP && parsed.Scheme == "http") {
		return "", fmt.Errorf("openapi server scheme %q is not allowed", parsed.Scheme)
	}
	if len(options.AllowedHosts) > 0 {
		allowed := false
		for _, host := range options.AllowedHosts {
			if strings.EqualFold(strings.TrimSpace(host), parsed.Hostname()) {
				allowed = true
				break
			}
		}
		if !allowed {
			return "", fmt.Errorf("openapi server host %q is not in the allowlist", parsed.Hostname())
		}
	}
	return strings.TrimRight(parsed.String(), "/"), nil
}

func operationTool(method, path string, operation openAPIOperation, namespace string, seen map[string]struct{}) (schemas.ChatTool, error) {
	name := strings.TrimSpace(operation.OperationID)
	if name == "" {
		name = strings.ToLower(method) + "_" + strings.Trim(path, "/")
	}
	name = toolNameUnsafe.ReplaceAllString(name, "_")
	name = strings.Trim(name, "_-")
	if name == "" {
		return schemas.ChatTool{}, fmt.Errorf("operation has no usable tool name")
	}
	if namespace = toolNameUnsafe.ReplaceAllString(strings.TrimSpace(namespace), "_"); namespace != "" {
		name = namespace + "__" + name
	}
	if _, exists := seen[name]; exists {
		return schemas.ChatTool{}, fmt.Errorf("tool name %q is duplicated", name)
	}
	seen[name] = struct{}{}
	properties := schemas.NewOrderedMap()
	var required []string
	for _, parameter := range operation.Parameters {
		if parameter.Name == "" || (parameter.In != "path" && parameter.In != "query" && parameter.In != "header" && parameter.In != "cookie") {
			return schemas.ChatTool{}, fmt.Errorf("parameter %q has unsupported location", parameter.Name)
		}
		schema, err := schemaValue(parameter.Schema)
		if err != nil {
			return schemas.ChatTool{}, fmt.Errorf("parameter %q: %w", parameter.Name, err)
		}
		properties.Set(parameter.Name, schema)
		if parameter.Required || parameter.In == "path" {
			required = append(required, parameter.Name)
		}
	}
	if operation.RequestBody != nil {
		schema, err := requestBodySchema(*operation.RequestBody)
		if err != nil {
			return schemas.ChatTool{}, err
		}
		properties.Set("body", schema)
		if operation.RequestBody.Required {
			required = append(required, "body")
		}
	}
	description := strings.TrimSpace(operation.Description)
	if description == "" {
		description = strings.TrimSpace(operation.Summary)
	}
	readOnly := method == "get" || method == "head" || method == "options"
	destructive := method == "delete" || method == "patch"
	return schemas.ChatTool{Type: schemas.ChatToolTypeFunction, Function: &schemas.ChatToolFunction{
		Name: name, Description: stringPtr(description), Parameters: &schemas.ToolFunctionParameters{
			Type: "object", Properties: properties, Required: required,
		},
	}, Annotations: &schemas.MCPToolAnnotations{
		Title: name, ReadOnlyHint: &readOnly, DestructiveHint: &destructive,
		IdempotentHint: boolPtr(method == "get" || method == "put" || method == "delete"), OpenWorldHint: boolPtr(true),
	}}, nil
}

func requestBodySchema(body openAPIRequestBody) (any, error) {
	if len(body.Content) == 0 {
		return map[string]any{"type": "object"}, nil
	}
	mediaTypes := make([]string, 0, len(body.Content))
	for mediaType := range body.Content {
		mediaTypes = append(mediaTypes, mediaType)
	}
	sort.Strings(mediaTypes)
	return schemaValue(body.Content[mediaTypes[0]].Schema)
}

func schemaValue(raw json.RawMessage) (any, error) {
	if len(raw) == 0 || string(raw) == "null" {
		return map[string]any{"type": "string"}, nil
	}
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		return nil, fmt.Errorf("invalid schema: %w", err)
	}
	if hasExternalRef(value) {
		return nil, fmt.Errorf("external $ref is not allowed")
	}
	return value, nil
}

func hasExternalRef(value any) bool {
	switch v := value.(type) {
	case map[string]any:
		for key, child := range v {
			if key == "$ref" {
				ref, ok := child.(string)
				if !ok || !strings.HasPrefix(ref, "#/") {
					return true
				}
			}
			if hasExternalRef(child) {
				return true
			}
		}
	case []any:
		for _, child := range v {
			if hasExternalRef(child) {
				return true
			}
		}
	}
	return false
}

func isHTTPMethod(method string) bool {
	switch method {
	case "get", "post", "put", "patch", "delete", "head", "options", "trace":
		return true
	default:
		return false
	}
}

func stringPtr(value string) *string { return &value }
func boolPtr(value bool) *bool       { return &value }
