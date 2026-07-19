package datasheet

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

// A small method-bearing adapter keeps this probe a pure interface check; it
// intentionally does not implement the full provider interface or perform
// any provider calls.
type conformanceProbeProvider struct{}

func (*conformanceProbeProvider) ChatCompletion()  {}
func (*conformanceProbeProvider) ImageGeneration() {}
func (*conformanceProbeProvider) BatchCreate()     {}

func TestValidateProviderInterfaceCoversMultimodalAndBatch(t *testing.T) {
	rows := ValidateProviderInterface(schemas.OpenAI, &conformanceProbeProvider{}, CapabilityRegistry{
		schemas.OpenAI: {
			"chat":             CapabilitySupported,
			"image_generation": CapabilitySupported,
			"image_variation":  CapabilityUnsupported,
			"batch_create":     CapabilitySupported,
			"batch_results":    CapabilitySupported,
		},
	})
	byMode := make(map[string]ProviderOperationConformance, len(rows))
	for _, row := range rows {
		byMode[row.Mode] = row
	}
	if len(rows) != 17 {
		t.Fatalf("expected all multimodal and batch operation observations, got %d", len(rows))
	}
	if !byMode["chat"].Conformant || !byMode["chat"].InterfacePresent {
		t.Fatalf("chat method should conform: %+v", byMode["chat"])
	}
	if !byMode["image_generation"].Conformant || !byMode["image_generation"].InterfacePresent {
		t.Fatalf("image generation method should conform: %+v", byMode["image_generation"])
	}
	if !byMode["image_variation"].Conformant || byMode["image_variation"].InterfacePresent {
		t.Fatalf("explicit unsupported variation should be conformant without a method: %+v", byMode["image_variation"])
	}
	if !byMode["batch_create"].Conformant || !byMode["batch_create"].InterfacePresent {
		t.Fatalf("batch create method should conform: %+v", byMode["batch_create"])
	}
	if byMode["batch_results"].Conformant || byMode["batch_results"].InterfacePresent {
		t.Fatalf("supported batch results without a method must be actionable drift: %+v", byMode["batch_results"])
	}
	if byMode["image_edit"].RegistryState != CapabilityUnknown || byMode["image_edit"].Actionable || !byMode["image_edit"].Conformant {
		t.Fatalf("unknown capability must remain non-actionable: %+v", byMode["image_edit"])
	}
}

func TestValidateProviderInterfaceNilImplementationIsDeterministic(t *testing.T) {
	rows := ValidateProviderInterface(schemas.Bedrock, nil, CapabilityRegistry{
		schemas.Bedrock: {"responses": CapabilitySupported},
	})
	if len(rows) != 17 || rows[0].Mode != "batch_cancel" {
		t.Fatalf("unexpected deterministic operation report: len=%d first=%+v", len(rows), rows[0])
	}
	if rows[len(rows)-1].Mode != "video_generation" {
		t.Fatalf("unexpected sorted operation report: %+v", rows[len(rows)-1])
	}
	if !rows[len(rows)-1].Conformant {
		t.Fatalf("unknown operation should not be treated as drift: %+v", rows[len(rows)-1])
	}
}
