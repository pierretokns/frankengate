package datasheet

import "testing"

func TestEffectiveSyncURLs(t *testing.T) {
	t.Setenv("FRANKENGATE_PRICING_URL", " https://mirror.example/pricing ")
	t.Setenv("FRANKENGATE_MODEL_PARAMETERS_URL", " https://mirror.example/parameters ")
	if got := EffectiveURL(); got != "https://mirror.example/pricing" {
		t.Fatalf("pricing override not resolved: %q", got)
	}
	if got := EffectiveModelParametersURL(); got != "https://mirror.example/parameters" {
		t.Fatalf("model parameter override not resolved: %q", got)
	}
	t.Setenv("FRANKENGATE_PRICING_URL", "")
	t.Setenv("FRANKENGATE_MODEL_PARAMETERS_URL", "")
	if EffectiveURL() != DefaultURL || EffectiveModelParametersURL() != DefaultModelParametersURL {
		t.Fatal("empty overrides must preserve compatibility defaults")
	}
}
