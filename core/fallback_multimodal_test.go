package bifrost

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestPrepareFallbackRequestPreservesImageEditRoute(t *testing.T) {
	account := NewMockAccount()
	account.AddProvider(schemas.Bedrock, 1, 1)
	b := &Bifrost{account: account, logger: NewDefaultLogger(schemas.LogLevelError)}
	req := &schemas.BifrostRequest{
		RequestType: schemas.ImageEditRequest,
		ImageEditRequest: &schemas.BifrostImageEditRequest{
			Provider: schemas.OpenAI,
			Model:    "image-primary",
		},
	}
	fallback := b.prepareFallbackRequest(req, schemas.Fallback{Provider: schemas.Bedrock, Model: "image-fallback"})
	if fallback == nil || fallback.ImageEditRequest == nil {
		t.Fatal("image edit request was dropped while preparing fallback")
	}
	if fallback.ImageEditRequest.Provider != schemas.Bedrock || fallback.ImageEditRequest.Model != "image-fallback" {
		t.Fatalf("fallback route not applied: provider=%q model=%q", fallback.ImageEditRequest.Provider, fallback.ImageEditRequest.Model)
	}
	if req.ImageEditRequest.Provider != schemas.OpenAI || req.ImageEditRequest.Model != "image-primary" {
		t.Fatal("preparing a fallback mutated the primary image edit request")
	}
}

func TestPrepareFallbackRequestPreservesImageVariationRoute(t *testing.T) {
	account := NewMockAccount()
	account.AddProvider(schemas.Vertex, 1, 1)
	b := &Bifrost{account: account, logger: NewDefaultLogger(schemas.LogLevelError)}
	req := &schemas.BifrostRequest{
		RequestType: schemas.ImageVariationRequest,
		ImageVariationRequest: &schemas.BifrostImageVariationRequest{
			Provider: schemas.OpenAI,
			Model:    "image-primary",
		},
	}
	fallback := b.prepareFallbackRequest(req, schemas.Fallback{Provider: schemas.Vertex, Model: "image-fallback"})
	if fallback == nil || fallback.ImageVariationRequest == nil {
		t.Fatal("image variation request was dropped while preparing fallback")
	}
	if fallback.ImageVariationRequest.Provider != schemas.Vertex || fallback.ImageVariationRequest.Model != "image-fallback" {
		t.Fatalf("fallback route not applied: provider=%q model=%q", fallback.ImageVariationRequest.Provider, fallback.ImageVariationRequest.Model)
	}
	if req.ImageVariationRequest.Provider != schemas.OpenAI || req.ImageVariationRequest.Model != "image-primary" {
		t.Fatal("preparing a fallback mutated the primary image variation request")
	}
}

func TestPrepareFallbackRequestClonesMutableImagePayloads(t *testing.T) {
	nestedBytes := []byte{6, 7}
	extra := map[string]interface{}{"provider_option": "keep", "nested": map[string]interface{}{"bytes": nestedBytes}}
	image := []byte{1, 2, 3}
	req := &schemas.BifrostRequest{RequestType: schemas.ImageEditRequest,
		ImageEditRequest: &schemas.BifrostImageEditRequest{
			Provider: schemas.OpenAI, Model: "primary",
			Input:  &schemas.ImageEditInput{Images: []schemas.ImageInput{{Image: image}}},
			Params: &schemas.ImageEditParameters{Mask: []byte{4, 5}, ExtraParams: extra},
		}}
	account := NewMockAccount()
	account.AddProvider(schemas.Bedrock, 1, 1)
	b := &Bifrost{account: account}
	fallback := b.prepareFallbackRequest(req, schemas.Fallback{Provider: schemas.Bedrock, Model: "fallback"})
	fallback.ImageEditRequest.Params.ExtraParams["provider_option"] = "changed"
	fallback.ImageEditRequest.Params.ExtraParams["nested"].(map[string]interface{})["bytes"].([]byte)[0] = 0
	fallback.ImageEditRequest.Params.Mask[0] = 9
	fallback.ImageEditRequest.Input.Images[0].Image[0] = 8
	if extra["provider_option"] != "keep" || nestedBytes[0] != 6 || req.ImageEditRequest.Params.Mask[0] != 4 || image[0] != 1 {
		t.Fatal("fallback preparation shared mutable image state with primary request")
	}
}
