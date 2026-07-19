package datasheet

import (
	"sort"

	"github.com/maximhq/bifrost/core/schemas"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
)

// CapabilityState describes what the provider registry knows about an
// operation. Unknown is deliberately different from Unsupported: the former
// means the registry has no assertion and must not be used as a deny signal.
type CapabilityState string

const (
	CapabilitySupported   CapabilityState = "supported"
	CapabilityUnsupported CapabilityState = "unsupported"
	CapabilityUnknown     CapabilityState = "unknown"
)

// CapabilityRegistry is a provider-owned operation registry. Keys are the
// canonical datasheet mode names (for example "chat", "responses", or
// "image_generation"). Missing keys are unknown; callers should not encode
// missing entries as false.
type CapabilityRegistry map[schemas.ModelProvider]map[string]CapabilityState

// CapabilityDrift is one catalog/provider comparison. A row is drift only
// when the provider explicitly says unsupported. Unknown observations are
// reported for visibility but are not treated as drift or a deny decision.
type CapabilityDrift struct {
	Model         string
	Provider      schemas.ModelProvider
	Mode          string
	Catalog       CapabilityState
	ProviderState CapabilityState
	IsDrift       bool
}

// ValidateCapabilityDrift compares every authoritative pricing capability
// row with a local provider registry. It performs no network calls and is
// therefore suitable for startup checks, CI, and scheduled catalog audits.
// Rows are deduplicated by model/provider/mode and returned deterministically.
func (s *Store) ValidateCapabilityDrift(registry CapabilityRegistry) []CapabilityDrift {
	if s == nil {
		return nil
	}
	s.mu.RLock()
	rows := make([]configstoreTables.TableModelPricing, 0, len(s.pricingData))
	for _, row := range s.pricingData {
		rows = append(rows, row)
	}
	s.mu.RUnlock()
	return ValidateCapabilityRows(rows, registry)
}

// ValidateCapabilityRows is the pure, local form used by tests and tooling
// that already has catalog rows. It does not infer provider support from
// absent map entries: absence always produces CapabilityUnknown.
func ValidateCapabilityRows(rows []configstoreTables.TableModelPricing, registry CapabilityRegistry) []CapabilityDrift {
	seen := make(map[string]struct{}, len(rows))
	out := make([]CapabilityDrift, 0, len(rows))
	for _, row := range rows {
		provider := schemas.ModelProvider(normalizeProvider(row.Provider))
		mode := normalizeMode(row.Mode)
		key := row.Model + "\x00" + string(provider) + "\x00" + mode
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		state := CapabilityUnknown
		if ops, ok := registry[provider]; ok {
			if candidate, exists := ops[mode]; exists {
				state = candidate
			}
		}
		out = append(out, CapabilityDrift{
			Model: row.Model, Provider: provider, Mode: mode,
			Catalog: CapabilitySupported, ProviderState: state,
			IsDrift: state == CapabilityUnsupported,
		})
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Provider != out[j].Provider {
			return out[i].Provider < out[j].Provider
		}
		if out[i].Model != out[j].Model {
			return out[i].Model < out[j].Model
		}
		return out[i].Mode < out[j].Mode
	})
	return out
}

func normalizeMode(mode string) string {
	if mode == "batch_create" || mode == "batch_list" || mode == "batch_retrieve" || mode == "batch_cancel" || mode == "batch_results" || mode == "batch_delete" {
		return "batch"
	}
	if mode == "completion" || mode == "chat" || mode == "responses" || mode == "embedding" || mode == "rerank" || mode == "speech" || mode == "transcription" || mode == "image_generation" || mode == "image_edit" || mode == "image_variation" || mode == "video_generation" || mode == "ocr" || mode == "realtime" {
		return mode
	}
	for _, rt := range []schemas.RequestType{
		schemas.ChatCompletionRequest, schemas.ResponsesRequest, schemas.EmbeddingRequest,
		schemas.RerankRequest, schemas.SpeechRequest, schemas.TranscriptionRequest,
		schemas.ImageGenerationRequest, schemas.ImageEditRequest, schemas.ImageVariationRequest,
		schemas.VideoGenerationRequest, schemas.OCRRequest, schemas.BatchCreateRequest,
		schemas.TextCompletionRequest, schemas.RealtimeRequest,
	} {
		if string(rt) == mode {
			return normalizeRequestType(rt)
		}
	}
	return mode
}
