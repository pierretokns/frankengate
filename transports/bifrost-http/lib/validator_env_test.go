package lib

import "testing"

func TestConfiguredConfigSchemaLocationPrefersForkOverride(t *testing.T) {
	t.Setenv(ConfigSchemaURLEnv, "https://upstream.example/schema")
	t.Setenv(FrankenGateSchemaURLEnv, " https://fork.example/schema ")
	if got := configuredConfigSchemaLocation(); got != "https://fork.example/schema" {
		t.Fatalf("fork schema override was not preferred: %q", got)
	}
	t.Setenv(FrankenGateSchemaURLEnv, "")
	if got := configuredConfigSchemaLocation(); got != "https://upstream.example/schema" {
		t.Fatalf("compatibility schema override was not preserved: %q", got)
	}
}
