package datasheet

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
	configstoreTables "github.com/maximhq/bifrost/framework/configstore/tables"
)

func TestValidateCapabilityRowsDistinguishesUnsupportedAndUnknown(t *testing.T) {
	rows := []configstoreTables.TableModelPricing{
		{Model: "chat-model", Provider: "openai", Mode: "chat"},
		{Model: "image-model", Provider: "openai", Mode: "image_generation"},
		{Model: "batch-model", Provider: "openai", Mode: "batch_create"},
	}
	report := ValidateCapabilityRows(rows, CapabilityRegistry{
		schemas.OpenAI: {
			"chat":             CapabilitySupported,
			"image_generation": CapabilityUnsupported,
			// batch intentionally absent: registry has no assertion.
		},
	})
	if len(report) != 3 {
		t.Fatalf("expected 3 observations, got %d", len(report))
	}
	byModel := make(map[string]CapabilityDrift, len(report))
	for _, item := range report {
		byModel[item.Model] = item
	}
	if byModel["chat-model"].IsDrift || byModel["chat-model"].ProviderState != CapabilitySupported {
		t.Fatalf("supported operation incorrectly drifted: %+v", byModel["chat-model"])
	}
	if !byModel["image-model"].IsDrift || byModel["image-model"].ProviderState != CapabilityUnsupported {
		t.Fatalf("explicit unsupported operation not reported: %+v", byModel["image-model"])
	}
	if byModel["batch-model"].IsDrift || byModel["batch-model"].ProviderState != CapabilityUnknown || byModel["batch-model"].Mode != "batch" {
		t.Fatalf("missing registry assertion must remain unknown: %+v", byModel["batch-model"])
	}
}

func TestValidateCapabilityRowsNormalizesProviderAndDeduplicates(t *testing.T) {
	rows := []configstoreTables.TableModelPricing{
		{Model: "claude", Provider: "bedrock_converse", Mode: "responses"},
		{Model: "claude", Provider: "bedrock_converse", Mode: "responses"},
	}
	report := ValidateCapabilityRows(rows, CapabilityRegistry{
		schemas.Bedrock: {"responses": CapabilitySupported},
	})
	if len(report) != 1 || report[0].Provider != schemas.Bedrock || report[0].ProviderState != CapabilitySupported {
		t.Fatalf("expected canonical provider and one row, got %+v", report)
	}
}
