package contract

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/framework/configstore"
)

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
}
