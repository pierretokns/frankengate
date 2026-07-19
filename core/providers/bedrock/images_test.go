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
