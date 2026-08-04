package registry

import "testing"

func TestParseOpenAPIToMCPIsDeterministicAndAnnotatesOperations(t *testing.T) {
	doc := []byte(`{"openapi":"3.0.3","info":{"title":"Example","version":"1"},"servers":[{"url":"https://api.example.test/v1"}],"paths":{"/items/{id}":{"get":{"operationId":"getItem","parameters":[{"name":"id","in":"path","required":true,"schema":{"type":"string"}}]},"delete":{"operationId":"deleteItem","parameters":[{"name":"id","in":"path","required":true,"schema":{"type":"string"}}]}}}}`)
	result, err := ParseOpenAPIToMCP(doc, OpenAPIOptions{AllowedHosts: []string{"api.example.test"}, Namespace: "catalog"})
	if err != nil {
		t.Fatal(err)
	}
	if result.BaseURL != "https://api.example.test/v1" || len(result.Tools) != 2 {
		t.Fatalf("unexpected result: %#v", result)
	}
	if result.Tools[0].Function.Name != "catalog__deleteItem" || result.Tools[1].Function.Name != "catalog__getItem" {
		t.Fatalf("tools are not stable: %#v", result.Tools)
	}
	if result.Tools[0].Annotations == nil || result.Tools[0].Annotations.DestructiveHint == nil || !*result.Tools[0].Annotations.DestructiveHint {
		t.Fatal("delete operation should be marked destructive")
	}
	if result.Tools[1].Annotations == nil || result.Tools[1].Annotations.ReadOnlyHint == nil || !*result.Tools[1].Annotations.ReadOnlyHint {
		t.Fatal("get operation should be marked read-only")
	}
}

func TestParseOpenAPIToMCPRejectsNetworkAndExternalReferenceHazards(t *testing.T) {
	tests := []struct {
		name string
		doc  string
		want string
	}{
		{"host", `{"openapi":"3.0.3","info":{"title":"x","version":"1"},"servers":[{"url":"https://evil.example"}],"paths":{}}`, "allowlist"},
		{"ref", `{"openapi":"3.0.3","info":{"title":"x","version":"1"},"paths":{"/x":{"get":{"parameters":[{"name":"x","in":"query","schema":{"$ref":"https://evil.example/schema.json"}}]}}}}`, "external $ref"},
		{"path", `{"openapi":"3.0.3","info":{"title":"x","version":"1"},"paths":{"../x":{"get":{}}}}`, "safe absolute"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := ParseOpenAPIToMCP([]byte(tt.doc), OpenAPIOptions{AllowedHosts: []string{"api.example"}})
			if err == nil || !contains(err.Error(), tt.want) {
				t.Fatalf("expected %q, got %v", tt.want, err)
			}
		})
	}
}

func TestParseOpenAPIToMCPResolvesBoundedLocalSchemaReferences(t *testing.T) {
	doc := []byte(`{"openapi":"3.1.0","info":{"title":"Example","version":"1"},"paths":{"/items":{"post":{"operationId":"createItem","requestBody":{"content":{"application/json":{"schema":{"$ref":"#/components/schemas/Item"}}}}}}},"components":{"schemas":{"Item":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}}}`)
	result, err := ParseOpenAPIToMCP(doc, OpenAPIOptions{Namespace: "catalog"})
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Tools) != 1 {
		t.Fatalf("expected one tool, got %#v", result.Tools)
	}
	body, ok := result.Tools[0].Function.Parameters.Properties.Get("body")
	if !ok {
		t.Fatal("resolved request body is missing")
	}
	if bodyMap, ok := body.(map[string]any); !ok || bodyMap["type"] != "object" {
		t.Fatalf("local schema ref was not resolved: %#v", body)
	}
}

func TestParseOpenAPIToMCPRejectsCyclicLocalSchemaReferences(t *testing.T) {
	doc := []byte(`{"openapi":"3.1.0","paths":{"/x":{"post":{"requestBody":{"content":{"application/json":{"schema":{"$ref":"#/components/schemas/A"}}}}}}},"components":{"schemas":{"A":{"$ref":"#/components/schemas/B"},"B":{"$ref":"#/components/schemas/A"}}}}`)
	if _, err := ParseOpenAPIToMCP(doc, OpenAPIOptions{}); err == nil || !contains(err.Error(), "cyclic schema") {
		t.Fatalf("expected cyclic local ref rejection, got %v", err)
	}
}

func contains(value, fragment string) bool {
	for i := 0; i+len(fragment) <= len(value); i++ {
		if value[i:i+len(fragment)] == fragment {
			return true
		}
	}
	return false
}
