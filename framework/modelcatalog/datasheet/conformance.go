package datasheet

import (
	"reflect"
	"sort"

	"github.com/maximhq/bifrost/core/schemas"
)

// ProviderOperationConformance is a deterministic, local observation of the
// relationship between the model catalog's capability registry and a
// provider implementation. It deliberately does not invoke provider code or
// make network calls. Unknown registry entries are reported (rather than
// treated as denied), while an explicitly supported operation with no
// matching method is actionable drift.
type ProviderOperationConformance struct {
	Provider         schemas.ModelProvider
	Mode             string
	Method           string
	RegistryState    CapabilityState
	InterfacePresent bool
	Conformant       bool
	Actionable       bool
}

// providerOperationMethods is intentionally kept in one place. The entries
// include the multimodal and every batch operation family so a catalog audit
// cannot silently overlook those paths.
var providerOperationMethods = []struct {
	mode   string
	method string
}{
	{"chat", "ChatCompletion"},
	{"responses", "Responses"},
	{"embedding", "Embedding"},
	{"rerank", "Rerank"},
	{"ocr", "OCR"},
	{"speech", "Speech"},
	{"transcription", "Transcription"},
	{"image_generation", "ImageGeneration"},
	{"image_edit", "ImageEdit"},
	{"image_variation", "ImageVariation"},
	{"video_generation", "VideoGeneration"},
	{"batch_create", "BatchCreate"},
	{"batch_list", "BatchList"},
	{"batch_retrieve", "BatchRetrieve"},
	{"batch_cancel", "BatchCancel"},
	{"batch_results", "BatchResults"},
	{"batch_delete", "BatchDelete"},
}

// ValidateProviderInterface compares every operation in the local provider
// interface with the registry for providerName. A nil implementation is
// treated as having no methods, which makes this useful for CI and generated
// adapter checks without constructing a provider or credentials.
func ValidateProviderInterface(providerName schemas.ModelProvider, implementation any, registry CapabilityRegistry) []ProviderOperationConformance {
	var typ reflect.Type
	if implementation != nil {
		typ = reflect.TypeOf(implementation)
		if typ.Kind() != reflect.Ptr && typ.Kind() != reflect.Interface {
			typ = reflect.PointerTo(typ)
		}
	}
	ops := registry[providerName]
	out := make([]ProviderOperationConformance, 0, len(providerOperationMethods))
	for _, spec := range providerOperationMethods {
		state := CapabilityUnknown
		if candidate, ok := ops[spec.mode]; ok {
			state = candidate
		}
		present := typ != nil
		if present {
			_, present = typ.MethodByName(spec.method)
		}
		// Unknown capabilities remain non-actionable; explicit support must
		// have a callable method, while explicit unsupported is conformant even
		// when the adapter omits the operation entirely.
		conformant := state != CapabilitySupported || present
		out = append(out, ProviderOperationConformance{
			Provider: providerName, Mode: spec.mode, Method: spec.method,
			RegistryState: state, InterfacePresent: present, Conformant: conformant,
			Actionable: state != CapabilityUnknown,
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Mode < out[j].Mode })
	return out
}
