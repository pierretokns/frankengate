package bedrock

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestToBedrockImageVariationRequestDoesNotMutateExtraParams(t *testing.T) {
	params := map[string]interface{}{
		"images":             [][]byte{[]byte("second")},
		"prompt":             "make it brighter",
		"negativeText":       "blur",
		"similarityStrength": 0.8,
		"vendorFlag":         "retain-me",
	}
	req := &schemas.BifrostImageVariationRequest{
		Input:  &schemas.ImageVariationInput{Image: schemas.ImageInput{Image: []byte("first")}},
		Params: &schemas.ImageVariationParameters{ExtraParams: params},
	}

	converted, err := ToBedrockImageVariationRequest(req)
	if err != nil {
		t.Fatalf("convert variation request: %v", err)
	}
	if len(params) != 5 || params["prompt"] != "make it brighter" || params["vendorFlag"] != "retain-me" {
		t.Fatalf("conversion mutated caller-owned extra params: %#v", params)
	}
	if _, ok := converted.ExtraParams["prompt"]; ok {
		t.Fatal("provider-only prompt should not remain in converted extra params")
	}
	if converted.ImageVariationParams.Text == nil || *converted.ImageVariationParams.Text != "make it brighter" {
		t.Fatalf("prompt was not converted: %#v", converted.ImageVariationParams)
	}
}

func TestToBedrockImageGenerationRequestDoesNotMutateExtraParams(t *testing.T) {
	params := map[string]interface{}{"cfgScale": 7.5, "vendorFlag": "retain-me"}
	req := &schemas.BifrostImageGenerationRequest{
		Input:  &schemas.ImageGenerationInput{Prompt: "draw a test"},
		Params: &schemas.ImageGenerationParameters{ExtraParams: params},
	}
	converted, err := ToBedrockImageGenerationRequest(req)
	if err != nil {
		t.Fatalf("convert image request: %v", err)
	}
	if len(params) != 2 || params["cfgScale"] != 7.5 || params["vendorFlag"] != "retain-me" {
		t.Fatalf("conversion mutated caller-owned extra params: %#v", params)
	}
	if _, ok := converted.ExtraParams["cfgScale"]; ok {
		t.Fatal("provider-only cfgScale should not remain in converted extra params")
	}
	if converted.ImageGenerationConfig.CfgScale == nil || *converted.ImageGenerationConfig.CfgScale != 7.5 {
		t.Fatalf("cfgScale was not converted: %#v", converted.ImageGenerationConfig)
	}
}

func TestToStabilityAIImageGenerationRequestDoesNotMutateExtraParams(t *testing.T) {
	params := map[string]interface{}{"aspect_ratio": "16:9", "vendorFlag": "retain-me"}
	req := &schemas.BifrostImageGenerationRequest{
		Input:  &schemas.ImageGenerationInput{Prompt: "draw a test"},
		Params: &schemas.ImageGenerationParameters{ExtraParams: params},
	}
	converted, err := ToStabilityAIImageGenerationRequest(req)
	if err != nil {
		t.Fatalf("convert stability image request: %v", err)
	}
	if len(params) != 2 || params["aspect_ratio"] != "16:9" {
		t.Fatalf("conversion mutated caller-owned extra params: %#v", params)
	}
	if _, ok := converted.ExtraParams["aspect_ratio"]; ok {
		t.Fatal("provider-only aspect_ratio should not remain in converted extra params")
	}
	if converted.AspectRatio == nil || *converted.AspectRatio != "16:9" {
		t.Fatalf("aspect ratio was not converted: %#v", converted)
	}
}

func TestToBedrockImageEditRequestDoesNotMutateExtraParams(t *testing.T) {
	params := map[string]interface{}{
		"mask_prompt": "subject",
		"return_mask": true,
		"cfgScale":    6.5,
		"vendorFlag":  "retain-me",
	}
	req := &schemas.BifrostImageEditRequest{
		Input: &schemas.ImageEditInput{
			Prompt: "edit this",
			Images: []schemas.ImageInput{{Image: []byte("image")}},
		},
		Params: &schemas.ImageEditParameters{
			Type:        schemas.Ptr("inpainting"),
			ExtraParams: params,
		},
	}
	converted, err := ToBedrockImageEditRequest(req)
	if err != nil {
		t.Fatalf("convert image edit request: %v", err)
	}
	if len(params) != 4 || params["mask_prompt"] != "subject" || params["cfgScale"] != 6.5 {
		t.Fatalf("conversion mutated caller-owned extra params: %#v", params)
	}
	if _, ok := converted.ExtraParams["mask_prompt"]; ok {
		t.Fatal("provider-only mask_prompt should not remain in converted extra params")
	}
	if converted.InPaintingParams == nil || converted.InPaintingParams.MaskPrompt == nil || *converted.InPaintingParams.MaskPrompt != "subject" {
		t.Fatalf("mask_prompt was not converted: %#v", converted.InPaintingParams)
	}
}
