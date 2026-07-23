package contract

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/framework/configstore"
)

const sealedLabPostgresPassword = "sealed-lab-only"

func credentialEntropy(value string) float64 {
	counts := make(map[rune]int)
	for _, character := range value {
		counts[character]++
	}
	length := float64(len([]rune(value)))
	if length == 0 {
		return 0
	}
	var entropy float64
	for _, count := range counts {
		probability := float64(count) / length
		entropy -= probability * math.Log2(probability)
	}
	return entropy
}

func validateSealedCredential(fixtureCredential, composeCredential string) error {
	lower := strings.ToLower(fixtureCredential)
	for _, prefix := range []string{"sk-", "akia", "ghp_", "github_pat_", "xoxb-", "xoxp-", "eyj"} {
		if strings.HasPrefix(lower, prefix) {
			return fmt.Errorf("credential uses known secret prefix %q", prefix)
		}
	}
	if strings.Contains(fixtureCredential, "-----BEGIN") || strings.Contains(fixtureCredential, "PRIVATE KEY") {
		return fmt.Errorf("credential contains PEM material")
	}
	if len(fixtureCredential) >= 24 && credentialEntropy(fixtureCredential) >= 3.5 {
		return fmt.Errorf("credential resembles high-entropy secret material")
	}
	if fixtureCredential != sealedLabPostgresPassword {
		return fmt.Errorf("credential is not the exact reviewed synthetic value")
	}
	if composeCredential != fixtureCredential {
		return fmt.Errorf("fixture and Compose credentials differ")
	}
	return nil
}

func TestBootstrapConfigOnlySelectsPostgresAuthority(t *testing.T) {
	root := filepath.Join("..", "..", "..", "..")
	fixturePath := filepath.Join(root, "tests/conformance/lab/fixtures/bootstrap-config.json")
	data, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Fatal(err)
	}
	var document map[string]json.RawMessage
	if err := json.Unmarshal(data, &document); err != nil {
		t.Fatal(err)
	}
	allowed := map[string]bool{"$schema": true, "version": true, "source_of_truth": true, "config_store": true, "logs_store": true}
	for key := range document {
		if !allowed[key] {
			t.Fatalf("bootstrap fixture must not own mutable section %q", key)
		}
	}
	for _, required := range []string{"$schema", "version", "source_of_truth", "config_store", "logs_store"} {
		if _, ok := document[required]; !ok {
			t.Fatalf("bootstrap fixture misses %q", required)
		}
	}
	var sourceOfTruth string
	if err := json.Unmarshal(document["source_of_truth"], &sourceOfTruth); err != nil || sourceOfTruth != "split" {
		t.Fatalf("source_of_truth = %q, %v; want split", sourceOfTruth, err)
	}
	var store struct {
		Enabled bool   `json:"enabled"`
		Type    string `json:"type"`
		Config  struct {
			Host     string `json:"host"`
			Port     string `json:"port"`
			User     string `json:"user"`
			Password string `json:"password"`
			DBName   string `json:"db_name"`
			SSLMode  string `json:"ssl_mode"`
		} `json:"config"`
	}
	if err := json.Unmarshal(document["config_store"], &store); err != nil {
		t.Fatal(err)
	}
	if !store.Enabled || store.Type != "postgres" || store.Config.Host != "postgres" || store.Config.Port != "5432" || store.Config.User != "bifrost" || store.Config.Password == "" || store.Config.DBName != "bifrost" || store.Config.SSLMode != "disable" {
		t.Fatalf("invalid PostgreSQL bootstrap: %#v", store)
	}
	var runtimeStore configstore.Config
	if err := json.Unmarshal(document["config_store"], &runtimeStore); err != nil {
		t.Fatalf("runtime config-store parser rejected fixture: %v", err)
	}
	if runtimeStore.Type != configstore.ConfigStoreTypePostgres {
		t.Fatalf("runtime config-store type = %q, want postgres", runtimeStore.Type)
	}
	if _, ok := runtimeStore.Config.(*configstore.PostgresConfig); !ok {
		t.Fatalf("runtime config-store payload has type %T, want *configstore.PostgresConfig", runtimeStore.Config)
	}
	var logs struct {
		Enabled bool `json:"enabled"`
	}
	if err := json.Unmarshal(document["logs_store"], &logs); err != nil || logs.Enabled {
		t.Fatalf("logs_store must be explicitly disabled: %#v, %v", logs, err)
	}

	composeData, err := os.ReadFile(filepath.Join(root, "tests/conformance/lab/compose.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	compose := string(composeData)
	for _, required := range []string{"source: sealed_bootstrap_config", "target: /app/data/config.json", "mode: 0444", "file: ./fixtures/bootstrap-config.json"} {
		if !strings.Contains(compose, required) {
			t.Fatalf("Compose bootstrap wiring misses %q", required)
		}
	}
	if strings.Contains(compose, "BIFROST_CONFIG_STORE_") {
		t.Fatal("Compose still advertises unsupported config-store environment variables")
	}
	passwordLines := regexp.MustCompile(`(?m)^\s+POSTGRES_PASSWORD:\s*([^\s#]+)\s*$`).FindAllStringSubmatch(compose, -1)
	if len(passwordLines) != 1 || len(passwordLines[0]) != 2 {
		t.Fatal("Compose must declare exactly one unambiguous POSTGRES_PASSWORD")
	}
	if err := validateSealedCredential(store.Config.Password, passwordLines[0][1]); err != nil {
		t.Fatal(err)
	}
}

func TestSealedCredentialRejectsMutants(t *testing.T) {
	tests := map[string]struct {
		fixture string
		compose string
	}{
		"mismatch":      {sealedLabPostgresPassword, "sealed-lab-other"},
		"non-synthetic": {"production-password", "production-password"},
		"OpenAI prefix": {"sk-not-a-real-key", "sk-not-a-real-key"},
		"AWS prefix":    {"AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"},
		"PEM material":  {"-----BEGIN PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----"},
		"high entropy":  {"mL7$2qP9!vR4#xT8@kN6&wC3", "mL7$2qP9!vR4#xT8@kN6&wC3"},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			if err := validateSealedCredential(test.fixture, test.compose); err == nil {
				t.Fatal("mutant credential accepted")
			}
		})
	}
}
